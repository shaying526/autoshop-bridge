"""Internal opt-in build artifacts; runtime verifies before dispatch, never rebuilds."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

from autoshop_bridge.errors import BridgeError

PROTOCOL = 1
TARGET = "netfx4-anycpu"
SOURCES = ("grid_reader.cs", "accessibility.cs", "grid_host.cs")
CACHE_ROOT = Path(__file__).resolve().parents[2] / ".autoshop_bridge_cache"


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def identity():
    parent = Path(__file__).resolve().parent
    sources = {name: _hash((parent / name).read_bytes()) for name in SOURCES}
    value = dict(schema=1, protocol=PROTOCOL, target=TARGET, sources=sources)
    key = _hash(json.dumps(value, sort_keys=True).encode("utf-8"))
    return key, value


def _plain(path):
    """Do not resolve a junction/symlink away before checking its components."""
    for part in [path] + list(path.parents):
        if not part.exists() and not part.is_symlink():
            continue
        info = part.lstat()
        if part.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise BridgeError("Grid host path contains a reparse point: {}".format(part))


def command(payload, cache_root=None):
    """None means unbuilt, before dispatch only. Corruption is an error."""
    root = Path(cache_root) if cache_root is not None else CACHE_ROOT
    key, expected = identity()
    directory = root / ("grid-" + key)
    _plain(directory)
    if root.exists() and not root.is_dir():
        raise BridgeError("Grid host cache is not a directory.")
    if not directory.exists():
        return None
    exe, meta = directory / "grid_host.exe", directory / "manifest.json"
    for path in (exe, meta):
        _plain(path)
        if not path.is_file() or path.stat().st_nlink != 1:
            raise BridgeError("Incomplete or linked grid host artifact: {}".format(path))
    try:
        if meta.stat().st_size > 16384 or not 0 < exe.stat().st_size <= 4*1024*1024:
            raise ValueError("artifact size")
        value = json.loads(meta.read_text(encoding="utf-8"))
        if (set(value) != {"identity", "exe_sha256", "compiler"}
                or value["identity"] != expected
                or not isinstance(value["compiler"], dict)
                or value["exe_sha256"] != _hash(exe.read_bytes())):
            raise ValueError("identity or hash mismatch")
    except (OSError, ValueError, TypeError) as exc:
        raise BridgeError("Grid host artifact validation failed: {}".format(exc)) from exc
    return [str(exe.resolve()), payload]


def build(cache_root=None):
    """Explicit developer build. No AutoShop or project access."""
    if os.name != "nt":
        raise BridgeError("Grid host build requires Windows .NET Framework.")
    root = Path(cache_root) if cache_root is not None else CACHE_ROOT
    _plain(root)
    root.mkdir(parents=True, exist_ok=True)
    key, expected = identity()
    destination = root / ("grid-" + key)
    if destination.exists():
        return dict(status="already_built", executable=command("", root)[0], key=key)
    windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    candidates = [windows / "Microsoft.NET" / folder / "v4.0.30319" for folder in ("Framework64", "Framework")]
    framework = next((p for p in candidates if (p / "csc.exe").is_file() and (p / "Accessibility.dll").is_file()), None)
    if framework is None:
        raise BridgeError(".NET Framework C# compiler/Accessibility reference not found.")
    stage = root / ("build-" + uuid.uuid4().hex)
    stage.mkdir()
    try:
        exe = stage / "grid_host.exe"
        parent = Path(__file__).resolve().parent
        args = [str(framework / "csc.exe"), "/nologo", "/target:exe", "/platform:anycpu",
                "/reference:" + str(framework / "Accessibility.dll"), "/reference:System.Web.Extensions.dll",
                "/out:" + str(exe)] + [str(parent / name) for name in SOURCES]
        try:
            completed = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       timeout=30, creationflags=0x08000000)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BridgeError("Grid host build failed: {}".format(exc)) from exc
        if completed.returncode or not exe.is_file():
            raise BridgeError("Grid host compiler rejected source: {}".format(
                completed.stdout.decode("utf-8", errors="replace")[:4096]))
        if identity() != (key, expected):
            raise BridgeError("Grid host source changed during build.")
        manifest = dict(identity=expected, exe_sha256=_hash(exe.read_bytes()),
                        compiler=dict(path=str(framework / "csc.exe"), sha256=_hash((framework / "csc.exe").read_bytes())))
        with (stage / "manifest.json").open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
        try:
            stage.rename(destination)
        except FileExistsError:
            # Another explicit build won. Only accept its complete current artifact.
            command("", root)
        result = command("", root)
        if result is None:
            raise BridgeError("Grid host build was not published.")
        return dict(status="built", executable=result[0], key=key)
    finally:
        # Only our two known staged files may be removed; never recurse.
        if stage.exists():
            for name in ("grid_host.exe", "manifest.json"):
                path = stage / name
                if path.exists():
                    path.unlink()
            stage.rmdir()

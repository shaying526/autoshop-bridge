"""Verified backups and conservative single-file replacement."""

import hashlib
import json
import os
import stat
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from autoshop_bridge.errors import BridgeError, ConflictError


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise BridgeError("Invalid JSON metadata: {}".format(path)) from exc
    if not isinstance(value, dict):
        raise BridgeError("Metadata must be a JSON object: {}".format(path))
    return value


def write_new(path: Path, data: bytes) -> None:
    """Exclusive creation; remove only our own partial file if writing fails."""
    with path.open("xb") as stream:
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            stream.close()
            path.unlink()
            raise
    if path.read_bytes() != data:
        raise BridgeError("New file failed verification: {}".format(path))


def write_json_new(path: Path, value: dict) -> None:
    write_new(
        path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def regular_file(path: Path) -> Path:
    # Check the caller's path before resolving a final symlink away.
    if path.is_symlink():
        raise BridgeError("Symbolic-link files are unsupported: {}".format(path))
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise BridgeError("Expected a regular file: {}".format(path))
    return resolved


def native_file(path: Path) -> Path:
    resolved = regular_file(path)
    if resolved.suffix.lower() not in (".st", ".fb", ".fc", ".stru", ".gvt", ".fbi"):
        raise BridgeError(
            "Only existing native .ST/.FB/.FC/.stru/.gvt/.fbi files are supported."
        )
    return resolved


def writable_target(path: Path) -> Path:
    resolved = native_file(path)
    info = resolved.stat()
    if info.st_nlink > 1:
        raise BridgeError("Refusing to replace a file with multiple hard links.")
    if not info.st_mode & stat.S_IWRITE:
        raise BridgeError("Target is read-only: {}".format(resolved))
    return resolved


@contextmanager
def target_lock(target: Path):
    lock = target.with_name(target.name + ".autoshop_bridge.lock")
    try:
        stream = lock.open("xb")
    except FileExistsError as exc:
        raise BridgeError(
            "Target lock exists; check active jobs before removing: {}".format(lock)
        ) from exc
    try:
        with stream:
            stream.write((str(os.getpid()) + "\n").encode("ascii"))
            stream.flush()
            yield
    finally:
        lock.unlink()


def assert_hash(target: Path, expected: str) -> bytes:
    current = target.read_bytes()
    if sha256(current) != expected:
        raise ConflictError("Target changed; refusing overwrite: {}".format(target))
    return current


def create_backup(
    target: Path,
    data: bytes,
    root: Optional[Path] = None,
    reason: str = "manual",
    planned_after: Optional[str] = None,
) -> Path:
    root = root or target.parent / ".autoshop_bridge_backups"
    root.mkdir(parents=True, exist_ok=True)
    backup = root / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        + "-"
        + uuid.uuid4().hex
    )
    backup.mkdir()  # No exist_ok: no run can reuse a prior backup.
    write_new(backup / "original.native", data)
    meta = {
        "schema": 1,
        "target_path": str(target),
        "sha256": sha256(data),
        "size": len(data),
        "created_at": utc_now(),
        "reason": reason,
        "planned_after_sha256": planned_after,
    }
    write_json_new(backup / "backup.json", meta)
    # Verify both durable files before returning authorization to replace.
    loaded = read_json(backup / "backup.json")
    if (
        loaded != meta
        or sha256((backup / "original.native").read_bytes()) != meta["sha256"]
    ):
        raise BridgeError("Backup verification failed: {}".format(backup))
    return backup.resolve()


def replace_verified(
    target: Path,
    expected: str,
    data: bytes,
    backup_root: Optional[Path],
    reason: str,
    validate_context=None,
) -> dict:
    """Backup first, stage on the same filesystem, recheck, then replace.

    The lock coordinates this tool only. Avoid concurrent edits/saves; an
    external writer can race the final hash check and os.replace. AutoShop
    editor reload behavior requires separate verification. No project
    transaction or power-loss durability guarantee is made.
    """
    target = writable_target(target)
    with target_lock(target):
        original = assert_hash(target, expected)
        if validate_context is not None:
            validate_context()
        if original == data:
            return {"status": "unchanged", "target": str(target), "sha256": expected}
        backup = create_backup(target, original, backup_root, reason, sha256(data))
        staged = None
        try:
            fd, name = tempfile.mkstemp(
                prefix="." + target.name + ".", suffix=".tmp", dir=str(target.parent)
            )
            staged = Path(name)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if staged.read_bytes() != data:
                raise BridgeError("Staged file failed verification.")
            os.chmod(staged, stat.S_IMODE(target.stat().st_mode))
            writable_target(target)
            assert_hash(target, expected)
            if validate_context is not None:
                validate_context()
            os.replace(str(staged), str(target))
            staged = None
            if target.read_bytes() != data:
                raise BridgeError("Target failed verification after replacement.")
        except (OSError, BridgeError) as exc:
            raise BridgeError("{} Backup retained at: {}".format(exc, backup)) from exc
        finally:
            if staged is not None and staged.exists():
                staged.unlink()
    return {
        "status": "replaced",
        "target": str(target),
        "sha256": sha256(data),
        "backup": str(backup),
    }

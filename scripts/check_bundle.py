"""Read-only integrity check, not a signature, deployment or AutoShop test."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


def check(root):
    root = Path(root).resolve(strict=True)
    manifest = json.loads((root / "bundle-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != 1 or manifest.get("name") != "autoshop-bridge":
        raise ValueError("Unknown bundle manifest")
    expected = manifest["files"]
    for name, meta in expected.items():
        path = PurePosixPath(name)
        if (path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name
                or not re.fullmatch(r"[0-9a-f]{64}", meta["sha256"])):
            raise ValueError("Unsafe manifest entry")
        target = root / name
        for part in [target] + list(target.parents):
            if part == root:
                break
            if part.exists() or part.is_symlink():
                info = part.lstat()
                if part.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                    raise ValueError("Linked bundle resource: " + name)
        raw = target.read_bytes()
        if len(raw) != meta["bytes"] or hashlib.sha256(raw).hexdigest() != meta["sha256"]:
            raise ValueError("Bundle resource mismatch: " + name)
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    if actual != set(expected) | {"bundle-manifest.json"}:
        raise ValueError("Unexpected or missing bundle files")
    return dict(status="bundle_verified", backend_version=manifest["backend_version"],
                skill_revision=manifest["skill_revision"], files=len(actual),
                autoshop_tested=False, readonly=True)


if __name__ == "__main__":
    try:
        result = check(Path(__file__).resolve().parents[1])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps(dict(status="bundle_invalid", error=str(exc))), file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(result))

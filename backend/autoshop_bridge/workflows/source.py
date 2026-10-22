"""Bounded source reads and explicit local patches; never mutate a PLC project."""

import difflib
import os
import uuid
from pathlib import Path

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats.st import (
    MAX_NATIVE_SIZE,
    validate_program_edit,
    validate_text,
)
from autoshop_bridge.storage import (
    assert_hash,
    create_backup,
    read_json,
    regular_file,
    sha256,
    target_lock,
    write_json_new,
    write_new,
)


def bounded_int(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise BridgeError("{} must be in {}..{}.".format(label, low, high))
    return value


def clipped(text, maximum=1200):
    return dict(text=text[:maximum], truncated=len(text) > maximum)


def source_read(
    workspace, start=1, end=None, search=None, context=2, limit=20, expected=None
):
    from autoshop_bridge.service import load_workspace

    _, _, source = load_workspace(workspace)
    digest = sha256(source)
    if expected is not None and digest != expected:
        raise BridgeError("Source baseline changed; read again before patching.")
    bounded_int(context, 0, 20, "context")
    bounded_int(limit, 1, 100, "limit")
    lines = source.decode("utf-8").split("\n")
    bounded_int(start, 1, len(lines), "start")
    if end is not None:
        bounded_int(end, start, len(lines), "end")
    if search is not None:
        if not isinstance(search, str) or not search or len(search) > 512:
            raise BridgeError("Search must contain 1..512 literal characters.")
        hits = [i for i in range(start - 1, end or len(lines)) if search in lines[i]]
        selected = sorted(
            {
                j
                for i in hits[:limit]
                for j in range(max(0, i - context), min(len(lines), i + context + 1))
            }
        )
        more = len(hits) > limit or len(selected) > 200
        selected = selected[:200]
        total = len(hits)
    else:
        stop = end or min(len(lines), start + limit - 1)
        selected = list(range(start - 1, stop))[:100]
        total, more = stop - start + 1, stop - start + 1 > 100
    return dict(
        status="source_read",
        workspace=str(Path(workspace).resolve()),
        source_sha256=digest,
        total_lines=len(lines),
        total_matches=total,
        truncated=more,
        rows=[dict(line=i + 1, **clipped(lines[i].rstrip("\r"))) for i in selected],
    )


def plan_patch(source, document):
    if (
        not isinstance(document, dict)
        or set(document) != {"schema", "source_sha256", "operations"}
        or document["schema"] != 1
        or document["source_sha256"] != sha256(source)
    ):
        raise BridgeError(
            "Patch requires schema=1 and the exact current source_sha256."
        )
    ops = document["operations"]
    if not isinstance(ops, list) or not 1 <= len(ops) <= 100:
        raise BridgeError("Patch requires 1..100 ordered replace operations.")
    changed = source
    for op in ops:
        if (
            not isinstance(op, dict)
            or set(op) != {"old", "new"}
            or not isinstance(op["old"], str)
            or not op["old"]
            or not isinstance(op["new"], str)
        ):
            raise BridgeError("Each patch operation needs nonempty old and string new.")
        try:
            old, new = op["old"].encode("utf-8"), op["new"].encode("utf-8")
        except UnicodeError as exc:
            raise BridgeError("Patch strings must be valid UTF-8 Unicode.") from exc
        if changed.count(old) != 1:
            raise BridgeError(
                "Patch old text must match exactly once; include more context."
            )
        changed = changed.replace(old, new, 1)
    validate_program_edit(changed)
    diff = list(
        difflib.unified_diff(
            source.decode("utf-8").splitlines(),
            changed.decode("utf-8").splitlines(),
            fromfile="before/source.st",
            tofile="after/source.st",
            lineterm="",
        )
    )
    preview = "\n".join(diff[:80])
    return changed, dict(
        before_sha256=sha256(source),
        after_sha256=sha256(changed),
        before_lines=source.count(b"\n") + 1,
        after_lines=changed.count(b"\n") + 1,
        edited=source != changed,
        diff=preview[:12000],
        diff_truncated=len(diff) > 80 or len(preview) > 12000,
    )


def source_patch(workspace, patch_file, dry_run=False):
    from autoshop_bridge.service import load_workspace

    workspace = Path(workspace).resolve(strict=True)
    _, _, source = load_workspace(workspace)
    document = read_json(regular_file(patch_file))
    changed, result = plan_patch(source, document)
    result.update(
        status="source_patch_ready",
        workspace=str(workspace),
        native_unchanged=True,
        requires_editor_or_apply=True,
    )
    if dry_run or source == changed:
        return result
    target = regular_file(workspace / "source.st")
    if target.stat().st_nlink != 1:
        raise BridgeError("Refusing to patch a source file with multiple hard links.")
    with target_lock(target):
        assert_hash(target, sha256(source))
        backup = create_backup(
            target, source, workspace / "patch_history", "source_patch", sha256(changed)
        )
        write_json_new(backup / "patch.json", document)
        temporary = workspace / (".source-patch-" + uuid.uuid4().hex)
        try:
            write_new(temporary, changed)
            assert_hash(target, sha256(source))
            os.replace(str(temporary), str(target))
            assert_hash(target, sha256(changed))
        finally:
            if temporary.exists():
                temporary.unlink()
        result.update(status="source_patched", backup=str(backup))
        write_json_new(backup / "result.json", result)
    return result


def source_restore(workspace, saved, expected):
    """Restore local patch history; generic native restore must not parse source."""
    from autoshop_bridge.service import load_workspace

    workspace = Path(workspace).resolve(strict=True)
    _, _, current = load_workspace(workspace)
    target = regular_file(workspace / "source.st")
    saved = Path(saved).resolve(strict=True)
    history = (workspace / "patch_history").resolve(strict=True)
    if history not in saved.parents:
        raise BridgeError(
            "Source restore requires this workspace patch_history backup."
        )
    meta = read_json(regular_file(saved / "backup.json"))
    original = regular_file(saved / "original.native").read_bytes()
    if (
        meta.get("target_path") != str(target)
        or meta.get("sha256") != sha256(original)
        or meta.get("size") != len(original)
        or sha256(current) != expected
    ):
        raise BridgeError("Source restore hash, target or backup integrity differs.")
    validate_text(original)
    if len(original) > MAX_NATIVE_SIZE:
        raise BridgeError("Source backup exceeds size limit.")
    if target.stat().st_nlink != 1:
        raise BridgeError("Refusing source restore to a hard-linked file.")
    with target_lock(target):
        assert_hash(target, expected)
        backup = create_backup(
            target, current, history, "source_restore", sha256(original)
        )
        temporary = workspace / (".source-restore-" + uuid.uuid4().hex)
        try:
            write_new(temporary, original)
            assert_hash(target, expected)
            os.replace(str(temporary), str(target))
            assert_hash(target, sha256(original))
        finally:
            if temporary.exists():
                temporary.unlink()
    return dict(
        status="source_restored",
        source_sha256=sha256(original),
        backup=str(backup),
        native_unchanged=True,
    )

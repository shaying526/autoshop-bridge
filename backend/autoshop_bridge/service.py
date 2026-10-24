"""Reusable operations independent of command-line argument parsing."""

from pathlib import Path
from typing import Optional

from autoshop_bridge import __version__
from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats.st import (
    MAX_PROGRAM_LINES,
    validate_text,
    validate_program_edit,
)
from autoshop_bridge.formats.native import PROFILES, parse, line_metadata_matches
from autoshop_bridge.storage import (
    assert_hash,
    create_backup,
    native_file,
    read_json,
    regular_file,
    replace_verified,
    sha256,
    target_lock,
    utc_now,
    writable_target,
    write_json_new,
    write_new,
)

# Explicit public surface. Imported helpers and test backends are internal.
# Parameter/result and validation scopes live in docs/UI_INTEGRATION.md.
__all__ = (
    "scan",
    "project_summary",
    "system_variables_read",
    "code_query",
    "code_context",
    "export",
    "check",
    "build",
    "apply",
    "backup",
    "restore",
    "source_read",
    "source_patch",
    "source_restore",
    "table_export",
    "table_check",
    "table_build",
    "table_apply",
    "editor_open",
    "editor_read",
    "editor_sync",
    "editor_save",
    "editor_close",
    "editor_variables",
    "table_editor_read",
    "table_editor_edit",
    "table_editor_close",
    "instances_editor_read",
    "instances_editor_add",
    "build_baseline",
    "build_report",
    "change_check",
    "change_run",
    "object_dialog",
    "object_create_st",
)


def scan(project: Path, output: Optional[Path] = None) -> dict:
    from autoshop_bridge.projects.inventory import scan as scan_project

    result = scan_project(project, allow_readonly_tail=True)
    if output is not None:
        write_json_new(output, result)
        return {
            "status": result["status"],
            "output": str(output.resolve()),
            "counts": result["counts"],
            "registration_source": result["registration_source"],
        }
    return result


def system_variables_read(project, definitions_dir, table=None, type_name=None,
                          search=None, limit=20, offset=0, output=None):
    from autoshop_bridge.projects.system_variables import read

    return read(project, definitions_dir, table, type_name, search, limit, offset, output)


def object_dialog(**options):
    from autoshop_bridge.windows.creation import inspect_dialog

    return inspect_dialog(**options)


def project_summary(**options):
    from autoshop_bridge.projects.inventory import summary

    return summary(**options)


def object_create_st(**options):
    from autoshop_bridge.windows.creation import create_st

    return create_st(**options)


def source_read(**options):
    from autoshop_bridge.workflows.source import source_read as run

    return run(**options)


def source_patch(**options):
    from autoshop_bridge.workflows.source import source_patch as run

    return run(**options)


def source_restore(**options):
    from autoshop_bridge.workflows.source import source_restore as run

    return run(**options)


def code_query(**options):
    from autoshop_bridge.projects.query import code_query as run

    return run(**options)


def code_context(**options):
    from autoshop_bridge.projects.query import code_context as run

    return run(**options)


def build_baseline(**options):
    from autoshop_bridge.workflows.builds import build_baseline as run

    return run(**options)


def build_report(**options):
    from autoshop_bridge.workflows.builds import build_report as run

    return run(**options)


def change_check(**options):
    from autoshop_bridge.workflows.changes import change_check as run

    return run(**options)


def change_run(**options):
    from autoshop_bridge.workflows.changes import change_run as run

    return run(**options)


def editor_open(project, program, pid=None):
    from autoshop_bridge.windows.session import open_program

    return open_program(project, program, pid)


def editor_read(project, program, pid=None, open_if_missing=False, output=None):
    from autoshop_bridge.windows.session import read_program

    return read_program(project, program, pid, open_if_missing, output)


def editor_close(project, program, pid=None):
    from autoshop_bridge.windows.session import close_program

    return close_program(project, program, pid)


def editor_save(snapshot_file, pid=None, close_after=False, backup_root=None):
    from autoshop_bridge.windows.session import save_snapshot

    return save_snapshot(snapshot_file, pid, close_after, backup_root)


def instances_editor_read(**options):
    from autoshop_bridge.windows.instance_session import read

    return read(**options)


def instances_editor_add(**options):
    from autoshop_bridge.windows.instance_session import add

    return add(**options)


def editor_variables(**options):
    from autoshop_bridge.windows.variables import edit

    return edit(**options)


def table_export(**options):
    from autoshop_bridge.workflows.tables import export

    return export(**options)


def table_check(**options):
    from autoshop_bridge.workflows.tables import check

    return check(**options)


def table_build(**options):
    from autoshop_bridge.workflows.tables import build

    return build(**options)


def table_apply(**options):
    from autoshop_bridge.workflows.tables import apply

    return apply(**options)


def table_editor_read(**options):
    from autoshop_bridge.workflows.tables import editor_read

    return editor_read(**options)


def table_editor_edit(**options):
    from autoshop_bridge.workflows.tables import editor_edit

    return editor_edit(**options)


def table_editor_close(**options):
    from autoshop_bridge.workflows.tables import editor_close

    return editor_close(**options)


def export(native: Path, workspace: Path) -> dict:
    native = native_file(native)
    raw = native.read_bytes()
    kind = native.suffix.lower()[1:]
    container = parse(raw, kind)
    workspace.mkdir(parents=True)  # Existing workspaces are never overwritten.
    workspace = workspace.resolve()
    write_new(workspace / "original.native", raw)
    write_new(workspace / "source.st", container.source)
    if kind in ("fb", "fc"):
        write_json_new(workspace / "variables.json", container.variable_document())
    manifest = {
        "schema": 1,
        "tool_version": __version__,
        "profile": PROFILES[kind],
        "native_kind": kind,
        "native_path": str(native),
        "native_sha256": sha256(raw),
        "source_sha256": sha256(container.source),
        "created_at": utc_now(),
    }
    write_json_new(workspace / "manifest.json", manifest)
    return {
        "status": "exported",
        "workspace": str(workspace),
        "source": str(workspace / "source.st"),
        "native_sha256": sha256(raw),
        "payload_offset": container.payload_offset,
        "source_bytes": len(container.source),
        "line_count": container.line_count,
        "native_kind": kind,
        "line_table_count": container.line_table_count,
        "line_metadata_matches_source": line_metadata_matches(container),
        "variable_count": len(container.variables) if kind in ("fb", "fc") else None,
        "autoshop_verified": False,
    }


def load_workspace(workspace: Path):
    workspace = workspace.resolve(strict=True)
    manifest = read_json(regular_file(workspace / "manifest.json"))
    kind = manifest.get("native_kind", "st")  # 0.1.0 ST workspaces omitted this key.
    if (
        not isinstance(kind, str)
        or kind not in PROFILES
        or manifest.get("schema") != 1
        or manifest.get("profile") != PROFILES.get(kind)
    ):
        raise BridgeError("Unsupported workspace schema/profile.")
    if (
        not isinstance(manifest.get("native_path"), str)
        or not Path(manifest["native_path"]).is_absolute()
    ):
        raise BridgeError("Workspace native_path must be absolute.")
    raw = regular_file(workspace / "original.native").read_bytes()
    if sha256(raw) != manifest.get("native_sha256"):
        raise BridgeError("Workspace native snapshot hash mismatch.")
    container = parse(raw, kind)
    if kind in ("fb", "fc"):
        exported_variables = read_json(regular_file(workspace / "variables.json"))
        if exported_variables != container.variable_document():
            raise BridgeError(
                "FB/FC variables.json is read-only; variable write-back is unsupported."
            )
    if sha256(container.source) != manifest.get("source_sha256"):
        raise BridgeError("Workspace source baseline hash mismatch.")
    source = regular_file(workspace / "source.st").read_bytes()
    validate_text(source)
    return manifest, container, source


def check(workspace: Path, target: Optional[Path] = None, method="file") -> dict:
    if method not in ("file", "editor"):
        raise BridgeError("Check method must be file or editor.")
    manifest, container, source = load_workspace(workspace)
    target = native_file(target or Path(manifest["native_path"]))
    if target.suffix.lower()[1:] != manifest.get("native_kind", "st"):
        raise BridgeError("Target extension does not match the workspace native kind.")
    current = target.read_bytes()
    line_count = source.count(b"\n") + 1
    reasons = []
    if sha256(current) != manifest["native_sha256"]:
        reasons.append("target_changed")
    if method == "file" and line_count != container.line_count:
        reasons.append("line_count_changed")
    if (
        method == "file"
        and source != container.source
        and not line_metadata_matches(container)
    ):
        reasons.append("line_metadata_mismatch")
    if source != container.source and line_count > MAX_PROGRAM_LINES:
        reasons.append("program_line_limit_exceeded")
    if not reasons and method == "file":
        container.rebuild(source)
    if not reasons and method == "editor" and source != container.source:
        validate_program_edit(source)
    return {
        "status": "ready" if not reasons else "blocked",
        "reasons": reasons,
        "target": str(target),
        "current_sha256": sha256(current),
        "baseline_sha256": manifest["native_sha256"],
        "edited": source != container.source,
        "source_bytes": len(source),
        "baseline_source_bytes": len(container.source),
        "line_count": line_count,
        "baseline_line_count": container.line_count,
        "line_table_count": container.line_table_count,
        "line_metadata_matches_source": line_metadata_matches(container),
        "experimental_required": source != container.source,
        "method": method,
        "editor_session_checked": False,
        "autoshop_verified": False,
    }


def candidate(workspace: Path, experimental: bool):
    manifest, container, source = load_workspace(workspace)
    if source != container.source and not experimental:
        raise BridgeError(
            "Edited write-back has limited AutoShop validation; use --experimental on copies."
        )
    return manifest, container.rebuild(source)


def build(workspace: Path, output: Path, experimental: bool = False) -> dict:
    # A candidate is generated from the snapshot even if the live source changed.
    # It is never eligible for apply unless the target matches the baseline.
    _, raw = candidate(workspace, experimental)
    write_new(output, raw)
    return {
        "status": "built",
        "output": str(output.resolve()),
        "sha256": sha256(raw),
        "autoshop_verified": False,
    }


def apply(
    workspace: Path,
    target: Optional[Path] = None,
    experimental: bool = False,
    backup_root: Optional[Path] = None,
) -> dict:
    manifest, raw = candidate(workspace, experimental)
    target = native_file(target or Path(manifest["native_path"]))
    if target.suffix.lower()[1:] != manifest.get("native_kind", "st"):
        raise BridgeError("Target extension does not match the workspace native kind.")
    result = replace_verified(
        target, manifest["native_sha256"], raw, backup_root, "apply"
    )
    result["autoshop_verified"] = False
    return result


def backup(native: Path, backup_root: Optional[Path] = None) -> dict:
    native = native_file(native)
    with target_lock(native):
        raw = native.read_bytes()
        saved = create_backup(native, raw, backup_root)
        assert_hash(native, sha256(raw))
    return {"status": "backed_up", "backup": str(saved), "sha256": sha256(raw)}


def restore(
    saved: Path,
    expected: str,
    target: Optional[Path] = None,
    backup_root: Optional[Path] = None,
) -> dict:
    if len(expected) != 64 or any(c not in "0123456789abcdefABCDEF" for c in expected):
        raise BridgeError("Expected SHA-256 must contain 64 hexadecimal characters.")
    meta = read_json(regular_file(saved / "backup.json"))
    if meta.get("schema") != 1 or not isinstance(meta.get("target_path"), str):
        raise BridgeError("Invalid backup metadata.")
    if not Path(meta["target_path"]).is_absolute():
        raise BridgeError("Backup target_path must be absolute.")
    raw = regular_file(saved / "original.native").read_bytes()
    if sha256(raw) != meta.get("sha256") or len(raw) != meta.get("size"):
        raise BridgeError("Backup integrity check failed; refusing restore.")
    return replace_verified(
        target or Path(meta["target_path"]),
        expected.lower(),
        raw,
        backup_root,
        "restore",
    )


def editor_sync(
    workspace: Path,
    project: Path,
    program: str,
    experimental: bool = False,
    dry_run: bool = False,
    pid: Optional[int] = None,
    backup_root: Optional[Path] = None,
    backend=None,
    open_if_missing=False,
    save=False,
    close_after=False,
) -> dict:
    """Update one validated editor buffer; AutoShop saving remains a user action."""
    from autoshop_bridge.windows.editor import assert_baseline

    if close_after and not save:
        raise BridgeError(
            "--close requires --save; unsaved changes are never discarded."
        )
    if dry_run and open_if_missing:
        raise BridgeError("--dry-run does not open tabs; use editor-open first.")

    manifest, container, source = load_workspace(workspace)
    target = native_file(Path(manifest["native_path"]))
    if save:
        writable_target(target)
    if target.suffix.lower()[1:] != manifest.get("native_kind", "st"):
        raise BridgeError("Target extension does not match the workspace native kind.")
    project = project.resolve(strict=True)
    if not project.is_dir() or project not in target.parents:
        raise BridgeError(
            "Workspace native target must be inside the explicit project directory."
        )
    expected_program = (
        container.program_name if manifest.get("native_kind") in ("fb", "fc") else target.stem
    )
    if program != expected_program:
        raise BridgeError("Program does not match the workspace native object.")
    edited = source != container.source
    if edited:
        validate_program_edit(
            source
        )  # AutoShop generates native rows on explicit save.
    if edited and not experimental and not dry_run:
        raise BridgeError("Editor synchronization requires --experimental.")
    original = assert_hash(target, manifest["native_sha256"])
    lifecycle = open_if_missing or save or close_after
    opened = False
    if backend is not None:
        adapter = backend
    else:
        from autoshop_bridge.windows.session import WindowsSession, resolve_target

        _, registered_target = resolve_target(project, program)
        if registered_target != target:
            raise BridgeError(
                "Workspace target differs from the program registered in the open project."
            )
        adapter = WindowsSession(project, program, pid)
        if target.suffix.lower() == ".fc":
            from autoshop_bridge.windows.session import FC_COLUMNS
            adapter.columns = FC_COLUMNS
        opened = adapter.ensure_open(open_if_missing)
    initial_snapshot = None
    if lifecycle or backend is None or hasattr(adapter, "grid"):
        from autoshop_bridge.windows.session import assert_clean_native, snapshot

        initial_snapshot = snapshot(adapter, target)
        assert_clean_native(adapter, target, original, observed=initial_snapshot)
    state = adapter.read()
    assert_baseline(state, container.source)
    base = {
        "target": str(target),
        "project": str(project),
        "program": program,
        "editor_hwnd": state.hwnd,
        "pid": state.pid,
        "edited": edited,
        "opened": opened,
        "experimental_required": edited,
        "autoshop_verified": False,
    }
    base.update(
        line_count=source.count(b"\n") + 1,
        baseline_line_count=container.line_count,
        line_count_changed=source.count(b"\n") + 1 != container.line_count,
    )
    if dry_run:
        return dict(base, status="editor_ready", native_sha256=sha256(original))
    if not edited:
        if close_after:
            adapter.close()
            return dict(base, status="unchanged_closed", native_sha256=sha256(original))
        return dict(base, status="unchanged", native_sha256=sha256(original))
    with target_lock(target):
        original = assert_hash(target, manifest["native_sha256"])
        assert_baseline(adapter.read(), container.source)
        backup_path = create_backup(target, original, backup_root, "editor_sync")
        write_new(backup_path / "editor_before.st", container.source)
        write_new(backup_path / "editor_after.st", source)
        write_json_new(
            backup_path / "editor_sync.json",
            dict(
                base,
                source_before_sha256=sha256(container.source),
                source_after_sha256=sha256(source),
                created_at=utc_now(),
            ),
        )
        # All backup files must be durable before changing the editor buffer.
        assert_hash(target, manifest["native_sha256"])
        assert_baseline(adapter.read(), container.source)
        try:
            adapter.write(source)
            after = adapter.read()
            if after.source != source or not after.modified:
                raise BridgeError(
                    "Editor read-back/modified-state verification failed."
                )
            assert_hash(target, manifest["native_sha256"])
            result = dict(
                base,
                status="editor_updated_not_saved",
                backup=str(backup_path),
                source_sha256=sha256(source),
                source_bytes=len(source),
                native_unchanged=True,
                requires_manual_save=True,
            )
            if save:
                from autoshop_bridge.windows.session import snapshot, verify_saved

                expected = snapshot(adapter, target)
                if (
                    expected["source"].encode("utf-8") != source
                    or expected["variables"] != initial_snapshot["variables"]
                ):
                    raise BridgeError(
                        "Editor body/variable baseline changed before save."
                    )
                write_json_new(backup_path / "editor_expected.json", expected)
                assert_hash(target, manifest["native_sha256"])
                adapter.save()
                saved_hash = verify_saved(adapter, target, expected)
                saved_obj = parse(
                    assert_hash(target, saved_hash), target.suffix.lower()[1:]
                )
                result.update(
                    status="editor_saved",
                    native_sha256=saved_hash,
                    native_unchanged=False,
                    requires_manual_save=False,
                    saved_line_count=saved_obj.line_count,
                    saved_line_table_count=saved_obj.line_table_count,
                    line_metadata_matches_source=line_metadata_matches(saved_obj),
                )
                if close_after:
                    adapter.close()
                    result["status"] = "editor_saved_closed"
            write_json_new(backup_path / "editor_sync_result.json", result)
            return result
        except (OSError, BridgeError) as exc:
            raise BridgeError(
                "{} Editor buffer may have changed; inspect AutoShop before saving. "
                "Backup retained at: {}".format(exc, backup_path)
            ) from exc

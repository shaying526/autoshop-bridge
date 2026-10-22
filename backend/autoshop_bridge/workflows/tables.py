"""Table workspaces and both file/editor routes, sharing one validated change plan."""

import copy
from pathlib import Path

from autoshop_bridge import __version__
from autoshop_bridge.errors import BridgeError
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
from autoshop_bridge.formats.tables import parse, comment_display
from autoshop_bridge.projects import tables as table_context

PROFILE = "autoshop-native-tables-v1-experimental"


def export(native, workspace):
    target = native_file(native)
    kind = target.suffix.lower()[1:]
    raw = target.read_bytes()
    obj = parse(raw, kind)
    context = table_context.capture(target) if kind == "gvt" else None
    workspace.mkdir(parents=True)
    workspace = workspace.resolve()
    write_new(workspace / "original.native", raw)
    write_json_new(workspace / "table.json", obj.document())
    write_json_new(workspace / "changes.json", dict(schema=1, operations=[]))
    manifest = dict(
        schema=1,
        profile=PROFILE,
        kind=kind,
        tool_version=__version__,
        native_path=str(target),
        native_sha256=sha256(raw),
        created_at=utc_now(),
    )
    if context is not None:
        manifest["global_context"] = context
    write_json_new(workspace / "manifest.json", manifest)
    return dict(
        status="table_exported",
        workspace=str(workspace),
        kind=kind,
        row_count=len(obj.rows),
        native_sha256=sha256(raw),
    )


def load(workspace):
    workspace = workspace.resolve(strict=True)
    manifest = read_json(regular_file(workspace / "manifest.json"))
    if (
        manifest.get("schema") != 1
        or manifest.get("profile") != PROFILE
        or manifest.get("kind") not in ("stru", "gvt")
        or not isinstance(manifest.get("native_path"), str)
        or not Path(manifest["native_path"]).is_absolute()
    ):
        raise BridgeError("Unsupported table workspace manifest.")
    raw = regular_file(workspace / "original.native").read_bytes()
    if sha256(raw) != manifest.get("native_sha256"):
        raise BridgeError("Table snapshot hash mismatch.")
    obj = parse(raw, manifest["kind"])
    if read_json(regular_file(workspace / "table.json")) != obj.document():
        raise BridgeError("table.json is read-only; edit changes.json instead.")
    changes = read_json(regular_file(workspace / "changes.json"))
    if set(changes) != {"schema", "operations"} or changes.get("schema") != 1:
        raise BridgeError("Table changes require schema=1 and operations.")
    result = obj.rebuild(changes["operations"])
    return manifest, obj, changes["operations"], result


def target_for(manifest, target=None):
    target = native_file(target or Path(manifest["native_path"]))
    if target.suffix.lower() != "." + manifest["kind"]:
        raise BridgeError("Table target extension differs from workspace kind.")
    return target


def check(workspace, target=None):
    manifest, obj, ops, result = load(workspace)
    target = target_for(manifest, target)
    current = target.read_bytes()
    conflict = sha256(current) != manifest["native_sha256"]
    reasons = ["target_changed"] if conflict else []
    try:
        table_context.validate(manifest, ops, target)
    except BridgeError as exc:
        reasons.append(str(exc))
        conflict = True
    return dict(
        status="blocked" if conflict else "table_ready",
        reasons=reasons,
        target=str(target),
        edited=result != obj.raw,
        row_count=len(parse(result, obj.kind).rows),
        native_sha256=sha256(current),
        candidate_sha256=sha256(result),
        autoshop_verified=False,
    )


def build(workspace, output, experimental=False):
    manifest, obj, ops, result = load(workspace)
    table_context.validate(manifest, ops, target_for(manifest))
    if result != obj.raw and not experimental:
        raise BridgeError("Table modifications require --experimental.")
    write_new(output, result)
    return dict(
        status="table_built",
        output=str(output.resolve()),
        sha256=sha256(result),
        autoshop_verified=False,
    )


def apply(workspace, target=None, experimental=False, backup_root=None):
    manifest, obj, ops, result = load(workspace)
    if result != obj.raw and not experimental:
        raise BridgeError("Table modifications require --experimental.")
    target = target_for(manifest, target)
    with table_context.lock_others(manifest, ops, target):
        response = replace_verified(
            target,
            manifest["native_sha256"],
            result,
            backup_root,
            "table_apply",
            validate_context=lambda: table_context.validate(manifest, ops, target),
        )
    response["autoshop_verified"] = False
    return response


def connect(project, table, pid=None, open_if_missing=False):
    from autoshop_bridge.windows.table_session import WindowsTableSession
    from autoshop_bridge.projects.inventory import scan

    inventory = scan(project)
    found = [
        r
        for r in inventory["files"]
        if r.get("kind") in ("structure", "global_variables")
        and (r.get("name") == table or Path(r["file"]).stem == table)
    ]
    if len(found) != 1:
        raise BridgeError(
            "Expected one registered native table; found {}.".format(len(found))
        )
    target = native_file(Path(found[0]["path"]))
    kind = target.suffix.lower()[1:]
    obj = parse(target.read_bytes(), kind)
    if kind == "stru" and obj.name != table:
        raise BridgeError("Structure name differs from requested document.")
    adapter = WindowsTableSession(Path(inventory["project"]), table, kind, pid)
    opened = adapter.ensure_open(open_if_missing)
    return adapter, target, opened


def editor_read(project, table, pid=None, open_if_missing=False, output=None):
    from autoshop_bridge.windows.table_session import assert_native_table

    adapter, target, opened = connect(project, table, pid, open_if_missing)
    raw = target.read_bytes()
    obj = parse(raw, target.suffix.lower()[1:])
    rows = adapter.grid()
    matches, reason = True, None
    try:
        assert_native_table(obj, rows)
    except BridgeError as exc:
        matches, reason = False, str(exc)
    result = dict(
        status="table_editor_read",
        schema=1,
        project=adapter.project,
        table=table,
        target=str(target),
        pid=adapter.pid,
        kind=obj.kind,
        opened=opened,
        modified=adapter.dirty(),
        native_sha256=sha256(raw),
        native=obj.document(),
        editor_rows=rows,
        displayed_fields_match_native=matches,
        mismatch_reason=reason,
    )
    result["grid_read"] = getattr(adapter, "last_grid_read", None)
    if output:
        write_json_new(output, result)
        return dict(
            status=result["status"],
            output=str(output.resolve()),
            row_count=len(rows),
            modified=result["modified"],
            displayed_fields_match_native=matches,
        )
    return result


def semantic_document(obj):
    document = obj.document()
    for row in document["rows"]:
        row["comment"] = comment_display(row["comment"])
    return document


def editor_edit(
    workspace,
    project,
    table,
    pid=None,
    open_if_missing=False,
    experimental=False,
    dry_run=False,
    save=False,
    close_after=False,
    backup_root=None,
    backend=None,
):
    from autoshop_bridge.windows.table_session import assert_native_table, add_row

    if close_after and not save:
        raise BridgeError("--close requires --save; unsaved edits are never discarded.")
    if dry_run and open_if_missing:
        raise BridgeError(
            "--dry-run does not open tabs; open first with table-editor-read --open."
        )
    manifest, obj, ops, result = load(workspace)
    edited = obj.raw != result
    if edited and not experimental and not dry_run:
        raise BridgeError("Table editor modifications require --experimental.")
    target = target_for(manifest)
    if save:
        writable_target(target)
    if backend is None:
        adapter, registered, opened = connect(project, table, pid, open_if_missing)
        if registered != target:
            raise BridgeError("Workspace target differs from the registered table.")
    else:
        adapter, opened = backend, False
    with table_context.lock_others(manifest, ops, target), target_lock(target):
        raw = assert_hash(target, manifest["native_sha256"])
        before = adapter.grid()
        if adapter.dirty():
            raise BridgeError("Table editor has unsaved changes.")
        assert_native_table(obj, before)
        if dry_run:
            return dict(
                status="table_editor_ready", row_count=len(before), edited=edited
            )
        if not edited:
            if close_after:
                adapter.close()
            return dict(
                status="unchanged_closed" if close_after else "unchanged",
                row_count=len(before),
            )
        saved = create_backup(target, raw, backup_root, "table_editor")
        write_json_new(
            saved / "table_editor_before.json", dict(rows=before, native=obj.document())
        )
        write_json_new(
            saved / "table_editor_changes.json", dict(schema=1, operations=ops)
        )
        if adapter.dirty() or adapter.grid() != before:
            raise BridgeError("Table editor changed during backup.")
        assert_hash(target, manifest["native_sha256"])
        table_context.validate(manifest, ops, target)
        current = copy.deepcopy(before)
        try:
            for op in ops:
                desired = copy.deepcopy(current)
                if op["op"] == "set":
                    row = next(r for r in desired if r["name"] == op["name"])
                    field = op["field"]
                    expected = (
                        comment_display(op["expected"])
                        if field == "comment"
                        else op["expected"]
                    )
                    value = (
                        comment_display(op["value"])
                        if field == "comment"
                        else op["value"]
                    )
                    if row[field] != expected:
                        raise BridgeError("Table editor field changed before edit.")
                    if expected == value:
                        continue
                    row[field] = value
                    if field == "initial_value":
                        row["initial_raw"] = value
                    actual = adapter.set_cell(op["name"], field, expected, value)
                    if actual != desired:
                        raise BridgeError("Full table readback differs after edit.")
                else:
                    desired = add_row(adapter, current, op, obj.kind)
                current = desired
                assert_hash(target, manifest["native_sha256"])
                table_context.validate(manifest, ops, target)
            if adapter.grid() != current or not adapter.dirty():
                raise BridgeError("Table final readback/dirty state differs.")
            candidate = parse(result, obj.kind)
            assert_native_table(candidate, current)
            write_json_new(
                saved / "table_editor_expected.json",
                dict(rows=current, native=candidate.document()),
            )
            response = dict(
                status="table_editor_updated_not_saved",
                target=str(target),
                backup=str(saved),
                row_count=len(current),
                opened=opened,
                requires_manual_save=True,
                autoshop_verified=False,
            )
            if save:
                assert_hash(target, manifest["native_sha256"])
                table_context.validate(manifest, ops, target)
                adapter.save()
                after_raw = target.read_bytes()
                after = parse(after_raw, obj.kind)
                if adapter.dirty() or adapter.grid() != current:
                    raise BridgeError("Table view changed during save.")
                assert_native_table(after, current)
                if semantic_document(after) != semantic_document(candidate):
                    raise BridgeError(
                        "Saved table metadata or non-target fields differ from candidate."
                    )
                table_context.validate(manifest, ops, target, include_target=False)
                response.update(
                    status="table_editor_saved",
                    requires_manual_save=False,
                    sha256=sha256(after_raw),
                )
                if close_after:
                    adapter.close()
                    response["status"] = "table_editor_saved_closed"
            write_json_new(saved / "table_editor_result.json", response)
            return response
        except (BridgeError, OSError) as exc:
            raise BridgeError(
                "{} Table buffer or saved file may have changed; inspect AutoShop. Backup: {}".format(
                    exc, saved
                )
            ) from exc


def editor_close(project, table, pid=None):
    from autoshop_bridge.windows.table_session import assert_native_table

    adapter, target, _ = connect(project, table, pid)
    raw = target.read_bytes()
    obj = parse(raw, target.suffix.lower()[1:])
    if adapter.dirty():
        raise BridgeError("Refusing to close an unsaved table.")
    assert_native_table(obj, adapter.grid())
    adapter.close()
    assert_hash(target, sha256(raw))
    return dict(status="table_editor_closed", table=table, target=str(target))

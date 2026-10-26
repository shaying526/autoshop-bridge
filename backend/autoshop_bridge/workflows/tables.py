"""Table workspaces and both file/editor routes, sharing one validated change plan."""

import copy
from contextlib import ExitStack
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
from autoshop_bridge.projects import types as type_context
from autoshop_bridge.projects.identifiers import precheck_addition_names

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


def load(workspace, *, editor_project=None):
    workspace = workspace.resolve(strict=True)
    manifest = read_json(regular_file(workspace / "manifest.json"))
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != 1
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
    if not isinstance(changes, dict) or set(changes) != {"schema", "operations"} or changes.get("schema") != 1:
        raise BridgeError("Table changes require schema=1 and operations.")
    operations = changes["operations"]
    if not isinstance(operations, list) or len(operations) > 32:
        raise BridgeError("Expected a list of at most 32 explicit table operations.")
    for op in operations:
        if not isinstance(op, dict):
            raise BridgeError("Table operation must be an object.")
        if not isinstance(op.get("op"), str):
            raise BridgeError("Table operation requires a string op.")
        if op["op"] == "add":
            fields = {"op", "name", "data_type", "comment"}
            if obj.kind == "gvt":
                fields.add("initial_value")
            if set(op) != fields or not isinstance(op.get("data_type"), str) or not op["data_type"]:
                raise BridgeError("Table addition requires exact declaration fields and a string data_type.")
    precheck_addition_names(changes)
    named = [op["data_type"] for op in operations
             if isinstance(op, dict) and op.get("op") == "add"
             and op.get("data_type") not in ("BOOL", "INT", "DINT")]
    if editor_project is not None and obj.kind == "gvt" and named:
        from autoshop_bridge.formats.offline_globals import rebuild
        context = type_context.catalog(editor_project, named)
        if any(context["types"][name]["code"] != 64 for name in named):
            raise BridgeError("Global table editor additions require project structures.")
        type_context.check(context)
        definitions = {name: regular_file(Path(context["types"][name]["path"])).read_bytes()
                       for name in named}
        result = rebuild(raw, operations, definitions)
        type_context.check(context)
        manifest["editor_type_context"] = context
    else:
        result = obj.rebuild(operations)
    return manifest, obj, changes["operations"], result


def _instance_namespace(target):
    from autoshop_bridge.formats import instances
    from autoshop_bridge.formats.st import MAX_NATIVE_SIZE
    result, names = {}, set()
    for path in sorted(target.parent.iterdir()):
        if path.suffix.lower() == ".fbi":
            path = regular_file(path)
            if path.stat().st_nlink > 1:
                raise BridgeError("Multiple hard links are unsupported for FBI namespace dependencies.")
            with path.open("rb") as stream:
                raw = stream.read(MAX_NATIVE_SIZE + 1)
            if len(raw) > MAX_NATIVE_SIZE:
                raise BridgeError("FBI namespace dependency exceeds the native size limit.")
            result[str(path)] = sha256(raw)
            names.update(row["name"].casefold() for row in instances.parse(raw)["instances"])
    return result, names


def _assert_editor_saved(candidate, after, complex_names):
    """Only new complex IDE defaults/address allocation are intentionally opaque."""
    expected, actual = semantic_document(candidate), semantic_document(after)
    for left, right in zip(expected["rows"], actual["rows"]):
        if left["name"] in complex_names:
            right["initial_value_raw"] = left["initial_value_raw"]
            right["uninterpreted_metadata"]["address_raw"] = left["uninterpreted_metadata"]["address_raw"]
    if expected != actual:
        raise BridgeError("Saved table metadata or non-target fields differ from candidate.")


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
    response = dict(
        status="blocked" if conflict else "table_ready",
        reasons=reasons,
        target=str(target),
        edited=result != obj.raw,
        row_count=len(parse(result, obj.kind).rows),
        native_sha256=sha256(current),
        candidate_sha256=sha256(result),
        autoshop_verified=False,
    )
    if obj.kind == "stru" and any(op.get("op") == "set" and op.get("field") == "name" for op in ops):
        response.update(execution="project_rename_batch", associated_metadata_pending=True,
                        references_updated=False, requires_close_entire_project=True)
    return response


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
    if obj.kind == "stru" and any(op.get("op") == "set" and op.get("field") == "name" for op in ops):
        from autoshop_bridge.workflows.structure_rename import apply_table
        return apply_table(target, manifest["native_sha256"], ops, backup_root)
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
    manifest, obj, ops, result = load(workspace, editor_project=project)
    if obj.kind == "stru" and any(op.get("op") == "set" and op.get("field") == "name" for op in ops):
        raise BridgeError("Structure member rename is implemented by table-apply or structure-rename-plan/apply with the project closed, including associated native metadata. Editor rename has not implemented that synchronization yet.")
    context = manifest.get("editor_type_context", dict(types={}, hashes={}))
    complex_names = {op["name"] for op in ops if op["op"] == "add"
                     and op["data_type"] in context["types"]}
    edited = obj.raw != result
    if edited and not experimental and not dry_run:
        raise BridgeError("Table editor modifications require --experimental.")
    target = target_for(manifest)
    namespace_enabled = obj.kind == "gvt" and any(op["op"] == "add" for op in ops)
    instance_hashes, instance_names = _instance_namespace(target) if namespace_enabled else ({}, set())
    if any(op["op"] == "add" and op["name"].casefold() in instance_names for op in ops):
        raise BridgeError("Global variable name conflicts with an FBI instance.")

    def dependencies():
        type_context.check(context)
        if namespace_enabled and _instance_namespace(target)[0] != instance_hashes:
            raise BridgeError("Global FBI namespace changed during editor operation.")

    dependencies()
    if save:
        writable_target(target)
    if backend is None:
        adapter, registered, opened = connect(project, table, pid, open_if_missing)
        if registered != target:
            raise BridgeError("Workspace target differs from the registered table.")
    else:
        adapter, opened = backend, False
    with ExitStack() as locks:
        locks.enter_context(table_context.lock_others(manifest, ops, target))
        for path in sorted(instance_hashes):
            locks.enter_context(target_lock(Path(path)))
        locks.enter_context(target_lock(target))
        raw = assert_hash(target, manifest["native_sha256"])
        before = adapter.grid()
        if adapter.dirty():
            raise BridgeError("Table editor has unsaved changes.")
        assert_native_table(obj, before)
        dependencies()
        if complex_names:
            probe = next((r for r in before if r["data_type"] in ("BOOL", "INT", "DINT")), None)
            if probe is None:
                raise BridgeError("Complex GVT additions require an existing scalar selector probe.")
            choices = adapter.selector_choices(probe["name"], "data_type", probe["data_type"])
            requested_types = {op["data_type"] for op in ops if op["op"] == "add" and op["name"] in complex_names}
            if any(choices.count(name) != 1 for name in requested_types):
                raise BridgeError("Requested project structure is unavailable or ambiguous in the IDE selector.")
            if adapter.grid() != before or adapter.dirty():
                raise BridgeError("Table changed during type selector preflight.")
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
        write_json_new(saved / "table_editor_dependencies.json", dict(types=context, instances=instance_hashes))
        if adapter.dirty() or adapter.grid() != before:
            raise BridgeError("Table editor changed during backup.")
        assert_hash(target, manifest["native_sha256"])
        table_context.validate(manifest, ops, target)
        dependencies()
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
                    desired = add_row(adapter, current, op, obj.kind, complex_type=op["name"] in complex_names)
                current = desired
                assert_hash(target, manifest["native_sha256"])
                table_context.validate(manifest, ops, target)
                dependencies()
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
                dependencies()
                adapter.save()
                after_raw = target.read_bytes()
                after = parse(after_raw, obj.kind)
                if adapter.dirty() or adapter.grid() != current:
                    raise BridgeError("Table view changed during save.")
                assert_native_table(after, current)
                _assert_editor_saved(candidate, after, complex_names)
                dependencies()
                table_context.validate(manifest, ops, target, include_target=False)
                response.update(
                    status="table_editor_saved",
                    requires_manual_save=False,
                    sha256=sha256(after_raw),
                )
                if complex_names:
                    response["complex_initialization"] = dict(scope="IDE defaults; hidden preview is independent from native initializer", native=[r.document() for r in after.rows if r.name in complex_names], editor=[r for r in current if r["name"] in complex_names])
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

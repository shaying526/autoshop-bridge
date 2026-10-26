"""Global FB instances: normal IDE serialization, strict native segment readback."""

import copy
import stat
import re
from pathlib import Path
from autoshop_bridge.formats import instances
from autoshop_bridge.projects import types as type_context
from autoshop_bridge.projects.identifiers import precheck_addition_names
from autoshop_bridge.errors import BridgeError
from autoshop_bridge.projects.inventory import scan
from autoshop_bridge.storage import (
    regular_file,
    assert_hash,
    sha256,
    target_lock,
    create_backup,
    read_json,
    write_json_new,
)
from autoshop_bridge.formats.tables import identifier
from autoshop_bridge.windows.table_session import WindowsTableSession, comment_display

INSTANCE_COLUMNS = dict(
    row="序号",
    name="变量名",
    data_type="数据类型",
    initial_raw="隐藏初始值",
    initial_value="初始值",
    comment="注释",
    allocated_address="分配地址",
    retain_address="保持区地址",
    pointer_address="指针地址",
    bit_length="长度",
    id="ID",
)

# The candidate first-row path below has synthetic coverage only. The user
# deferred the fresh-project registration blocker; no public flag enables it.
EMPTY_INSTANCE_ADDITIONS_VALIDATED = False


def normalize(raw):
    rows, names, ids = [], set(), set()
    for record in raw:
        if set(record) != set(INSTANCE_COLUMNS.values()):
            raise BridgeError("Unsupported global instance columns.")
        row = {k: record[v] or "" for k, v in INSTANCE_COLUMNS.items()}
        if (
            row["row"] != str(len(rows) + 1)
            or not identifier(row["name"])
            or row["name"].casefold() in names
            or not row["id"].isdigit()
            or row["id"] in ids
        ):
            raise BridgeError("Invalid/duplicate global instance row identity.")
        names.add(row["name"].casefold())
        ids.add(row["id"])
        rows.append(row)
    return rows


class WindowsInstanceSession(WindowsTableSession):
    def __init__(self, project, program, pid=None):
        super().__init__(project, program, "gvt", pid)
        self.columns = INSTANCE_COLUMNS

    def grid(self):
        return normalize(self.raw_grid())


def connect(project, table, pid=None, open_if_missing=False):
    inventory = scan(project)
    matches = [
        r
        for r in inventory["files"]
        if r.get("kind") == "function_block_instances"
        and (r.get("name") == table or Path(r["file"]).stem == table)
    ]
    if len(matches) != 1 or matches[0].get("status") != "parsed":
        raise BridgeError("Expected one registered, parsed global instance table.")
    row = matches[0]
    target = regular_file(Path(row["path"]))
    adapter = WindowsInstanceSession(Path(inventory["project"]), table, pid)
    opened = adapter.ensure_open(open_if_missing)
    return adapter, target, opened, inventory


def assert_native(raw, rows):
    native = instances.parse(raw)["instances"]
    if len(native) != len(rows):
        raise BridgeError("Global instance editor/native count differs.")
    for var, row in zip(native, rows):
        if (
            var["name"] != row["name"]
            or var["data_type"] != row["data_type"]
            or comment_display(var["comment"]) != row["comment"]
        ):
            raise BridgeError(
                "Global instance editor/native definition differs: " + var["name"]
            )
        address = var["uninterpreted_metadata"]["address_raw"]
        if address == 0xFFFFFFFF and row["allocated_address"] == "":
            continue
        try:
            shown = int(row["allocated_address"], 16)
        except ValueError as exc:
            raise BridgeError("Unsupported instance allocation display.") from exc
        if address != shown:
            raise BridgeError("Global instance editor/native address differs.")


def snapshot(adapter, target):
    return dict(
        schema=1,
        project=adapter.project,
        table=adapter.program,
        pid=adapter.pid,
        target=str(target),
        native_sha256=sha256(target.read_bytes()),
        modified=adapter.dirty(),
        rows=adapter.grid(),
    )


def read(project, table, pid=None, open_if_missing=False, output=None):
    a, t, opened, _ = connect(project, table, pid, open_if_missing)
    value = snapshot(a, t)
    value.update(
        status="instances_editor_read",
        read_only=True,
        source="editor",
        opened=opened,
        instance_count=len(value["rows"]),
    )
    if output:
        write_json_new(output, value)
        return dict(
            status=value["status"],
            output=str(output.resolve()),
            instance_count=len(value["rows"]),
            modified=value["modified"],
        )
    return value


def validate(document, rows, types, occupied=()):
    precheck_addition_names(document)
    if (
        not isinstance(document, dict)
        or set(document) != {"schema", "operations"}
        or document["schema"] != 1
    ):
        raise BridgeError("Instance changes require schema=1 and operations.")
    ops = document["operations"]
    if not isinstance(ops, list) or not 1 <= len(ops) <= 32:
        raise BridgeError("Expected 1..32 explicit instance additions.")
    names = {r["name"].casefold() for r in rows} | {n.casefold() for n in occupied}
    for op in ops:
        if (
            not isinstance(op, dict)
            or set(op) != {"op", "name", "data_type", "initial_value", "comment"}
            or op.get("op") != "add"
            or not identifier(op.get("name"))
            or op["name"].casefold() in names
            or not isinstance(op.get("data_type"), str)
            or types.get(op["data_type"], {}).get("code") != 256
            or op["initial_value"] is not None
            or not isinstance(op["comment"], str)
            or len(op["comment"].encode("utf-8")) > 4096
            or any(ord(c) < 32 for c in op["comment"])
        ):
            raise BridgeError(
                "Instance add requires a unique name, parsed project FB, initial_value=null and bounded comment."
            )
        names.add(op["name"].casefold())
    return copy.deepcopy(ops)


def verify_preserved(before, after, ops):
    old, new = instances.parse(before), instances.parse(after)
    a, b = old["instances"], new["instances"]
    if [r["name"] for r in b] != [r["name"] for r in a] + [op["name"] for op in ops]:
        raise BridgeError("Saved instance names/order differ.")
    for first, second in zip(a, b):
        start, end = first["record_offset"], second["record_offset"]
        if (
            before[start : start + first["record_bytes"]]
            != after[end : end + second["record_bytes"]]
        ):
            raise BridgeError(
                "Existing native instance record changed: " + first["name"]
            )
    for row, op in zip(b[len(a) :], ops):
        if row["data_type"] != op["data_type"] or row["comment"] != op["comment"]:
            raise BridgeError("Saved new global instance differs.")
    # IDE owns opaque archive sections; compare/report them, never patch them.
    return dict(
        opaque_prefix_changed=old["opaque_prefix_sha256"]
        != new["opaque_prefix_sha256"],
        opaque_suffix_changed=old["opaque_suffix_sha256"]
        != new["opaque_suffix_sha256"],
    )


def add(
    project,
    table,
    changes,
    expected,
    pid=None,
    open_if_missing=False,
    save=False,
    close_after=False,
    experimental=False,
    dry_run=False,
    backup_root=None,
):
    if close_after and not save:
        raise BridgeError("--close requires --save.")
    if (
        not isinstance(expected, str)
        or len(expected) != 64
        or any(c not in "0123456789abcdefABCDEF" for c in expected)
    ):
        raise BridgeError("Expected SHA-256 must contain 64 hexadecimal characters.")
    if not experimental and not dry_run:
        raise BridgeError("Instance additions require --experimental.")
    if dry_run and open_if_missing:
        raise BridgeError("Dry run does not open tabs.")
    document = read_json(changes)
    precheck_addition_names(document)
    a, t, opened, inventory = connect(project, table, pid, open_if_missing)
    info = t.stat()
    if save and (info.st_nlink > 1 or not info.st_mode & stat.S_IWRITE):
        raise BridgeError("Instance target is read-only or has multiple hard links.")
    with target_lock(t):
        raw = assert_hash(t, expected.lower())
        before = snapshot(a, t)
        if before["modified"]:
            raise BridgeError("Global instance table has unsaved changes.")
        assert_native(raw, before["rows"])
        if not before["rows"] and not EMPTY_INSTANCE_ADDITIONS_VALIDATED:
            raise BridgeError(
                "Empty global instance additions are pending AutoShop validation; no row was created."
            )
        raw_ops = document.get("operations", [])
        requested = [
            op.get("data_type")
            for op in (raw_ops if isinstance(raw_ops, list) else [])
            if isinstance(op, dict) and isinstance(op.get("data_type"), str)
        ]
        context = type_context.catalog(project, requested)
        occupied = []
        for item in inventory["files"]:
            if item.get("kind") == "global_variables":
                if item.get("status") != "parsed":
                    raise BridgeError(
                        "All global tables must be parsed for name collision checks."
                    )
                occupied.extend(r["name"] for r in item["table"]["rows"])
                context["hashes"][item["path"]] = item["sha256"]
        ops = validate(document, before["rows"], context["types"], occupied)
        type_context.check(context)
        if dry_run:
            return dict(
                status="instances_ready",
                operations=ops,
                instance_count=len(before["rows"]),
            )
        backup = create_backup(t, raw, backup_root, "editor_instances")
        write_json_new(backup / "editor_before.json", before)
        write_json_new(backup / "instance_changes.json", document)
        write_json_new(backup / "type_context.json", context)
        if snapshot(a, t) != before:
            raise BridgeError("Instance table changed during backup.")
        current = copy.deepcopy(before["rows"])
        try:
            # An empty table has no selector until AutoShop creates its first
            # named row. Validate that exact default before deferred preflight.
            preflight_pending = not current
            if current:
                choices = a.selector_choices(
                    current[0]["name"], "data_type", current[0]["data_type"]
                )
                if any(choices.count(op["data_type"]) != 1 for op in ops):
                    raise BridgeError(
                        "Requested instance type is unavailable/ambiguous in the IDE."
                    )
                if snapshot(a, t) != before:
                    raise BridgeError("Type-selector preflight changed the instance table.")
            for op in ops:
                assert_hash(t, expected.lower())
                type_context.check(context)
                actual = a.set_cell(
                    "#row:" + str(len(current) + 1), "name", "", op["name"]
                )
                if len(actual) != len(current) + 1 or actual[:-1] != current:
                    raise BridgeError("Instance addition altered existing rows/count.")
                row = actual[-1]
                if (
                    row["name"] != op["name"]
                    or not row["id"].isdigit()
                    or row["id"] in {r["id"] for r in current}
                ):
                    raise BridgeError("Unsupported new instance identity.")
                if (
                    row["allocated_address"]
                    or row["retain_address"]
                    or row["pointer_address"]
                    or row["comment"]
                    or row["initial_value"] != "..."
                    or not row["data_type"]
                    or not re.fullmatch(r"nBitLen:[1-9][0-9]*", row["bit_length"])
                ):
                    raise BridgeError(
                        "Unsupported new instance defaults/allocation state."
                    )
                current = actual
                if preflight_pending:
                    choices = a.selector_choices(row["name"], "data_type", row["data_type"])
                    if any(choices.count(item["data_type"]) != 1 for item in ops):
                        raise BridgeError("Requested instance type is unavailable/ambiguous after the first default row; inspect unsaved buffer.")
                    observed = snapshot(a, t)
                    if observed["rows"] != current or not observed["modified"]:
                        raise BridgeError("Deferred instance selector changed the first-row buffer.")
                    assert_hash(t, expected.lower())
                    type_context.check(context)
                    preflight_pending = False
                if row["data_type"] != op["data_type"]:
                    actual = a.set_cell(
                        op["name"], "data_type", row["data_type"], op["data_type"]
                    )
                    desired = copy.deepcopy(current)
                    desired[-1].update(
                        data_type=op["data_type"],
                        initial_raw=actual[-1]["initial_raw"],
                        initial_value=actual[-1]["initial_value"],
                        bit_length=actual[-1]["bit_length"],
                    )
                    if actual != desired:
                        raise BridgeError(
                            "Instance type change affected unexpected columns/rows."
                        )
                    current = actual
                if current[-1]["comment"] != op["comment"]:
                    desired = copy.deepcopy(current)
                    desired[-1]["comment"] = op["comment"]
                    actual = a.set_cell(
                        op["name"], "comment", current[-1]["comment"], op["comment"]
                    )
                    if actual != desired:
                        raise BridgeError(
                            "Instance comment full-table readback differs."
                        )
                    current = actual
            assert_hash(t, expected.lower())
            type_context.check(context)
            after = snapshot(a, t)
            if after["rows"] != current or not after["modified"]:
                raise BridgeError("Instance expected buffer/dirty state differs.")
            write_json_new(backup / "editor_expected.json", after)
            result = dict(
                status="instances_updated_not_saved",
                backup=str(backup),
                target=str(t),
                instance_count=len(current),
                opened=opened,
                requires_manual_save=True,
                autoshop_compile_verified=False,
            )
            if save:
                assert_hash(t, expected.lower())
                type_context.check(context)
                a.save()
                saved = t.read_bytes()
                assert_native(saved, a.grid())
                if a.dirty() or a.grid() != current:
                    raise BridgeError(
                        "Saved instance table differs from expected buffer."
                    )
                result.update(
                    status="instances_saved",
                    sha256=sha256(saved),
                    requires_manual_save=False,
                    archive_changes=verify_preserved(raw, saved, ops),
                )
                write_json_new(
                    backup / "native_added_instances.json",
                    dict(
                        schema=1,
                        instances=instances.parse(saved)["instances"][
                            len(before["rows"]) :
                        ],
                        initialization_scope="IDE default; nested initializer syntax remains opaque",
                    ),
                )
                if close_after:
                    a.close()
                    result["status"] = "instances_saved_closed"
            write_json_new(backup / "instance_result.json", result)
            return result
        except (BridgeError, OSError) as exc:
            raise BridgeError(
                "{} Instance buffer or saved file may have changed; inspect AutoShop. Backup: {}".format(
                    exc, backup
                )
            ) from exc

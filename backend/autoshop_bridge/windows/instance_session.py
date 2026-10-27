"""Global FB instances: normal IDE serialization, strict native segment readback."""

import copy
import ctypes
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

# V4.11.0.5: empty table -> first/second project-FB instance saved and read back
# in an independent copy. Registration/type/hash/backup checks remain mandatory.
EMPTY_INSTANCE_ADDITIONS_VALIDATED = True


def normalize(raw):
    rows, names, ids = [], set(), set()
    for record in raw:
        if set(record) != set(INSTANCE_COLUMNS.values()):
            raise BridgeError("Unsupported global instance columns.")
        row = {k: record[v] or "" for k, v in INSTANCE_COLUMNS.items()}
        if (
            row["row"] != str(len(rows) + 1)
            or not row["name"].isidentifier()
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

    def raw_grid(self):
        self.assert_no_cell_edit()
        rows, names = [], None
        while True:
            page = self.accessible("instance_grid_page", self.variable_grid(), offset=len(rows), limit=16)
            if (not isinstance(page, dict) or set(page) != {"schema", "scope", "offset", "limit", "total", "names", "columns", "rows"}
                    or page["schema"] != 1 or page["scope"] != "fbi_declarations_page"
                    or type(page["offset"]) is not int or page["offset"] != len(rows)
                    or page["limit"] != 16 or type(page["total"]) is not int or not 0 <= page["total"] <= 4096
                    or not isinstance(page["names"], list) or len(page["names"]) != page["total"]
                    or any(not isinstance(name, str) or not name.isidentifier() for name in page["names"])
                    or len({name.casefold() for name in page["names"]}) != page["total"]
                    or page["columns"] != list(INSTANCE_COLUMNS.values())
                    or not isinstance(page["rows"], list) or len(page["rows"]) != min(16, page["total"] - len(rows))):
                raise BridgeError("Incomplete/inconsistent FBI grid page.")
            if names is not None and names != page["names"]:
                raise BridgeError("FBI declaration identities changed between pages.")
            names = page["names"]
            for index, row in enumerate(page["rows"], len(rows)):
                if (not isinstance(row, dict) or set(row) != set(INSTANCE_COLUMNS.values())
                        or any(not isinstance(value, str) for value in row.values())
                        or row[INSTANCE_COLUMNS["name"]] != names[index]
                        or row[INSTANCE_COLUMNS["row"]] != str(index + 1)):
                    raise BridgeError("FBI page row identity/columns differ.")
            rows.extend(page["rows"])
            if len(rows) == len(names):
                self.last_grid_read = dict(read_scope="declarations", declaration_rows=len(rows),
                                           paged=True, page_size=16, complete=True)
                return rows

    def set_cell(self, variable, field, expected, value):
        self.write_cell(variable, field, expected, value)
        if field == "name":
            # Normal FBI rename can rebuild the document/grid and open a source
            # reference. Resolve the same exact registered table, never reuse
            # its former control handle or repeat the name edit.
            self.validate_main()
            self.locate_editor()
        return self.grid()

    def _initial_grid(self):
        self.validate_handles()
        grids = []
        for handle in self.children(self.main):
            if self.class_name(handle) != "VSFlexGrid8N" or not self.user.IsWindowVisible(handle):
                continue
            parent = self.user.GetParent(handle)
            while parent and parent != self.main:
                if self.text(parent) == "工具箱":
                    grids.append(handle)
                    break
                parent = self.user.GetParent(parent)
        if len(grids) != 1:
            raise BridgeError("Expected one visible instance initial-value toolbox grid.")
        return grids[0]

    def _initial_rows(self, grid, instance):
        value = self.accessible("instance_initial_read", grid, variable=instance)
        columns = dict(name="变量名", initial_value="初始值", data_type="类型", comment="注释",
                       full_name="全名", device_address="软元件地址", allocated_address="分配地址")
        if (not isinstance(value, dict) or set(value) != {"schema", "scope", "instance", "rows"}
                or value["schema"] != 1 or value["scope"] != "selected_instance_initial_members"
                or value["instance"] != instance or not isinstance(value["rows"], list)
                or not 1 <= len(value["rows"]) <= 4096):
            raise BridgeError("Unsupported instance initial-value snapshot.")
        rows = []
        for row in value["rows"]:
            if (not isinstance(row, dict) or set(row) != set(columns.values())
                    or any(not isinstance(text, str) for text in row.values())):
                raise BridgeError("Unsupported instance initial-value columns.")
            rows.append({key: row[label] for key, label in columns.items()})
        names = [row["full_name"].casefold() for row in rows]
        if (names[0] != instance.casefold() or len(set(names)) != len(names)
                or any(not (name.startswith(instance.casefold() + ".") or name.startswith(instance.casefold() + "[")) for name in names[1:])):
            raise BridgeError("Instance initial-value member identities differ.")
        return rows

    def initial_members(self, instance):
        grid = self._initial_grid()
        if any(self.class_name(h).startswith("ATL:") and self.user.IsWindowVisible(h) for h in self.children(grid)):
            raise BridgeError("An instance member initial-value cell is being edited; finish/cancel it first.")
        self.restore_for_cell_edit()
        self.activate()
        self.assert_no_cell_edit()
        if self.accessible("select_verified_cell", self.variable_grid(), variable=instance,
                           column=self.columns["name"], expected=instance) != "selection_verified":
            raise BridgeError("Initial-value instance selection was not verified.")
        return self._initial_rows(self._initial_grid(), instance)

    def set_initial_member(self, instance, member, expected, value):
        rows = self.initial_members(instance)
        full = instance + "." + member
        matches = [row for row in rows[1:] if row["full_name"].casefold() == full.casefold()]
        if len(matches) != 1 or matches[0]["initial_value"] != expected:
            raise BridgeError("Initial-value member is not displayed or its baseline differs.")
        if matches[0]["initial_value"] == "...":
            raise BridgeError("Composite initial-value cells need a displayed member leaf; full native strings use the offline workflow.")
        grid = self._initial_grid()
        if self.accessible("instance_initial_select", grid, variable=instance, column=member,
                           expected=expected) != "initial_member_selection_verified":
            raise BridgeError("Initial-value member selection was not verified.")
        self.post(grid, 0x100, 113)
        self.post(grid, 0x101, 113)
        def controls():
            return [h for h in self.children(grid) if self.class_name(h).startswith("ATL:") and self.user.IsWindowVisible(h)]
        self.wait_until(lambda: len(controls()) == 1, "instance member initial-value editor")
        control = controls()[0]
        if self.control_text(control) != expected:
            raise BridgeError("Initial-value inline editor baseline differs.")
        if matches[0]["data_type"] == "BOOL":
            count = self.window_message(control, 0x0146)
            if count != 2:
                raise BridgeError("Unsupported BOOL initial-value selector.")
            choices = []
            for index in range(count):
                length = self.window_message(control, 0x0149, index)
                if not 0 <= length <= 32:
                    raise BridgeError("Unsupported BOOL initial-value choice length.")
                text = ctypes.create_unicode_buffer(length + 1)
                self.window_message(control, 0x0148, index, ctypes.addressof(text))
                choices.append(text.value)
            if set(choices) != {"ON", "OFF"} or value not in choices:
                raise BridgeError("BOOL initial-value requires an actual ON/OFF choice.")
            self.window_message(control, 0x014E, choices.index(value))
        else:
            text = ctypes.create_unicode_buffer(value)
            if not self.window_message(control, 0x000C, 0, ctypes.addressof(text)):
                raise BridgeError("Initial-value editor rejected text.")
        if self.control_text(control) != value:
            raise BridgeError("Initial-value inline text readback differs.")
        self.post(control, 0x100, 13)
        self.post(control, 0x101, 13)
        self.wait_until(lambda: not self.user.IsWindowVisible(control), "instance member initial-value commit")
        return self._initial_rows(grid, instance)


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
                selector_preflight="pending_first_default_row" if not before["rows"] else "not_performed",
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

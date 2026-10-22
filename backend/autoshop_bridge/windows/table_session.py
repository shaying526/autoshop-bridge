"""Windows adapter for native structure/global variable table documents."""

import copy
from autoshop_bridge.errors import BridgeError
from autoshop_bridge.windows.editor import EditorState
from autoshop_bridge.windows.session import WindowsSession
from autoshop_bridge.formats.tables import TYPES, UNALLOCATED_ADDRESS, comment_display

STRUCT_COLUMNS = dict(
    row="序号", name="成员变量名", data_type="数据类型", comment="注释", id="ID"
)
GLOBAL_COLUMNS = dict(
    row="序号",
    name="变量名",
    data_type="数据类型",
    comment="注释",
    id="ID",
    initial_raw="隐藏初始值",
    initial_value="初始值",
    retention="掉电保持",
    network="网络公开",
    device_address="软元件地址",
    allocated_address="分配地址",
    bit_length="长度",
    current_value="当前值",
    value1="数据值1",
    value2="数据值2",
    value3="数据值3",
    value4="数据值4",
    full_name="全名称",
)


def normalize_rows(raw, kind):
    columns = STRUCT_COLUMNS if kind == "stru" else GLOBAL_COLUMNS
    rows, names, positions = [], set(), set()
    for record in raw:
        if set(record) != set(columns.values()):
            raise BridgeError("Unsupported native table columns.")
        row = {key: record[label] or "" for key, label in columns.items()}
        if row["row"] == columns["row"]:
            continue
        if not row["row"].isdigit() or row["row"] in positions:
            raise BridgeError("Invalid/duplicate native table row position.")
        positions.add(row["row"])
        if not row["name"]:
            if any(v for k, v in row.items() if k != "row"):
                raise BridgeError("Incomplete native table spare row.")
            continue
        if row["name"].casefold() in names:
            raise BridgeError("Duplicate native table row name.")
        names.add(row["name"].casefold())
        rows.append(row)
    return rows


def assert_native_table(obj, rows):
    if len(obj.rows) != len(rows):
        raise BridgeError("Table editor/native row count differs.")
    for native, ui in zip(obj.rows, rows):
        if (
            native.name != ui["name"]
            or comment_display(native.comment) != ui["comment"]
        ):
            raise BridgeError(
                "Table editor/native name or comment differs: {}.".format(native.name)
            )
        dtype = native.type_text or TYPES.get(native.type_code)
        if native.type_code != 128 and dtype and dtype != ui["data_type"]:
            raise BridgeError(
                "Table editor/native data type differs: {}.".format(native.name)
            )
        if obj.kind == "gvt":
            if (
                native.type_code in (1, 4, 16, 32)
                and native.initial_raw != ui["initial_raw"]
            ):
                raise BridgeError("Table editor/native scalar initial value differs.")
            if native.metadata["device_address_text"] != ui["device_address"]:
                raise BridgeError("Table editor/native device address differs.")
            if (
                native.metadata["address_raw"] == UNALLOCATED_ADDRESS
                and not ui["allocated_address"]
            ):
                continue  # Saved new scalar: address allocation is still pending.
            try:
                address = int(ui["allocated_address"], 16)
            except ValueError as exc:
                raise BridgeError(
                    "Unsupported table allocation address display."
                ) from exc
            if address != native.metadata["address_raw"]:
                raise BridgeError("Table editor/native allocation address differs.")


def add_row(adapter, before, op, kind):
    """Append via the IDE, verify observed defaults and every committed field."""
    actual = adapter.set_cell("#row:" + str(len(before) + 1), "name", "", op["name"])
    if len(actual) != len(before) + 1 or actual[:-1] != before:
        raise BridgeError("New table row altered existing rows.")
    row = actual[-1]
    if not row["id"].isdigit() or row["id"] in {r["id"] for r in before}:
        raise BridgeError("New table row has an invalid/duplicate ID.")
    columns = STRUCT_COLUMNS if kind == "stru" else GLOBAL_COLUMNS
    expected = {key: "" for key in columns}
    expected.update(
        row=str(len(before) + 1), id=row["id"], name=op["name"], data_type="BOOL"
    )
    if kind == "gvt":
        expected.update(
            initial_raw="OFF",
            initial_value="OFF",
            retention="不保持",
            network="私有",
            bit_length="nBitLen:1",
            full_name=op["name"],
        )
    if row != expected:
        raise BridgeError("Unsupported new table row defaults.")
    desired = copy.deepcopy(actual)

    def commit(field, old, value):
        updated = adapter.set_cell(op["name"], field, old, value)
        if updated != desired:
            raise BridgeError(
                "New table row full readback differs after {}.".format(field)
            )

    if op["data_type"] != "BOOL":
        desired[-1]["data_type"] = op["data_type"]
        if kind == "gvt":
            bits = 32 if op["data_type"] == "DINT" else 16
            desired[-1].update(
                initial_raw="0", initial_value="0", bit_length="nBitLen:" + str(bits)
            )
        commit("data_type", "BOOL", op["data_type"])
    if kind == "gvt" and op["initial_value"] != desired[-1]["initial_value"]:
        old = desired[-1]["initial_value"]
        desired[-1].update(
            initial_raw=op["initial_value"], initial_value=op["initial_value"]
        )
        commit("initial_value", old, op["initial_value"])
    if op["comment"]:
        desired[-1]["comment"] = comment_display(op["comment"])
        commit("comment", "", desired[-1]["comment"])
    return desired


class WindowsTableSession(WindowsSession):
    def __init__(self, project, program, kind, pid=None):
        if kind not in ("stru", "gvt"):
            raise BridgeError("Unsupported table document kind.")
        self.kind = kind
        self.columns = STRUCT_COLUMNS if kind == "stru" else GLOBAL_COLUMNS
        super().__init__(project, program, pid)

    def locate_editor(self, required=True):
        found = []
        for child in self.children(self.main):
            if (
                not self.program_title_matches(self.text(child))
                or self.class_name(self.user.GetParent(child)) != "MDIClient"
            ):
                continue
            grids = [
                h
                for h in self.children(child)
                if self.class_name(h) == "VSFlexGrid8N" and self.user.IsWindowVisible(h)
            ]
            for grid in grids:
                found.append((child, grid))
        if len(found) > 1 or (required and not found):
            raise BridgeError(
                "Expected one table document/grid; found {}.".format(len(found))
            )
        if found:
            self.program_window, self.hwnd = found[0]
        return bool(found)

    def validate_handles(self):
        self.validate_main()
        if (
            self.window_pid(self.hwnd) != self.pid
            or not self.program_title_matches(self.text(self.program_window))
            or self.class_name(self.hwnd) != "VSFlexGrid8N"
            or not self.user.IsChild(self.program_window, self.hwnd)
            or not self.user.IsWindowVisible(self.hwnd)
        ):
            raise BridgeError("Target table document/grid changed.")

    def variable_grid(self):
        self.validate_handles()
        return self.hwnd

    def read(self):
        self.validate_handles()
        return EditorState(
            source=b"",
            modified=self.text(self.program_window).endswith("*"),
            hwnd=self.hwnd,
            pid=self.pid,
            title=self.text(self.main),
        )

    def raw_grid(self):
        self.assert_no_cell_edit()
        return self.accessible("grid", self.variable_grid())

    def grid(self):
        return normalize_rows(self.raw_grid(), self.kind)

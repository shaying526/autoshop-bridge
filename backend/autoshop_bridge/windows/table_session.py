"""Windows adapter for native structure/global variable table documents."""

import copy
import re
from autoshop_bridge.errors import BridgeError
from autoshop_bridge.windows.editor import EditorState
from autoshop_bridge.windows.session import WindowsSession
from autoshop_bridge.formats.tables import TYPES, UNALLOCATED_ADDRESS, comment_display
from autoshop_bridge.formats.scalar_types import descriptor, STRING_DEFAULT_LENGTH

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
        string_descriptor=descriptor(native.type_text) if native.type_code==2048 else None
        string_display=(string_descriptor is not None and string_descriptor.string_length==STRING_DEFAULT_LENGTH
                        and native.type_text==string_descriptor.canonical
                        and ui['data_type']=='STRING')
        if native.type_code != 128 and dtype and dtype != ui["data_type"] and not string_display:
            raise BridgeError(
                "Table editor/native data type differs: {}.".format(native.name)
            )
        if obj.kind == "gvt":
            if (
                native.type_code in (1, 4, 16, 32, 2048)
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


def add_row(adapter, before, op, kind, complex_type=False, preflight_types=()):
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
    choices = None
    if preflight_types:
        choices = adapter.selector_choices(op["name"], "data_type", "BOOL")
        if any(choices.count(name) != 1 for name in preflight_types):
            raise BridgeError("Requested project structure is unavailable or ambiguous after the first default row; inspect unsaved buffer.")
        if adapter.grid() != desired or not adapter.dirty():
            raise BridgeError("Deferred type-selector preflight changed the first-row buffer.")

    def commit(field, old, value):
        updated = adapter.set_cell(op["name"], field, old, value)
        if updated != desired:
            raise BridgeError(
                "New table row full readback differs after {}.".format(field)
            )

    if op["data_type"] != "BOOL":
        scalar=descriptor(op['data_type'])
        if scalar is not None and scalar.code==2048:
            updated=adapter.set_cell(op['name'],'data_type','BOOL',op['data_type'])
            if len(updated)!=len(desired) or updated[:-1]!=desired[:-1]:
                raise BridgeError('STRING type change altered existing table rows.')
            allowed_types=(scalar.canonical,'STRING') if scalar.string_length==STRING_DEFAULT_LENGTH else (scalar.canonical,)
            if updated[-1]['data_type'] not in allowed_types:
                raise BridgeError('STRING type change returned an unexpected display capacity.')
            desired[-1]['data_type']=updated[-1]['data_type']
            if kind=='gvt':
                # The normal STRING<20> save has empty hidden/display defaults
                # and 160 bits. No structure preview or scalar integer default.
                desired[-1].update(initial_raw='',initial_value='',
                                   bit_length='nBitLen:'+str(scalar.string_length*8))
            if updated!=desired:
                raise BridgeError('STRING type change altered unrelated new-row fields or defaults.')
        elif complex_type:
            if kind != "gvt" or op.get("initial_value", "missing") is not None:
                raise BridgeError("Complex GVT additions require null IDE initialization.")
            if choices is None:
                choices = adapter.selector_choices(op["name"], "data_type", "BOOL")
            if choices.count(op["data_type"]) != 1 or adapter.grid() != desired:
                raise BridgeError("Complex table type selector differs from the preflight.")
            updated = adapter.set_cell(op["name"], "data_type", "BOOL", op["data_type"])
            if len(updated) != len(desired) or updated[:-1] != desired[:-1]:
                raise BridgeError("Complex type change altered existing table rows.")
            # These are IDE-produced opaque display fields, not inferred native
            # initializer syntax or a guessed structure layout/bit length.
            allowed = {"data_type", "initial_value", "initial_raw", "bit_length"}
            expected_row = copy.deepcopy(desired[-1])
            for field in allowed:
                expected_row[field] = updated[-1][field]
            if updated[-1] != expected_row or updated[-1]["data_type"] != op["data_type"]:
                raise BridgeError("Complex type change altered unrelated new-row fields.")
            desired = updated
        else:
            desired[-1]["data_type"] = op["data_type"]
            if kind == "gvt":
                bits = 32 if op["data_type"] in ("DINT", "REAL") else 16
                desired[-1].update(
                    initial_raw="0", initial_value="0", bit_length="nBitLen:" + str(bits)
                )
            if kind == "gvt" and op["data_type"] == "REAL":
                updated = adapter.set_cell(op["name"], "data_type", "BOOL", "REAL")
                if len(updated) != len(desired) or updated[:-1] != desired[:-1]:
                    raise BridgeError("REAL type change altered existing table rows.")
                # Native REAL archives differ between FB and GVT and the IDE
                # owns its new-row default spelling. Freeze the actual default
                # while retaining every unrelated field and the known 32 bits.
                if updated[-1]["initial_value"] != updated[-1]["initial_raw"]:
                    raise BridgeError("REAL hidden/display initializer differs.")
                desired[-1].update(initial_raw=updated[-1]["initial_raw"],
                                   initial_value=updated[-1]["initial_value"])
                if updated != desired:
                    raise BridgeError("REAL type change altered unrelated new-row fields.")
            else:
                commit("data_type", "BOOL", op["data_type"])
    if kind == "gvt" and not complex_type and op["initial_value"] != desired[-1]["initial_value"]:
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
        super().__init__(project, program, pid)
        # WindowsSession initializes FB column labels. Restore the actual
        # table labels after it, before any name/first-row cell operation.
        self.columns = STRUCT_COLUMNS if kind == "stru" else GLOBAL_COLUMNS

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

    def prepare_edit_rows(self, rows=None):
        """Materialize sparse old GVT metadata from the actual visible grid.

        Selecting an existing name may paint a previously unvisited declaration
        root. Only empty id/bit-length fields may become known; nothing is filled
        from native bytes or inferred from a type. No F2, value edit or save.
        """
        current=copy.deepcopy(self.grid() if rows is None else rows)
        record=dict(status='not_required',source='actual_name_cell_and_complete_grid',
                    native_values_used=False,targeted_names=[],materialized_fields=[])
        self.last_edit_row_preparation=record
        if self.kind!='gvt' or not current:return current
        missing=[row['name'] for row in current if row['id']=='' or row['bit_length']=='']
        if not missing:return current
        if self.dirty():raise BridgeError('Cannot prepare existing table metadata with unsaved changes.')
        record['status']='preparing'
        self.restore_for_cell_edit()
        self.activate()
        for name in missing:
            previous=next(row for row in current if row['name']==name)
            if previous['id']!='' and previous['bit_length']!='':continue
            self.assert_no_cell_edit()
            selected=self.accessible('select_verified_cell',self.variable_grid(),
                                     variable=name,column=GLOBAL_COLUMNS['name'],expected=name)
            if selected!='selection_verified':
                raise BridgeError('Existing declaration name was not verified during metadata preparation.')
            record['targeted_names'].append(name)
            observed=self.grid()
            if self.dirty():raise BridgeError('Metadata preparation changed table dirty state.')
            if len(observed)!=len(current):raise BridgeError('Declaration count changed during metadata preparation.')
            for before,after in zip(current,observed):
                if set(before)!=set(after):raise BridgeError('Declaration columns changed during metadata preparation.')
                for field,value in before.items():
                    actual=after[field]
                    if field in ('id','bit_length') and value=='' and actual!='':
                        valid=(isinstance(actual,str) and (
                            re.fullmatch(r'[1-9][0-9]*',actual) if field=='id'
                            else re.fullmatch(r'nBitLen:[1-9][0-9]*',actual)))
                        if not valid:raise BridgeError('Unsupported actual declaration metadata during preparation: '+field)
                        record['materialized_fields'].append(dict(name=before['name'],field=field,before=value,after=actual))
                    elif actual!=value:
                        raise BridgeError('Existing declaration changed during metadata preparation: '+before['name']+'.'+field)
            current=copy.deepcopy(observed)
            target=next(row for row in current if row['name']==name)
            if target['id']=='' or target['bit_length']=='':
                raise BridgeError('Could not materialize complete existing declaration metadata from the GUI before writing: '+name)
        if any(row['id']=='' or row['bit_length']=='' for row in current):
            raise BridgeError('Existing declaration metadata is still incomplete before writing.')
        if len({row['id'] for row in current})!=len(current):
            raise BridgeError('Duplicate declaration IDs after actual metadata preparation.')
        record['status']='prepared_from_actual_grid'
        return current

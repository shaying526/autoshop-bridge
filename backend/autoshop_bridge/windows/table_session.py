"""Windows adapter for native structure/global variable table documents."""

import copy
import json
import re
import stat
from pathlib import Path
from autoshop_bridge.errors import BridgeError, FormatRejection
from autoshop_bridge.windows.editor import EditorState
from autoshop_bridge.windows.session import WindowsSession
from autoshop_bridge.formats.tables import TYPES, UNALLOCATED_ADDRESS, comment_display, structure_comment_display
from autoshop_bridge.formats.scalar_types import descriptor, STRING_DEFAULT_LENGTH
from autoshop_bridge.formats.array_types import descriptor as array_descriptor
from autoshop_bridge.projects.types import array_ui_type_matches

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

_GVT_PHYSICAL_COLUMNS = (
    "序号", "变量名", "数据类型", "隐藏初始值", "初始值", "掉电保持", "网络公开", "注释",
    "软元件地址", "分配地址", "长度", "ID", "当前值", "数据值1", "数据值2", "数据值3", "数据值4", "全名称",
)
_GVT_REQUIRED_ROOT_FIELDS = (0, 1, 2, 5, 6, 10, 11)
_GVT_MISSING_ROOT_MARKER = "HYBRID_ROOT_FIELDS_MISSING:"
_GVT_FRAME_REQUIRED_MARKER = "HYBRID_FRAME_REQUIRED:"


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


def assert_native_table(obj, rows, *, strict_array_names=()):
    strict_arrays=set(strict_array_names);verified_arrays=[];unverified_arrays=[]
    display_comment = structure_comment_display if obj.kind == 'stru' else comment_display
    if len(obj.rows) != len(rows):
        raise BridgeError("Table editor/native row count differs.")
    for native, ui in zip(obj.rows, rows):
        if (
            native.name != ui["name"]
            or display_comment(native.comment) != ui["comment"]
        ):
            raise BridgeError(
                "Table editor/native name or comment differs: {}.".format(native.name)
            )
        dtype = native.type_text or TYPES.get(native.type_code)
        if native.type_code==128:
            try:
                if obj.kind=='gvt':
                    from autoshop_bridge.formats.array_types import from_gvt_row
                    native_array=from_gvt_row(native)
                else:
                    native_array=array_descriptor(native.type_text)
                if native_array is None:
                    raise FormatRejection('ARRAY native type text profile is not interpreted.',
                        code='array_type_profile_unobserved',context=dict(stage='array_type_descriptor',
                            field='type_text_raw',value=native.type_text,reason='native_array_text_unobserved'))
            except FormatRejection as exc:
                if (native.name in strict_arrays or exc.code!='array_type_profile_unobserved'
                        or exc.context.get('stage')!='array_type_descriptor'):
                    exc.context.setdefault('name',native.name)
                    raise
                # Existing native records remain byte protected by the editor
                # workflow, and their real complete UI rows stay frozen. An
                # unrelated unresolved ARRAY layout is no new write profile.
                fields=list(dict.fromkeys(['data_type',exc.context.get('field','native_descriptor')]))
                unverified_arrays.append(dict(name=native.name,fields=fields,
                    error_code=exc.code,error_context=exc.context))
            else:
                if ((obj.kind!='gvt' and native_array.canonical!=native.type_text)
                        or not array_ui_type_matches(native_array,ui['data_type'])):
                    raise BridgeError('Table editor/native ARRAY element type or dimensions differ: '+native.name)
                verified_arrays.append(native.name)
            if (obj.kind=='gvt' and native.name in strict_arrays
                    and descriptor(native_array.element_type) is not None and native.initial_raw!=''):
                raise BridgeError('New ARRAY native initializer differs from the observed empty default: '+native.name)
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
                native.type_code in (1, 4, 16, 32, 2048, 4096, 8192)
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
    if verified_arrays or unverified_arrays:
        return dict(status='partial' if unverified_arrays else 'verified',
                    comparison_scope='ARRAY native element/dimensions/capacity versus actual displayed data_type; hidden initializer and preview are independent observations, not asserted equal here',
                    verified_names=verified_arrays,unverified_native_fields=unverified_arrays)


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
        array=array_descriptor(op['data_type'])
        if array is not None:
            if kind=='gvt' and op.get('initial_value','missing') is not None:
                raise BridgeError('ARRAY additions require null IDE initialization.')
            if choices is None:choices=adapter.selector_choices(op['name'],'data_type','BOOL')
            if choices.count('ARRAY')!=1 or adapter.grid()!=desired:
                raise BridgeError('ARRAY selector differs from the verified default row.')
            updated=adapter.set_cell(op['name'],'data_type','BOOL',op['data_type'])
            if len(updated)!=len(desired) or updated[:-1]!=desired[:-1]:
                raise BridgeError('ARRAY type change altered existing table rows.')
            if not array_ui_type_matches(array,updated[-1]['data_type']):
                raise BridgeError('ARRAY type selection returned a different capacity, element type or dimensions.')
            expected_row=copy.deepcopy(desired[-1]);expected_row['data_type']=updated[-1]['data_type']
            if kind=='gvt':
                for field in ('initial_raw','initial_value','bit_length'):expected_row[field]=updated[-1][field]
            if updated[-1]!=expected_row:
                raise BridgeError('ARRAY type change altered element/dimensions or unrelated new-row fields.')
            desired=updated
        elif scalar is not None and scalar.code==2048:
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
        elif kind=='gvt' and scalar is not None and scalar.code in (4096,8192):
            # Independent V4.11.0.5 GVT saves: BYTE is eight bits and IP is
            # thirty-two bits; both expose their complete literal defaults.
            bits,initial=(8,'0') if scalar.code==8192 else (32,'192.168.1.0')
            desired[-1].update(data_type=op['data_type'],initial_raw=initial,
                               initial_value=initial,bit_length='nBitLen:'+str(bits))
            updated=adapter.set_cell(op['name'],'data_type','BOOL',op['data_type'])
            if updated!=desired:
                raise BridgeError('BYTE/IP type change altered defaults, bit length or unrelated GVT fields.')
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
    if kind == "gvt" and not complex_type and array_descriptor(op['data_type']) is None and op["initial_value"] != desired[-1]["initial_value"]:
        old = desired[-1]["initial_value"]
        desired[-1].update(
            initial_raw=op["initial_value"], initial_value=op["initial_value"]
        )
        commit("initial_value", old, op["initial_value"])
    if op["comment"]:
        desired[-1]["comment"] = (structure_comment_display if kind == 'stru' else comment_display)(op["comment"])
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
        if self.kind == "gvt":
            self._gvt_verified_frame = None
        try:
            return self.accessible("grid", self.variable_grid())
        except BridgeError as exc:
            if (self.kind != "gvt" or not any(marker in str(exc) for marker in (
                    _GVT_MISSING_ROOT_MARKER, _GVT_FRAME_REQUIRED_MARKER))
                    or getattr(self, "_gvt_root_preparing", False)):
                raise
            raw, inventory, context = self._read_gvt_frame_pair()
            if raw is not None:
                return raw
            return self._prepare_gvt_read_roots(inventory, context)

    @staticmethod
    def _gvt_hybrid_frame(value):
        """Validate one explicitly unverified real MSAA frame, not native data."""
        if (not isinstance(value, dict) or value.get("schema") != 1
                or value.get("profile") != "autoshop-gvt-hybrid-frame-v1"
                or value.get("stable_two_pass") is not False or value.get("atomic_snapshot") is not False
                or value.get("native_values_used") is not False
                or type(value.get("elapsed_ms")) is not int or value["elapsed_ms"] < 0
                or not isinstance(value.get("frame"), dict)):
            raise BridgeError("Unsupported/unqualified GVT hybrid frame.")
        frame = value["frame"]
        if (set(frame) != {"physical_rows", "accessible_children", "columns", "observed_cells", "row_shapes", "inventory", "grid"}
                or type(frame["physical_rows"]) is not int or type(frame["accessible_children"]) is not int
                or not 2 <= frame["physical_rows"] <= frame["accessible_children"] <= 10000
                or frame["columns"] != list(_GVT_PHYSICAL_COLUMNS)
                or not isinstance(frame["observed_cells"], list) or not isinstance(frame["row_shapes"], list)):
            raise BridgeError("GVT hybrid frame count/columns/shape differs.")
        shapes = frame["row_shapes"]
        if shapes != [[row, 28, 18] for row in range(frame["physical_rows"])]:
            raise BridgeError("GVT hybrid frame lacks complete physical row roles/shapes.")
        cells, previous = {}, (-1, -1)
        for cell in frame["observed_cells"]:
            if (not isinstance(cell, list) or len(cell) != 5
                    or type(cell[0]) is not int or not 0 <= cell[0] < frame["physical_rows"]
                    or type(cell[1]) is not int or not 0 <= cell[1] < 18
                    or type(cell[2]) is not int or cell[2] != 29
                    or cell[3] != _GVT_PHYSICAL_COLUMNS[cell[1]] or not isinstance(cell[4], str)
                    or (cell[0], cell[1]) <= previous):
                raise BridgeError("GVT hybrid frame cell identity/order differs.")
            previous = (cell[0], cell[1]); cells[previous] = cell[4]
        if (any((row, 17) not in cells for row in range(frame["physical_rows"]))
                or any(cells.get((0, column)) != label for column, label in enumerate(_GVT_PHYSICAL_COLUMNS))
                or any((frame["physical_rows"] - 1, column) not in cells for column in range(18))):
            raise BridgeError("GVT hybrid frame is missing full-name/header/spare observations.")
        inventory = frame["inventory"]
        if (not isinstance(inventory, dict) or inventory.get("stable_two_pass") is not False
                or inventory.get("physical_rows") != frame["physical_rows"]
                or inventory.get("accessible_children") != frame["accessible_children"]):
            raise BridgeError("GVT hybrid frame inventory qualification differs.")
        inventory = WindowsTableSession._gvt_root_inventory(inventory, expected_stability=False)
        preorder, current = [], None
        for row in range(1, frame["physical_rows"] - 1):
            full = cells[(row, 17)]
            if current is not None and (full.startswith(current + "[") or full.startswith(current + ".")):
                continue
            if not full or any(mark in full for mark in (".", "[", "]", "\r", "\n", "\0")):
                raise BridgeError("GVT hybrid frame full-name branch preorder is incomplete.")
            preorder.append((row, full)); current = full
        if preorder != [(root["physical_row"], root["full_name"]) for root in inventory["roots"]]:
            raise BridgeError("GVT hybrid frame root mapping differs from complete full-name preorder.")
        spare = frame["physical_rows"] - 1
        if cells[(spare, 0)] not in ("", str(spare)) or any(cells[(spare, column)] for column in range(1, 18)):
            raise BridgeError("GVT hybrid frame final spare row is not completely blank.")
        for root in inventory["roots"]:
            if (any(cells.get((root["physical_row"], column)) != content for column, content in enumerate(root["row"]))
                    or cells.get((root["physical_row"] - 1, 17)) != root["before_full_name"]
                    or cells.get((root["physical_row"] + 1, 17)) != root["after_full_name"]):
                raise BridgeError("GVT hybrid frame root row differs from its actual cells.")
        grid = frame["grid"]
        if grid is not None:
            if (not isinstance(grid, dict) or not isinstance(grid.get("metadata"), dict)
                    or grid["metadata"].get("stable_two_pass") is not False
                    or grid["metadata"].get("atomic_snapshot") is not False
                    or any(root["missing_fields"] for root in inventory["roots"])):
                raise BridgeError("GVT hybrid frame contains an unqualified complete grid.")
        elif not any(root["missing_fields"] for root in inventory["roots"]):
            raise BridgeError("GVT hybrid frame omits its complete mapped grid.")
        return copy.deepcopy(frame)

    def _read_gvt_frame_pair(self, context=None):
        """Two bounded complete real frames, stable across the guarded calls."""
        from autoshop_bridge.storage import sha256
        from autoshop_bridge.windows.grid_protocol import unpack_grid

        self.validate_handles(); self.assert_no_cell_edit()
        self._gvt_verified_frame = None
        if context is None:
            dirty = self.dirty()
            context = dict(handles=(self.main, self.pid, self.program_window, self.hwnd),
                           identity=self._gvt_prepare_process_identity(), baseline=self._gvt_prepare_source_baseline(),
                           dirty=dirty)
        identity, baseline, handles = context["identity"], context["baseline"], context["handles"]
        record = dict(status="observing", source="two_complete_actual_hybrid_frames", stable_two_pass=False,
                      atomic_snapshot=False, native_values_used=False, expected_dirty=context["dirty"], completed_frames=0,
                      process_identity=copy.deepcopy(identity), native_source_baseline=copy.deepcopy(baseline["states"]))
        self.last_read_frame_verification = record
        frames, elapsed = [], 0
        try:
            for _ in range(2):
                self._gvt_prepare_guard(identity, baseline, handles, context["dirty"])
                value = self.accessible("grid_hybrid_frame", self.variable_grid())
                self._gvt_prepare_guard(identity, baseline, handles, context["dirty"])
                frames.append(self._gvt_hybrid_frame(value)); elapsed += value["elapsed_ms"]
                record["completed_frames"] += 1
            if frames[0] != frames[1]:
                raise BridgeError("Complete GVT hybrid observations changed between the two bounded frames.")
            frame = frames[1]
            inventory = copy.deepcopy(frame["inventory"]); inventory["stable_two_pass"] = True
            inventory = self._gvt_root_inventory(inventory)
            record.update(status="verified", stable_two_pass=True, elapsed_ms=elapsed,
                          observed_cells=len(frame["observed_cells"]), physical_rows=frame["physical_rows"],
                          process_identity=identity, protected_source_files=len(baseline["states"]),
                          frame_sha256=sha256(json.dumps(frame, ensure_ascii=True, sort_keys=True,
                                                       separators=(",", ":")).encode("ascii")))
            if frame["grid"] is None:
                return None, inventory, context
            grid = copy.deepcopy(frame["grid"])
            grid["metadata"].update(elapsed_ms=elapsed, stable_two_pass=True, atomic_snapshot=False,
                                    verification_scope="two_complete_frames_with_process_source_and_dirty_guards")
            rows, metadata = unpack_grid(grid)
            if (metadata["physical_rows"] != inventory["physical_rows"]
                    or metadata["accessible_children"] != inventory["accessible_children"]
                    or [row.get("变量名") for row in rows] != [root["full_name"] for root in inventory["roots"]]):
                raise BridgeError("Complete GVT grid does not match the stable root inventory.")
            self._gvt_validate_reader_roots(rows, inventory["roots"], record)
            self.last_grid_read = metadata
            # A complete read supplies a one-use checkpoint for the next
            # bounded cell selection. Every dispatch still checks live values.
            self._gvt_verified_frame = dict(frame=copy.deepcopy(frame), context=copy.deepcopy(context),
                                            frame_sha256=record["frame_sha256"])
            return rows, inventory, context
        except BaseException as exc:
            record.update(status="stopped", error=str(exc), stable_two_pass=False)
            raise

    @staticmethod
    def _gvt_cell_checkpoint(frame, variable, field, expected):
        """Map only an authenticated frame's actual source/display cell rows."""
        if not isinstance(variable, str) or not isinstance(expected, str) or field not in GLOBAL_COLUMNS:
            raise BridgeError("GVT cell checkpoint requires an explicit variable/field/string baseline.")
        column = _GVT_PHYSICAL_COLUMNS.index(GLOBAL_COLUMNS[field])
        roots = frame["inventory"]["roots"]
        cells = {(cell[0], cell[1]): cell[4] for cell in frame["observed_cells"]}
        spare = variable.startswith("#row:")
        if spare:
            if variable != "#row:" + str(len(roots) + 1) or field != "name":
                raise BridgeError("GVT spare selection requires the exact next declaration name cell.")
            source = display = frame["physical_rows"] - 1
        else:
            matches = [index for index, root in enumerate(roots) if root["full_name"] == variable]
            if len(matches) != 1:
                raise BridgeError("GVT checkpoint has no unique exact declaration root.")
            index = matches[0]
            metadata = frame["grid"]["metadata"]
            physical = metadata.get("physical_root_rows")
            hidden = metadata.get("hidden_initializer_rows")
            if (physical != [root["physical_row"] for root in roots]
                    or not isinstance(hidden, list) or len(hidden) != len(roots)
                    or any(type(row) is not int or not 1 <= row < frame["physical_rows"] - 1 for row in hidden)):
                raise BridgeError("GVT cell source/display mapping differs from the authenticated root inventory.")
            display = roots[index]["physical_row"]
            source = hidden[index] if column == 3 else display
        try:
            source_values = [cells[(source, index)] for index in range(18)]
            display_values = [cells[(display, index)] for index in range(18)]
            before = cells[(display - 1, 17)]
            after = cells[(display + 1, 17)] if display + 1 < frame["physical_rows"] else ""
        except KeyError as exc:
            raise BridgeError("GVT checkpoint lacks a complete actual source/display row.") from exc
        if source_values[column] != expected:
            raise BridgeError("GVT checkpoint selected field differs from its requested original value.")
        if spare:
            if source_values[0] not in ("", str(source)) or any(source_values[1:]):
                raise BridgeError("GVT spare checkpoint is not the complete actual blank boundary.")
        else:
            if display_values[17] != variable or display_values[1] != variable:
                raise BridgeError("GVT display checkpoint differs from the exact declaration root.")
            if source != display and (column != 3 or any(source_values[i] != display_values[i] for i in (1, 2, 5, 6, 7))
                                      or source_values[11] and source_values[11] != display_values[11]):
                raise BridgeError("GVT hidden initializer source is not an authenticated same-name declaration row.")
        return dict(physical_rows=frame["physical_rows"], source_row=source, display_row=display,
                    column_index=column, expected_source_row=source_values, expected_display_row=display_values,
                    before_full_name=before, after_full_name=after, variable=variable, expected=expected, spare=spare)

    def select_cell_for_edit(self, grid, variable, field, expected):
        """Select one GVT cell from a one-use complete UI frame checkpoint."""
        if self.kind != "gvt":
            return super().select_cell_for_edit(grid, variable, field, expected)
        cached = getattr(self, "_gvt_verified_frame", None)
        if cached is None:
            self.raw_grid()  # A simple layout retains its original selector.
            cached = getattr(self, "_gvt_verified_frame", None)
            if cached is None:
                return super().select_cell_for_edit(grid, variable, field, expected)
        self._gvt_verified_frame = None  # Never replay a failed/pending selection.
        context = cached["context"]
        identity, baseline, handles = context["identity"], context["baseline"], context["handles"]
        record = dict(status="selecting", source="actual_complete_frame_cell_checkpoint",
                      native_values_used=False, frame_sha256=cached["frame_sha256"],
                      expected_dirty=context["dirty"], checkpoint_consumed_once=True, steps=[])
        self.last_cell_checkpoint_selection = record
        try:
            self._gvt_prepare_guard(identity, baseline, handles, context["dirty"])
            if grid != self.hwnd:
                raise BridgeError("GVT selection grid differs from its authenticated handle.")
            checkpoint = self._gvt_cell_checkpoint(cached["frame"], variable, field, expected)
            record["checkpoint"] = copy.deepcopy(checkpoint)
            step, clicked, reveals = "observe", False, 0
            while True:
                self._gvt_prepare_guard(identity, baseline, handles, context["dirty"])
                receipt = self.accessible("grid_cell_step", self.variable_grid(), step=step, **checkpoint)
                record["steps"].append(copy.deepcopy(receipt))
                self._gvt_prepare_guard(identity, baseline, handles, context["dirty"])
                if (not isinstance(receipt, dict) or receipt.get("status") != "grid_cell_checkpoint_step"
                        or receipt.get("step") != step or receipt.get("stop") is not False
                        or receipt.get("post_guard_error") is not None or receipt.get("native_values_used") is not False
                        or receipt.get("global_preorder_verified") is not False
                        or any(receipt.get(key) != checkpoint[key] for key in (
                            "physical_rows", "source_row", "display_row", "column_index", "variable", "expected", "spare"))
                        or receipt.get("source_values") != checkpoint["expected_source_row"]
                        or receipt.get("display_values") != checkpoint["expected_display_row"]):
                    raise BridgeError("GVT cell checkpoint actual row/identity/guard receipt differs.")
                scroll, click = receipt.get("scroll_dispatched_once"), receipt.get("selection_dispatched_once")
                phase = ("scroll_dispatched" if scroll else "visible_observed") if step == "reveal_one" else (
                    ("selection_dispatched" if click else "already_selected_observed") if step == "select_once" else "observed")
                if (type(scroll) is not bool or type(click) is not bool or scroll and click
                        or type(receipt.get("visible_observed")) is not bool
                        or type(receipt.get("selection_verified")) is not bool
                        or receipt.get("needs_observe") is not (scroll or click)
                        or receipt.get("phase") != phase or scroll and step != "reveal_one"
                        or click and step != "select_once"):
                    raise BridgeError("GVT cell selection dispatch receipt differs.")
                if scroll or click:
                    step = "observe"  # Dispatch never permits immediate F2.
                    continue
                if receipt["selection_verified"]:
                    if not receipt["visible_observed"]:
                        raise BridgeError("GVT selected cell has no verified visible geometry.")
                    record.update(status="selection_verified", selected_from_actual_checkpoint=True)
                    return None  # Existing begin_cell owns F2 and inline-text validation.
                if clicked:
                    raise BridgeError("GVT cell selection is still pending after one click; do not repeat.")
                if receipt["visible_observed"]:
                    step, clicked = "select_once", True
                else:
                    reveals += 1
                    if reveals > checkpoint["physical_rows"] + len(_GVT_PHYSICAL_COLUMNS):
                        raise BridgeError("Bounded GVT checkpoint reveal did not expose its actual cell.")
                    step = "reveal_one"
        except BaseException as exc:
            record.update(status="stopped", error=str(exc), selected_from_actual_checkpoint=False)
            raise

    def _gvt_prepare_process_identity(self):
        """Reuse the existing read-only process/start/liveness observation."""
        import ctypes
        from types import SimpleNamespace
        from autoshop_bridge.windows.project_lifecycle import WindowsProjectDriver

        self.kernel.GetProcessTimes.argtypes = [self.types.HANDLE] + [ctypes.POINTER(self.types.FILETIME)] * 4
        self.kernel.WaitForSingleObject.argtypes = [self.types.HANDLE, self.types.DWORD]
        self.kernel.WaitForSingleObject.restype = self.types.DWORD
        self.kernel.GetExitCodeProcess.argtypes = [self.types.HANDLE, ctypes.POINTER(self.types.DWORD)]
        self.kernel.GetExitCodeProcess.restype = self.types.BOOL
        return WindowsProjectDriver._identity(SimpleNamespace(a=self, c=ctypes, w=self.types))

    def _gvt_prepare_source_baseline(self):
        from autoshop_bridge.projects.inventory import scan, member_path
        from autoshop_bridge.projects.registration_evidence import SOURCE_SUFFIXES

        inventory = scan(Path(self.project))  # Retains any active registration scope/provider.
        directory = Path(inventory["project"])
        matches = [row for row in inventory["files"] if row.get("kind") == "global_variables"
                   and (row.get("name") == self.program or Path(row.get("file", "")).stem == self.program)]
        if len(matches) != 1:
            raise BridgeError("Root preparation requires one exact registered GVT target.")
        target = directory.joinpath(*member_path(matches[0]["file"]))
        registered = [directory.joinpath(*member_path(row["file"])) for row in inventory["files"]
                      if row.get("file") and Path(row["file"]).suffix.lower() in SOURCE_SUFFIXES]
        baseline = dict(directory=directory, registered=registered, target=target)
        baseline["states"] = self._gvt_prepare_source_states(baseline)
        key = target.relative_to(directory).as_posix()
        if baseline["states"].get(key, {}).get("state") != "readable":
            raise BridgeError("Root preparation requires a readable target native baseline.")
        return baseline

    def _gvt_prepare_source_states(self, baseline):
        from autoshop_bridge.projects.inventory import bounded_read
        from autoshop_bridge.projects.registration_evidence import SOURCE_SUFFIXES
        from autoshop_bridge.storage import sha256

        directory = baseline["directory"]
        paths = set(baseline["registered"])
        paths.update(path for path in directory.iterdir() if path.suffix.lower() in SOURCE_SUFFIXES)
        result = {}
        for path in sorted(paths):
            key = path.relative_to(directory).as_posix()
            # Check original components before resolve can hide a junction.
            for component in (path, *path.parents):
                if component == directory.parent:
                    break
                if not component.exists() and not component.is_symlink():
                    continue
                info = component.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                    raise BridgeError("Root preparation source traverses a reparse point.")
            if directory.resolve() not in path.resolve().parents:
                raise BridgeError("Root preparation source resolves outside the project.")
            if not path.exists():
                result[key] = dict(state="missing")
                continue
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise BridgeError("Root preparation source is not a unique regular file.")
            try:
                raw = bounded_read(path)
            except OSError:
                # Unrelated locked inputs are not parsed or newly qualified.
                result[key] = dict(state="unreadable", size=info.st_size, mtime_ns=info.st_mtime_ns)
            else:
                after = path.stat()
                if (info.st_size, info.st_mtime_ns, info.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                    raise BridgeError("Root preparation source changed while reading.")
                result[key] = dict(state="readable", sha256=sha256(raw))
        return result

    def _gvt_prepare_guard(self, identity, baseline, handles, expected_dirty=False):
        self.validate_handles()
        self.assert_no_cell_edit()
        if (self.main, self.pid, self.program_window, self.hwnd) != handles:
            raise BridgeError("Root preparation target handles changed.")
        if self.dirty() is not expected_dirty:
            raise BridgeError("GVT observation/preparation dirty state changed.")
        if self._gvt_prepare_process_identity() != identity:
            raise BridgeError("Root preparation process/start identity changed.")
        if self._gvt_prepare_source_states(baseline) != baseline["states"]:
            raise BridgeError("Root preparation native/source baseline changed.")

    @staticmethod
    def _gvt_root_inventory(value, expected_stability=True):
        if (not isinstance(value, dict) or value.get("schema") != 1
                or value.get("profile") != "autoshop-gvt-root-inventory-v1"
                or value.get("columns") != list(_GVT_PHYSICAL_COLUMNS)
                or value.get("root_preorder_complete") is not True
                or value.get("stable_two_pass") is not expected_stability or value.get("native_values_used") is not False
                or type(value.get("physical_rows")) is not int
                or type(value.get("accessible_children")) is not int
                or not 2 <= value["physical_rows"] <= value["accessible_children"] <= 10000
                or not isinstance(value.get("roots"), list) or len(value["roots"]) > 4096):
            raise BridgeError("Unsupported/incomplete GVT root inventory.")
        names, positions, ids = set(), set(), set()
        for root in value["roots"]:
            if (not isinstance(root, dict) or type(root.get("physical_row")) is not int
                    or not 1 <= root["physical_row"] < value["physical_rows"] - 1
                    or root["physical_row"] in positions or root["physical_row"] <= max(positions, default=0)
                    or not isinstance(root.get("row"), list) or len(root["row"]) != 18
                    or not all(isinstance(cell, str) for cell in root["row"])
                    or not isinstance(root.get("full_name"), str) or not root["full_name"]
                    or any(mark in root["full_name"] for mark in (".", "[", "]"))
                    or root["full_name"].casefold() in names
                    or root["row"][17] != root["full_name"]
                    or root["row"][1] not in ("", root["full_name"])
                    or not isinstance(root.get("before_full_name"), str)
                    or not isinstance(root.get("after_full_name"), str)):
                raise BridgeError("Invalid/duplicate GVT root checkpoint.")
            names.add(root["full_name"].casefold()); positions.add(root["physical_row"])
            row = root["row"]
            missing = [_GVT_PHYSICAL_COLUMNS[index] for index in _GVT_REQUIRED_ROOT_FIELDS if not row[index]]
            if (root.get("missing_fields") != missing or root.get("complete_root_fields") is not (not missing)
                    or row[0] not in ("", str(root["physical_row"]))):
                raise BridgeError("GVT root inventory missing-field/sequence checkpoint differs.")
            if row[11]:
                if not re.fullmatch(r"[1-9][0-9]*", row[11]) or int(row[11]) in ids:
                    raise BridgeError("Invalid/duplicate actual GVT root ID.")
                ids.add(int(row[11]))
            if row[10] and not re.fullmatch(r"nBitLen:[1-9][0-9]*", row[10]):
                raise BridgeError("Invalid actual GVT root bit length.")
        return copy.deepcopy(value)

    @staticmethod
    def _gvt_validate_reader_roots(raw, roots, record):
        actual = normalize_rows(raw, "gvt")
        if ([row["name"] for row in actual] != [root["full_name"] for root in roots]
                or [row["row"] for row in actual] != [str(index + 1) for index in range(len(roots))]):
            raise BridgeError("Complete GVT reader root order/count differs from inventory.")
        keys = {label: key for key, label in GLOBAL_COLUMNS.items()}
        for root, row in zip(roots, actual):
            for index, label in enumerate(_GVT_PHYSICAL_COLUMNS):
                if index == 3 and root["row"][2] not in ("BOOL", "INT", "DINT", "REAL", "BYTE", "IP"):
                    # The normal reader independently authenticates its mapped
                    # declaration-cache hidden value; physical complex roots
                    # may expose a different actual expanded display preview.
                    record.setdefault("complex_initializer_observations", []).append(dict(
                        name=root["full_name"], physical_root_hidden=root["row"][3],
                        declaration_hidden=row["initial_raw"], equality_asserted=False))
                    continue
                if index and root["row"][index] and row[keys[label]] != root["row"][index]:
                    raise BridgeError("Complete GVT reader differs from an observed root field.")

    def _prepare_gvt_read_roots(self, inventory=None, context=None):
        """Observe bounded ordinary view preparation, then rerun the full reader."""
        record = dict(status="preparing", source="actual_root_inventory_and_bounded_view_steps",
                      native_values_used=False, steps=[], materialized_fields=[], target_names=[])
        self.last_read_row_preparation = record
        self._gvt_root_preparing = True
        try:
            self.validate_handles(); self.assert_no_cell_edit()
            if self.dirty():
                raise BridgeError("Cannot prepare cold GVT root fields with unsaved changes.")
            if context is None:
                context = dict(handles=(self.main, self.pid, self.program_window, self.hwnd),
                               identity=self._gvt_prepare_process_identity(), baseline=self._gvt_prepare_source_baseline(), dirty=False)
            handles, identity, baseline = context["handles"], context["identity"], context["baseline"]
            self._gvt_prepare_guard(identity, baseline, handles)
            if inventory is None:
                _, inventory, _ = self._read_gvt_frame_pair(context)
            inventory = self._gvt_root_inventory(inventory)
            self._gvt_prepare_guard(identity, baseline, handles)
            roots = inventory["roots"]
            record.update(process_identity=identity, physical_rows=inventory["physical_rows"],
                          root_count=len(roots), protected_source_files=len(baseline["states"]),
                          native_source_baseline=copy.deepcopy(baseline["states"]),
                          complete_inventory_verified=True)
            if any(root["missing_fields"] for root in roots):
                # Only the identified cold-field path may expose/activate the
                # clean document for ordinary painting. Warm reads keep focus.
                self.restore_for_cell_edit()
                self.activate()
                self._gvt_prepare_guard(identity, baseline, handles)
                record["view_restored_and_activated_once"] = True
            for root in roots:
                expected = root["row"]
                if all(expected[index] != "" for index in _GVT_REQUIRED_ROOT_FIELDS):
                    continue
                record["target_names"].append(root["full_name"])
                step, selected, reveals = "observe", False, 0
                while True:
                    self._gvt_prepare_guard(identity, baseline, handles)
                    other_ids = [int(other["row"][11]) for other in roots
                                 if other is not root and other["row"][11]]
                    observed = self.accessible("grid_prepare_root_step", self.variable_grid(),
                        physical_rows=inventory["physical_rows"], physical_row=root["physical_row"],
                        expected_row=expected, before_full_name=root["before_full_name"],
                        after_full_name=root["after_full_name"], step=step, known_other_ids=other_ids)
                    record["steps"].append(copy.deepcopy(observed))
                    self._gvt_prepare_guard(identity, baseline, handles)
                    if (not isinstance(observed, dict) or observed.get("status") != "physical_root_preparation_step"
                            or observed.get("step") != step or observed.get("physical_row") != root["physical_row"]
                            or observed.get("physical_rows") != inventory["physical_rows"]
                            or observed.get("full_name") != root["full_name"] or observed.get("stop") is not False
                            or observed.get("post_guard_error") is not None or observed.get("native_values_used") is not False
                            or observed.get("nonempty_fields_preserved") is not True
                            or observed.get("known_id_conflicts_checked") is not True):
                        raise BridgeError("GVT root preparation step identity/guard receipt differs.")
                    row = observed.get("observed_row")
                    if (not isinstance(row, list) or len(row) != 18 or not all(isinstance(cell, str) for cell in row)
                            or row[17] != root["full_name"] or row[1] not in ("", root["full_name"])
                            or row[0] not in ("", str(root["physical_row"]))):
                        raise BridgeError("GVT root preparation returned an incomplete actual row.")
                    for index, (before, after) in enumerate(zip(expected, row)):
                        if before and before != after:
                            raise BridgeError("GVT root preparation changed a frozen nonempty field.")
                        if not before and after:
                            record["materialized_fields"].append(dict(name=root["full_name"],
                                column=_GVT_PHYSICAL_COLUMNS[index], before=before, after=after))
                    if row[11] and (not re.fullmatch(r"[1-9][0-9]*", row[11]) or int(row[11]) in other_ids):
                        raise BridgeError("GVT root preparation returned an invalid/duplicate actual ID.")
                    if row[10] and not re.fullmatch(r"nBitLen:[1-9][0-9]*", row[10]):
                        raise BridgeError("GVT root preparation returned invalid actual bit length.")
                    expected = root["row"] = list(row)
                    scroll, click = observed.get("scroll_dispatched_once"), observed.get("selection_dispatched_once")
                    phase = ("scroll_dispatched" if scroll else "visible_observed") if step == "reveal_one" else (
                        ("selection_dispatched" if click else "already_selected_observed") if step == "select_once" else "observed")
                    if (type(scroll) is not bool or type(click) is not bool or scroll and click
                            or type(observed.get("visible_observed")) is not bool
                            or type(observed.get("selection_verified")) is not bool
                            or observed.get("phase") != phase
                            or observed.get("needs_observe") is not (scroll or click)
                            or scroll and step != "reveal_one" or click and step != "select_once"):
                        raise BridgeError("GVT root preparation dispatch receipt differs.")
                    complete = all(row[index] != "" for index in _GVT_REQUIRED_ROOT_FIELDS)
                    if observed.get("complete_root_fields") is not complete:
                        raise BridgeError("GVT root preparation completion receipt differs.")
                    if scroll or click:
                        step = "observe"  # A dispatch never proves asynchronous completion.
                        continue
                    if complete:
                        break
                    if selected:
                        raise BridgeError("GVT root fields remain incomplete after one name selection; do not repeat.")
                    if observed.get("visible_observed") is True:
                        step, selected = "select_once", True
                    else:
                        reveals += 1
                        if reveals > inventory["physical_rows"] + len(_GVT_PHYSICAL_COLUMNS):
                            raise BridgeError("Bounded GVT root reveal did not expose complete fields.")
                        step = "reveal_one"
            self._gvt_prepare_guard(identity, baseline, handles)
            raw, _, _ = self._read_gvt_frame_pair(context)
            if raw is None:
                raise BridgeError("GVT root fields are still incomplete after preparation; do not repeat.")
            self._gvt_prepare_guard(identity, baseline, handles)
            self._gvt_validate_reader_roots(raw, roots, record)
            record["status"] = "prepared_and_complete_grid_verified"
            record["complete_reader_rerun"] = True
            return raw
        except BaseException as exc:
            record.update(status="stopped", error=str(exc), complete_reader_rerun=False)
            raise
        finally:
            self._gvt_root_preparing = False

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

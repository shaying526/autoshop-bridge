"""Global FB instances: normal IDE serialization, strict native segment readback."""

import copy
import ctypes
import stat
import re
from pathlib import Path
from autoshop_bridge.formats import instances
from autoshop_bridge.formats.scalar_types import descriptor as scalar_descriptor
from autoshop_bridge.projects import types as type_context
from autoshop_bridge.projects.identifiers import precheck_addition_names
from autoshop_bridge.errors import BridgeError, FormatRejection
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

INITIAL_COLUMNS = dict(name="变量名", initial_value="初始值", data_type="类型", comment="注释",
                       full_name="全名", device_address="软元件地址", allocated_address="分配地址")
# V4.11.0.5 normal single-toggle observations, EV08 param / WpCoordComp.
# These are measured depth profiles; no spacing formula is inferred.
INITIAL_GLYPH_OFFSETS = {1: 19, 2: 32}


def initial_member_paths(paths):
    """Validate relative dot paths before performing any editor operation."""
    if paths is None:
        return ()
    if not isinstance(paths, (list, tuple)) or len(paths) > 128:
        raise BridgeError("Expected at most 128 explicit initial-value member paths.")
    result = []
    for path in paths:
        if (not isinstance(path, str) or not path or len(path) > 1024
                or any(not part.isidentifier() for part in path.split("."))):
            raise BridgeError("Initial-value member paths require dot-separated identifiers; ARRAY indices are not supported.")
        if path.casefold() not in {item.casefold() for item in result}:
            result.append(path)
    return tuple(result)


def assert_initial_scalar(row, member=None):
    if scalar_descriptor(row["data_type"]) is None or row["initial_value"] == "...":
        raise BridgeError("Composite initial-value cells require an explicit scalar member leaf.")
    if member is not None and "." in member and row["data_type"] not in ("BOOL", "INT", "DINT", "REAL"):
        raise BridgeError("Nested initial-value leaf editing is currently validated only for BOOL/INT/DINT/REAL.")


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
    initial_member_paths_supported = True
    physical_initial_selection = False
    def __init__(self, project, program, pid=None):
        super().__init__(project, program, "gvt", pid)
        self.columns = INSTANCE_COLUMNS

    def grid(self):
        return normalize(self.raw_grid())

    def raw_grid(self):
        self.assert_no_cell_edit()
        rows, names = [], None
        while True:
            page = self._read_page(len(rows), 16)
            if names is not None and names != page["names"]:
                raise BridgeError("FBI declaration identities changed between pages.")
            names = page["names"]
            rows.extend(page["rows"])
            if len(rows) == len(names):
                self.last_grid_read = dict(read_scope="declarations", declaration_rows=len(rows),
                                           paged=True, page_size=16, complete=True)
                return rows

    def _read_page(self, offset, limit):
        """Read all declaration identities and complete values for one range."""
        if type(offset) is not int or not 0 <= offset <= 4096 or type(limit) is not int or not 1 <= limit <= 32:
            raise BridgeError("Invalid FBI page range.")
        self.assert_no_cell_edit()
        page = self.accessible("instance_grid_page", self.variable_grid(), offset=offset, limit=limit)
        if (not isinstance(page, dict) or set(page) != {"schema", "scope", "offset", "limit", "total", "names", "columns", "rows"}
                or page["schema"] != 1 or page["scope"] != "fbi_declarations_page"
                or type(page["offset"]) is not int or page["offset"] != offset
                or type(page["limit"]) is not int or page["limit"] != limit
                or type(page["total"]) is not int or not 0 <= offset <= page["total"] <= 4096
                or not isinstance(page["names"], list) or len(page["names"]) != page["total"]
                or any(not isinstance(name, str) or not name.isidentifier() for name in page["names"])
                or len({name.casefold() for name in page["names"]}) != page["total"]
                or page["columns"] != list(INSTANCE_COLUMNS.values())
                or not isinstance(page["rows"], list) or len(page["rows"]) != min(limit, page["total"] - offset)):
            raise BridgeError("Incomplete/inconsistent FBI grid page.")
        for index, row in enumerate(page["rows"], offset):
            if (not isinstance(row, dict) or set(row) != set(INSTANCE_COLUMNS.values())
                    or any(not isinstance(value, str) for value in row.values())
                    or row[INSTANCE_COLUMNS["name"]] != page["names"][index]
                    or row[INSTANCE_COLUMNS["row"]] != str(index + 1)):
                raise BridgeError("FBI page row identity/columns differ.")
        return page

    def set_new_cell(self, variable, field, expected, value, known_rows):
        """Read one new last row per cell; the caller must prove the final table.

        All names/count/columns and the new row's complete values remain live.
        Existing non-name values are frozen here and re-read before any save.
        This adapter is exclusively for the current add batch's last new row.
        """
        if field == "name":
            if variable != "#row:" + str(len(known_rows) + 1) or expected != "" or not identifier(value):
                raise BridgeError("New-instance writes require the exact next spare row.")
            prefix = known_rows
            names = [row["name"] for row in known_rows] + [value]
        elif field in ("data_type", "comment") and known_rows:
            if variable != known_rows[-1]["name"] or expected != known_rows[-1][field]:
                raise BridgeError("New-instance writes require the current last-row baseline.")
            prefix = known_rows[:-1]
            names = [row["name"] for row in known_rows]
        else:
            raise BridgeError("Unsupported new-instance cell operation.")
        self.write_cell(variable, field, expected, value)
        if field == "name":
            self.validate_main()
            self.locate_editor()
        page = self._read_page(len(prefix), 1)
        if page["names"] != names or page["total"] != len(names):
            raise BridgeError("FBI declaration names/count changed during new-row edit.")
        raw_prefix = [{INSTANCE_COLUMNS[key]: row[key] for key in INSTANCE_COLUMNS} for row in prefix]
        return normalize(raw_prefix + page["rows"])

    def set_cell(self, variable, field, expected, value):
        self.write_cell(variable, field, expected, value)
        if field == "name":
            # Normal FBI rename can rebuild the document/grid and open a source
            # reference. Resolve the same exact registered table, never reuse
            # its former control handle or repeat the name edit.
            self.validate_main()
            self.locate_editor()
        return self.grid()

    def _initial_toolbox_grids(self):
        """Observe optional cold toolbox state without selecting/committing it."""
        self.validate_handles()
        grids = []
        for handle in self.children(self.main):
            if not self.user.IsWindowVisible(handle):
                continue
            kind = self.class_name(handle)
            if kind != "VSFlexGrid8N" and not kind.startswith("ATL:"):
                continue
            parent = self.user.GetParent(handle)
            while parent and parent != self.main:
                if self.text(parent) == "工具箱":
                    if kind.startswith("ATL:"):
                        raise BridgeError("An instance member initial-value cell is being edited; finish/cancel it first.")
                    grids.append(handle)
                    break
                parent = self.user.GetParent(parent)
        if len(grids) > 1:
            raise BridgeError("Multiple visible instance initial-value toolbox grids are unsupported.")
        return grids

    def _initial_grid(self):
        grids = self._initial_toolbox_grids()
        if len(grids) != 1:
            raise BridgeError("Expected one visible instance initial-value toolbox grid.")
        return grids[0]

    def _initial_frame(self, grid, instance):
        offset, result, identity = 0, [], None
        while True:
            page = self.accessible("instance_initial_page", grid, variable=instance, instance=instance, offset=offset, limit=64)
            if (not isinstance(page, dict) or page.get("schema") != 1
                    or page.get("scope") != "fbi_initial_physical_page" or page.get("instance") != instance
                    or page.get("columns") != list(INITIAL_COLUMNS.values())
                    or page.get("offset") != offset or page.get("limit") != 64
                    or page.get("boundary_stable") is not True or page.get("native_values_used") is not False
                    or type(page.get("physical_data_rows")) is not int or not 1 <= page["physical_data_rows"] <= 4096
                    or page.get("accessible_children") != page["physical_data_rows"] + 8
                    or not isinstance(page.get("root_row"), list) or len(page["root_row"]) != 7
                    or any(not isinstance(v, str) for v in page["root_row"])
                    or not isinstance(page.get("rows"), list)
                    or len(page["rows"]) != min(64, page["physical_data_rows"] - offset)):
                raise BridgeError("Incomplete/inconsistent FBI initial-value physical page.")
            current = (page["physical_data_rows"], page["accessible_children"], page["root_row"])
            if identity is not None and current != identity:
                raise BridgeError("FBI initial-value page identity changed.")
            identity = current
            for index, item in enumerate(page["rows"], offset):
                if (not isinstance(item, dict) or set(item) != {"physical_index", "values", "row_height", "name_height"}
                        or type(item["physical_index"]) is not int or item["physical_index"] != index
                        or not isinstance(item["values"], list) or len(item["values"]) != 7
                        or any(not isinstance(v, str) for v in item["values"])
                        or any(type(item[k]) is not int or item[k] < 0 for k in ("row_height", "name_height"))):
                    raise BridgeError("FBI initial-value physical row differs.")
                result.append(item)
            offset += len(page["rows"])
            if offset == identity[0]:
                if result[0]["values"] != identity[2]:
                    raise BridgeError("FBI initial-value root page differs.")
                return dict(total=identity[0], root=identity[2], rows=result)

    def _initial_rows(self, grid, instance):
        first = self._initial_frame(grid, instance)
        if self._initial_frame(grid, instance) != first:
            raise BridgeError("FBI initial-value complete collection changed between passes.")
        rows, names = [], set()
        for item in first["rows"]:
            values = item["values"]
            if all(value == "" for value in values):
                if item["row_height"] != 1 or item["name_height"] != 1:
                    raise BridgeError("Unknown empty initial-value physical slot profile.")
                continue
            row = dict(zip(INITIAL_COLUMNS, values)); full = row["full_name"].casefold()
            if (not row["name"] or not full or full in names
                    or (not rows and full != instance.casefold())
                    or (rows and not (full.startswith(instance.casefold()+".") or full.startswith(instance.casefold()+"[")))):
                raise BridgeError("FBI initial-value member identities differ.")
            rows.append(row); names.add(full)
        if not rows or first["rows"][0]["values"][4].casefold() != instance.casefold():
            raise BridgeError("FBI initial-value physical root is missing.")
        self._initial_checkpoint = first
        self.last_initial_read = dict(complete=True, paged=True, page_size=64, complete_passes=2,
                                      physical_data_rows=first["total"], named_rows=len(rows),
                                      placeholder_rows=first["total"]-len(rows), atomic_snapshot=False,
                                      native_values_used=False)
        return rows

    def _initial_step(self, grid, instance, full, action):
        frame = self._initial_checkpoint
        matches = [r for r in frame["rows"] if r["values"][4].casefold() == full.casefold()]
        if len(matches) != 1:
            raise BridgeError("Expected one physical initial-value member.")
        item = matches[0]; index = item["physical_index"]
        checkpoint = dict(variable=instance, instance=instance, physical_data_rows=frame["total"], physical_index=index,
                          target_column=0 if action == "expand_once" else 1,
                          expected_root=frame["root"], expected_row=item["values"],
                          expected_before=frame["rows"][index-1]["values"] if index else None,
                          expected_after=frame["rows"][index+1]["values"] if index+1 < frame["total"] else None)
        if action == "expand_once":
            depth = len(full.split("."))-1
            if depth not in INITIAL_GLYPH_OFFSETS:
                raise BridgeError("Initial-value expansion glyph geometry is not validated for this depth.")
            checkpoint["glyph_offset_x"] = INITIAL_GLYPH_OFFSETS[depth]
        self._prepare_initial_interaction(grid)
        step, dispatched, reveals = "observe", False, 0
        record = dict(instance=instance, full_name=full, action=action, steps=[],
                      interaction_preparation=copy.deepcopy(getattr(self, "last_initial_interaction", {})))
        self.last_initial_step = record
        while True:
            receipt = self.accessible("instance_initial_step", grid, step=step, **checkpoint)
            record["steps"].append(copy.deepcopy(receipt))
            if (not isinstance(receipt, dict) or receipt.get("schema") != 1
                    or receipt.get("status") != "fbi_initial_step" or receipt.get("instance") != instance
                    or receipt.get("step") != step or receipt.get("stop") is not False
                    or receipt.get("post_guard_error") is not None or receipt.get("native_values_used") is not False
                    or receipt.get("physical_data_rows") != frame["total"] or receipt.get("physical_index") != index
                    or receipt.get("root_row") != frame["root"] or receipt.get("observed_row") != item["values"]):
                raise BridgeError("FBI initial-value step identity/baseline differs.")
            scroll, click = receipt.get("scroll_dispatched_once"), receipt.get("click_dispatched_once")
            phases = {"observe": {"observed"}, "reveal_one": {"scroll_dispatched" if scroll else "visible_observed"},
                      "select_once": {"selection_dispatched", "selection_verified"} if click else {"already_selected_observed"},
                      "expand_once": {"expansion_dispatched"}}
            if (type(scroll) is not bool or type(click) is not bool or scroll and click
                    or type(receipt.get("visible_observed")) is not bool
                    or type(receipt.get("selection_verified")) is not bool
                    or type(receipt.get("needs_observe")) is not bool
                    or receipt.get("phase") not in phases[step]
                    or receipt["needs_observe"] != (scroll or (click and not receipt["selection_verified"]) or step == "expand_once")
                    or any(receipt.get(key) != item[key] for key in ("row_height", "name_height"))
                    or scroll and step != "reveal_one" or click and step != action):
                raise BridgeError("FBI initial-value step dispatch receipt differs.")
            if click and action == "expand_once":
                return receipt
            if scroll or click:
                step = "observe"
                continue
            if action == "select_once" and receipt["selection_verified"] and receipt["visible_observed"]:
                return receipt
            if dispatched:
                raise BridgeError("FBI initial-value selection pending after one click; do not repeat.")
            if receipt["visible_observed"]:
                step, dispatched = action, True
            else:
                reveals += 1
                if reveals > frame["total"] + 7:
                    raise BridgeError("Bounded initial-value reveal did not expose the member.")
                step = "reveal_one"

    def _prepare_initial_interaction(self, grid):
        """One foreground request before acting on the exact toolbox grid."""
        identity = (self.main, self.pid, self.program_window, self.hwnd)
        foreground = self.user.GetForegroundWindow
        request = self.user.SetForegroundWindow
        # Win64 HWNDs must not be truncated by ctypes' default int return.
        if hasattr(foreground, "restype"):
            foreground.argtypes = []
            foreground.restype = ctypes.c_void_p
            request.argtypes = [ctypes.c_void_p]
            request.restype = ctypes.c_int

        def guard():
            if (self.main, self.pid, self.program_window, self.hwnd) != identity:
                raise BridgeError("Initial-value interaction session handles changed.")
            self.validate_handles()
            self.assert_no_cell_edit()
            if grid is None:
                self._initial_toolbox_grids()  # Cold selection may have no toolbox yet.
            elif self._initial_grid() != grid:
                raise BridgeError("Initial-value interaction toolbox handle changed.")
            if grid is not None and any(self.class_name(h).startswith("ATL:") and self.user.IsWindowVisible(h)
                   for h in self.children(grid)):
                raise BridgeError("An initial-value inline editor is active; finish or cancel it explicitly.")

        guard()
        modified = self.dirty()
        self.restore_for_cell_edit()
        self.activate()
        guard()
        record = dict(foreground_before=foreground(), request_dispatched_once=False,
                      requested_main=self.main, dirty_before=modified, toolbox=grid,
                      status="preparing", automatic_retry=False)
        self.last_initial_interaction = record
        if record["foreground_before"] != self.main:
            record["request_dispatched_once"] = True
            if not request(self.main):
                record["status"] = "foreground_request_denied"
                raise BridgeError("AutoShop foreground activation was denied; no initial-value action was dispatched.")
            self.wait_until(lambda: foreground() == self.main, "exact AutoShop foreground observation")
        guard()
        if self.dirty() != modified or foreground() != self.main:
            record["status"] = "stopped"
            raise BridgeError("Initial-value interaction dirty state or foreground changed.")
        record.update(status="foreground_verified", foreground_after=foreground(), dirty_after=modified)

    def _physical_select_initial_instance(self, instance):
        """Explicit, bounded preparation followed by one actual selection."""
        target = getattr(self, "initial_native_target", None)
        if target is None:
            raise BridgeError("Physical initial selection requires an exact connected native target.")
        target = regular_file(Path(target))
        raw = target.read_bytes()
        native_rows = instances.parse(raw)["instances"]
        self._prepare_initial_interaction(None)
        if target.read_bytes() != raw:
            raise BridgeError("Native baseline changed during physical selection preparation.")
        # One fresh full preimage after the nonediting window preparation. The
        # full postimage is retained below; no declaration field is omitted.
        rows = self.grid()
        planned = getattr(self, "initial_selection_expected_rows", None)
        if planned is None:
            assert_native(raw, rows)
        elif (rows != planned or sha256(raw) != getattr(self, "initial_selection_native_sha256", None)
                or getattr(self, "initial_selection_native_names", []) != [row["name"] for row in native_rows]
                or len(rows) != len(native_rows)
                or any(row["data_type"] != native["data_type"] for row, native in zip(rows, native_rows))):
            raise BridgeError("Planned current declarations/native prototype differ before physical selection.")
        matches = [(index, row) for index, row in enumerate(rows) if row["name"] == instance]
        if len(matches) != 1:
            raise BridgeError("Physical selection requires one exact native instance name/type.")
        index, expected = matches[0]
        native_row = native_rows[index]
        grid = self.variable_grid()
        modified = self.dirty()
        expected_row = [expected[key] for key in INSTANCE_COLUMNS]
        expected_names = [row["name"] for row in rows]
        common = dict(instance=instance, instance_type=native_row["data_type"], physical_select=True,
                      physical_row=index+1, physical_rows=len(rows)+2, expected_row=expected_row, expected_names=expected_names)
        aggregate = dict(schema=1, status="initial_instance_selection_preparing", physical_select=True,
                         instance=instance, instance_type=native_row["data_type"], physical_row=index+1,
                         physical_rows=len(rows)+2, native_sha256=sha256(raw), expected_names=expected_names,
                         prepare_receipts=[], prepare_summary=dict(scroll_limit=64, helper_call_limit=129,
                         helper_calls=0, observe_calls=0, reveal_requests=0, scroll_attempts_observed=0,
                         scroll_dispatches_observed=0), physical_input_outcome="not_called",
                         physical_move_attempts=0, click_attempts=0, send_input_calls=0, input_events_sent=0,
                         stop=False, automatic_retry=False)
        if not hasattr(self, "initial_physical_selection_receipts"):
            self.initial_physical_selection_receipts = []
        history_index = len(self.initial_physical_selection_receipts)
        self.initial_physical_selection_receipts.append(aggregate)
        self.last_initial_physical_selection = aggregate
        summary = aggregate["prepare_summary"]

        def guard():
            if target.read_bytes() != raw or self.variable_grid() != grid or self.dirty() != modified:
                raise BridgeError("Native/session/dirty baseline changed during physical selection preparation.")

        try:
            step = "observe"
            while True:
                guard()
                if summary["helper_calls"] >= 129:
                    raise BridgeError("Bounded physical declaration preparation exhausted its helper-call budget.")
                if step == "reveal_one" and summary["reveal_requests"] >= 64:
                    raise BridgeError("Bounded physical declaration preparation exhausted 64 scroll requests.")
                summary["helper_calls"] += 1
                summary["observe_calls" if step == "observe" else "reveal_requests"] += 1
                try:
                    receipt = self.accessible("prepare_initial_instance_step", grid, step=step, **common)
                except BridgeError as exc:
                    aggregate["prepare_transport_failure"] = dict(step=step, reply_received=False,
                        error=str(exc), scroll_dispatch_unknown=step == "reveal_one")
                    raise
                aggregate["prepare_receipts"].append(copy.deepcopy(receipt))
                if isinstance(receipt, dict):
                    summary["scroll_attempts_observed"] += receipt.get("scroll_attempted_once") is True
                    summary["scroll_dispatches_observed"] += receipt.get("scroll_dispatched_once") is True
                guard()
                if (not isinstance(receipt, dict) or receipt.get("schema") != 1
                        or receipt.get("status") != "initial_instance_preparation_step"
                        or receipt.get("instance") != instance or receipt.get("instance_type") != native_row["data_type"]
                        or receipt.get("physical_row") != index+1 or receipt.get("physical_rows") != len(rows)+2
                        or receipt.get("step") != step or receipt.get("stop") is not False
                        or receipt.get("post_guard_error") is not None
                        or receipt.get("before_row") != expected_row or receipt.get("after_row") != expected_row
                        or receipt.get("before_names") != expected_names or receipt.get("after_names") != expected_names
                        or type(receipt.get("visible_observed")) is not bool
                        or type(receipt.get("scroll_attempted_once")) is not bool
                        or type(receipt.get("scroll_dispatched_once")) is not bool
                        or type(receipt.get("needs_observe")) is not bool
                        or receipt["needs_observe"] != receipt["scroll_attempted_once"]
                        or receipt.get("physical_select") is not True
                        or any(type(receipt.get(key)) is not int or receipt[key] != 0 for key in (
                            "physical_move_attempts", "click_attempts", "send_input_calls", "input_events_sent"))
                        or receipt["scroll_dispatched_once"] and not receipt["scroll_attempted_once"]
                        or step == "observe" and (receipt["scroll_attempted_once"] or receipt["scroll_dispatched_once"])):
                    raise BridgeError("Physical declaration preparation receipt/baseline differs; do not repeat.")
                if step == "observe" and receipt["visible_observed"]:
                    break
                step = "reveal_one" if step == "observe" else "observe"
            guard()
            # Once this helper starts, a lost response leaves physical dispatch
            # unknown. Never infer zero input from an empty receipt or timeout.
            aggregate.update(physical_input_outcome="unknown", final_selection_started=True,
                             physical_move_attempts=None, click_attempts=None, send_input_calls=None, input_events_sent=None)
            receipt = self.accessible("select_initial_instance", grid, **common)
            actual_protocol = (isinstance(receipt, dict) and receipt.get("schema") == 1
                               and receipt.get("status") == "initial_instance_physical_selection_dispatched")
            final = copy.deepcopy(receipt) if actual_protocol else dict(raw_response=receipt,
                    physical_move_attempts=None, click_attempts=None, send_input_calls=None, input_events_sent=None)
            final.update(prepare_receipts=copy.deepcopy(aggregate["prepare_receipts"]),
                         prepare_summary=copy.deepcopy(summary), native_sha256=sha256(raw),
                         physical_input_outcome="actual_receipt" if actual_protocol else "unknown", final_selection_started=True)
            self.initial_physical_selection_receipts[history_index] = final
            self.last_initial_physical_selection = final
            aggregate = final
            valid = (isinstance(receipt, dict) and receipt.get("schema") == 1
                     and receipt.get("status") == "initial_instance_physical_selection_dispatched"
                     and receipt.get("instance") == instance and receipt.get("instance_type") == native_row["data_type"]
                     and receipt.get("physical_row") == index+1 and receipt.get("physical_rows") == len(rows)+2
                     and receipt.get("observed_row") == expected_row and receipt.get("stop") is False
                     and receipt.get("post_guard_error") is None
                     and all(type(receipt.get(key)) is int and receipt[key] == value for key, value in (
                         ("physical_move_attempts", 1), ("click_attempts", 1), ("send_input_calls", 1), ("input_events_sent", 2)))
                     and receipt.get("context_restored") is True and receipt.get("physical_select") is True
                     and receipt.get("caller_target_dpi_matched") is True and receipt.get("input_event_flags") == [2, 4])
            if not valid:
                raise BridgeError("Physical initial selection stopped; inspect actual receipt, never repeat.")
            guard()
            if self.grid() != rows:
                raise BridgeError("Physical initial selection changed complete declaration contents.")
            guard()
            return final
        except BridgeError as exc:
            aggregate.update(orchestration_stop=True, orchestration_error=str(exc), orchestration_status="stopped")
            raise FormatRejection(str(exc), code="physical_initial_selection_stopped",
                                  context=dict(physical_selection_receipt=copy.deepcopy(aggregate), automatic_retry=False)) from exc

    def _expand_initial_paths(self, grid, instance, paths, rows):
        for path in paths:
            parts = path.split(".")
            for length in range(1, len(parts)+1):
                full = instance + "." + ".".join(parts[:length])
                found = [r for r in rows if r["full_name"].casefold() == full.casefold()]
                if len(found) != 1:
                    raise BridgeError("Requested initial-value path is missing: " + full)
                if scalar_descriptor(found[0]["data_type"]) is not None:
                    if length < len(parts):
                        raise BridgeError("Scalar initial-value path cannot have descendants.")
                    continue
                if "[" in found[0]["data_type"] or found[0]["data_type"].startswith("ARRAY"):
                    raise BridgeError("ARRAY initial-value expansion is not supported.")
                prefix = full.casefold()+"."
                if any(r["full_name"].casefold().startswith(prefix) for r in rows):
                    continue
                before = copy.deepcopy(rows)
                self._initial_step(grid, instance, full, "expand_once")
                self.last_initial_expansions.append(copy.deepcopy(self.last_initial_step))
                rows = self._initial_rows(grid, instance)
                previous = {r["full_name"].casefold(): r for r in before}
                current = {r["full_name"].casefold(): r for r in rows}
                added = set(current) - set(previous)
                if (not added or any(current.get(k) != r for k, r in previous.items())
                        or any(not k.startswith(prefix) or "." in k[len(prefix):] for k in added)):
                    raise BridgeError("Initial-value expansion changed existing members or failed to expose descendants.")
        return rows

    def initial_members(self, instance, member_paths=None):
        paths = initial_member_paths(member_paths)
        self.last_initial_expansions = []
        self._initial_toolbox_grids()  # Zero grids is valid before the first FBI selection.
        self.restore_for_cell_edit()
        self.activate()
        self.assert_no_cell_edit()
        self._initial_toolbox_grids()
        if self.physical_initial_selection:
            self._physical_select_initial_instance(instance)
        elif self.accessible("select_verified_cell", self.variable_grid(), variable=instance,
                             column=self.columns["name"], expected=instance) != "selection_verified":
            raise BridgeError("Initial-value instance selection was not verified.")
        grid = self._initial_grid()
        rows = self._initial_rows(grid, instance)
        if self.physical_initial_selection:
            receipt = self.last_initial_physical_selection
            if rows[0]["name"] != instance or rows[0]["data_type"].casefold() != receipt["instance_type"].casefold():
                raise BridgeError("Actual toolbox root/name/type differs after physical selection.")
        return self._expand_initial_paths(grid, instance, paths, rows)

    def set_initial_member(self, instance, member, expected, value, member_paths=None):
        paths = initial_member_paths(member_paths if member_paths is not None else [member])
        rows = self.initial_members(instance, paths)
        full = instance + "." + member
        matches = [row for row in rows[1:] if row["full_name"].casefold() == full.casefold()]
        if len(matches) != 1 or matches[0]["initial_value"] != expected:
            raise BridgeError("Initial-value member is not displayed or its baseline differs.")
        assert_initial_scalar(matches[0], member)
        grid = self._initial_grid()
        self._initial_step(grid, instance, full, "select_once")
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
    adapter.initial_native_target = target
    opened = adapter.ensure_open(open_if_missing)
    return adapter, target, opened, inventory


def assert_native(raw, rows, *, allow_allocation_preview=False):
    native = instances.parse(raw)["instances"]
    if len(native) != len(rows):
        raise BridgeError("Global instance editor/native count differs.")
    differences = []
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
        if allow_allocation_preview:
            display = row["allocated_address"]
            if (not isinstance(display, str)
                    or re.fullmatch(r"(?:0[xX])?[0-9a-fA-F]{1,8}", display) is None):
                raise BridgeError("Unsupported instance allocation preview; expected uint32 hex or an unallocated native address.")
            shown = int(display, 16)
            if shown != address:
                differences.append(dict(name=var["name"], native_address=address,
                                        editor_address=display))
            continue
        try:
            shown = int(row["allocated_address"], 16)
        except ValueError as exc:
            raise BridgeError("Unsupported instance allocation display.") from exc
        if address != shown:
            raise BridgeError("Global instance editor/native address differs.")
    return differences


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
                "Instance add requires a unique name, identified project/qualified library FB, initial_value=null and bounded comment."
            )
        names.add(op["name"].casefold())
    return copy.deepcopy(ops)


def verify_preserved(before, after, ops, *, expected_allocation_rows=None):
    old, new = instances.parse(before), instances.parse(after)
    a, b = old["instances"], new["instances"]
    allocation_updates = []
    if expected_allocation_rows is not None:
        if not isinstance(expected_allocation_rows, list) or any(
            not isinstance(row, dict) or set(row) != set(INSTANCE_COLUMNS)
            or any(not isinstance(value, str) for value in row.values())
            for row in expected_allocation_rows
        ):
            raise BridgeError("Expected a complete frozen IDE allocation table.")
        assert_native(before, expected_allocation_rows, allow_allocation_preview=True)
    if [r["name"] for r in b] != [r["name"] for r in a] + [op["name"] for op in ops]:
        raise BridgeError("Saved instance names/order differ.")
    for index, (first, second) in enumerate(zip(a, b)):
        start, end = first["record_offset"], second["record_offset"]
        old_record = before[start : start + first["record_bytes"]]
        new_record = after[end : end + second["record_bytes"]]
        if old_record == new_record:
            continue
        allowed = False
        if expected_allocation_rows is not None and len(old_record) == len(new_record):
            preview = expected_allocation_rows[index]["allocated_address"]
            old_address = first["uninterpreted_metadata"]["address_raw"]
            new_address = second["uninterpreted_metadata"]["address_raw"]
            # Decode the known flags/address pair boundary, never infer it from
            # a project offset or reconstruct an existing record's encoding.
            offsets = []
            for raw, row in ((before, first), (after, second)):
                reader = instances.Reader(raw, row["record_offset"], row["record_offset"] + row["record_bytes"])
                reader.take(8)
                reader.string()
                reader.string()
                reader.u32()  # flags are kept byte-exact.
                offsets.append(reader.pos - row["record_offset"])
            offset = offsets[0]
            allowed = (bool(preview) and old_address != new_address and new_address == int(preview, 16)
                       and offsets[0] == offsets[1]
                       and old_record[:offset] == new_record[:offset]
                       and old_record[offset + 4:] == new_record[offset + 4:])
            if allowed:
                allocation_updates.append(dict(name=first["name"], before=old_address,
                                               after=new_address, editor_address=preview))
        if not allowed:
            raise BridgeError(
                "Existing native instance record changed: " + first["name"]
            )
    for row, op in zip(b[len(a) :], ops):
        if row["data_type"] != op["data_type"] or row["comment"] != op["comment"]:
            raise BridgeError("Saved new global instance differs.")
    # IDE owns opaque archive sections; compare/report them, never patch them.
    result = dict(
        opaque_prefix_changed=old["opaque_prefix_sha256"]
        != new["opaque_prefix_sha256"],
        opaque_suffix_changed=old["opaque_suffix_sha256"]
        != new["opaque_suffix_sha256"],
    )
    if expected_allocation_rows is not None:
        result["native_allocation_updates"] = allocation_updates
    return result


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
        allocation_preview = dict(
            scope="not_saved_native_allocation",
            before=assert_native(raw, before["rows"], allow_allocation_preview=True),
            after_save=None,
        )
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
        context = type_context.ide_catalog(project, requested, fb_only=True)
        occupied = []
        for item in inventory["files"]:
            if item.get("kind") == "global_variables":
                if item.get("status") == "parsed":
                    occupied.extend(r["name"] for r in item["table"]["rows"])
                if not item.get("sha256"):
                    raise BridgeError("Global table has no readable hash baseline: " + item["path"])
                context["hashes"][item["path"]] = item["sha256"]
        ops = validate(document, before["rows"], context["types"], occupied)
        type_context.check(context)
        if dry_run:
            return dict(
                status="instances_ready",
                operations=ops,
                instance_count=len(before["rows"]),
                selector_preflight="pending_first_default_row" if not before["rows"] else "not_performed",
                allocation_preview=allocation_preview,
                native_allocation_updates=[],
                compile_pending=True,
            )
        backup = create_backup(t, raw, backup_root, "editor_instances")
        write_json_new(backup / "editor_before.json", before)
        write_json_new(backup / "instance_changes.json", document)
        write_json_new(backup / "type_context.json", context)
        write_json_new(backup / "allocation_preview_before.json", allocation_preview)
        if snapshot(a, t) != before:
            raise BridgeError("Instance table changed during backup.")
        current = copy.deepcopy(before["rows"])
        new_writer = getattr(a, "set_new_cell", None)

        def write_new_cell(variable, field, expected_value, value):
            if callable(new_writer):
                return new_writer(variable, field, expected_value, value, known_rows=current)
            return a.set_cell(variable, field, expected_value, value)

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
                actual = write_new_cell(
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
                    actual = write_new_cell(
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
                    actual = write_new_cell(
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
                allocation_preview=allocation_preview,
                native_allocation_updates=[],
                compile_pending=True,
            )
            if save:
                assert_hash(t, expected.lower())
                type_context.check(context)
                a.save()
                saved = t.read_bytes()
                saved_rows = a.grid()
                allocation_preview["after_save"] = assert_native(
                    saved, saved_rows, allow_allocation_preview=True
                )
                if a.dirty() or saved_rows != current:
                    raise BridgeError(
                        "Saved instance table differs from expected buffer."
                    )
                preservation = verify_preserved(
                    raw, saved, ops, expected_allocation_rows=before["rows"]
                )
                allocation_updates = preservation.pop("native_allocation_updates")
                if allocation_updates:
                    allocation_preview["scope"] = "editor_preview_with_native_updates"
                result.update(
                    status="instances_saved",
                    sha256=sha256(saved),
                    requires_manual_save=False,
                    archive_changes=preservation,
                    native_allocation_updates=allocation_updates,
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

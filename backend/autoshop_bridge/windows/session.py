"""Explicit Windows document lifecycle, with exact identity and readback checks."""

import base64
import ctypes
import json
import subprocess
import time
from pathlib import Path

from autoshop_bridge.windows.editor import Win32Editor
from autoshop_bridge.errors import BridgeError
from autoshop_bridge.formats.native import parse
from autoshop_bridge.projects.inventory import scan
from autoshop_bridge.storage import (
    assert_hash,
    create_backup,
    native_file,
    read_json,
    sha256,
    target_lock,
    utc_now,
    writable_target,
    write_json_new,
)

COLUMNS = {
    "row": "序号",
    "category": "类别",
    "name": "名称",
    "data_type": "数据类型",
    "initial_raw": "隐藏初始值",
    "initial_value": "初始值",
    "retention": "掉电保持",
    "comment": "注释",
    "id": "ID",
}
FC_COLUMNS = {key: value for key, value in COLUMNS.items()
              if key not in ("initial_raw", "initial_value", "retention")}


def resolve_target(project, program):
    inventory = scan(project)
    matches = [
        item
        for item in inventory["files"]
        if item.get("kind") in ("st_program", "function_block", "function")
        and (item.get("name") == program or Path(item["file"]).stem == program)
    ]
    if len(matches) != 1:
        raise BridgeError(
            "Expected one registered ST/FB program: {} (found {}).".format(
                program, len(matches)
            )
        )
    target = native_file(Path(matches[0]["path"]))
    return Path(inventory["project"]), target


def normalize_rows(raw_rows, columns=None):
    columns = columns or COLUMNS
    result, names, row_numbers = [], set(), set()
    for raw in raw_rows:
        if set(raw) != set(columns.values()):
            raise BridgeError("Unsupported FB variable grid columns.")
        row = {key: raw[value] or "" for key, value in columns.items()}
        if row["row"] == columns["row"]:
            continue
        if not row["row"].isdigit() or row["row"] in row_numbers:
            raise BridgeError("Invalid/duplicate variable row number.")
        row_numbers.add(row["row"])
        if not row["name"]:
            # Spare rows have their sequence number but otherwise no values.
            if any(row[key] for key in columns if key != "row"):
                raise BridgeError("Incomplete spare variable row.")
            continue
        if row["name"].casefold() in names:
            raise BridgeError("Duplicate variable name in editor.")
        names.add(row["name"].casefold())
        result.append(row)
    return result


def assert_native_variables(container, rows):
    if len(rows) != len(container.variables):
        raise BridgeError("FB editor/native variable count differs.")
    for index, (var, row) in enumerate(zip(container.variables, rows)):
        expected = var.as_dict(index)
        for field in ("name", "category", "data_type", "comment"):
            if expected[field] is None or expected[field] != row[field]:
                raise BridgeError(
                    "FB editor/native variable {} differs: {}.".format(index + 1, field)
                )
        if hasattr(var, "initial_raw") and var.type_code in (1, 4, 16) and var.initial_raw != row["initial_raw"]:
            raise BridgeError("FB editor/native scalar initial value differs.")


class WindowsSession(Win32Editor):
    def __init__(self, project, program, pid=None):
        super().__init__(project, program, pid, require_open=False)
        self.columns = COLUMNS

    def validate_main(self):
        if (
            self.window_pid(self.main) != self.pid
            or not self.is_autoshop(self.pid)
            or not self.title_matches(self.text(self.main))
        ):
            raise BridgeError("AutoShop project/session changed.")
        if not self.user.IsWindowEnabled(self.main):
            raise BridgeError(
                "AutoShop has a modal dialog; inspect it before continuing."
            )

    def accessible(self, action, target, **options):
        self.validate_main()
        request = dict(
            action=action,
            main=self.main,
            target=target,
            pid=self.pid,
            project=self.project,
            program=self.program,
            **options,
        )
        payload = base64.b64encode(
            json.dumps(request, ensure_ascii=True).encode()
        ).decode()
        helper = Path(__file__).with_name("accessibility.ps1")
        args = [
            "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy",
            "Bypass", "-File", str(helper), "-RequestBase64", payload,
        ]
        self.last_grid_transport = "powershell_source"
        if action == "grid":
            from autoshop_bridge.windows.grid_host import command, PROTOCOL

            grid_request = dict(request, protocol=PROTOCOL)
            grid_payload = base64.b64encode(json.dumps(grid_request, ensure_ascii=True).encode()).decode()
            compiled = command(grid_payload)
            if compiled is not None:
                args = compiled
                self.last_grid_transport = "precompiled_grid"
        try:
            call = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                creationflags=0x08000000,
            )
            if len(call.stdout) > 8 * 1024 * 1024:
                raise ValueError("accessibility response exceeds 8 MiB")
            response = json.loads(call.stdout.decode("utf-8-sig"))
            if not isinstance(response, dict) or response.get("status") not in ("ok", "error"):
                raise ValueError("invalid accessibility response envelope")
            if response["status"] == "ok" and "result" not in response:
                raise ValueError("missing accessibility result")
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            raise BridgeError(
                "Windows accessibility helper failed: {}".format(exc)
            ) from exc
        if call.returncode or response.get("status") != "ok":
            raise BridgeError(
                "Accessibility: {}".format(response.get("error", "helper failed"))
            )
        result = response["result"]
        if action == "grid":
            from autoshop_bridge.windows.grid_protocol import unpack_grid

            result, self.last_grid_read = unpack_grid(result)
        return result

    def wait_until(self, check, description, seconds=4):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            # MFC briefly replaces the title while creating/closing an MDI.
            # Wait through that transition without issuing another mutation.
            if not self.user.IsWindowEnabled(self.main):
                raise BridgeError(
                    "AutoShop has a modal dialog; inspect it before continuing."
                )
            if self.window_pid(self.main) != self.pid or not self.title_matches(
                self.text(self.main)
            ):
                time.sleep(0.05)
                continue
            if check():
                return
            time.sleep(0.05)
        raise BridgeError("Timed out waiting for {}.".format(description))

    def ensure_open(self, allow_open=False):
        self.validate_main()
        if self.locate_editor(required=False):
            return False
        if not allow_open:
            raise BridgeError("Target program is not open; use --open or editor-open.")
        trees = []
        for h in self.children(self.main):
            if self.class_name(h) != "SysTreeView32":
                continue
            ancestor = self.user.GetParent(h)
            while ancestor and ancestor != self.main:
                if self.text(ancestor) == "工程管理":
                    trees.append(h)
                    break
                ancestor = self.user.GetParent(ancestor)
        if len(trees) != 1:
            raise BridgeError("Expected one project management tree.")
        self.accessible("open", trees[0])
        self.wait_until(
            lambda: self.locate_editor(required=False), "requested program to open"
        )
        return True

    def activate(self):
        self.validate_handles()
        mdi = self.user.GetParent(self.program_window)
        self.window_message(mdi, 0x0222, self.program_window)  # WM_MDIACTIVATE
        self.wait_until(
            lambda: self.window_message(mdi, 0x0229) == self.program_window,
            "requested program activation",
        )

    def variable_grid(self):
        self.validate_handles()
        grids = [
            h
            for h in self.children(self.program_window)
            if self.class_name(h) == "VSFlexGrid8N" and self.user.IsWindowVisible(h)
        ]
        if len(grids) != 1:
            raise BridgeError("Expected one visible FB variable table.")
        return grids[0]

    def assert_no_cell_edit(self):
        self.validate_handles()
        edits = [
            h
            for h in self.children(self.program_window)
            if self.class_name(h).startswith("ATL:") and self.user.IsWindowVisible(h)
        ]
        if edits:
            raise BridgeError(
                "A variable cell is being edited; finish/cancel it before continuing."
            )

    def grid(self):
        self.assert_no_cell_edit()
        raw = self.accessible("grid", self.variable_grid())
        columns = getattr(self, "columns", COLUMNS)
        return normalize_rows(raw, columns)

    def dirty(self):
        return self.read().modified or self.text(self.program_window).endswith("*")

    def begin_cell(self, variable, field, expected):
        self.restore_for_cell_edit()
        self.activate()
        self.assert_no_cell_edit()
        grid = self.variable_grid()
        columns = getattr(self, "columns", COLUMNS)
        # The helper waits for the posted click and verifies a fresh live cell
        # before returning. No second PowerShell process or unverified F2.
        selected = self.accessible(
            "select_verified_cell",
            grid,
            variable=variable,
            column=columns[field],
            expected=expected,
        )
        if selected != "selection_verified":
            raise BridgeError("Variable cell selection was not verified.")
        self.post(grid, 0x100, 113)  # F2, targeted to the verified grid.
        self.post(grid, 0x101, 113)

        def cell_editors():
            return [
                h
                for h in self.children(grid)
                if self.class_name(h).startswith("ATL:")
                and self.user.IsWindowVisible(h)
            ]

        self.wait_until(lambda: len(cell_editors()) == 1, "FB cell editor")
        handle = cell_editors()[0]
        if self.control_text(handle) != expected:
            raise BridgeError(
                "Inline variable editor baseline differs; inspect before proceeding."
            )
        return grid, handle

    def restore_for_cell_edit(self):
        """A minimized ActiveX grid can select cells but cannot enter F2 edit."""
        self.validate_main()
        if self.user.IsIconic(self.main):
            if not self.user.ShowWindowAsync(self.main, 9):  # SW_RESTORE
                raise BridgeError(
                    "Cannot restore the target AutoShop window for table editing."
                )
            self.wait_until(
                lambda: not self.user.IsIconic(self.main), "AutoShop window restore"
            )
            self.validate_main()

    def control_text(self, handle):
        length = self.window_message(handle, 0x000E)
        if length > 1024 * 1024:
            raise BridgeError("Unexpected inline editor length.")
        value = ctypes.create_unicode_buffer(length + 1)
        copied = self.window_message(
            handle, 0x000D, length + 1, ctypes.addressof(value)
        )
        if copied != length:
            raise BridgeError("Inline editor text changed during read.")
        return value.value

    def post(self, hwnd, message, value):
        if not self.user.PostMessageW(hwnd, message, value, 0):
            raise BridgeError("Targeted UI message failed.")

    def selector_choices(self, variable, field, expected):
        """Inspect a known combo without committing a definition change."""
        grid, control = self.begin_cell(variable, field, expected)
        try:
            count = self.window_message(control, 0x0146)
            if not 1 <= count <= 4096:
                raise BridgeError("Unsupported selector item count.")
            choices = []
            for i in range(count):
                length = self.window_message(control, 0x0149, i)
                if not 0 <= length <= 512:
                    raise BridgeError("Unsupported selector item length.")
                value = ctypes.create_unicode_buffer(length + 1)
                self.window_message(control, 0x0148, i, ctypes.addressof(value))
                choices.append(value.value)
            return choices
        finally:
            self.post(control, 0x100, 27)
            self.post(control, 0x101, 27)
            self.wait_until(
                lambda: not self.user.IsWindowVisible(control), "selector cancel"
            )

    def set_cell(self, variable, field, expected, value):
        self.write_cell(variable, field, expected, value)
        return self.grid()

    def write_cell(self, variable, field, expected, value):
        """Commit one verified cell; the caller must verify the full batch table.

        Only existing-field set batches defer the whole-table read. Structural
        edits retain set_cell and its immediate full-table verification.
        """
        grid, control = self.begin_cell(variable, field, expected)
        if field in ("data_type", "category"):
            count = self.window_message(control, 0x0146)  # CB_GETCOUNT
            if not 1 <= count <= 4096:
                raise BridgeError("Unsupported data-type selector.")
            choices = []
            for i in range(count):
                length = self.window_message(control, 0x0149, i)
                if not 0 <= length <= 512:
                    raise BridgeError("Unexpected data-type selector item.")
                text = ctypes.create_unicode_buffer(length + 1)
                self.window_message(control, 0x0148, i, ctypes.addressof(text))
                choices.append(text.value)
            if field == "category" and choices != ["VAR", "IN", "OUT", "INOUT"]:
                raise BridgeError("Unsupported FB category selector choices.")
            if choices.count(value) != 1:
                raise BridgeError("Requested data type is unavailable or ambiguous.")
            self.window_message(control, 0x014E, choices.index(value))
        elif field == "initial_value" and value in ("ON", "OFF"):
            count = self.window_message(control, 0x0146)  # CB_GETCOUNT
            if count != 2:
                raise BridgeError("Unsupported BOOL initial-value selector.")
            choices = []
            for i in range(count):
                length = self.window_message(control, 0x0149, i)  # CB_GETLBTEXTLEN
                if length > 32:
                    raise BridgeError("Unexpected BOOL selector item.")
                text = ctypes.create_unicode_buffer(length + 1)
                self.window_message(
                    control, 0x0148, i, ctypes.addressof(text)
                )  # CB_GETLBTEXT
                choices.append(text.value)
            if set(choices) != {"ON", "OFF"}:
                raise BridgeError("Unsupported BOOL initial-value choices.")
            self.window_message(control, 0x014E, choices.index(value))  # CB_SETCURSEL
        else:
            payload = ctypes.create_unicode_buffer(value)
            if not self.window_message(control, 0x000C, 0, ctypes.addressof(payload)):
                raise BridgeError("Inline editor rejected text.")
        if self.control_text(control) != value:
            raise BridgeError("Inline editor text readback differs.")
        if getattr(self, "columns", COLUMNS) == FC_COLUMNS and field == "comment":
            # The observed FC comment editor is multiline: Enter inserts CRLF.
            # A targeted click on this verified row's name commits focus loss.
            self.accessible("select_cell", grid, variable=variable,
                            column=FC_COLUMNS["name"], expected=variable)
        else:
            self.post(control, 0x100, 13)
            self.post(control, 0x101, 13)
        self.wait_until(
            lambda: not self.user.IsWindowVisible(control), "variable edit commit"
        )

    def save(self):
        self.assert_no_cell_edit()
        self.activate()
        # Standard MFC ID_FILE_SAVE; exact active MDI verified above.
        self.post(self.main, 0x0111, 0xE103)
        self.wait_until(lambda: not self.dirty(), "document save", seconds=8)

    def close(self):
        self.assert_no_cell_edit()
        if self.dirty():
            raise BridgeError("Refusing to close a document with unsaved changes.")
        self.activate()
        handle = self.program_window
        self.post(handle, 0x0010, 0)  # WM_CLOSE, only the clean requested MDI.
        self.wait_until(lambda: not self.user.IsWindow(handle), "document close")
        self.program_window = self.hwnd = 0


def snapshot(adapter, target):
    state = adapter.read()
    data = target.read_bytes()
    result = {
        "schema": 1,
        "project": adapter.project,
        "program": adapter.program,
        "target": str(target),
        "pid": adapter.pid,
        "source": state.source.decode("utf-8"),
        "source_sha256": sha256(state.source),
        "native_sha256": sha256(data),
        "modified": adapter.dirty(),
        "variables": None,
        "observed_at": utc_now(),
    }
    if target.suffix.lower() in (".fb", ".fc"):
        result["variables"] = adapter.grid()
    return result


def connect(project, program, pid=None, open_if_missing=False):
    directory, target = resolve_target(project, program)
    adapter = WindowsSession(directory, program, pid)
    adapter.columns = FC_COLUMNS if target.suffix.lower() == ".fc" else COLUMNS
    opened = adapter.ensure_open(open_if_missing)
    return adapter, target, opened


def open_program(project, program, pid=None):
    adapter, target, opened = connect(project, program, pid, True)
    adapter.activate()
    return dict(
        status="editor_opened" if opened else "editor_activated",
        project=adapter.project,
        program=program,
        pid=adapter.pid,
        target=str(target),
    )


def read_program(project, program, pid=None, open_if_missing=False, output=None):
    adapter, target, opened = connect(project, program, pid, open_if_missing)
    value = snapshot(adapter, target)
    value.update(status="editor_read", opened=opened)
    if output is not None:
        write_json_new(output, value)
        return {
            "status": "editor_read",
            "output": str(output.resolve()),
            "program": program,
            "modified": value["modified"],
            "variable_count": len(value["variables"] or []),
            "opened": opened,
        }
    return value


def assert_clean_native(adapter, target, raw, observed=None):
    state = adapter.read()
    container = parse(raw, target.suffix.lower()[1:])
    adapter.assert_no_cell_edit()
    if adapter.dirty() or state.source != container.source:
        raise BridgeError(
            "Document is dirty or cached editor source differs from native file."
        )
    if observed is not None:
        # The caller just captured this complete snapshot. Recheck cheap live
        # state after its grid read; never accept a stale/different target or an
        # edit made while that read was in progress.
        if (
            observed["target"] != str(target)
            or observed["native_sha256"] != sha256(raw)
            or observed["source"].encode("utf-8") != state.source
            or observed["modified"]
        ):
            raise BridgeError("Document baseline changed while taking snapshot.")
        assert_hash(target, observed["native_sha256"])
    if target.suffix.lower() in (".fb", ".fc"):
        rows = observed["variables"] if observed is not None else adapter.grid()
        assert_native_variables(container, rows)
    return container


def close_program(project, program, pid=None):
    adapter, target, _ = connect(project, program, pid)
    raw = target.read_bytes()
    assert_clean_native(adapter, target, raw)
    adapter.close()
    assert_hash(target, sha256(raw))
    return dict(
        status="editor_closed",
        project=adapter.project,
        program=program,
        pid=adapter.pid,
    )


def verify_saved(adapter, target, expected):
    if adapter.dirty() or adapter.read().source.decode("utf-8") != expected["source"]:
        raise BridgeError(
            "Save did not preserve the expected editor source/clean state."
        )
    raw = target.read_bytes()
    container = parse(raw, target.suffix.lower()[1:])
    if container.source.decode("utf-8") != expected["source"]:
        raise BridgeError("Saved native body differs from expected editor body.")
    if expected["variables"] is not None:
        rows = adapter.grid()
        if rows != expected["variables"]:
            raise BridgeError("Variable grid changed during save.")
        assert_native_variables(container, rows)
    return sha256(raw)


def save_snapshot(snapshot_file, pid=None, close_after=False, backup_root=None):
    expected = read_json(snapshot_file)
    if (
        expected.get("schema") != 1
        or not all(
            isinstance(expected.get(k), str)
            for k in ("project", "program", "target", "source", "native_sha256")
        )
        or not isinstance(expected.get("modified"), bool)
        or "variables" not in expected
        or not (
            expected["variables"] is None or isinstance(expected["variables"], list)
        )
    ):
        raise BridgeError("Unsupported editor snapshot.")
    adapter, target, _ = connect(
        Path(expected["project"]),
        expected["program"],
        pid if pid is not None else expected.get("pid"),
    )
    writable_target(target)
    current = snapshot(adapter, target)
    for key in (
        "project",
        "program",
        "target",
        "source",
        "variables",
        "native_sha256",
        "modified",
    ):
        if current[key] != expected.get(key):
            raise BridgeError("Editor snapshot baseline changed: {}.".format(key))
    with target_lock(target):
        raw = assert_hash(target, expected["native_sha256"])
        saved = create_backup(target, raw, backup_root, "editor_save")
        write_json_new(saved / "editor_expected.json", expected)
        # Recheck the buffer and disk after durable backup, before saving.
        check = snapshot(adapter, target)
        for key in ("source", "variables", "native_sha256", "modified"):
            if check[key] != expected[key]:
                raise BridgeError("Editor changed during save backup.")
        assert_hash(target, expected["native_sha256"])
        try:
            adapter.save()
            result_hash = verify_saved(adapter, target, expected)
            if close_after:
                adapter.close()
            result = dict(
                status="editor_saved_closed" if close_after else "editor_saved",
                backup=str(saved),
                target=str(target),
                sha256=result_hash,
                autoshop_compile_verified=False,
            )
            write_json_new(saved / "editor_save_result.json", result)
            return result
        except (BridgeError, OSError) as exc:
            raise BridgeError(
                "{} Save may have changed disk; inspect AutoShop. Backup: {}".format(
                    exc, saved
                )
            ) from exc

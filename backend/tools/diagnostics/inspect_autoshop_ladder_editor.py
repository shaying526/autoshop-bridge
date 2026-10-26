"""Separate experimental live LD reader; not a stable public service API.

Never falls back to disk source. Copy changes selection and briefly owns the
clipboard. The default path preserves only empty/text clipboards and refuses
other formats before sending any command. Explicit scratch-clipboard consent
is an experimental test option, not a general permission to lose user data.
The opt-in supported-HGLOBAL path verifies restoration of its narrow whitelist.
"""

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import time

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from autoshop_bridge.errors import BridgeError
from autoshop_bridge.windows.session import WindowsSession
from autoshop_bridge.formats.st import validate_text
from tools.diagnostics.ladder_clipboard import FORMAT, decode, project_result
from tools.diagnostics.ladder_clipboard_snapshot import snapshot_hglobal, restore_hglobal

MAX_PAYLOAD = 16 * 1024 * 1024
MAX_EMBEDDED_EDITORS = 64
TEXT_FORMATS = {1, 7, 13, 16}
NON_MEMORY_FORMATS = {2, 3, 9, 14, 0x80, 0x82, 0x83, 0x8E}
OLE_METADATA = {"DataObject", "Ole Private Data"}


def open_clipboard_bounded(try_open, last_error, *, timeout=.5,
                           clock=time.monotonic, pause=time.sleep):
    """Wait only for clipboard access; never replay Copy, Paste or an edit.

    Callers still verify sequence/owner after acquisition and before restore.
    An unrelated error stops immediately. The finite attempt bound also holds
    for a broken/nonadvancing clock; no permission or clipboard-format guard
    is relaxed here.
    """
    require(type(timeout) in (int, float) and 0 <= timeout <= .5,
            "Invalid clipboard access wait budget.")
    deadline = clock() + timeout
    for attempt in range(26):
        if try_open():
            return
        error = last_error()
        require(error in (5, 32, 33, 170),
                "Clipboard access failed (Windows error %s); no command replayed." % error)
        remaining = deadline - clock()
        require(remaining > 0 and attempt < 25,
                "Clipboard stayed busy; no copy or edit command replayed.")
        pause(min(.02, remaining))


def require(condition, message):
    if not condition:
        raise BridgeError(message)


def snapshot_text(clipboard):
    """No clipboard mutation; reject unsupported content before any command."""
    with clipboard.opened():
        formats = clipboard.formats()
        require(all(item["format"] in TEXT_FORMATS for item in formats),
                "Clipboard contains non-text formats; preserve it elsewhere and use an "
                "explicit scratch clipboard for this experiment, or copy plain text first.")
        values = {item["format"]: clipboard.data(item["format"]) for item in formats}
        require(sum(len(value) for value in values.values()) <= MAX_PAYLOAD,
                "Clipboard snapshot exceeds limit.")
        return clipboard.sequence(), values


def copy_payload(adapter, clipboard, *, scratch=False, preserve_supported_clipboard=False):
    """Default returns the existing record list; opt-in also returns evidence.

    With preserve_supported_clipboard=True, the result is an object containing
    records and clipboard_restoration (metadata only). Raw recovery bytes never
    leave the snapshot helper or enter the restoration evidence.
    """
    try:
        return _copy_payload(adapter, clipboard, scratch=scratch,
                             preserve_supported_clipboard=preserve_supported_clipboard)
    finally:
        restore = getattr(adapter, "restore_viewport", None)
        if restore:
            restore()


def _copy_payload(adapter, clipboard, *, scratch=False, preserve_supported_clipboard=False):
    """Return raw application formats, preserving supported clipboard state.

    Adapter validates active document before both commands. No retry or paste.
    Scratch is opt-in and leaves the application's copied data on clipboard.
    """
    require(not (scratch and preserve_supported_clipboard),
            "Supported clipboard preservation and scratch clipboard are mutually exclusive.")
    supported_snapshot = None
    supported_result = dict(records=None, clipboard_restoration=None)
    if preserve_supported_clipboard:
        supported_snapshot = snapshot_hglobal(clipboard)
        original_sequence, original = supported_snapshot.sequence, None
    elif scratch:
        original_sequence, original = clipboard.sequence(), None
    else:
        original_sequence, original = snapshot_text(clipboard)
    adapter.validate()
    require(clipboard.sequence() == original_sequence,
            "Clipboard changed before copy; nothing sent.")
    if supported_snapshot is not None:
        require(clipboard.owner_pid() == supported_snapshot.owner_pid,
                "Clipboard owner changed before selection; nothing sent.")
    adapter.select_all()
    # A user copy during selection must not be overwritten by our copy.
    require(clipboard.sequence() == original_sequence,
            "Clipboard changed during selection; copy not sent.")
    if supported_snapshot is not None:
        require(clipboard.owner_pid() == supported_snapshot.owner_pid,
                "Clipboard owner changed during selection; copy not sent.")
    copied_sequence = None
    try:
        adapter.copy()
        copied_sequence = clipboard.sequence()
        require(copied_sequence != original_sequence, "Copy did not update clipboard; no data read.")
        with clipboard.opened():
            require(clipboard.sequence() == copied_sequence, "Clipboard changed after copy.")
            require(clipboard.owner_pid() == adapter.pid,
                    "Clipboard owner is not the selected AutoShop process.")
            formats = clipboard.formats()
            records = []
            for item in formats:
                if item["name"] != FORMAT:
                    records.append(dict(item, skipped="not_observed_ld_format"))
                    continue
                value = clipboard.data(item["format"])
                records.append(dict(item, data=value, size=len(value),
                                    sha256=hashlib.sha256(value).hexdigest()))
            require(sum(item.get("size", 0) for item in records) <= MAX_PAYLOAD,
                    "Combined copy payload exceeds limit.")
            if preserve_supported_clipboard:
                require(clipboard.formats() == formats,
                        "Clipboard format set changed during copy read; no retry.")
                require(clipboard.sequence() == copied_sequence and clipboard.owner_pid() == adapter.pid,
                        "Clipboard changed during copy read; no retry.")
        adapter.validate()
        if preserve_supported_clipboard:
            supported_result["records"] = records
            return supported_result
        return records
    finally:
        # If copy raises after changing the clipboard, restoration is unsafe:
        # its outcome is unknown. Keep the failure explicit and do not retry.
        if supported_snapshot is not None and copied_sequence is not None and copied_sequence != original_sequence:
            supported_result["clipboard_restoration"] = restore_hglobal(
                clipboard, supported_snapshot, expected_current_sequence=copied_sequence,
                expected_owner_pid=adapter.pid)
        elif original is not None and copied_sequence is not None and copied_sequence != original_sequence:
            with clipboard.opened():
                require(clipboard.sequence() == copied_sequence,
                        "Clipboard changed concurrently; original not restored to avoid clobbering newer data.")
                require(clipboard.owner_pid() == adapter.pid,
                        "Clipboard owner changed; original not restored.")
                clipboard.replace(original)


class WinClipboard:
    def __init__(self):
        require(os.name == "nt", "Interactive Windows session required.")
        from ctypes import wintypes as w
        self.w = w
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.user.OpenClipboard.argtypes = [w.HWND]
        self.user.GetClipboardData.argtypes = [w.UINT]
        self.user.GetClipboardData.restype = w.HANDLE
        self.user.SetClipboardData.argtypes = [w.UINT, w.HANDLE]
        self.user.SetClipboardData.restype = w.HANDLE
        self.user.EnumClipboardFormats.argtypes = [w.UINT]
        self.user.GetClipboardOwner.restype = w.HWND
        self.user.GetClipboardFormatNameW.argtypes = [w.UINT, w.LPWSTR, ctypes.c_int]
        self.user.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
        self.user.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            w.HWND, w.HMENU, w.HINSTANCE, ctypes.c_void_p]
        self.user.CreateWindowExW.restype = w.HWND
        self.user.DestroyWindow.argtypes = [w.HWND]
        self.kernel.GlobalSize.argtypes = [w.HGLOBAL]
        self.kernel.GlobalSize.restype = ctypes.c_size_t
        self.kernel.GlobalLock.argtypes = [w.HGLOBAL]
        self.kernel.GlobalLock.restype = ctypes.c_void_p
        self.kernel.GlobalUnlock.argtypes = [w.HGLOBAL]
        self.kernel.GlobalAlloc.argtypes = [w.UINT, ctypes.c_size_t]
        self.kernel.GlobalAlloc.restype = w.HGLOBAL
        self.kernel.GlobalFree.argtypes = [w.HGLOBAL]
        self.kernel.GlobalFree.restype = w.HGLOBAL
        # A real local owner is necessary; OpenClipboard(NULL)+EmptyClipboard
        # would leave no owner and make SetClipboardData fail.
        self.hwnd = self.user.CreateWindowExW(0, "STATIC", "Bridge LD clipboard probe",
                                             0, 0, 0, 0, 0, -3, None, None, None)
        require(bool(self.hwnd), "Cannot create clipboard owner window.")

    def close(self):
        if self.hwnd:
            self.user.DestroyWindow(self.hwnd)
            self.hwnd = 0

    def sequence(self):
        return self.user.GetClipboardSequenceNumber()

    def opened(self):
        from contextlib import contextmanager

        @contextmanager
        def context():
            def attempt():
                ctypes.set_last_error(0)
                return bool(self.user.OpenClipboard(self.hwnd))
            open_clipboard_bounded(attempt, ctypes.get_last_error)
            try:
                yield
            finally:
                self.user.CloseClipboard()
        return context()

    def formats(self):
        result, current = [], 0
        for _ in range(128):
            ctypes.set_last_error(0)
            current = self.user.EnumClipboardFormats(current)
            if not current:
                require(ctypes.get_last_error() == 0, "Clipboard enumeration failed.")
                return result
            name = ctypes.create_unicode_buffer(256)
            self.user.GetClipboardFormatNameW(current, name, len(name))
            result.append(dict(format=current, name=name.value))
        raise BridgeError("Clipboard has too many formats.")

    def owner_pid(self):
        pid = self.w.DWORD()
        self.user.GetWindowThreadProcessId(self.user.GetClipboardOwner(), ctypes.byref(pid))
        return pid.value

    def data(self, format_id):
        require(format_id not in NON_MEMORY_FORMATS, "Non-memory clipboard format refused.")
        handle = self.user.GetClipboardData(format_id)
        require(bool(handle), "Clipboard format could not be rendered.")
        size = self.kernel.GlobalSize(handle)
        require(0 < size <= MAX_PAYLOAD, "Clipboard memory size invalid or exceeds limit.")
        memory = self.kernel.GlobalLock(handle)
        require(bool(memory), "Clipboard memory lock failed.")
        try:
            return ctypes.string_at(memory, size)
        finally:
            self.kernel.GlobalUnlock(handle)

    def replace(self, values):
        handles = {}
        try:
            # Prepare every allocation before EmptyClipboard can lose data.
            for key, value in values.items():
                handle = self.kernel.GlobalAlloc(2, len(value))
                require(bool(handle), "Cannot allocate clipboard restore buffer.")
                handles[key] = handle
                memory = self.kernel.GlobalLock(handle)
                require(bool(memory), "Cannot lock clipboard restore buffer.")
                try:
                    ctypes.memmove(memory, value, len(value))
                finally:
                    self.kernel.GlobalUnlock(handle)
            require(bool(self.user.EmptyClipboard()), "Cannot begin clipboard restoration.")
            for key, handle in list(handles.items()):
                require(bool(self.user.SetClipboardData(key, handle)),
                        "Clipboard restore failed after emptying; may be partially restored.")
                del handles[key]  # The system now owns this handle.
        finally:
            for handle in handles.values():
                self.kernel.GlobalFree(handle)


class LadderWindow(WindowsSession):
    def locate_editor(self, required=True):
        # The base constructor searches for a single ordinary ST editor. LD
        # documents can own several nested Scintillas; locate their root canvas
        # below instead, without changing the public ordinary-ST adapter.
        require(not required, "Use diagram or embedded-source discovery for ladder documents.")
        return False

    def embedded_source_controls(self):
        return [h for h in self.children(self.hwnd) if self.class_name(h) == "Scintilla"
                and self.class_name(self.user.GetParent(h)) == "AfxFrameOrView90u"
                and self.user.GetParent(self.user.GetParent(h)) == self.hwnd]

    def diagram_canvases(self, document):
        """Observed LD root view; an embedded ST editor is a nested view.

        A pure ST view owns Scintilla directly and must not be copied as LD.
        FBs place the canvas below an MDI frame containing the variable grid;
        ordinary LD programs can place it directly below the document. Never
        treat an execution-block's nested editor view as the root canvas.
        """
        result = []
        for view in self.children(document):
            parent = self.user.GetParent(view)
            if self.class_name(view) != "AfxFrameOrView90u" or not (
                    parent == document or self.class_name(parent) == "AfxMDIFrame90u"):
                continue
            if any(self.user.GetParent(k) == view and self.class_name(k) == "Scintilla"
                   for k in self.children(view)):
                continue
            result.append(view)
        return result

    def __init__(self, project, program, pid=None, *, activate=False, whole=False):
        super().__init__(Path(project), program, pid)
        self.whole = whole
        self.scroll_restore = []
        matches = []
        for child in self.children(self.main):
            if self.class_name(self.user.GetParent(child)) != "MDIClient" or not self.program_title_matches(self.text(child)):
                continue
            canvases = self.diagram_canvases(child)
            if len(canvases) == 1:
                matches.append((child, canvases[0]))
        require(len(matches) == 1, "Expected one open diagram window; no source or disk fallback.")
        self.program_window, self.hwnd = matches[0]
        self.before_title = self.text(self.program_window)
        if activate:
            self.validate_main()
            mdi = self.user.GetParent(self.program_window)
            self.window_message(mdi, 0x222, self.program_window)
            self.wait_until(lambda: self.text(self.main).endswith("[" + self.before_title + "]"),
                            "diagram tab activation")
        self.validate()

    def validate(self):
        require(self.window_pid(self.main) == self.pid and self.window_pid(self.hwnd) == self.pid,
                "AutoShop process changed.")
        require(self.title_matches(self.text(self.main)) and self.user.IsWindowEnabled(self.main),
                "Project changed or modal dialog open.")
        require(self.user.IsChild(self.program_window, self.hwnd)
                and self.class_name(self.hwnd) == "AfxFrameOrView90u"
                and self.text(self.program_window) == self.before_title,
                "Diagram document changed.")
        require(self.text(self.main).endswith("[" + self.before_title + "]"),
                "Requested document must be the active tab; no automatic focus guess.")

    def select_all(self):
        self.validate()
        require(not self.embedded_source_controls(),
                "Diagram copy with embedded source is not validated after an IDE exit; "
                "use embedded-source for its currently materialized text editor.")
        # WM_MOUSEACTIVATE performs MFC's active-view routing. Merely setting
        # focus or sending COPY to the canvas can still copy the variable grid.
        self.window_message(self.hwnd, 0x21, self.main, (0x201 << 16) | 1)
        if not self.whole:
            return
        require(not self.user.IsIconic(self.main), "Restore the test window before whole-grid selection.")
        w = self.types

        class Scroll(ctypes.Structure):
            _fields_ = [("size", w.UINT), ("mask", w.UINT), ("minimum", ctypes.c_int),
                        ("maximum", ctypes.c_int), ("page", w.UINT),
                        ("position", ctypes.c_int), ("track", ctypes.c_int)]
        self.scroll_type = Scroll
        self.user.GetScrollInfo.argtypes = [w.HWND, ctypes.c_int, ctypes.POINTER(Scroll)]
        self.user.GetClientRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
        bounds = w.RECT()
        require(bool(self.user.GetClientRect(self.hwnd, ctypes.byref(bounds)))
                and bounds.right >= 180 and bounds.bottom >= 100,
                "Diagram viewport too small for observed header selection.")
        saved = []
        for axis, message in ((0, 0x114), (1, 0x115)):
            info = Scroll()
            info.size, info.mask = ctypes.sizeof(info), 0x17
            require(bool(self.user.GetScrollInfo(self.hwnd, axis, ctypes.byref(info)))
                    and 0 <= info.position <= info.maximum <= 65535,
                    "Unsupported diagram scroll range; nothing selected.")
            saved.append((message, info.position))
        self.scroll_restore = saved
        for message, _ in saved:
            self.window_message(self.hwnd, message, 6)  # SB_TOP / SB_LEFT
        self._selection_click(110, 20, shift=False)
        self.window_message(self.hwnd, 0x115, 7)  # SB_BOTTOM; network range clamps in IDE.
        self._selection_click(110, bounds.bottom - 20, shift=True)
        self.validate()

    def read_embedded_source(self):
        """Read the unique currently materialized nested editor, never COPY.

        Use legacy WM_GETTEXT's OS marshalling, not Scintilla's cross-process
        pointer messages. This does not identify every execution block or map
        the control to a network; absent/ambiguous controls are refused.
        """
        self.validate()
        controls = tuple(sorted(self.embedded_source_controls()))
        require(len(controls) == 1, "Expected one materialized embedded source editor; no disk fallback.")
        state = self._read_embedded_control(controls[0], controls)
        return dict(status="ladder_embedded_editor_source_read_experimental",
                    source="live_windows_scintilla", source_disk_read=False,
                    project=self.project, program=self.program, pid=self.pid,
                    document=self.program_window, canvas=self.hwnd,
                    scope="unique_currently_materialized_embedded_editor", **state,
                    clipboard_used=False, complete_logic_read=False,
                    limitations=["Reads only the unique materialized nested editor, not all blocks.",
                                 "No automatic block opening, network binding, copy, editing or saving."])

    def read_embedded_sources(self, *, offset=0, limit=20):
        """Read all materialized nested editors, then paginate output only."""
        require(0 <= offset and 1 <= limit <= 100, "Invalid embedded source pagination.")
        self.validate()
        controls = tuple(sorted(self.embedded_source_controls()))
        require(0 < len(controls) <= MAX_EMBEDDED_EDITORS,
                "Expected 1..64 materialized embedded editors; no disk fallback.")
        states, total_bytes = [], 0
        for hwnd in controls:
            state = self._read_embedded_control(hwnd, controls)
            total_bytes += len(state["source_text"].encode("utf-8"))
            require(total_bytes <= MAX_PAYLOAD, "Aggregate embedded source size exceeds limit.")
            states.append(state)
        self.validate()
        require(tuple(sorted(self.embedded_source_controls())) == controls,
                "Embedded editor collection changed after reading; no retry.")
        return dict(status="ladder_embedded_editor_sources_read_experimental",
                    source="live_windows_scintilla", source_disk_read=False,
                    project=self.project, program=self.program, pid=self.pid,
                    document=self.program_window, canvas=self.hwnd,
                    scope="all_currently_materialized_embedded_editors",
                    ordering="ascending_window_handle", atomic_snapshot=False,
                    all_blocks_covered=False, native_binding_verified=False,
                    clipboard_used=False, complete_logic_read=False,
                    items=states[offset:offset + limit], total=len(states),
                    offset=offset, limit=limit,
                    next_offset=offset + limit if offset + limit < len(states) else None,
                    limitations=["Materialized controls are not a count of every saved execution block.",
                                 "Two reads protect each control; the collection is not an atomic snapshot.",
                                 "No automatic block opening, network binding, copy, editing or saving."])

    def _read_embedded_control(self, hwnd, controls):
        """Shared guarded text read; no clipboard or file access."""

        def message(code, wparam=0, lparam=0):
            self.validate()
            require(tuple(sorted(self.embedded_source_controls())) == controls
                    and self.user.IsWindow(hwnd) and self.window_pid(hwnd) == self.pid,
                    "Embedded editor was recreated or changed; stop without retry.")
            return self.window_message(hwnd, code, wparam, lparam)

        require(bool(self.user.IsWindowUnicode(hwnd)) and message(2137) == 65001,
                "Embedded source is not the observed Unicode UTF-8 editor.")

        def read_once():
            length = message(0xE)  # WM_GETTEXTLENGTH, marshalled by Windows.
            require(0 <= length <= MAX_PAYLOAD, "Unexpected embedded source size.")
            buffer = ctypes.create_string_buffer(2 * (length + 1))
            copied = message(0xD, length + 1, ctypes.addressof(buffer))
            require(copied == length and message(2006) == length,
                    "Embedded text changed or legacy read is incompatible.")
            raw = buffer.raw[:copied]
            validate_text(raw)
            return raw

        raw = read_once()
        require(read_once() == raw, "Embedded text changed while reading; no retry.")
        modified = bool(message(2159)) or self.before_title.endswith("*")
        self.validate()
        return dict(editor=hwnd,
                    source_text=raw.decode("utf-8"), source_sha256=hashlib.sha256(raw).hexdigest(),
                    source_line_count=raw.count(b"\n") + 1, modified=modified,
                    native_binding_verified=False, network_ordinal=None, reference=None)

    def _selection_click(self, x, y, *, shift):
        point = x | (y << 16)
        self.window_message(self.hwnd, 0x201, 1 | (4 if shift else 0), point)
        self.window_message(self.hwnd, 0x202, 4 if shift else 0, point)

    def viewport_geometry(self):
        from tools.diagnostics.ladder_viewport import window_geometry
        return window_geometry(self)

    def capture_viewport(self, path):
        from tools.diagnostics.inspect_autoshop_compile import capture_png
        self.validate()
        require(not self.user.IsIconic(self.main), "Restore AutoShop before viewport capture.")
        capture_png(self, self.hwnd, path)
        self.validate()

    def restore_viewport(self):
        if self.scroll_restore:
            self.validate()
            scroll_type = self.scroll_type
            self.user.SetScrollInfo.argtypes = [self.types.HWND, ctypes.c_int,
                                               ctypes.POINTER(scroll_type), self.types.BOOL]
            for message, position in self.scroll_restore:
                axis = 0 if message == 0x114 else 1
                info = scroll_type()
                info.size, info.mask, info.position = ctypes.sizeof(info), 4, position
                # This view reads SIF_TRACKPOS, not just WM_*SCROLL's high word.
                self.user.SetScrollInfo(self.hwnd, axis, ctypes.byref(info), True)
                self.window_message(self.hwnd, message, (position << 16) | 4)
                require(bool(self.user.GetScrollInfo(self.hwnd, axis, ctypes.byref(info)))
                        and info.position == position, "Diagram viewport restoration failed.")
            self.scroll_restore = []

    def validate_handles(self):
        # Reuse the existing real MSAA variable-grid reader while validating
        # this diagram canvas instead of requiring a Scintilla source editor.
        self.validate()

    def copy(self):
        self.validate()
        self.window_message(self.main, 0x111, 0xE122, 0)

    def read(self):
        raise BridgeError("Diagram has no Scintilla source; use the LD clipboard decoder.")

    def write(self, source):
        raise BridgeError("This diagnostic does not expose diagram editing.")

    def save(self):
        raise BridgeError("This diagnostic does not save diagrams.")

    def close(self):
        raise BridgeError("This diagnostic does not close diagram tabs.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--program", required=True)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--section", choices=("window", "variables", "embedded-source", "embedded-sources", "viewport", "selection", "diagram"), default="window")
    parser.add_argument("--activate", action="store_true", help="Activate the requested already-open tab only")
    parser.add_argument("--network", type=int, help="Selection-relative network ordinal for paged element output")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--copy", action="store_true", help="Copy the selection; diagram section selects the whole grid")
    parser.add_argument("--scratch-clipboard", action="store_true",
                        help="Explicit prior consent required: clipboard is disposable for this test")
    parser.add_argument("--preserve-supported-clipboard", action="store_true",
                        help="Opt in to strict text/HTML/Chromium HGLOBAL backup and verified restoration")
    parser.add_argument("--output", type=Path, help="New artifact directory for copy JSON or viewport PNG/JSON")
    args = parser.parse_args(argv)
    args.copy = args.copy or args.section in ("selection", "diagram")
    clipboard = None
    try:
        require(not args.scratch_clipboard or args.copy, "Scratch option requires --copy.")
        require(not args.preserve_supported_clipboard or args.copy,
                "Supported clipboard preservation requires --copy.")
        require(not (args.scratch_clipboard and args.preserve_supported_clipboard),
                "Supported clipboard preservation and scratch clipboard are mutually exclusive.")
        require(args.section != "viewport" or (args.output and not args.copy),
                "Viewport requires --output and does not use copy.")
        require(not args.output or args.copy or args.section == "viewport", "Output directory requires copy or viewport.")
        require(args.section != "variables" or not args.copy, "Variable read does not use copy.")
        require(args.section not in ("embedded-source", "embedded-sources") or not args.copy,
                "Embedded source read does not use copy.")
        require(0 <= args.offset and 1 <= args.limit <= 100, "Invalid output pagination.")
        require(args.network is None or args.section in ("selection", "diagram"),
                "Network output requires selection or diagram section.")
        require(args.network is None or args.network >= 1, "Network ordinal must be positive.")
        if args.output:
            require(args.output.is_absolute() and not args.output.exists(),
                    "Output requires a new absolute directory outside the project.")
            require(args.project.resolve() not in args.output.resolve().parents
                    and args.project.resolve() != args.output.resolve(), "Output cannot be inside target project.")
        adapter = LadderWindow(args.project, args.program, args.pid,
                               activate=args.activate, whole=args.section == "diagram")
        if args.section == "viewport":
            from tools.diagnostics.ladder_viewport import capture_viewport, project_viewport
            args.output.mkdir(parents=True)
            result = capture_viewport(adapter, args.output)
            with (args.output / "viewport.json").open("x", encoding="utf-8") as stream:
                json.dump(result, stream, ensure_ascii=True, indent=2)
            response = project_viewport(result, offset=args.offset, limit=args.limit)
            response["output"] = str(args.output / "viewport.json")
            print(json.dumps(response, ensure_ascii=True, indent=2))
            return 0
        if args.section == "embedded-source":
            print(json.dumps(adapter.read_embedded_source(), ensure_ascii=True, indent=2))
            return 0
        if args.section == "embedded-sources":
            print(json.dumps(adapter.read_embedded_sources(offset=args.offset, limit=args.limit),
                             ensure_ascii=True, indent=2))
            return 0
        if args.section == "variables":
            rows = adapter.grid()
            print(json.dumps(dict(status="ladder_editor_variables_read_experimental",
                                  project=adapter.project, program=args.program, pid=adapter.pid,
                                  source="live_windows_msaa", source_disk_read=False,
                                  complete_logic_read=False, modified=adapter.before_title.endswith("*"),
                                  items=rows, total=len(rows)), ensure_ascii=True, indent=2))
            return 0
        clipboard = WinClipboard()
        start = time.perf_counter()
        clipboard_restoration = None
        if args.copy:
            copied = copy_payload(adapter, clipboard, scratch=args.scratch_clipboard,
                                  preserve_supported_clipboard=args.preserve_supported_clipboard)
            if args.preserve_supported_clipboard:
                records, clipboard_restoration = copied["records"], copied["clipboard_restoration"]
            else:
                records = copied
        else:
            with clipboard.opened():
                records = clipboard.formats()
        result = dict(status="ladder_editor_copy_probe" if args.copy else "ladder_editor_window_identified",
                      project=str(args.project.resolve()), program=args.program, pid=adapter.pid,
                      main=adapter.main, document=adapter.program_window, canvas=adapter.hwnd,
                      modified=adapter.before_title.endswith("*"), source="live_windows_clipboard" if args.copy else "window_metadata_only",
                      complete_logic_read=False, source_disk_read=False,
                      clipboard_preserved=bool(args.copy and not args.scratch_clipboard),
                      selection_changed=bool(args.copy), seconds=time.perf_counter() - start,
                      formats=[{key: value for key, value in item.items() if key != "data"} for item in records])
        if args.preserve_supported_clipboard:
            result["clipboard_restoration"] = clipboard_restoration
        if args.section in ("selection", "diagram"):
            payloads = [item["data"] for item in records if item.get("name") == FORMAT and "data" in item]
            require(len(payloads) == 1, "Expected LD Clip Format V3; received " +
                    ", ".join(item["name"] or str(item["format"]) for item in records))
            result.update(decode(payloads[0], whole_requested=args.section == "diagram"))
            result["viewport_restored"] = True
        result["seconds"] = time.perf_counter() - start
        response = project_result(result, network=args.network, offset=args.offset, limit=args.limit) \
            if args.section in ("selection", "diagram") else result
        if args.output:
            args.output.mkdir(parents=True)
            # Never serialize raw allocation capacity: it can contain stale heap bytes.
            with (args.output / "editor.json").open("x", encoding="utf-8") as stream:
                json.dump(result, stream, ensure_ascii=True, indent=2)
        if args.output:
            response["output"] = str(args.output / "editor.json")
        print(json.dumps(response, ensure_ascii=True, indent=2))
        return 0
    except (OSError, BridgeError) as exc:
        print(json.dumps(dict(status="error", error=str(exc), complete_logic_read=False)), file=sys.stderr)
        return 1
    finally:
        if clipboard:
            clipboard.close()


if __name__ == "__main__":
    sys.exit(main())

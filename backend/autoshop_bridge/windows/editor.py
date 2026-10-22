"""Optional Windows adapter for the observed AutoShop UTF-8 Scintilla editor.

Explicit editor commands invoke this adapter. No global input, clipboard,
DLL injection or process-memory access. Lifecycle operations live in session.py.
"""

import ctypes
import os
import re
from dataclasses import dataclass
from pathlib import Path

from autoshop_bridge.errors import BridgeError


@dataclass(frozen=True)
class EditorState:
    source: bytes
    modified: bool = False
    read_only: bool = False
    unicode_window: bool = True
    code_page: int = 65001
    hwnd: int = 0
    pid: int = 0
    title: str = ""


def assert_baseline(state: EditorState, expected: bytes) -> None:
    if not state.unicode_window or state.code_page != 65001:
        raise BridgeError(
            "Only the observed Unicode-window UTF-8 Scintilla adapter is supported."
        )
    if state.read_only:
        raise BridgeError("AutoShop code editor is read-only.")
    if state.modified:
        raise BridgeError(
            "AutoShop code editor has unsaved changes; save and re-export first."
        )
    if state.source != expected:
        raise BridgeError(
            "AutoShop editor source differs from the workspace baseline; refusing sync."
        )


class Win32Editor:
    def __init__(self, project: Path, program: str, pid=None, require_open=True):
        if os.name != "nt":
            raise BridgeError(
                "editor-sync requires an interactive Windows desktop session."
            )
        from ctypes import wintypes

        self.types = wintypes
        self.user = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.callback_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )
        self.user.EnumWindows.argtypes = [self.callback_type, wintypes.LPARAM]
        self.user.EnumChildWindows.argtypes = [
            wintypes.HWND,
            self.callback_type,
            wintypes.LPARAM,
        ]
        self.user.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.user.GetWindowTextW.argtypes = [
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        ]
        self.user.GetClassNameW.argtypes = [
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        ]
        self.user.IsWindowUnicode.argtypes = [wintypes.HWND]
        self.user.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user.IsWindowEnabled.argtypes = [wintypes.HWND]
        self.user.IsIconic.argtypes = [wintypes.HWND]
        self.user.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user.IsChild.argtypes = [wintypes.HWND, wintypes.HWND]
        self.user.SendMessageTimeoutW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
            wintypes.UINT,
            wintypes.UINT,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        self.user.SendMessageTimeoutW.restype = wintypes.LPARAM
        self.kernel.OpenProcess.argtypes = [
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.user.GetParent.argtypes = [wintypes.HWND]
        self.user.GetParent.restype = wintypes.HWND
        self.user.IsWindow.argtypes = [wintypes.HWND]
        self.user.PostMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        self.project, self.program = str(project.resolve(strict=True)), program
        found = []

        @self.callback_type
        def top(hwnd, unused):
            actual_pid = self.window_pid(hwnd)
            if pid is not None and actual_pid != pid:
                return True
            if not self.title_matches(self.text(hwnd)) or not self.is_autoshop(
                actual_pid
            ):
                return True
            found.append((hwnd, actual_pid))
            return True

        if not self.user.EnumWindows(top, 0):
            raise BridgeError(
                "Cannot enumerate desktop windows; run in the interactive Windows user session."
            )
        if len(found) != 1:
            raise BridgeError(
                "Expected one AutoShop project window; found {}. "
                "Use --pid if ambiguous and an interactive desktop.".format(len(found))
            )
        self.main, self.pid = found[0]
        self.program_window = self.hwnd = 0
        self.locate_editor(required=require_open)

    def locate_editor(self, required=True):
        found = []
        for child in self.children(self.main):
            if (
                not self.program_title_matches(self.text(child))
                or self.class_name(self.user.GetParent(child)) != "MDIClient"
            ):
                continue
            for control in self.children(child):
                if self.class_name(
                    control
                ) == "Scintilla" and self.user.IsWindowVisible(control):
                    found.append((child, control))
        if len(found) > 1 or (required and not found):
            raise BridgeError(
                "Expected one AutoShop program editor; found {}. Open target program.".format(
                    len(found)
                )
            )
        if found:
            self.program_window, self.hwnd = found[0]
        return bool(found)

    def window_pid(self, hwnd):
        pid = self.types.DWORD()
        self.user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def text(self, hwnd):
        value = ctypes.create_unicode_buffer(8192)
        self.user.GetWindowTextW(hwnd, value, len(value))
        return value.value

    def class_name(self, hwnd):
        value = ctypes.create_unicode_buffer(256)
        self.user.GetClassNameW(hwnd, value, len(value))
        return value.value

    def title_matches(self, title):
        return bool(
            re.fullmatch(
                r"AutoShop\s+\S+\s{2,}" + re.escape(self.project) + r"(?: - \[.*\])?",
                title,
                re.IGNORECASE,
            )
        )

    def program_title_matches(self, title):
        return title in (self.program, self.program + "*", self.program + " *")

    def is_autoshop(self, pid):
        handle = self.kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            value = ctypes.create_unicode_buffer(32768)
            size = self.types.DWORD(len(value))
            return (
                bool(
                    self.kernel.QueryFullProcessImageNameW(
                        handle, 0, value, ctypes.byref(size)
                    )
                )
                and Path(value.value).name.lower() == "autoshop.exe"
            )
        finally:
            self.kernel.CloseHandle(handle)

    def children(self, hwnd):
        result = []

        @self.callback_type
        def callback(child, unused):
            result.append(child)
            return len(result) < 10000

        self.user.EnumChildWindows(hwnd, callback, 0)
        return result

    def validate_handles(self):
        if (
            self.window_pid(self.main) != self.pid
            or self.window_pid(self.hwnd) != self.pid
            or not self.title_matches(self.text(self.main))
            or not self.program_title_matches(self.text(self.program_window))
            or self.class_name(self.hwnd) != "Scintilla"
            or not self.user.IsChild(self.program_window, self.hwnd)
            or not self.user.IsWindowVisible(self.hwnd)
        ):
            raise BridgeError("Target AutoShop project/program window changed.")
        if not self.user.IsWindowEnabled(self.main):
            raise BridgeError(
                "AutoShop has a modal dialog; handle it before editor-sync."
            )

    def message(self, code, wparam=0, lparam=0):
        return self.window_message(self.hwnd, code, wparam, lparam)

    def window_message(self, hwnd, code, wparam=0, lparam=0):
        result = ctypes.c_size_t()
        if not self.user.SendMessageTimeoutW(
            hwnd, code, wparam, lparam, 2, 1500, ctypes.byref(result)
        ):
            raise BridgeError(
                "AutoShop editor message timed out or was denied (Windows error {}).".format(
                    ctypes.get_last_error()
                )
            )
        return result.value

    def read(self) -> EditorState:
        self.validate_handles()
        unicode_window = bool(self.user.IsWindowUnicode(self.hwnd))
        code_page = self.message(2137)  # SCI_GETCODEPAGE; scalar, no remote pointer.
        if not unicode_window or code_page != 65001:
            raise BridgeError(
                "Unsupported Scintilla window encoding; refusing conversion."
            )
        length = self.message(0x000E)  # WM_GETTEXTLENGTH
        if length > 16 * 1024 * 1024:
            raise BridgeError("Unexpected editor source size.")
        # The observed Unicode Scintilla consumes/returns UTF-8 for legacy
        # messages. W-to-W messaging avoids ANSI conversion. Over-allocate for
        # the OS marshaller, then compare exact UTF-8 bytes against the baseline.
        buffer = ctypes.create_string_buffer(2 * (length + 1))
        copied = self.message(0x000D, length + 1, ctypes.addressof(buffer))
        if copied != length or self.message(2006) != length:  # SCI_GETLENGTH
            raise BridgeError(
                "Editor text changed while reading or legacy message is incompatible."
            )
        source = buffer.raw[:copied]
        try:
            source.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BridgeError(
                "Editor text read-back is not UTF-8; refusing sync."
            ) from exc
        modified = bool(self.message(2159)) or self.text(self.program_window).endswith(
            "*"
        )
        return EditorState(
            source,
            modified,
            bool(self.message(2140)),
            unicode_window,
            code_page,
            self.hwnd,
            self.pid,
            self.text(self.main),
        )

    def write(self, source: bytes) -> None:
        self.validate_handles()
        if (
            not self.user.IsWindowUnicode(self.hwnd)
            or self.message(2137) != 65001
            or self.message(2140)
        ):
            raise BridgeError("Editor is no longer writable UTF-8.")
        # Four NULs terminate either byte parity for the W-message marshaller.
        # WM_SETTEXT is documented compatibility API; never use SCI pointer
        # messages across processes or inject/patch the AutoShop process.
        payload = ctypes.create_string_buffer(source + b"\0" * 4)
        if not self.message(0x000C, 0, ctypes.addressof(payload)):
            raise BridgeError("AutoShop editor rejected WM_SETTEXT.")

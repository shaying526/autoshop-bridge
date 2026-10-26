"""Capture the visible AutoShop compile output for human/AI review, never compile.

Maintainer diagnostic, not a public API. Images are evidence, not parsed results.
No clipboard, LB_GETTEXT, remote pointers, source access or PLC commands.
"""

import argparse
import ctypes
import json
from pathlib import Path
import struct
import sys
import time
import zlib

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from autoshop_bridge.errors import BridgeError

MAX_PAGES = 64
MAX_PIXELS = 20_000_000


def require(condition, message):
    if not condition:
        raise BridgeError(message)


def page_positions(count, visible):
    require(0 <= count <= 4096 and 1 <= visible <= 4096,
            "Unsupported compile list geometry or row count.")
    positions = list(range(0, count, max(1, visible - 1))) or [0]
    require(len(positions) <= MAX_PAGES, "Compile log exceeds 64 capture pages.")
    return positions


def capture_pages(adapter, output):
    """Capture with overlapping rows; no interpretation or freshness inference."""
    signature = adapter.signature()
    count, visible = adapter.geometry()
    positions = page_positions(count, visible)
    original = adapter.position()
    require(0 <= original <= max(0, count - 1), "Invalid original log position.")
    pages = []
    covered = 0
    try:
        for requested in positions:
            require(adapter.signature() == signature, "Compile output changed; capture incomplete.")
            if count:
                adapter.scroll(requested)
            actual = adapter.position()
            require(0 <= actual <= covered and actual <= requested,
                    "Compile pagination skipped rows; capture incomplete.")
            if pages and actual == pages[-1]["top_index"]:
                require(covered >= count, "Compile list failed to scroll; capture incomplete.")
                break
            path = output / "page-{:03d}.png".format(len(pages))
            adapter.capture(path)
            require(adapter.signature() == signature, "Compile output changed during capture.")
            covered = max(covered, min(count, actual + visible))
            pages.append(dict(file=path.name, top_index=actual,
                              last_full_row_exclusive=min(count, actual + visible)))
        require(covered >= count, "Compile capture did not cover every list row.")
    finally:
        # Changed/recreated windows must not receive restoration messages.
        adapter.restore(original)
    return dict(status="compile_output_visual_review_required", compile_outcome="unknown",
                freshness="unknown", structured_log_read=False, atomic_snapshot=False,
                row_count=count, pages=pages, viewport_restored=True,
                source="live_windows_printwindow", clipboard_used=False,
                compile_dispatched=False, plc_commands_sent=False,
                limitations=["No OCR, text parser, automatic success or failure decision.",
                             "Same-count log changes cannot be excluded; non-atomic capture.",
                             "Only the currently visible output list; other tabs are not read.",
                             "Completion messages do not establish zero errors."])


def capture_png(adapter, hwnd, path):
    """Client-only PrintWindow; no third-party image package or process memory."""
    w = adapter.types
    user = adapter.user
    gdi = ctypes.WinDLL("gdi32", use_last_error=True)
    user.GetDC.argtypes, user.GetDC.restype = [w.HWND], w.HDC
    user.ReleaseDC.argtypes = [w.HWND, w.HDC]
    user.PrintWindow.argtypes = [w.HWND, w.HDC, w.UINT]
    user.GetClientRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
    for name, arguments, result in (
        ("CreateCompatibleDC", [w.HDC], w.HDC),
        ("CreateCompatibleBitmap", [w.HDC, ctypes.c_int, ctypes.c_int], w.HBITMAP),
        ("SelectObject", [w.HDC, w.HANDLE], w.HANDLE),
        ("DeleteObject", [w.HANDLE], w.BOOL),
        ("DeleteDC", [w.HDC], w.BOOL),
        ("GetDIBits", [w.HDC, w.HBITMAP, w.UINT, w.UINT, ctypes.c_void_p,
                       ctypes.c_void_p, w.UINT], ctypes.c_int),
    ):
        method = getattr(gdi, name)
        method.argtypes, method.restype = arguments, result

    class Header(ctypes.Structure):
        _fields_ = [("size", w.DWORD), ("width", w.LONG), ("height", w.LONG),
                    ("planes", w.WORD), ("bits", w.WORD), ("compression", w.DWORD),
                    ("image", w.DWORD), ("xp", w.LONG), ("yp", w.LONG),
                    ("used", w.DWORD), ("important", w.DWORD)]

    bounds = w.RECT()
    require(user.GetClientRect(hwnd, ctypes.byref(bounds)), "Cannot query output bounds.")
    width, height = bounds.right, bounds.bottom
    require(width > 0 and height > 0 and width * height <= MAX_PIXELS,
            "Unsupported output image size.")
    dc = user.GetDC(hwnd)
    require(dc, "Cannot acquire output DC.")
    memory = bitmap = previous = 0
    selected = False
    try:
        memory = gdi.CreateCompatibleDC(dc)
        require(memory, "Cannot create image DC.")
        bitmap = gdi.CreateCompatibleBitmap(dc, width, height)
        require(bitmap, "Cannot create output bitmap.")
        previous = gdi.SelectObject(memory, bitmap)
        require(previous and previous != ctypes.c_void_p(-1).value, "Cannot select bitmap.")
        selected = True
        require(user.PrintWindow(hwnd, memory, 1), "PrintWindow failed; no evidence accepted.")
        gdi.SelectObject(memory, previous)
        selected = False
        header = Header(ctypes.sizeof(Header), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        buffer = ctypes.create_string_buffer(width * height * 4)
        require(gdi.GetDIBits(memory, bitmap, 0, height, buffer, ctypes.byref(header), 0) == height,
                "Cannot read output bitmap.")
        bgra = buffer.raw
        rgb = bytearray(width * height * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = bgra[2::4], bgra[1::4], bgra[0::4]
        pixels = b"".join(b"\0" + rgb[y * width * 3:(y + 1) * width * 3]
                          for y in range(height))

        def chunk(kind, value):
            return (struct.pack(">I", len(value)) + kind + value
                    + struct.pack(">I", zlib.crc32(kind + value) & 0xffffffff))

        png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
               + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))
        with path.open("xb") as stream:
            stream.write(png)
    finally:
        if selected:
            gdi.SelectObject(memory, previous)
        if bitmap:
            gdi.DeleteObject(bitmap)
        if memory:
            gdi.DeleteDC(memory)
        user.ReleaseDC(hwnd, dc)


class CompilePanel:
    def __init__(self, project, pid=None):
        # Lazy import: offline test/discovery must not load Windows components.
        from autoshop_bridge.windows.editor import Win32Editor
        self.adapter = a = Win32Editor(project, "__compile_output_diagnostic__", pid, require_open=False)
        panes = [h for h in a.children(a.main) if a.text(h) == "信息输出窗口"
                 and a.class_name(h).startswith("Afx:ControlBar:") and a.user.IsWindowVisible(h)]
        require(len(panes) == 1, "Expected one visible information output pane.")
        self.pane = panes[0]
        lists = [h for h in a.children(self.pane) if a.class_name(h) == "ListBox"
                 and a.user.IsWindowVisible(h)]
        require(len(lists) == 1, "Expected one visible compile output ListBox; no tab switch.")
        self.list = lists[0]
        a.user.GetWindowLongW.argtypes = [a.types.HWND, ctypes.c_int]
        a.user.GetClientRect.argtypes = [a.types.HWND, ctypes.POINTER(a.types.RECT)]
        self.signature()

    def validate(self):
        a = self.adapter
        require(a.user.IsWindow(a.main) and a.is_autoshop(a.pid)
                and a.window_pid(a.main) == a.pid and a.title_matches(a.text(a.main))
                and a.user.IsWindowEnabled(a.main), "Project changed or modal dialog open.")
        require(a.user.IsWindow(self.pane) and a.window_pid(self.pane) == a.pid
                and a.user.IsChild(a.main, self.pane) and a.text(self.pane) == "信息输出窗口"
                and a.user.IsWindowVisible(self.pane) and a.user.IsChild(self.pane, self.list)
                and a.window_pid(self.list) == a.pid and a.class_name(self.list) == "ListBox"
                and a.user.IsWindowVisible(self.list), "Compile output controls changed.")

    def signature(self):
        self.validate()
        a = self.adapter
        style = a.user.GetWindowLongW(self.list, -16) & 0xffffffff
        # Reject multicolumn/variable-height/no-data layouts; row paging is unknown.
        require(not style & (0x20 | 0x200 | 0x2000), "Unsupported compile list layout.")
        count = a.window_message(self.list, 0x18B)  # LB_GETCOUNT, scalar only.
        bounds = a.types.RECT()
        require(a.user.GetClientRect(self.list, ctypes.byref(bounds)), "Cannot query log geometry.")
        row_height = a.window_message(self.list, 0x1A1, 0)  # LB_GETITEMHEIGHT.
        require(0 < row_height <= bounds.bottom and bounds.right > 0,
                "Invalid compile output row geometry.")
        return (a.main, self.pane, self.list, style, count,
                bounds.right, bounds.bottom, row_height)

    def geometry(self):
        signature = self.signature()
        return signature[4], signature[6] // signature[7]

    def position(self):
        self.validate()
        return self.adapter.window_message(self.list, 0x18E)

    def scroll(self, position):
        self.validate()
        result = self.adapter.window_message(self.list, 0x197, position)
        require(result == 0, "Cannot scroll compile output.")

    def restore(self, position):
        self.validate()
        if self.position() != position:
            self.scroll(position)
        require(self.position() == position, "Compile viewport restoration failed.")

    def capture(self, path):
        self.validate()
        capture_png(self.adapter, self.pane, path)
        self.validate()


def output_path(project, output):
    project = project.resolve(strict=True)
    require(project.is_dir(), "Project must be a directory.")
    require(output.is_absolute() and not output.exists(), "Output must be a new absolute directory.")
    resolved = output.resolve()
    require(project != resolved and project not in resolved.parents,
            "Output must be outside the native project.")
    return project, resolved


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    created = False
    try:
        project, output = output_path(args.project, args.output)
        panel = CompilePanel(project, args.pid)
        output.mkdir()  # Existing parent required; never overwrite artifacts.
        created = True
        started = time.time()
        result = capture_pages(panel, output)
        result.update(project=str(project), pid=panel.adapter.pid, main=panel.adapter.main,
                      captured_at_unix=started, elapsed_seconds=time.time() - started)
        with (output / "result.json").open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=True, indent=2)
        print(json.dumps(dict(status=result["status"], compile_outcome="unknown",
                              output=str(output), page_count=len(result["pages"])), ensure_ascii=True))
        return 0
    except (OSError, BridgeError) as exc:
        print(json.dumps(dict(status="error", error=str(exc), compile_outcome="unknown",
                              partial_artifacts_possible=created), ensure_ascii=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

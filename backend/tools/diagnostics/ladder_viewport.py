"""Current LD viewport evidence; never a complete graph or network binding."""

import ctypes

from autoshop_bridge.errors import BridgeError


def require(condition, message):
    if not condition:
        raise BridgeError(message)


def clipped_rect(rect, width, height, visible):
    require(len(rect) == 4 and width > 0 and height > 0
            and rect[0] <= rect[2] and rect[1] <= rect[3], "Invalid viewport geometry.")
    clipped = [max(0, rect[0]), max(0, rect[1]), min(width, rect[2]), min(height, rect[3])]
    return clipped if visible and clipped[0] < clipped[2] and clipped[1] < clipped[3] else None


def window_geometry(adapter):
    adapter.validate()
    user, w = adapter.user, adapter.types
    user.GetClientRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
    user.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(w.RECT)]
    user.ScreenToClient.argtypes = [w.HWND, ctypes.POINTER(w.POINT)]
    bounds = w.RECT()
    require(user.GetClientRect(adapter.hwnd, ctypes.byref(bounds)), "Cannot query canvas size.")
    width, height = bounds.right, bounds.bottom
    require(width > 0 and height > 0, "Canvas has no visible client area.")
    controls = tuple(sorted(adapter.embedded_source_controls()))
    items = []
    for hwnd in controls:
        require(adapter.window_pid(hwnd) == adapter.pid, "Embedded editor process changed.")
        rect = w.RECT()
        require(user.GetWindowRect(hwnd, ctypes.byref(rect)), "Cannot query embedded editor rectangle.")
        left, right = w.POINT(rect.left, rect.top), w.POINT(rect.right, rect.bottom)
        require(user.ScreenToClient(adapter.hwnd, ctypes.byref(left))
                and user.ScreenToClient(adapter.hwnd, ctypes.byref(right)), "Cannot map editor coordinates.")
        rect = [left.x, left.y, right.x, right.y]
        visible = bool(user.IsWindowVisible(hwnd))
        clipped = clipped_rect(rect, width, height, visible)
        items.append(dict(editor=hwnd, parent=int(user.GetParent(hwnd)),
                          window_rect_in_canvas=rect, window_visible=visible,
                          clipped_rect_in_canvas=clipped, intersects_canvas=clipped is not None))
    adapter.validate()
    require(tuple(sorted(adapter.embedded_source_controls())) == controls,
            "Embedded editor collection changed during geometry read.")
    return dict(width=width, height=height, coordinates="canvas_client_pixels",
                rectangle="left_top_right_bottom_exclusive", editors=items)


def capture_viewport(adapter, output):
    """Read every materialized source before/after capture, including offscreen."""
    adapter.validate()
    controls = tuple(sorted(adapter.embedded_source_controls()))
    before = adapter.read_embedded_sources(limit=100) if controls else None
    geometry = adapter.viewport_geometry()
    require(tuple(item["editor"] for item in geometry["editors"]) == controls,
            "Source/geometry editor collection differs.")
    if before:
        require(tuple(item["editor"] for item in before["items"]) == controls,
                "Incomplete materialized source collection.")
    adapter.capture_viewport(output / "preview.png")
    adapter.validate()
    require(tuple(sorted(adapter.embedded_source_controls())) == controls,
            "Embedded editor collection changed after capture.")
    after = adapter.read_embedded_sources(limit=100) if controls else None
    require(before == after, "Embedded source changed during viewport capture; no success result.")
    require(adapter.viewport_geometry() == geometry,
            "Viewport geometry changed during capture; no success result.")
    sources = before["items"] if before else []
    return dict(status="ladder_viewport_read_experimental", image="preview.png",
                source="live_windows_printwindow_and_scintilla", source_disk_read=False,
                scope="current_canvas_viewport_and_materialized_editors",
                project=adapter.project, program=adapter.program, pid=adapter.pid,
                document=adapter.program_window, canvas=adapter.hwnd,
                modified=adapter.before_title.endswith("*") or any(i["modified"] for i in sources), geometry=geometry,
                items=sources, total=len(sources), ordering="ascending_window_handle",
                atomic_snapshot=False, all_blocks_covered=False,
                complete_logic_read=False, native_binding_verified=False,
                clipboard_used=False, selection_changed=False, scroll_changed=False,
                limitations=["Image covers the current canvas viewport only, not the whole diagram.",
                             "Materialized source controls are not a count of all execution blocks.",
                             "Coordinates are window rectangles, not network or element identities.",
                             "Before/after comparisons do not establish an atomic snapshot.",
                             "No OCR, graph parsing, disk fallback, editing, saving or compilation."])


def project_viewport(result, offset=0, limit=20):
    require(offset >= 0 and 1 <= limit <= 100, "Invalid viewport source pagination.")
    return dict(result, items=result["items"][offset:offset + limit], offset=offset, limit=limit,
                next_offset=offset + limit if offset + limit < result["total"] else None)

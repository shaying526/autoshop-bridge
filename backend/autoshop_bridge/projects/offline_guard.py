"""Hold a read-only, share-none HCP handle for the whole offline write batch."""

import sys
from contextlib import contextmanager

from autoshop_bridge.errors import BridgeError, ConflictError, FormatRejection
from autoshop_bridge.formats.st import MAX_NATIVE_SIZE


class OfflineProjectUnavailable(BridgeError):
    code = "offline_project_unavailable"

    def __init__(self, message, *, winerror=None):
        super().__init__(message)
        self.winerror = winerror
        self.requires_close_entire_project = winerror in (32, 33)


def error_code(exc):
    if isinstance(exc, ConflictError):
        return "offline_conflict"
    if isinstance(exc, FormatRejection):
        return exc.code
    if isinstance(exc, OfflineProjectUnavailable):
        return exc.code
    if isinstance(exc, OSError):
        return "offline_project_unavailable"
    return "offline_invalid_request"


@contextmanager
def exclusive_hcp(path):
    """Yield HCP bytes while denying all other read/write/delete opens on Windows.

    This proves an exclusive handle was acquired; it is not proof that no IDE
    process has an old in-memory project. The caller must require a closed
    project and must not release this handle between validation and final reads.
    """
    if sys.platform != "win32":
        raise BridgeError("Offline writes require the Windows exclusive HCP guard.")
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                               ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
    kernel.ReadFile.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(path), 0x80000000, 0, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        code = ctypes.get_last_error()
        reason = "requires_close_entire_project" if code in (32, 33) else "exclusive_hcp_open_failed"
        raise OfflineProjectUnavailable("{}: cannot exclusively open HCP: {}".format(reason, ctypes.WinError(code)), winerror=code)
    try:
        chunks, total = [], 0
        while total <= MAX_NATIVE_SIZE:
            buffer = ctypes.create_string_buffer(min(65536, MAX_NATIVE_SIZE + 1 - total))
            count = wintypes.DWORD()
            if not kernel.ReadFile(handle, buffer, len(buffer), ctypes.byref(count), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if not count.value:
                yield b"".join(chunks)
                return
            chunks.append(buffer.raw[:count.value])
            total += count.value
        raise BridgeError("HCP exceeds supported size limit.")
    finally:
        kernel.CloseHandle(handle)

"""Hold share-none Windows handles throughout guarded offline operations."""

import os
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
    with exclusive_project_file(path) as stream:
        yield read_locked(stream)


def read_locked(stream):
    stream.seek(0)
    raw = stream.read(MAX_NATIVE_SIZE + 1)
    if len(raw) > MAX_NATIVE_SIZE:
        raise BridgeError("Project input exceeds supported size limit.")
    return raw


@contextmanager
def exclusive_project_file(path, *, writable=False):
    if sys.platform != "win32":
        raise BridgeError("Offline writes require the Windows exclusive HCP guard.")
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    access = 0xC0000000 if writable else 0x80000000
    handle = kernel.CreateFileW(str(path), access, 0, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        code = ctypes.get_last_error()
        reason = "requires_close_entire_project" if code in (32, 33) else "exclusive_hcp_open_failed"
        raise OfflineProjectUnavailable("{}: cannot exclusively open {}: {}".format(reason, path.name, ctypes.WinError(code)), winerror=code)
    try:
        fd = msvcrt.open_osfhandle(handle, os.O_BINARY | (os.O_RDWR if writable else os.O_RDONLY))
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(fd, "r+b" if writable else "rb") as stream:
        yield stream

"""Resources and Windows external-launch behavior in source and frozen builds."""

import ctypes
import os
import sys
from contextlib import contextmanager
from pathlib import Path


def resource_path(relative: str) -> Path:
    # PyInstaller sets __file__ relative to the bundled app package too.
    return Path(__file__).resolve().parent / "resources" / relative


@contextmanager
def external_library_search():
    """Keep bundled DLL search paths out of explicitly opened Windows apps."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        yield
        return
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    get_directory = kernel.GetDllDirectoryW
    get_directory.argtypes = [ctypes.c_uint, ctypes.c_wchar_p]
    get_directory.restype = ctypes.c_uint
    set_directory = kernel.SetDllDirectoryW
    set_directory.argtypes = [ctypes.c_wchar_p]
    set_directory.restype = ctypes.c_int
    size = get_directory(0, None)
    buffer = ctypes.create_unicode_buffer(size + 1)
    get_directory(len(buffer), buffer)
    previous = buffer.value or None
    if not set_directory(None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        if not set_directory(previous):
            raise ctypes.WinError(ctypes.get_last_error())

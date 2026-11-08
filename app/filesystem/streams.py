"""Enumerate Windows named data streams without reading their contents."""

import os
from pathlib import Path


def named_streams(path: Path) -> tuple[tuple[str, int], ...]:
    """Return stable (stream suffix, byte length) pairs, excluding the main data.

    Keep the full ':name:$DATA' suffix returned by Windows, including the type,
    when opening a stream. Fail closed if enumeration is not supported or fails.
    """
    if os.name != "nt":
        return ()
    import ctypes
    from ctypes import wintypes

    class StreamData(ctypes.Structure):
        _fields_ = [("size", ctypes.c_longlong), ("name", wintypes.WCHAR * 296)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    first = kernel.FindFirstStreamW
    first.argtypes = [wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(StreamData), wintypes.DWORD]
    first.restype = wintypes.HANDLE
    next_stream = kernel.FindNextStreamW
    next_stream.argtypes = [wintypes.HANDLE, ctypes.POINTER(StreamData)]
    next_stream.restype = wintypes.BOOL
    close = kernel.FindClose
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    data = StreamData()
    handle = first(str(path), 0, ctypes.byref(data), 0)
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.get_last_error()
        if error == 38:  # ERROR_HANDLE_EOF: no streams on this filesystem.
            return ()
        raise OSError(error, "Cannot inspect file streams safely", str(path))
    result = []
    try:
        while True:
            name = data.name
            if name != "::$DATA":
                if not name.startswith(":") or not name.endswith(":$DATA") or any(character in name[1:-6] for character in ":/\\") or data.size < 0:
                    raise ValueError(f"Unsupported file stream: {name}")
                result.append((name, data.size))
            if not next_stream(handle, ctypes.byref(data)):
                error = ctypes.get_last_error()
                if error != 38:
                    raise OSError(error, "Cannot inspect file streams safely", str(path))
                break
    finally:
        close(handle)
    return tuple(sorted(result))


def stream_path(path: Path, suffix: str) -> Path:
    return Path(str(path) + suffix)

"""Bounded retries and read-only removal, without changing ACLs or other flags."""

import os
import stat
import time
from pathlib import Path


def retry_locked(function):
    for attempt in range(5):
        try:
            return function()
        except OSError as error:
            # Access denied is not necessarily a temporary lock. Never retry ACL
            # failures indiscriminately or change permissions to work around them.
            if getattr(error, "winerror", None) not in {32, 33} or attempt == 4:
                raise
            time.sleep(0.1 * (attempt + 1))


def set_readonly(path: Path, readonly: bool) -> None:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        get = kernel.GetFileAttributesW
        get.argtypes, get.restype = [wintypes.LPCWSTR], wintypes.DWORD
        put = kernel.SetFileAttributesW
        put.argtypes, put.restype = [wintypes.LPCWSTR, wintypes.DWORD], wintypes.BOOL
        flags = get(str(path))
        if flags == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        flags = flags | stat.FILE_ATTRIBUTE_READONLY if readonly else flags & ~stat.FILE_ATTRIBUTE_READONLY
        if not put(str(path), flags or stat.FILE_ATTRIBUTE_NORMAL):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        mode = path.stat().st_mode
        path.chmod(mode & ~stat.S_IWUSR if readonly else mode | stat.S_IWUSR)


def remove_file(path: Path, expected: tuple[int, ...] | None = None) -> None:
    """Remove a validated regular file; restore its read-only bit on failure.

    Callers validate policy and content before passing a user source here. An
    expected fingerprint also guards every retry against a changed/replaced file.
    """
    from app.filesystem.file_operations import fingerprint

    before = fingerprint(path)
    if expected is not None and before != expected:
        raise ValueError(f"File changed before removal; retained: {path}")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError(f"Refusing to remove a link or special file: {path}")
    readonly = not bool(info.st_mode & stat.S_IWRITE)
    changed = False
    try:
        if readonly:
            set_readonly(path, False)
            changed = True
        current = fingerprint(path)
        if current[:4] != before[:4]:
            raise ValueError(f"File changed before removal; retained: {path}")

        def remove():
            if fingerprint(path) != current:
                raise ValueError(f"File changed during cleanup; retained: {path}")
            path.unlink()

        retry_locked(remove)
    finally:
        if changed and path.exists() and fingerprint(path)[:2] == before[:2]:
            set_readonly(path, True)

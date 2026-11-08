"""Conservative protection for Windows paths and reparse points."""

import os
import stat
import sys
from pathlib import Path


def check_file_data(path: Path) -> None:
    """Reject special file types not supported by the transfer engine."""
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Only regular files can be transferred.")
    if getattr(info, "st_file_attributes", 0) & (stat.FILE_ATTRIBUTE_ENCRYPTED | stat.FILE_ATTRIBUTE_SYSTEM):
        raise ValueError(f"Encrypted/system files are not supported for moves: {path}")


class SafetyPolicy:
    def __init__(self, roots: list[Path]) -> None:
        self.roots = tuple(root.resolve() for root in roots)

    def allows_candidate(self, path: Path) -> bool:
        """Cheap lexical hover check; worker validation still checks real paths."""
        if not path.is_absolute():
            return False
        return not any(path == root or root in path.parents for root in self.roots)

    def check(self, path: Path) -> Path:
        path = path.absolute()
        # Reject aliases before resolution, including junctions and cloud reparse
        # points. They can otherwise redirect an operation after confirmation.
        for part in (path, *path.parents):
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError(f"Links/reparse-point locations are not supported for moves: {part}")
        resolved = path.resolve(strict=True)
        if any(resolved == root or root in resolved.parents for root in self.roots):
            raise ValueError(f"Protected location: {resolved}")
        return resolved


def default_policy(database_path: Path) -> SafetyPolicy:
    roots = [database_path.parent, Path(__file__).resolve().parents[2], Path(sys.prefix), Path(sys.base_prefix)]
    for key in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "ProgramData", "LOCALAPPDATA", "APPDATA"):
        if os.environ.get(key):
            roots.append(Path(os.environ[key]))
    return SafetyPolicy(roots)

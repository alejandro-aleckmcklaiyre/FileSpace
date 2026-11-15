"""Explicit Windows shell requests using argument lists, never a command shell."""

import os
import subprocess
from pathlib import Path

from app.runtime import external_library_search


def select_in_explorer(path: Path) -> None:
    if os.name != "nt":
        raise OSError("Selecting a file in Explorer requires Windows.")
    explorer = Path(os.environ.get("SystemRoot", "C:/Windows")) / "explorer.exe"
    with external_library_search():
        subprocess.Popen([str(explorer), "/select,", str(path.absolute())], close_fds=True)

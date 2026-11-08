"""Read-only directory validation, suitable for running in a worker."""

import os
from pathlib import Path


def validate_directory(value: str, base: Path | None = None) -> Path:
    """Resolve a directory and check that its entries can be enumerated.

    Raise OSError or ValueError for unavailable or invalid destinations.
    Relative paths are interpreted against the current browsing location.
    """
    if not value.strip():
        raise ValueError("Enter a folder path.")
    path = Path(value).expanduser()
    if not path.is_absolute() and base is not None:
        path = base / path
    path = path.resolve(strict=True)
    if not path.is_dir():
        raise NotADirectoryError(f"Not a folder: {path}")
    with os.scandir(path) as entries:
        next(entries, None)
    return path

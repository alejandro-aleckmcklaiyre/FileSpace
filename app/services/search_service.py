"""Current-directory filename and extension/category matching."""

import re
from functools import lru_cache
from pathlib import Path

CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"},
    "Videos": {".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv"},
    "Documents": {".pdf", ".txt", ".log", ".csv", ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".ppt"},
    "Audio": {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg"},
    "Archives": {".zip", ".7z", ".rar", ".tar", ".gz"},
}


@lru_cache(maxsize=128)
def extensions(value: str) -> frozenset[str]:
    return frozenset("." + part.lstrip("*.").casefold() for part in re.split(r"[,;\s]+", value.strip()) if part.lstrip("*."))


def matches(name: str, is_directory: bool, query: str, extension_filter: str, category: str) -> bool:
    if query.strip().casefold() not in name.casefold():
        return False
    if is_directory:
        return True  # Keep navigation folders when filtering file types.
    suffix = Path(name).suffix.casefold()
    allowed = extensions(extension_filter)
    if allowed and suffix not in allowed:
        return False
    return category not in CATEGORIES or suffix in CATEGORIES[category]

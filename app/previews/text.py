"""Bounded plain-text extraction."""

from pathlib import Path

MAX_TEXT_BYTES = 100_000


def read_text(path: Path) -> str:
    with path.open("rb") as stream:
        data = stream.read(MAX_TEXT_BYTES + 1)
    truncated = len(data) > MAX_TEXT_BYTES
    data = data[:MAX_TEXT_BYTES]
    encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    result = data.decode(encoding, errors="replace")
    return result + ("\n\n[Preview truncated at 100,000 bytes]" if truncated else "")

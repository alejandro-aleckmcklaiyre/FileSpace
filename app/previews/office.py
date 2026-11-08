"""Bounded Office content extraction; never executes embedded content."""

from itertools import islice
from pathlib import Path
from zipfile import ZipFile

MAX_OFFICE_BYTES = 20 * 1024 * 1024
MAX_CHARS = 100_000


def read_office(path: Path) -> tuple[str, object]:
    if path.stat().st_size > MAX_OFFICE_BYTES:
        raise ValueError("Office preview is limited to 20 MiB files.")
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 5000 or sum(entry.file_size for entry in entries) > 64 * 1024 * 1024:
            raise ValueError("Office document exceeds the preview expansion limit (64 MiB / 5,000 entries).")

    if path.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook

        book = load_workbook(path, read_only=True, data_only=True, keep_links=False)
        try:
            sheet = book.worksheets[0]
            rows = [
                [str(value)[:1000] if value is not None else "" for value in row]
                for row in sheet.iter_rows(min_row=1, max_row=100, max_col=20, values_only=True)
            ]
            return "table", (sheet.title, rows)
        finally:
            book.close()

    if path.suffix.lower() == ".docx":
        from docx import Document

        document = Document(path)
        parts = (paragraph.text for paragraph in document.paragraphs)
    else:
        from pptx import Presentation

        presentation = Presentation(path)
        parts = (
            f"Slide {number}: {shape.text}"
            for number, slide in enumerate(presentation.slides, 1)
            for shape in slide.shapes if shape.has_text_frame
        )
    result = []
    remaining = MAX_CHARS
    for part in islice(parts, 5000):
        result.append(part[:remaining])
        remaining -= len(result[-1]) + 1
        if remaining <= 0:
            break
    return "text", "\n".join(result) + "\n\n[Basic text only; up to 100,000 characters / 5,000 blocks]"

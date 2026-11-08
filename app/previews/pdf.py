"""Render one PDF page in a worker, closing its document before returning."""

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtPdf import QPdfDocument


def read_pdf(path: Path, page: int):
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("PDF preview is limited to 50 MiB files.")
    document = QPdfDocument()
    try:
        error = document.load(str(path))
        if error != QPdfDocument.Error.None_:
            raise ValueError(f"PDF could not be opened ({error.name}); it may be corrupt or password protected.")
        count = document.pageCount()
        if not 0 <= page < count:
            raise ValueError("PDF page is unavailable.")
        size = document.pagePointSize(page)
        if size.width() <= 0 or size.height() <= 0:
            raise ValueError("PDF page dimensions are invalid.")
        scale = min(1200 / size.width(), 1600 / size.height())
        image = document.render(page, QSize(max(1, int(size.width() * scale)), max(1, int(size.height() * scale))))
        if image.isNull():
            raise ValueError("PDF page could not be rendered.")
        return image, count
    finally:
        document.close()

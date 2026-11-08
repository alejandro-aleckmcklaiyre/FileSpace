"""Decode a bounded image on a worker thread; GIF uses its first frame."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImageReader


def read_image(path: Path):
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()
    if not size.isValid() or size.width() * size.height() > 40_000_000:
        raise ValueError("Image dimensions are invalid or exceed 40 million pixels.")
    reader.setScaledSize(size.scaled(QSize(1600, 1600), Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    if image.isNull():
        raise ValueError(reader.errorString())
    return image, f"Dimensions: {size.width()} × {size.height()}"

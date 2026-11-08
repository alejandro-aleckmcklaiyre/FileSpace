"""Preview regression checks using disposable, generated documents."""

import tempfile
import shutil
import subprocess
import time
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from PySide6.QtCore import QThreadPool, QUrl
from PySide6.QtGui import QImage, QPainter, QPdfWriter
from PySide6.QtWidgets import QApplication

from app.services.file_preview_service import FilePreviewService, PreviewResult, load_preview
from app.ui.preview_panel import PreviewPanel

APPLICATION = QApplication.instance() or QApplication([])


def wait_until(condition) -> None:
    deadline = time.monotonic() + 15
    while not condition():
        APPLICATION.processEvents()
        if time.monotonic() > deadline:
            raise AssertionError("Preview timed out")
        time.sleep(0.01)
    APPLICATION.processEvents()


class PreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        QThreadPool.globalInstance().waitForDone()
        APPLICATION.processEvents()
        self.temp.cleanup()

    def test_text_bounds_encoding_and_metadata(self) -> None:
        path = self.root / "test.csv"
        path.write_bytes(b"x" * 100_001)
        result = load_preview(str(path))
        self.assertEqual(result.kind, "text")
        self.assertIn("truncated", result.content)
        self.assertLess(len(result.content), 101_000)
        self.assertIn("100,001 bytes", result.metadata)
        path.write_text("Hello Unicode", encoding="utf-16")
        self.assertEqual(load_preview(str(path)).content, "Hello Unicode")

    def test_images_and_invalid_image(self) -> None:
        from PIL import Image

        for extension in ("jpg", "jpeg", "png", "webp", "bmp", "gif"):
            path = self.root / f"image.{extension}"
            Image.new("RGB", (80, 60), "red").save(path)
            result = load_preview(str(path))
            self.assertEqual(result.kind, "image", result.content)
            self.assertFalse(result.content.isNull())
            self.assertIn("80 × 60", result.metadata)
        path.write_bytes(b"corrupt")
        self.assertEqual(load_preview(str(path)).kind, "message")
        with patch("app.previews.image.QImageReader") as reader:
            reader.return_value.size.return_value.width.return_value = 10000
            reader.return_value.size.return_value.height.return_value = 10000
            result = load_preview(str(path))
            self.assertEqual(result.kind, "message")
            reader.return_value.read.assert_not_called()

    def test_pdf_pages_and_corruption(self) -> None:
        path = self.root / "pages.pdf"
        writer = QPdfWriter(str(path))
        painter = QPainter(writer)
        painter.drawText(100, 100, "Page one")
        writer.newPage()
        painter.drawText(100, 100, "Page two")
        painter.end()
        del writer
        result = load_preview(str(path), 1)
        self.assertEqual(result.kind, "pdf", result.content)
        self.assertEqual(result.pages, 2)
        self.assertFalse(result.content.isNull())
        self.assertEqual(load_preview(str(path), 2).kind, "message")
        panel = PreviewPanel()
        panel.show()
        panel.select_file(str(path))
        wait_until(lambda: panel.pages == 2)
        self.assertFalse(panel.previous.isEnabled())
        panel.next.click()
        wait_until(lambda: panel.page == 1)
        self.assertFalse(panel.next.isEnabled())
        panel.previous.click()
        wait_until(lambda: panel.page == 0)
        panel.shutdown()
        panel.close()
        panel.deleteLater()
        path.write_bytes(b"not a PDF")
        self.assertEqual(load_preview(str(path)).kind, "message")

    def test_office_formats(self) -> None:
        from docx import Document
        from openpyxl import Workbook
        from pptx import Presentation

        path = self.root / "document.docx"
        document = Document()
        document.add_paragraph("DOCX preview text")
        document.save(path)
        self.assertIn("DOCX preview text", load_preview(str(path)).content)
        path = self.root / "slides.pptx"
        slides = Presentation()
        slide = slides.slides.add_slide(slides.slide_layouts[1])
        slide.shapes.title.text = "PPTX preview text"
        slides.save(path)
        self.assertIn("PPTX preview text", load_preview(str(path)).content)
        path = self.root / "sheet.xlsx"
        book = Workbook()
        book.active.append(["XLSX", 42])
        book.active.cell(101, 21, "Outside bounds")
        book.save(path)
        book.close()
        result = load_preview(str(path))
        self.assertEqual(result.kind, "table")
        self.assertEqual(result.content[1][0][:2], ["XLSX", "42"])
        self.assertEqual(len(result.content[1]), 100)
        self.assertEqual(len(result.content[1][0]), 20)
        for extension in ("docx", "xlsx", "pptx"):
            path = self.root / f"broken.{extension}"
            path.write_bytes(b"invalid zip")
            self.assertEqual(load_preview(str(path)).kind, "message")

    def test_missing_unsupported_permission_and_video_dispatch(self) -> None:
        self.assertEqual(load_preview(str(self.root / "missing.txt")).kind, "message")
        path = self.root / "unknown.bin"
        path.write_bytes(b"data")
        self.assertIn("not available", load_preview(str(path)).content)
        with patch("app.services.file_preview_service.Path.stat", side_effect=PermissionError("Denied")):
            self.assertIn("Denied", load_preview(str(path)).content)
        for extension in ("mp4", "mkv", "mov", "avi"):
            path = self.root / f"video.{extension}"
            path.touch()
            self.assertEqual(load_preview(str(path)).kind, "video")

    def test_stale_results_and_coalescing(self) -> None:
        service = FilePreviewService()
        started, release = Event(), Event()
        seen = []
        service.ready.connect(seen.append)

        def delayed(path, page):
            if path == "old":
                started.set()
                release.wait(5)
            return PreviewResult(path, "text", path)

        with patch("app.services.file_preview_service.load_preview", side_effect=delayed):
            service.request("old")
            wait_until(started.is_set)
            service.request("skipped")
            service.request("latest")
            release.set()
            wait_until(lambda: bool(seen))
            self.assertEqual([item.path for item in seen], ["latest"])
            service.cancel()

    def test_document_size_limits(self) -> None:
        from zipfile import ZIP_DEFLATED, ZipFile

        for name, size in (("large.docx", 20 * 1024 * 1024 + 1), ("large.pdf", 50 * 1024 * 1024 + 1)):
            path = self.root / name
            with path.open("wb") as stream:
                stream.truncate(size)
            result = load_preview(str(path))
            self.assertEqual(result.kind, "message")
            self.assertIn("limited", result.content)
        path = self.root / "many_entries.docx"
        with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
            for number in range(5001):
                archive.writestr(str(number), "")
        self.assertIn("expansion limit", load_preview(str(path)).content)

    def test_panel_selection_hide_and_media_cleanup(self) -> None:
        panel = PreviewPanel()
        panel.show()
        path = self.root / "note.txt"
        path.write_text("Visible text", encoding="utf-8")
        panel.select_file(str(path))
        wait_until(lambda: panel.text.toPlainText() == "Visible text")
        self.assertTrue(panel.text.isReadOnly())
        panel.hide()
        self.assertEqual(panel.text.toPlainText(), "")
        self.assertTrue(panel.player.source().isEmpty())
        panel.show()
        wait_until(lambda: panel.text.toPlainText() == "Visible text")
        panel.select_file("")
        self.assertEqual(panel.text.toPlainText(), "")
        panel.player.setSource(QUrl.fromLocalFile(str(self.root / "missing.mp4")))
        panel.shutdown()
        self.assertTrue(panel.player.source().isEmpty())
        panel.close()
        panel.deleteLater()

    @unittest.skipUnless(shutil.which("ffmpeg"), "Optional FFmpeg fixture generator is unavailable")
    def test_real_video_decode_and_cleanup(self) -> None:
        panel = PreviewPanel()
        panel.show()
        frames = []
        panel.video.videoSink().videoFrameChanged.connect(
            lambda frame: frames.append(frame.isValid())
        )
        try:
            for extension in ("mp4", "mkv", "mov", "avi"):
                with self.subTest(extension=extension):
                    path = self.root / f"clip.{extension}"
                    subprocess.run(
                        [shutil.which("ffmpeg"), "-v", "error", "-f", "lavfi", "-i",
                         "color=c=blue:s=160x120:r=10", "-t", "1", "-c:v", "mpeg4", str(path)],
                        check=True, capture_output=True, timeout=15,
                    )
                    frames.clear()
                    panel.select_file(str(path))
                    wait_until(lambda: panel.player.duration() > 0)
                    panel.play.click()
                    wait_until(lambda: any(frames))
                    self.assertIn("Duration:", panel.metadata.toPlainText())
                    panel.hide()
                    self.assertTrue(panel.player.source().isEmpty())
                    panel.select_file("")
                    panel.show()
        finally:
            panel.shutdown()
            panel.close()
            panel.deleteLater()


if __name__ == "__main__":
    unittest.main()

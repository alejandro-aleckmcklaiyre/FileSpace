"""Explicit --smoke-test checks; only generated temporary files are operated on."""

import importlib
import json
import logging
import stat
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

from PySide6.QtCore import QEvent, QThreadPool, QTimer
from PySide6.QtGui import QImage, QPainter, QPdfWriter
from PySide6.QtWidgets import QMessageBox

from app.diagnostics import configure_logging
from app.filesystem.cleanup import set_readonly
from app.filesystem.file_operations import build_plan, transfer_file
from app.filesystem.safety import SafetyPolicy, default_policy
from app.runtime import resource_path
from app.services.file_action_service import FileActionService
from app.services.file_operation_service import FileOperationService
from app.ui.main_window import MainWindow


def run(application, report_path: Path) -> int:
    report_path = report_path.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    # A self-test must never overwrite an existing user report/file.
    output = report_path.open("x", encoding="utf-8")
    temporary = tempfile.TemporaryDirectory(prefix="filespace-smoke-")
    root = Path(temporary.name).resolve()
    source, destination, state = root / "source", root / "destination", root / "state"
    source.mkdir()
    destination.mkdir()
    configure_logging(state)
    application.setQuitOnLastWindowClosed(False)
    report = {
        "date_utc": datetime.now(UTC).isoformat(), "frozen": bool(getattr(sys, "frozen", False)),
        "executable": sys.executable, "working_directory": str(Path.cwd()), "checks": [],
        "manual_checks": ["Explorer mouse drag/drop", "real cross-drive/removable-drive behavior", "Windows Recycle Bin restore", "external associations/audio", "clean Windows machine"],
    }
    unexpected = []
    window = None

    def reject_unexpected_dialogs():
        dialog = application.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            unexpected.append(dialog.text())
            dialog.reject()

    guard = QTimer()
    guard.timeout.connect(reject_unexpected_dialogs)
    guard.start(100)

    def wait_until(condition, seconds=20):
        deadline = time.monotonic() + seconds
        while not condition():
            application.processEvents()
            if unexpected:
                raise RuntimeError("Unexpected dialog: " + unexpected[-1])
            if time.monotonic() > deadline:
                raise TimeoutError("Packaged check timed out")
            time.sleep(0.01)
        application.processEvents()

    def job(function):
        runner = FileOperationService(window)
        completed = []
        runner.finished.connect(lambda name, result, error: completed.append((result, error)))
        runner.start("packaged-check", function)
        wait_until(lambda: bool(completed))
        result, error = completed[0]
        runner.deleteLater()
        if error:
            raise RuntimeError(error)
        return result

    def check(name, function):
        try:
            detail = function()
            report["checks"].append({"name": name, "status": "passed", "detail": str(detail or "OK")})
        except Exception as error:
            logging.getLogger(__name__).exception("Packaged check failed: %s", name)
            report["checks"].append({"name": name, "status": "failed", "detail": str(error)})

    def make_fixtures():
        from docx import Document
        from openpyxl import Workbook
        from pptx import Presentation

        image = QImage(100, 80, QImage.Format.Format_RGB32)
        image.fill(0xFF2374AB)
        assert image.save(str(source / "image.png"))
        (source / "note.txt").write_text("FileSpace packaged text preview", encoding="utf-8")
        (source / "operation.txt").write_bytes(b"FileSpace verified transfer fixture")
        (source / "rename-me.txt").write_bytes(b"rename fixture")
        pdf = QPdfWriter(str(source / "document.pdf"))
        painter = QPainter(pdf)
        painter.drawText(100, 100, "FileSpace packaged PDF")
        painter.end()
        del pdf
        document = Document()
        document.add_paragraph("FileSpace DOCX fixture")
        document.save(source / "document.docx")
        workbook = Workbook()
        workbook.active.append(["FileSpace", 42])
        workbook.save(source / "sheet.xlsx")
        workbook.close()
        presentation = Presentation()
        slide = presentation.slides.add_slide(presentation.slide_layouts[1])
        slide.shapes.title.text = "FileSpace PPTX fixture"
        presentation.save(source / "slides.pptx")

    def checks():
        nonlocal window
        try:
            make_fixtures()
            window = MainWindow(state / "filespace.sqlite3", SafetyPolicy([state]), initial_location=source)
            window.show()
            wait_until(lambda: window.quick_sort.initialized and not window.quick_sort.busy)
            wait_until(lambda: window.explorer.model.rowCount(window.explorer.active_view.rootIndex()) == 8)

            def gui():
                assert window.isVisible() and window.windowTitle() == "FileSpace"
                assert not application.windowIcon().isNull()
                window.resize(900, 480)
                application.processEvents()
                assert all(value > 0 for value in window.splitter.sizes())
                window.navigation.view_mode.setCurrentText("Grid")
                assert window.explorer.grid.dragEnabled() and window.explorer.grid.viewport().acceptDrops()
                assert window.explorer.details.dragEnabled() and window.explorer.details.viewport().acceptDrops()
                window.explorer.set_filters("note", ".txt", "Documents")
                assert window.explorer.model.rowCount(window.explorer.active_view.rootIndex()) == 1
                window.explorer.set_filters("", "", "All files")
                return "Rendered window, icon, minimum size, grid, and filters"
            check("window_and_browsing", gui)

            for filename, widget in (("image.png", "image_label"), ("document.pdf", "image_label"), ("note.txt", "text"), ("document.docx", "text"), ("sheet.xlsx", "table"), ("slides.pptx", "text")):
                def preview(filename=filename, widget=widget):
                    window.preview.select_file(str(source / filename))
                    wait_until(lambda: window.preview.service.idle and window.preview.stack.currentWidget() is getattr(window.preview, widget))
                    if widget == "image_label":
                        assert not window.preview.image_label.pixmap().isNull()
                    elif widget == "text":
                        assert "FileSpace" in window.preview.text.toPlainText()
                    else:
                        assert window.preview.table.item(0, 0).text() == "FileSpace"
                check("preview_" + filename, preview)

            def video():
                fixture = resource_path("smoke/clip.mp4")
                assert fixture.is_file()
                frames = []
                window.preview.video.videoSink().videoFrameChanged.connect(lambda frame: frames.append(frame.isValid()))
                window.preview.select_file(str(fixture))
                wait_until(lambda: window.preview.player.duration() > 0)
                window.preview.player.play()
                wait_until(lambda: any(frames))
                window.preview.select_file("")
                assert window.preview.player.source().isEmpty()
                return "Bundled Qt multimedia backend decoded a video frame"
            check("video_decode_and_release", video)

            def transfers():
                service = window.quick_sort.service
                path = source / "operation.txt"
                plan = job(lambda progress: service.plan([str(path)], str(destination), "copy"))
                results = job(lambda progress: service.transfer(plan, ["copy"], Event(), progress))
                assert results[0].status == "copied" and path.exists()
                plan = job(lambda progress: service.plan([str(path)], str(destination), "copy"))
                results = job(lambda progress: service.transfer(plan, ["rename"], Event(), progress))
                assert results[0].status == "copied" and Path(results[0].destination).name != path.name
                other = root / "other"
                other.mkdir()
                plan = job(lambda progress: service.plan([str(path)], str(other), "move"))
                results = job(lambda progress: service.transfer(plan, ["move"], Event(), progress))
                assert results[0].status == "moved" and not path.exists()
                assert (other / path.name).read_bytes() == b"FileSpace verified transfer fixture"
                action = FileActionService(window.quick_sort.repository, window.quick_sort.service.policy)
                plan = job(lambda progress: action.plan_rename(str(source / "rename-me.txt"), "renamed"))
                results = job(lambda progress: action.execute(plan, Event(), progress))
                assert results[0].status == "renamed"
                return "Verified copy, conflict rename, move, rename, and history"
            check("disposable_file_operations", transfers)

            def readonly_cleanup():
                fixture = root / "readonly-source.txt"
                fixture.write_bytes(b"read-only verified fixture")
                folder = root / "readonly-destination"
                folder.mkdir()
                target = folder / fixture.name
                target.write_bytes(b"previous contents")
                set_readonly(fixture, True)
                set_readonly(target, True)
                policy = window.quick_sort.service.policy
                try:
                    plan = job(lambda progress: build_plan([str(fixture)], str(folder), policy, "copy"))
                    result = job(lambda progress: transfer_file(plan, plan.items[0], "replace", policy, progress))
                    assert result.status == "copied", result.message
                    assert not target.stat().st_mode & stat.S_IWRITE
                    assert not list(folder.glob(".filespace-*"))
                    move_folder = root / "readonly-move"
                    move_folder.mkdir()
                    plan = job(lambda progress: build_plan([str(fixture)], str(move_folder), policy, "move"))
                    result = job(lambda progress: transfer_file(plan, plan.items[0], "move", policy, progress))
                    assert result.status == "moved" and not fixture.exists(), result.message
                    moved = Path(result.destination)
                    assert not moved.stat().st_mode & stat.S_IWRITE
                    assert moved.read_bytes() == b"read-only verified fixture"
                    set_readonly(moved, False)
                    empty = root / "zero-byte.txt"
                    empty.touch()
                    for decision in ("copy", "replace"):
                        plan = job(lambda progress: build_plan([str(empty)], str(folder), policy, "copy"))
                        result = job(lambda progress, plan=plan, decision=decision: transfer_file(plan, plan.items[0], decision, policy, progress))
                        assert result.status == "copied" and Path(result.destination).stat().st_size == 0
                    return "Read-only Replace/Move preserve attributes without backups; zero-byte copy/replace verified"
                finally:
                    for owned in (fixture, target, root / "readonly-move/readonly-source.txt"):
                        if owned.exists():
                            set_readonly(owned, False)
            check("readonly_cleanup_and_zero_byte", readonly_cleanup)

            def restart():
                nonlocal window
                repository = window.quick_sort.repository
                job(lambda progress: repository.save_favorite("Fixture", str(source)))
                job(lambda progress: window.quick_sort.service.save("F", "Fixture", str(destination)))
                window.close()
                window.deleteLater()
                application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                window = MainWindow(state / "filespace.sqlite3", SafetyPolicy([state]), initial_location=source)
                window.show()
                wait_until(lambda: window.quick_sort.initialized and not window.quick_sort.busy)
                assert window.favorites.folders.count() == 1
                assert window.quick_sort.shortcuts.count() == 1
                assert window.navigation.view_mode.currentText() == "Grid"
                assert len(job(lambda progress: repository.history())) == 4
                return "Shortcuts, favorites, view mode, and history survived restart"
            check("persistence_restart", restart)

            def bundle():
                modules = [importlib.import_module(name) for name in ("PySide6", "docx", "openpyxl", "pptx", "sqlite3", "lxml.etree")]
                paths = {module.__name__: str(Path(module.__file__).resolve()) for module in modules}
                report["module_paths"] = paths
                policy = default_policy(state / "filespace.sqlite3")
                if getattr(sys, "frozen", False):
                    bundle_root = Path(sys._MEIPASS).resolve()
                    assert all(Path(path).is_relative_to(bundle_root) for path in paths.values())
                    assert Path(sys.executable).resolve().parent in policy.roots
                    assert not policy.allows_candidate(Path(sys.executable).resolve())
                return "Resource/import paths and executable-folder protection checked"
            check("bundle_isolation_and_safety", bundle)
            if unexpected:
                report["checks"].append({"name": "unexpected_dialogs", "status": "failed", "detail": unexpected})
        except Exception as error:
            report["checks"].append({"name": "smoke_setup", "status": "failed", "detail": str(error)})
        finally:
            if window is not None:
                window.preview.shutdown()
                window.close()
                window.deleteLater()
            QThreadPool.globalInstance().waitForDone(30000)
            application.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            guard.stop()
            report["passed"] = bool(report["checks"]) and all(item["status"] == "passed" for item in report["checks"])
            logging.shutdown()
            try:
                temporary.cleanup()
            except OSError as error:
                report["passed"] = False
                report["cleanup_error"] = str(error)
            json.dump(report, output, indent=2)
            output.close()
            application.exit(0 if report["passed"] else 1)

    QTimer.singleShot(0, checks)
    return application.exec()

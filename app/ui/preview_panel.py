"""Preview presentation, media lifecycle, and metadata."""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QSlider, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.services.file_preview_service import FilePreviewService, PreviewResult


class PreviewPanel(QWidget):
    """Keep decoding in workers and Qt multimedia's asynchronous backend."""

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(200)
        self.path = ""
        self.page = 0
        self.pages = 0
        self._image = None
        self._metadata = ""
        self.service = FilePreviewService(self)
        self.service.ready.connect(self._display)
        layout = QVBoxLayout(self)
        heading = QLabel("Preview")
        heading.setObjectName("panelHeading")
        layout.addWidget(heading)
        self.message = QLabel("No file selected")
        self.message.setWordWrap(True)
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.message)
        self.stack = QStackedWidget()
        self.blank = QWidget()
        self.image_label = QLabel()
        self.image_label.setMinimumSize(1, 1)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.video = QVideoWidget()
        for widget in (self.blank, self.image_label, self.text, self.table, self.video):
            self.stack.addWidget(widget)
        layout.addWidget(self.stack, 1)

        self.pdf_controls = QWidget()
        controls = QHBoxLayout(self.pdf_controls)
        self.previous = QPushButton("Previous")
        self.page_label = QLabel()
        self.next = QPushButton("Next")
        for widget in (self.previous, self.page_label, self.next):
            controls.addWidget(widget)
        self.previous.clicked.connect(lambda: self._request_page(self.page - 1))
        self.next.clicked.connect(lambda: self._request_page(self.page + 1))
        layout.addWidget(self.pdf_controls)

        self.media_controls = QWidget()
        controls = QHBoxLayout(self.media_controls)
        self.play = QPushButton("Play")
        self.position = QSlider(Qt.Orientation.Horizontal)
        self.position.setAccessibleName("Video position")
        controls.addWidget(self.play)
        controls.addWidget(self.position, 1)
        layout.addWidget(self.media_controls)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.play.clicked.connect(self._toggle_play)
        self.position.sliderMoved.connect(self.player.setPosition)
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.playbackStateChanged.connect(
            lambda state: self.play.setText("Pause" if state == QMediaPlayer.PlaybackState.PlayingState else "Play")
        )
        self.player.errorOccurred.connect(self._media_error)
        self.player.mediaStatusChanged.connect(self._media_status)
        self.metadata = QPlainTextEdit()
        self.metadata.setReadOnly(True)
        self.metadata.setAccessibleName("File metadata")
        self.metadata.setMaximumHeight(155)
        layout.addWidget(self.metadata)
        self._clear()

    def _clear(self) -> None:
        self.service.cancel()
        self.player.stop()
        self.player.setSource(QUrl())
        self._image = None
        self.image_label.clear()
        self.text.clear()
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self.metadata.clear()
        self.stack.setCurrentWidget(self.blank)
        self.pdf_controls.hide()
        self.media_controls.hide()
        self.position.setValue(0)
        self.position.setRange(0, 0)

    def select_file(self, path: str) -> None:
        self.path = path
        self.page = 0
        self._clear()
        self.message.setText("Loading preview…" if path else "Select a file to preview.")
        if path and self.isVisible():
            self.service.request(path)

    def _request_page(self, page: int) -> None:
        if 0 <= page < self.pages:
            self.message.setText("Loading PDF page…")
            self.previous.setEnabled(False)
            self.next.setEnabled(False)
            self.service.request(self.path, page)

    def _display(self, result: PreviewResult) -> None:
        if result.path != self.path or not self.isVisible():
            return
        self._metadata = result.metadata
        self.metadata.setPlainText(result.metadata)
        self.message.setText("")
        if result.kind in {"image", "pdf"}:
            self._image = result.content
            self.stack.setCurrentWidget(self.image_label)
            self._scale_image()
            if result.kind == "pdf":
                self.page, self.pages = result.page, result.pages
                self.page_label.setText(f"{self.page + 1} / {self.pages}")
                self.previous.setEnabled(self.page > 0)
                self.next.setEnabled(self.page + 1 < self.pages)
                self.pdf_controls.show()
        elif result.kind == "text":
            self.text.setPlainText(result.content)
            self.stack.setCurrentWidget(self.text)
        elif result.kind == "table":
            name, rows = result.content
            self.message.setText(f"{name}: first 100 rows × 20 columns; cached formula values only.")
            self.table.setRowCount(len(rows))
            self.table.setColumnCount(20)
            for row, values in enumerate(rows):
                for column, value in enumerate(values):
                    self.table.setItem(row, column, QTableWidgetItem(value))
            self.stack.setCurrentWidget(self.table)
        elif result.kind == "video":
            self.stack.setCurrentWidget(self.video)
            self.media_controls.show()
            self.message.setText("Loading video…")
            self.player.setSource(QUrl.fromLocalFile(result.path))
        else:
            self.stack.setCurrentWidget(self.blank)
            self.pdf_controls.hide()
            self.message.setText(str(result.content))

    def _scale_image(self) -> None:
        if self._image is not None:
            self.image_label.setPixmap(QPixmap.fromImage(self._image).scaled(
                self.image_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._scale_image()

    def hideEvent(self, event) -> None:
        self._clear()
        super().hideEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self.path:
            self.message.setText("Loading preview…")
            self.service.request(self.path, self.page)

    def shutdown(self) -> None:
        self._clear()

    def _toggle_play(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _position_changed(self, position: int) -> None:
        if not self.position.isSliderDown():
            self.position.setValue(position)

    def _duration_changed(self, duration: int) -> None:
        self.position.setRange(0, duration)
        if self.player.source().isValid():
            self.metadata.setPlainText(self._metadata + f"\nDuration: {duration / 1000:.1f} seconds")

    def _media_status(self, status) -> None:
        if self.player.source().isEmpty():
            return
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            self.message.setText("Press Play to preview video.")

    def _media_error(self, error, message: str) -> None:
        if self.player.source().isValid() and error != QMediaPlayer.Error.NoError:
            self.message.setText(f"Video unavailable: {message}. Codec support depends on this Windows installation.")

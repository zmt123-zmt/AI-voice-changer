from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QLine, QObject, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import audio_io


class AudioPlayer(QObject):
    playing_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._timer = QTimer(self)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._poll)
        self._data: np.ndarray | None = None
        self._sr = 48000

    def play(self, data: np.ndarray, sr: int) -> None:
        self.stop()
        import sounddevice as sd

        self._data = np.asarray(data, dtype=np.float32)
        self._sr = int(sr)
        try:
            sd.play(self._data, self._sr)
            self._timer.start()
            self.playing_changed.emit(True)
        except Exception:
            self.playing_changed.emit(False)

    def play_file(self, path: str | Path) -> None:
        sr, data = audio_io.decode_audio(path)
        self.play(data, sr)

    def stop(self) -> None:
        import sounddevice as sd

        try:
            sd.stop()
        except Exception:
            pass
        self._timer.stop()
        self._data = None
        self.playing_changed.emit(False)

    def _poll(self) -> None:
        import sounddevice as sd

        try:
            stream = sd.get_stream()
        except Exception:
            stream = None
        if stream is None:
            self._timer.stop()
            self._data = None
            self.playing_changed.emit(False)


class WaveformWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._data: np.ndarray | None = None
        self._peaks: np.ndarray | None = None  # 按当前像素宽度预计算的峰值（避免每次重绘全量计算）
        self._peaks_width = 0
        self.setMinimumHeight(72)

    def set_data(self, data: np.ndarray | None) -> None:
        self._data = np.asarray(data, dtype=np.float32) if data is not None else None
        self._peaks = None
        self._peaks_width = 0
        self.update()

    def _peaks_for_width(self, w: int) -> np.ndarray:
        """把音频压缩到 w 个像素列，每列取峰值；结果缓存，仅在宽度变化时重算。"""
        if self._peaks is not None and self._peaks_width == w:
            return self._peaks
        x = self._data
        n = len(x)
        if n == 0:
            peaks = np.zeros(0, dtype=np.float32)
        elif n <= w:
            peaks = np.abs(x[:w])
        else:
            step = max(1, n // w)
            usable = (n // step) * step
            peaks = np.max(np.abs(x[:usable].reshape(-1, step)), axis=1).astype(np.float32)
        self._peaks = peaks
        self._peaks_width = w
        return peaks

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#f8fafc"))
        p.setPen(QPen(QColor("#e2e8f0"), 1))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if self._data is None or len(self._data) == 0:
            p.setPen(QColor("#94a3b8"))
            p.drawText(self.rect(), 0x84, "暂无音频")
            return
        w, h = self.width(), self.height()
        peaks = self._peaks_for_width(w - 4)
        mid = h / 2
        scale = 0.9 * mid
        lines = [
            QLine(2 + i, mid - max(1.0, float(v) * scale), 2 + i, mid + max(1.0, float(v) * scale))
            for i, v in enumerate(peaks)
        ]
        p.setPen(QPen(QColor("#0f766e"), 1.4))
        if lines:
            p.drawLines(lines)


class LevelMeter(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._level = 0.0
        self.setMinimumSize(160, 14)

    def set_level(self, level: float) -> None:
        self._level = float(np.clip(level, 0.0, 1.0))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#e2e8f0"))
        w = int(self.width() * self._level)
        if w > 0:
            color = QColor("#0f766e") if self._level < 0.9 else QColor("#b45309")
            p.fillRect(0, 0, w, self.height(), color)


class FileField(QWidget):
    path_changed = Signal(str)

    def __init__(self, placeholder: str = "", file_filter: str = "", is_dir: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._filter = file_filter
        self._is_dir = is_dir
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.textChanged.connect(self.path_changed)
        self.btn = QPushButton("浏览")
        self.btn.clicked.connect(self._browse)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.btn)

    def text(self) -> str:
        return self.edit.text().strip()

    def setText(self, text: str) -> None:  # noqa: N802
        self.edit.setText(text)

    def _browse(self) -> None:
        if self._is_dir:
            path = QFileDialog.getExistingDirectory(self, "选择目录", self.text() or "")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "选择文件", self.text() or "", self._filter)
        if path:
            self.setText(path)


class Recorder(QThread):
    finished_path = Signal(str)
    failed = Signal(str)

    def __init__(self, output_path: str | Path, sr: int = 48000, parent=None) -> None:
        super().__init__(parent)
        self.output_path = Path(output_path)
        self.sr = sr
        self._stop_flag = threading.Event()

    def run(self) -> None:
        import sounddevice as sd

        frames: list[np.ndarray] = []

        def callback(indata, frames_count, time_info, status):
            frames.append(np.asarray(indata[:, 0], dtype=np.float32).copy())

        try:
            with sd.InputStream(samplerate=self.sr, channels=1, dtype="float32", callback=callback):
                self._stop_flag.wait()
            if frames:
                data = np.concatenate(frames)
                audio_io.save_wav(self.output_path, data, self.sr)
                self.finished_path.emit(str(self.output_path))
            else:
                self.failed.emit("未录制到任何声音")
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))

    def stop_recording(self) -> None:
        self._stop_flag.set()
        self.wait(5000)


class ToggleSwitch(QCheckBox):
    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setStyleSheet(
            """
            QCheckBox::indicator { width: 34px; height: 18px; border-radius: 9px; border: none; background: #cbd5e1; }
            QCheckBox::indicator:checked { background: #0f766e; }
            QCheckBox::indicator { image: none; }
            """
        )


def make_label(text: str = "", object_name: str = "") -> QLabel:
    label = QLabel(text)
    if object_name:
        label.setObjectName(object_name)
    return label


def card(layout_kind: str = "v") -> tuple[QWidget, object]:
    frame = QWidget()
    frame.setObjectName("Card")
    if layout_kind == "v":
        layout = QVBoxLayout(frame)
    else:
        layout = QHBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(10)
    return frame, layout

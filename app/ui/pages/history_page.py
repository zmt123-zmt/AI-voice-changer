from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core import audio_io
from app.core.jobs import Job

from ..context import AppContext, run_background, ui_soon
from ..widgets import make_label


class HistoryPage(QWidget):
    def __init__(self, ctx: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._records: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)
        root.addWidget(make_label("历史记录", "PageTitle"))
        root.addWidget(make_label("回听、导出或删除已生成的音频", "PageSub"))

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["时间", "类型", "音色", "内容", "时长"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 70)
        self.table.setColumnWidth(2, 130)
        self.table.setColumnWidth(4, 80)
        self.table.doubleClicked.connect(lambda _: self._play())
        root.addWidget(self.table, 1)

        row = QHBoxLayout()
        self.play_btn = QPushButton("播放选中")
        self.play_btn.clicked.connect(self._play)
        self.export_btn = QPushButton("导出选中")
        self.export_btn.clicked.connect(self._export)
        self.delete_btn = QPushButton("删除选中")
        self.delete_btn.setObjectName("Danger")
        self.delete_btn.clicked.connect(self._delete)
        self.clear_btn = QPushButton("清空记录")
        self.clear_btn.clicked.connect(self._clear)
        row.addWidget(self.play_btn)
        row.addWidget(self.export_btn)
        row.addWidget(self.delete_btn)
        row.addStretch(1)
        row.addWidget(self.clear_btn)
        root.addLayout(row)

        self.refresh()

    def refresh(self) -> None:
        self._records = self.ctx.history.list()
        self.table.setRowCount(len(self._records))
        for i, rec in enumerate(self._records):
            kind = {"tts": "TTS", "vc": "转换"}.get(rec.get("kind", ""), rec.get("kind", ""))
            self.table.setItem(i, 0, QTableWidgetItem(rec.get("created_at", "")))
            self.table.setItem(i, 1, QTableWidgetItem(kind))
            self.table.setItem(i, 2, QTableWidgetItem(rec.get("voice_name", "")))
            self.table.setItem(i, 3, QTableWidgetItem(rec.get("input_text", "")))
            self.table.setItem(i, 4, QTableWidgetItem(f"{rec.get('duration', 0):.1f}s"))

    def _selected(self) -> dict | None:
        row = self.table.currentRow()
        if 0 <= row < len(self._records):
            return self._records[row]
        return None

    def _play(self) -> None:
        rec = self._selected()
        if rec and Path(rec["output_path"]).exists():
            # 后台解码后再播放，避免主线程解码大文件冻结界面
            def work():
                return audio_io.decode_audio(rec["output_path"], self.ctx.config.settings)

            def done(result):
                sr, data = result
                self.ctx.player.play(data, sr)

            def error(exc):
                self.ctx.notify(f"播放失败：{exc}")

            run_background(work, ui_soon(done), ui_soon(error))

    def _export(self) -> None:
        rec = self._selected()
        if not rec:
            return
        if not Path(rec["output_path"]).exists():
            QMessageBox.warning(self, "导出失败", "源文件已不存在")
            return
        fmt = self.ctx.config.settings.output_format
        default = f"history_{rec['id']}.{fmt}"
        path, _ = QFileDialog.getSaveFileName(self, "导出音频", default, f"音频 (*.{fmt})")
        if not path:
            return
        same_suffix = Path(path).suffix.lower() == Path(rec["output_path"]).suffix.lower()
        self.export_btn.setEnabled(False)

        def work():
            if same_suffix:
                Path(rec["output_path"]).replace(path)
                return None
            sr, data = audio_io.decode_audio(rec["output_path"], self.ctx.config.settings)
            audio_io.export_audio(path, data, sr, fmt=fmt, settings=self.ctx.config.settings)
            return None

        def done(_):
            self.export_btn.setEnabled(True)
            self.ctx.notify(f"已导出：{path}")

        def error(exc):
            self.export_btn.setEnabled(True)
            QMessageBox.warning(self, "导出失败", str(exc))

        run_background(work, ui_soon(done), ui_soon(error))

    def _delete(self) -> None:
        rec = self._selected()
        if rec:
            self.ctx.history.delete(rec["id"])
            self.refresh()

    def _clear(self) -> None:
        r = QMessageBox.question(self, "清空记录", "确认清空全部历史记录？文件不会被删除。")
        if r == QMessageBox.Yes:
            self.ctx.history.clear()
            self.refresh()

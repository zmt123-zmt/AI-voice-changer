from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import audio_io
from app.core.jobs import Job
from app.core.validation import analyze_audio

from ..context import AppContext, run_background, ui_soon
from ..widgets import make_label


class ClonePage(QWidget):
    def __init__(self, ctx: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._report = None
        self._source_path = ""
        self.setAcceptDrops(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        root.addWidget(make_label("克隆音色", "PageTitle"))
        root.addWidget(make_label("① 导入校验 → ② 填写名称 → ③ 点击「保存到音色库」完成导入", "PageSub"))

        drop_card, drop_layout = self._drop_card()
        root.addWidget(drop_card)

        self.engine_hint = make_label("", "Muted")
        self.engine_hint.setWordWrap(True)
        root.addWidget(self.engine_hint)

        report_card, report_layout = self._report_card()
        root.addWidget(report_card, 1)

        save_card, save_layout = self._save_card()
        root.addWidget(save_card)

    def _drop_card(self):
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("拖入音频文件，或点击选择")
        pick = QPushButton("选择音频")
        pick.setObjectName("Primary")
        pick.clicked.connect(self._pick)
        row.addWidget(self.path_edit, 1)
        row.addWidget(pick)
        layout.addLayout(row)
        hint = make_label("支持 wav / mp3 / m4a / flac，≤ 100MB，建议 5~30 秒干净人声", "Muted")
        layout.addWidget(hint)
        return card, layout

    def _report_card(self):
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        layout.addWidget(make_label("质量校验", "SectionTitle"))
        self.report_labels = {
            "duration": make_label("-"),
            "sr": make_label("-"),
            "noise": make_label("-"),
            "speech": make_label("-"),
            "score": make_label("-"),
        }
        grid = QHBoxLayout()
        grid.setSpacing(18)
        for label in self.report_labels.values():
            grid.addWidget(label)
        grid.addStretch(1)
        layout.addLayout(grid)
        self.warn_label = make_label("", "Muted")
        self.warn_label.setWordWrap(True)
        layout.addWidget(self.warn_label)
        return card, layout

    def _save_card(self):
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        layout.addWidget(make_label("保存音色", "SectionTitle"))
        name_row = QHBoxLayout()
        name_row.addWidget(make_label("音色名称"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：我的声音")
        name_row.addWidget(self.name_edit, 1)
        layout.addLayout(name_row)
        prompt_row = QHBoxLayout()
        prompt_row.addWidget(make_label("参考文字（可选）"))
        self.prompt_edit = QLineEdit()
        self.prompt_edit.setPlaceholderText("GPT-SoVITS 参考音频对应的文字，可留空")
        prompt_row.addWidget(self.prompt_edit, 1)
        layout.addLayout(prompt_row)
        self.save_btn = QPushButton("保存到音色库")
        self.save_btn.setObjectName("Primary")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save)
        layout.addWidget(self.save_btn, 0, Qt.AlignRight)
        self.save_hint = make_label("导入音频并通过校验后，点击上方按钮完成保存", "Muted")
        layout.addWidget(self.save_hint, 0, Qt.AlignRight)
        return card, layout

    def _pick(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择参考音频",
            "",
            "音频文件 (*.wav *.mp3 *.m4a *.flac *.ogg *.aac);;所有文件 (*)",
        )
        if path:
            self._analyze(path)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if urls:
            self._analyze(urls[0].toLocalFile())

    def _analyze(self, path: str) -> None:
        self._source_path = path
        self.path_edit.setText(path)
        self.save_btn.setEnabled(False)
        for label in self.report_labels.values():
            label.setText("分析中…")
        self.warn_label.setText("")
        self.save_hint.setText("正在校验音频…")

        def work():
            sr, data = audio_io.decode_audio(path, self.ctx.config.settings)
            return sr, data, analyze_audio(data, sr, size_bytes=Path(path).stat().st_size)

        def done(result):
            sr, data, report = result
            self._report = report
            self._analyzed = (sr, data)
            self.report_labels["duration"].setText(f"时长：{report.duration:.1f} 秒")
            self.report_labels["sr"].setText(f"采样率：{report.sample_rate} Hz")
            self.report_labels["noise"].setText(f"噪声分：{report.noise_score:.0f}/100")
            self.report_labels["speech"].setText(f"有效人声：{report.speech_ratio * 100:.0f}%")
            self.report_labels["score"].setText(f"相似度预估：{report.similarity_estimate}/5")
            self.warn_label.setText("\n".join(report.warnings) if report.warnings else "校验通过")
            self.warn_label.setObjectName("Warn" if report.warnings else "Ok")
            self.warn_label.style().unpolish(self.warn_label)
            self.warn_label.style().polish(self.warn_label)
            self.save_btn.setEnabled(report.ok)
            if report.ok:
                self.save_btn.setFocus()
                self.save_hint.setText("✓ 校验通过！请点击上方「保存到音色库」完成导入")
                self.ctx.notify("校验通过：请点击「保存到音色库」完成导入")
            else:
                self.save_hint.setText("音频存在质量问题，无法保存（见上方提示）")
                self.ctx.notify("音频存在质量问题，无法保存")

        def error(exc):
            QMessageBox.warning(self, "分析失败", str(exc))
            self.warn_label.setText(str(exc))
            self.warn_label.setObjectName("Err")

        run_background(work, ui_soon(done), ui_soon(error))

    def _save(self) -> None:
        if not self._report or not self._source_path:
            return
        name = self.name_edit.text().strip() or Path(self._source_path).stem
        prompt = self.prompt_edit.text().strip()
        self.save_btn.setEnabled(False)
        self.save_btn.setText("保存中…")

        def work():
            # 解码 + 写文件在后台线程执行，避免冻结 UI
            voice = self.ctx.voices.add_from_file(name, self._source_path, self._report)
            if prompt:
                self.ctx.voices.save_prompt_text(voice.id, prompt)
            return voice

        def done(voice):
            self.save_btn.setEnabled(False)
            self.save_btn.setText("保存到音色库")
            self.save_hint.setText(f"✓ 音色“{voice.name}”已保存，可在左侧音色库页查看")
            self.ctx.notify(f"音色“{voice.name}”已保存")
            self._update_engine_hint()

        def error(exc):
            self.save_btn.setEnabled(True)
            self.save_btn.setText("保存到音色库")
            self.save_hint.setText("保存失败，请重试（见弹窗）")
            QMessageBox.warning(self, "保存失败", str(exc))

        run_background(work, ui_soon(done), ui_soon(error))

    def _update_engine_hint(self) -> None:
        """根据已配置的真实引擎给出引导提示。"""
        g = self.ctx.engines.gpt_sovits.status()
        r = self.ctx.engines.rvc.status()
        if not g.available and not r.available:
            self.engine_hint.setText(
                "当前为演示模式：保存的参考音频仅用于记录，TTS 使用系统语音、"
                "声音转换使用本地 DSP 变调，不会改变音色。\n"
                "要真正克隆音色：设置 → GPT-SoVITS（克隆朗读）或设置 → RVC（音色转换），"
                "配置后本页保存的音色将自动接入真实 AI 引擎。"
            )
            self.engine_hint.setObjectName("Warn")
        elif g.available:
            self.engine_hint.setText(
                f"GPT-SoVITS 已就绪（{g.detail}）：保存后即可在“文字转语音”中用该音色克隆朗读。"
            )
            self.engine_hint.setObjectName("Ok")
        else:
            self.engine_hint.setText(
                f"RVC 已就绪（{r.detail}）：保存后可在“声音转换 / 实时变声”中使用。"
            )
            self.engine_hint.setObjectName("Ok")
        self.engine_hint.style().unpolish(self.engine_hint)
        self.engine_hint.style().polish(self.engine_hint)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._update_engine_hint()

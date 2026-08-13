from __future__ import annotations

import time

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.core import audio_io, dsp
from app.engines.base import TTSParams
from app.core.jobs import Job

from ..context import AppContext, ui_soon
from ..widgets import WaveformWidget, make_label


def split_long_text(text: str, max_len: int = 300) -> list[str]:
    text = text.strip()
    if len(text) <= max_len:
        return [text]
    cuts = "。！？!?；;\n"
    out: list[str] = []
    buf = ""
    for ch in text:
        buf += ch
        if ch in cuts and len(buf) >= 40:
            out.append(buf)
            buf = ""
        elif len(buf) >= max_len:
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return out


class TTSPage(QWidget):
    def __init__(self, ctx: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._result: tuple[int, np.ndarray] | None = None
        self._result_path = ""
        self._busy = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)
        root.addWidget(make_label("文字转语音", "PageTitle"))
        root.addWidget(make_label("用已克隆音色朗读文字，支持自动分段与参数调节", "PageSub"))

        top = QHBoxLayout()
        top.addWidget(make_label("音色"))
        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(220)
        self.voice_combo.currentIndexChanged.connect(self._update_engine_label)
        top.addWidget(self.voice_combo, 1)
        top.addWidget(make_label("语言"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("自动", "auto")
        self.lang_combo.addItem("中文", "zh")
        self.lang_combo.addItem("英文", "en")
        self.lang_combo.addItem("日文", "ja")
        top.addWidget(self.lang_combo)
        root.addLayout(top)

        engine_card, el = self._card()
        self.engine_label = make_label("", "Muted")
        el.addWidget(self.engine_label)
        root.addWidget(engine_card)

        input_card, il = self._card()
        il.addWidget(make_label("文字（≤ 1000 字）", "SectionTitle"))
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("输入要朗读的文字，支持中文、英文、日文…")
        self.text_edit.setMinimumHeight(110)
        self.text_edit.textChanged.connect(self._update_counter)
        il.addWidget(self.text_edit)
        self.counter = make_label("0 / 1000", "Muted")
        self.counter.setAlignment(Qt.AlignRight)
        il.addWidget(self.counter)
        root.addWidget(input_card, 1)

        params_card, pl = self._card()
        pl.addWidget(make_label("参数", "SectionTitle"))
        self.speed = self._slider_row(pl, "语速", 50, 200, 100, "x")
        self.pitch = self._slider_row(pl, "音调", -12, 12, 0, " 半音")
        self.volume = self._slider_row(pl, "音量", 0, 100, 100, "%")
        root.addWidget(params_card)

        result_card, rl = self._card()
        rl.addWidget(make_label("结果", "SectionTitle"))
        self.waveform = WaveformWidget()
        rl.addWidget(self.waveform)
        btn_row = QHBoxLayout()
        self.generate_btn = QPushButton("生成语音")
        self.generate_btn.setObjectName("Primary")
        self.generate_btn.clicked.connect(self._generate)
        self.export_btn = QPushButton("导出")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export)
        self.play_btn = QPushButton("试听")
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._play_result)
        self.wechat_mode = QCheckBox("播放到虚拟声卡（微信语音条）")
        self.wechat_mode.setToolTip(
            "勾选后「试听」的声音进虚拟声卡（VB-Cable），音箱听不到，"
            "但微信按住说话能录到；不勾选正常音箱/耳机试听"
        )
        btn_row.addWidget(self.wechat_mode)
        btn_row.addStretch(1)
        btn_row.addWidget(self.play_btn)
        btn_row.addWidget(self.export_btn)
        btn_row.addWidget(self.generate_btn)
        rl.addLayout(btn_row)
        root.addWidget(result_card)

        self.refresh()

    def _card(self):
        card = QWidget()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        return card, layout

    def _slider_row(self, layout, name, lo, hi, val, suffix):
        row = QHBoxLayout()
        row.addWidget(make_label(name))
        slider = QSlider(Qt.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(val)
        value_label = make_label("", "Muted")
        value_label.setFixedWidth(70)

        def update():
            value_label.setText(f"{slider.value()}{suffix}")

        slider.valueChanged.connect(lambda _: update())
        update()
        row.addWidget(slider, 1)
        row.addWidget(value_label)
        layout.addLayout(row)
        return slider

    def _update_counter(self) -> None:
        n = len(self.text_edit.toPlainText())
        self.counter.setText(f"{n} / 1000")
        self.counter.setObjectName("Err" if n > 1000 else "Muted")
        self.counter.style().unpolish(self.counter)
        self.counter.style().polish(self.counter)

    def refresh(self) -> None:
        current = self.voice_combo.currentData()
        self.voice_combo.blockSignals(True)
        self.voice_combo.clear()
        voices = self.ctx.voices.list()
        if not voices:
            voices = [self.ctx.voices.add_demo()]
        for v in voices:
            kind_zh = {"zero_shot": "零样本", "rvc": "RVC", "demo": "演示"}.get(v.kind, v.kind)
            self.voice_combo.addItem(f"{v.name}（{kind_zh}）", v.id)
        if current:
            idx = self.voice_combo.findData(current)
            if idx >= 0:
                self.voice_combo.setCurrentIndex(idx)
        self.voice_combo.blockSignals(False)
        self._update_engine_label()

    def _selected_voice(self):
        return self.ctx.voices.get(self.voice_combo.currentData())

    def _update_engine_label(self) -> None:
        voice = self._selected_voice()
        engine = self.ctx.engines.tts_for(voice)
        st = engine.status()
        self.engine_label.setText(f"引擎：{st.name} — {st.detail}")

    def _params(self) -> TTSParams:
        return TTSParams(
            speed=self.speed.value() / 100.0,
            pitch=float(self.pitch.value()),
            volume=self.volume.value() / 100.0,
        )

    def _generate(self) -> None:
        if self._busy:
            return
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "提示", "请输入文字")
            return
        if len(text) > 1000:
            QMessageBox.warning(self, "提示", "文字不能超过 1000 字")
            return
        voice = self._selected_voice()
        engine = self.ctx.engines.tts_for(voice)
        lang = self.lang_combo.currentData()
        if lang == "auto":
            lang = "zh"
        params = self._params()
        self._busy = True
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("生成中…")
        self.ctx.notify("任务已加入队列")

        def work():
            parts = []
            out_sr = 0
            for i, seg in enumerate(split_long_text(text)):
                sr, data = engine.synthesize(seg, lang, params, voice)
                parts.append(data)
                out_sr = sr
            full = dsp.concat_parts(parts, out_sr) if len(parts) > 1 else parts[0]
            if params.volume != 1.0:
                full = dsp.volume(full, params.volume)
            out_sr = int(out_sr)
            if out_sr != self.ctx.config.settings.output_sr:
                full = audio_io.resample_audio(full, out_sr, self.ctx.config.settings.output_sr)
                out_sr = self.ctx.config.settings.output_sr
            path = self.ctx.config.settings.output_dir_path() / f"tts_{time.strftime('%Y%m%d_%H%M%S')}.wav"
            audio_io.save_wav(path, full, out_sr)
            return out_sr, full, str(path), voice.name

        def done(result):
            self._busy = False
            self.generate_btn.setEnabled(True)
            self.generate_btn.setText("生成语音")
            sr, data, path, voice_name = result
            self._result = (sr, data)
            self._result_path = path
            self.waveform.set_data(data)
            self.play_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            self.ctx.history.add(
                "tts",
                voice_name,
                path,
                len(data) / sr,
                voice_id=self._selected_voice().id if self._selected_voice() else "",
                input_text=text[:80],
                params={"speed": params.speed, "pitch": params.pitch},
            )
            self.ctx.player.play(data, sr)
            self.ctx.notify("TTS 生成完成，可试听或导出")

        def error(exc):
            self._busy = False
            self.generate_btn.setEnabled(True)
            self.generate_btn.setText("生成语音")
            QMessageBox.warning(self, "生成失败", str(exc))

        self.ctx.jobs.submit(Job("文字转语音", work, ui_soon(done), ui_soon(error)))

    def _play_result(self) -> None:
        if not self._result:
            return
        # 勾选「微信语音条」→ 播放走虚拟声卡（CABLE Input），否则系统默认（音箱/耳机）
        if self.wechat_mode.isChecked():
            self.ctx.player.set_output_device("CABLE Input (VB-Audio Virtual Cable)")
        else:
            self.ctx.player.set_output_device("")
        self.ctx.player.play(self._result[1], self._result[0])

    def _export(self) -> None:
        if not self._result:
            return
        fmt = self.ctx.config.settings.output_format
        default = f"tts_{time.strftime('%Y%m%d_%H%M%S')}.{fmt}"
        path, _ = QFileDialog.getSaveFileName(self, "导出音频", default, f"音频 (*.{fmt})")
        if not path:
            return
        try:
            audio_io.export_audio(
                path,
                self._result[1],
                self._result[0],
                fmt=fmt,
                settings=self.ctx.config.settings,
            )
            self.ctx.notify(f"已导出：{path}")
        except Exception as exc:
            QMessageBox.warning(self, "导出失败", str(exc))

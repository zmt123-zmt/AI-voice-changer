from __future__ import annotations

import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.core import audio_io, dsp
from app.engines.base import VCParams
from app.core.jobs import Job

from ..context import AppContext, run_background, ui_soon
from ..widgets import Recorder, WaveformWidget, make_label


class VCPage(QWidget):
    def __init__(self, ctx: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._recorder: Recorder | None = None
        self._source_path = ""
        self._source_audio: tuple[int, np.ndarray] | None = None
        self._result: tuple[int, np.ndarray] | None = None
        self._result_path = ""
        self._busy = False

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)
        root.addWidget(make_label("声音转换", "PageTitle"))
        root.addWidget(make_label("上传或录制自己的声音，转换为目标音色（说话/唱歌均可）", "PageSub"))

        src_card, sl = self._card()
        sl.addWidget(make_label("输入声音", "SectionTitle"))
        row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("选择音频或开始录音（≥ 3 秒）")
        row.addWidget(self.path_edit, 1)
        self.pick_btn = QPushButton("选择音频")
        self.pick_btn.clicked.connect(self._pick)
        self.record_btn = QPushButton("开始录音")
        self.record_btn.clicked.connect(self._toggle_record)
        row.addWidget(self.pick_btn)
        row.addWidget(self.record_btn)
        sl.addLayout(row)
        root.addWidget(src_card)

        cfg_card, cl = self._card()
        cfg_row = QHBoxLayout()
        cfg_row.addWidget(make_label("目标音色"))
        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(200)
        self.voice_combo.currentIndexChanged.connect(self._update_engine_label)
        cfg_row.addWidget(self.voice_combo, 1)
        cfg_row.addWidget(make_label(""))
        cl.addLayout(cfg_row)
        self.engine_label = make_label("", "Muted")
        cl.addWidget(self.engine_label)
        cl.addWidget(make_label("参数", "SectionTitle"))
        self.pitch = self._slider_row(cl, "音调", -24, 24, self.ctx.config.settings.rvc_f0up_key, " 半音")
        # 像训练样本 = RVC index_rate（0=自由发挥保留输入，100=完全贴训练样本）
        self.strength = self._slider_row(
            cl, "像训练样本", 0, 100, int(self.ctx.config.settings.rvc_index_rate * 100), "%"
        )
        self.denoise = self._slider_row(cl, "去噪", 0, 100, 0, "%")
        self.volume = self._slider_row(cl, "音量", 0, 100, 100, "%")
        root.addWidget(cfg_card)

        result_card, rl = self._card()
        rl.addWidget(make_label("结果对比", "SectionTitle"))
        self.waveform = WaveformWidget()
        rl.addWidget(self.waveform)
        btn_row = QHBoxLayout()
        self.original_btn = QPushButton("播放原声")
        self.original_btn.setEnabled(False)
        self.original_btn.clicked.connect(self._play_original)
        self.result_btn = QPushButton("播放转换后")
        self.result_btn.setEnabled(False)
        self.result_btn.clicked.connect(self._play_result)
        self.export_btn = QPushButton("导出")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export)
        self.convert_btn = QPushButton("开始转换")
        self.convert_btn.setObjectName("Primary")
        self.convert_btn.clicked.connect(self._convert)
        btn_row.addStretch(1)
        btn_row.addWidget(self.original_btn)
        btn_row.addWidget(self.result_btn)
        btn_row.addWidget(self.export_btn)
        btn_row.addWidget(self.convert_btn)
        rl.addLayout(btn_row)
        root.addWidget(result_card, 1)

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
        engine = self.ctx.engines.vc_for(voice)
        st = engine.status()
        self.engine_label.setText(f"引擎：{st.name} — {st.detail}")

    def _params(self) -> VCParams:
        strength = self.strength.value() / 100.0
        return VCParams(
            semitones=float(self.pitch.value()),
            strength=strength,
            denoise=self.denoise.value() / 100.0,
            wet=strength,
            volume=self.volume.value() / 100.0,
        )

    def _pick(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择输入音频",
            "",
            "音频文件 (*.wav *.mp3 *.m4a *.flac *.ogg);;所有文件 (*)",
        )
        if path:
            self._set_source(path)

    def _set_source(self, path: str) -> None:
        self._source_path = path
        self.path_edit.setText(path)
        self.original_btn.setEnabled(False)
        self.convert_btn.setEnabled(False)

        def work():
            return audio_io.decode_audio(path, self.ctx.config.settings)

        def done(result):
            self._source_audio = result
            sr, data = result
            duration = len(data) / sr
            self.original_btn.setEnabled(True)
            self.convert_btn.setEnabled(duration >= 3.0)
            if duration < 3.0:
                self.ctx.notify("音频过短（<3 秒），请重新录制或选择更长音频")

        def error(exc):
            QMessageBox.warning(self, "读取失败", str(exc))

        run_background(work, ui_soon(done), ui_soon(error))

    def _toggle_record(self) -> None:
        if self._recorder and self._recorder.isRunning():
            self._recorder.stop_recording()
            self.record_btn.setText("开始录音")
            return
        path = self.ctx.config.settings.tmp_dir() / f"record_{time.strftime('%Y%m%d_%H%M%S')}.wav"
        self._recorder = Recorder(path, parent=self)
        self._recorder.finished_path.connect(self._on_recorded)
        self._recorder.failed.connect(lambda msg: QMessageBox.warning(self, "录音失败", msg))
        self._recorder.start()
        self.record_btn.setText("停止录音")
        self.ctx.notify("录音中…")

    def _on_recorded(self, path: str) -> None:
        self.record_btn.setText("开始录音")
        self._set_source(path)
        self.ctx.notify("录音完成")

    def _play_original(self) -> None:
        if self._source_audio:
            self.ctx.player.play(self._source_audio[1], self._source_audio[0])

    def _play_result(self) -> None:
        if self._result:
            self.ctx.player.play(self._result[1], self._result[0])

    def _convert(self) -> None:
        if self._busy or not self._source_audio:
            return
        voice = self._selected_voice()
        engine = self.ctx.engines.vc_for(voice)
        params = self._params()
        src_sr, src_data = self._source_audio
        self._busy = True
        self.convert_btn.setEnabled(False)
        self.convert_btn.setText("转换中…")
        self.ctx.notify("任务已加入队列")

        def work():
            def prog(p, msg):
                ui_soon(self.ctx.notify)(f"RVC 转换 {p:.0%}：{msg}")

            out_sr, out_data = engine.convert(src_data, src_sr, voice, params, progress=prog)
            if params.volume != 1.0:
                out_data = dsp.volume(out_data, params.volume)
            out_sr = int(out_sr)
            if out_sr != self.ctx.config.settings.output_sr:
                out_data = audio_io.resample_audio(out_data, out_sr, self.ctx.config.settings.output_sr)
                out_sr = self.ctx.config.settings.output_sr
            path = self.ctx.config.settings.output_dir_path() / f"vc_{time.strftime('%Y%m%d_%H%M%S')}.wav"
            audio_io.save_wav(path, out_data, out_sr)
            return out_sr, out_data, str(path), voice.name

        def done(result):
            self._busy = False
            self.convert_btn.setEnabled(True)
            self.convert_btn.setText("开始转换")
            sr, data, path, voice_name = result
            self._result = (sr, data)
            self._result_path = path
            self.waveform.set_data(data)
            self.result_btn.setEnabled(True)
            self.export_btn.setEnabled(True)
            self.ctx.history.add(
                "vc",
                voice_name,
                path,
                len(data) / sr,
                voice_id=voice.id,
                input_text=Path(self._source_path).name,
                params={"semitones": params.semitones, "strength": params.strength},
            )
            self.ctx.player.play(data, sr)
            self.ctx.notify("转换完成，可对比原声")

        def error(exc):
            self._busy = False
            self.convert_btn.setEnabled(True)
            self.convert_btn.setText("开始转换")
            QMessageBox.warning(self, "转换失败", str(exc))

        self.ctx.jobs.submit(Job("声音转换", work, ui_soon(done), ui_soon(error)))

    def _export(self) -> None:
        if not self._result:
            return
        fmt = self.ctx.config.settings.output_format
        default = f"vc_{time.strftime('%Y%m%d_%H%M%S')}.{fmt}"
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

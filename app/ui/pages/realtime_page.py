from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.engines.base import VCParams
from app.engines.realtime import AudioDeviceManager

from ..context import AppContext
from ..widgets import LevelMeter, ToggleSwitch, make_label


class RealtimePage(QWidget):
    def __init__(self, ctx: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._transform = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)
        root.addWidget(make_label("实时变声", "PageTitle"))
        root.addWidget(make_label("麦克风输入实时转换并输出，支持音色切换与干湿比调节", "PageSub"))

        dev_card, dl = self._card()
        dl.addWidget(make_label("音频设备", "SectionTitle"))
        dev_row = QHBoxLayout()
        dev_row.addWidget(make_label("输入"))
        self.input_combo = QComboBox()
        self.input_combo.setMinimumWidth(260)
        dev_row.addWidget(self.input_combo, 1)
        dev_row.addWidget(make_label("输出"))
        self.output_combo = QComboBox()
        self.output_combo.setMinimumWidth(260)
        dev_row.addWidget(self.output_combo, 1)
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self._refresh_devices)
        dev_row.addWidget(refresh)
        dl.addLayout(dev_row)
        root.addWidget(dev_card)

        cfg_card, cl = self._card()
        cfg_row = QHBoxLayout()
        cfg_row.addWidget(make_label("音色"))
        self.voice_combo = QComboBox()
        self.voice_combo.setMinimumWidth(220)
        self.voice_combo.currentIndexChanged.connect(self._on_voice_changed)
        cfg_row.addWidget(self.voice_combo, 1)
        cl.addLayout(cfg_row)
        self.engine_label = make_label("", "Muted")
        cl.addWidget(self.engine_label)
        self.pitch = self._slider_row(cl, "音调", -24, 24, self.ctx.config.settings.rvc_f0up_key, " 半音")
        self.dry_wet = self._slider_row(cl, "干湿比", 0, 100, 100, "%")
        self.in_gain = self._slider_row(cl, "输入音量", 0, 150, 100, "%")
        self.out_gain = self._slider_row(cl, "输出音量", 0, 150, 100, "%")
        self.pitch.valueChanged.connect(lambda _: self._apply_params())
        self.dry_wet.valueChanged.connect(lambda _: self._apply_params())
        self.in_gain.valueChanged.connect(lambda _: self._apply_params())
        self.out_gain.valueChanged.connect(lambda _: self._apply_params())
        root.addWidget(cfg_card)

        ctrl_card, cl2 = self._card()
        row = QHBoxLayout()
        self.master = ToggleSwitch("实时变声")
        self.master.toggled.connect(self._on_master)
        self.bypass = ToggleSwitch("原声/变声对比")
        self.bypass.toggled.connect(lambda checked: setattr(self.ctx.realtime, "bypass", checked))
        row.addWidget(self.master)
        row.addWidget(self.bypass)
        row.addStretch(1)
        row.addWidget(make_label("输入"))
        self.in_meter = LevelMeter()
        row.addWidget(self.in_meter)
        row.addWidget(make_label("输出"))
        self.out_meter = LevelMeter()
        row.addWidget(self.out_meter)
        cl2.addLayout(row)
        self.latency_label = make_label("延迟：-", "Muted")
        cl2.addWidget(self.latency_label)
        root.addWidget(ctrl_card)
        root.addStretch(1)

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self.refresh()
        self._refresh_devices()

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
        value_label.setFixedWidth(60)

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
        self._on_voice_changed()

    def _selected_voice(self):
        return self.ctx.voices.get(self.voice_combo.currentData())

    def _on_voice_changed(self) -> None:
        voice = self._selected_voice()
        engine = self.ctx.engines.vc_for(voice)
        st = engine.status()
        self.engine_label.setText(f"引擎：{st.name} — {st.detail}")
        if self.master.isChecked():
            self._rebuild_transform()

    def _params(self) -> VCParams:
        strength = self.dry_wet.value() / 100.0
        return VCParams(
            semitones=float(self.pitch.value()),
            strength=-1.0,  # 像训练样本权重交给设置默认（干湿比滑杆只管原声/变声混合）
            wet=strength,
            volume=1.0,
        )

    def _refresh_devices(self) -> None:
        self.input_combo.clear()
        self.output_combo.clear()
        if not AudioDeviceManager.available():
            self.input_combo.addItem("音频设备不可用", -1)
            self.output_combo.addItem("音频设备不可用", -1)
            return
        try:
            for dev in AudioDeviceManager.input_devices():
                self.input_combo.addItem(f"{dev['name']} ({dev['channels']}ch)", dev["index"])
            for dev in AudioDeviceManager.output_devices():
                self.output_combo.addItem(f"{dev['name']} ({dev['channels']}ch)", dev["index"])
            default_in = AudioDeviceManager.default_input()
            default_out = AudioDeviceManager.default_output()
            idx = self.input_combo.findData(default_in)
            if idx >= 0:
                self.input_combo.setCurrentIndex(idx)
            idx = self.output_combo.findData(default_out)
            if idx >= 0:
                self.output_combo.setCurrentIndex(idx)
        except Exception as exc:
            self.input_combo.addItem("设备枚举失败", -1)
            self.output_combo.addItem("设备枚举失败", -1)
            self.ctx.notify(f"设备枚举失败：{exc}")

    def _rebuild_transform(self) -> None:
        voice = self._selected_voice()
        params = self._params()
        engine = self.ctx.engines.vc_for(voice)
        transform = engine.make_realtime(voice, params)
        if transform is None:
            transform = self.ctx.engines.fallback_vc.make_realtime(voice, params)
            self.engine_label.setText(f"当前模式：{self.ctx.engines.fallback_vc.display_name}（安装 RVC 后启用音色克隆）")
        else:
            self.engine_label.setText(f"当前模式：{engine.display_name}（AI 实时推理）")
        self.ctx.realtime.set_transform(transform)

    def _on_master(self, checked: bool) -> None:
        if not checked:
            self.ctx.realtime.stop()
            self.ctx.realtime.set_transform(None)
            self.latency_label.setText("延迟：-")
            self.ctx.notify("实时变声已停止")
            return
        if not AudioDeviceManager.available():
            QMessageBox.warning(self, "无法启动", "音频设备不可用（未检测到声卡）")
            self.master.setChecked(False)
            return
        in_dev = self.input_combo.currentData()
        out_dev = self.output_combo.currentData()
        if in_dev is None or out_dev is None or in_dev < 0 or out_dev < 0:
            QMessageBox.warning(self, "无法启动", "请选择输入/输出设备")
            self.master.setChecked(False)
            return
        try:
            self._rebuild_transform()
            self.ctx.realtime.bypass = self.bypass.isChecked()
            self.ctx.realtime.set_devices(int(in_dev), int(out_dev))
            self.ctx.realtime.start()
            self.ctx.notify("实时变声已启动")
        except Exception as exc:
            QMessageBox.warning(self, "启动失败", str(exc))
            self.master.setChecked(False)

    def _apply_params(self) -> None:
        rt = self.ctx.realtime
        rt.dry_wet = self.dry_wet.value() / 100.0
        rt.input_gain = self.in_gain.value() / 100.0
        rt.output_gain = self.out_gain.value() / 100.0
        if self.master.isChecked():
            self._rebuild_transform()

    def _tick(self) -> None:
        self.in_meter.set_level(self.ctx.realtime.in_level)
        self.out_meter.set_level(self.ctx.realtime.out_level)
        if self.ctx.realtime.running:
            self.latency_label.setText(f"最近分块处理延迟：{self.ctx.realtime.latency_ms:.0f} ms（含缓冲的实际端到端延迟会更高）")

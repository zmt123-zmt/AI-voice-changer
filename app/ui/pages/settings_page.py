from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..context import AppContext
from ..widgets import FileField, make_label


class SettingsPage(QWidget):
    consent_requested = Signal()

    def __init__(self, ctx: AppContext, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)
        root.addWidget(make_label("设置", "PageTitle"))
        root.addWidget(make_label("配置 ffmpeg、模型目录与输出选项", "PageSub"))

        # 卡片放入滚动区域，避免窗口较小时底部内容被裁掉
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(14)

        general_card, gl = self._card()
        gl.addWidget(make_label("通用", "SectionTitle"))
        form = QFormLayout()
        form.setSpacing(8)
        self.ffmpeg = FileField("ffmpeg 可执行文件路径（可留空自动查找）", "ffmpeg.exe;*.exe")
        form.addRow("ffmpeg", self.ffmpeg)
        self.output_dir = FileField("输出目录（留空使用 data/output）", is_dir=True)
        form.addRow("输出目录", self.output_dir)
        self.output_format = QComboBox()
        self.output_format.addItems(["wav", "mp3", "flac"])
        form.addRow("导出格式", self.output_format)
        self.output_sr = QComboBox()
        self.output_sr.addItem("48 kHz", 48000)
        self.output_sr.addItem("44.1 kHz", 44100)
        self.output_sr.addItem("24 kHz", 24000)
        form.addRow("输出采样率", self.output_sr)
        self.watermark = QCheckBox("导出时附带授权声明（语音水印）")
        form.addRow("合规", self.watermark)
        gl.addLayout(form)
        cl.addWidget(general_card)

        tts_card, tl = self._card()
        tl.addWidget(make_label("GPT-SoVITS（克隆 TTS）", "SectionTitle"))
        tform = QFormLayout()
        tform.setSpacing(8)
        self.gpt_dir = FileField("GPT-SoVITS 代码目录", is_dir=True)
        tform.addRow("代码目录", self.gpt_dir)
        self.gpt_script = FileField("api.py 路径（可留空，自动在目录中查找）", "api.py;*.py")
        tform.addRow("服务脚本", self.gpt_script)
        self.gpt_url = QLineEdit()
        tform.addRow("API 地址", self.gpt_url)
        tl.addLayout(tform)
        tl.addWidget(make_label("提示：零样本音色使用 5~30 秒参考音频，并在音色库填写参考文字。", "Muted"))
        cl.addWidget(tts_card)

        rvc_card, rl = self._card()
        rl.addWidget(make_label("RVC（音色转换 / 实时变声）", "SectionTitle"))
        rform = QFormLayout()
        rform.setSpacing(8)
        self.rvc_dir = FileField("RVC 代码目录（含 infer_cli.py）", is_dir=True)
        rform.addRow("代码目录", self.rvc_dir)
        self.rvc_model = FileField("RVC 模型文件 .pth", "*.pth")
        rform.addRow("模型文件", self.rvc_model)
        self.rvc_index = FileField("特征索引文件（可选）", "*.index;*.npy")
        rform.addRow("索引文件", self.rvc_index)
        self.rvc_f0 = QComboBox()
        self.rvc_f0.addItems(["rmvpe", "crepe", "harvest", "pm"])
        rform.addRow("F0 算法", self.rvc_f0)
        self.rvc_f0up = QSpinBox()
        self.rvc_f0up.setRange(-24, 24)
        rform.addRow("默认升调（半音）", self.rvc_f0up)
        self.rvc_rate = QDoubleSpinBox()
        self.rvc_rate.setRange(0.0, 1.0)
        self.rvc_rate.setSingleStep(0.05)
        self.rvc_rate.setValue(0.75)
        rform.addRow("索引比率", self.rvc_rate)
        rl.addLayout(rform)
        rl.addWidget(make_label("提示：RVC 实时变声需要训练好的模型（建议 3~10 分钟干净人声），并安装 rvc-python。", "Muted"))
        cl.addWidget(rvc_card)

        state_card, sl = self._card()
        sl.addWidget(make_label("引擎状态", "SectionTitle"))
        self.tts_state = make_label("", "Muted")
        self.vc_state = make_label("", "Muted")
        for _lbl in (self.tts_state, self.vc_state):
            _lbl.setWordWrap(True)
        sl.addWidget(self.tts_state)
        sl.addWidget(self.vc_state)
        cl.addWidget(state_card)

        btn_row = QHBoxLayout()
        self.consent_btn = QPushButton("重新显示授权声明")
        self.consent_btn.clicked.connect(self.consent_requested.emit)
        save = QPushButton("保存设置")
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        btn_row.addWidget(self.consent_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(save)
        cl.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        root.addLayout(btn_row)

        self._load()
        self.refresh()

    def _card(self):
        card = QWidget()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        return card, layout

    def _load(self) -> None:
        s = self.ctx.config.settings
        self.ffmpeg.setText(s.ffmpeg_path)
        self.output_dir.setText(s.output_dir)
        self.output_format.setCurrentText(s.output_format)
        idx = self.output_sr.findData(s.output_sr)
        if idx >= 0:
            self.output_sr.setCurrentIndex(idx)
        self.watermark.setChecked(s.watermark_enabled)
        self.gpt_dir.setText(s.gpt_sovits_dir)
        self.gpt_script.setText(s.gpt_sovits_api_script)
        self.gpt_url.setText(s.gpt_sovits_api_url)
        self.rvc_dir.setText(s.rvc_dir)
        self.rvc_model.setText(s.rvc_model_path)
        self.rvc_index.setText(s.rvc_index_path)
        idx = self.rvc_f0.findText(s.rvc_f0_method)
        if idx >= 0:
            self.rvc_f0.setCurrentIndex(idx)
        self.rvc_f0up.setValue(s.rvc_f0up_key)
        self.rvc_rate.setValue(s.rvc_index_rate)

    def _save(self) -> None:
        s = self.ctx.config.settings
        self.ctx.config.update(
            ffmpeg_path=self.ffmpeg.text(),
            output_dir=self.output_dir.text(),
            output_format=self.output_format.currentText(),
            output_sr=self.output_sr.currentData(),
            watermark_enabled=self.watermark.isChecked(),
            gpt_sovits_dir=self.gpt_dir.text(),
            gpt_sovits_api_script=self.gpt_script.text(),
            gpt_sovits_api_url=self.gpt_url.text().strip() or s.gpt_sovits_api_url,
            rvc_dir=self.rvc_dir.text(),
            rvc_model_path=self.rvc_model.text(),
            rvc_index_path=self.rvc_index.text(),
            rvc_f0_method=self.rvc_f0.currentText(),
            rvc_f0up_key=self.rvc_f0up.value(),
            rvc_index_rate=self.rvc_rate.value(),
        )
        self.refresh()
        self.ctx.notify("设置已保存")

    def refresh(self) -> None:
        g = self.ctx.engines.gpt_sovits.status()
        r = self.ctx.engines.rvc.status()
        self.tts_state.setText(f"TTS：{g.name} — {g.detail}")
        self.vc_state.setText(f"VC：{r.name} — {r.detail}")

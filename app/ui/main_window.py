from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .context import AppContext
from .pages.clone_page import ClonePage
from .pages.history_page import HistoryPage
from .pages.realtime_page import RealtimePage
from .pages.settings_page import SettingsPage
from .pages.tts_page import TTSPage
from .pages.vc_page import VCPage
from .pages.voices_page import VoicesPage
from .widgets import make_label


CONSENT_TEXT = (
    "使用前请阅读并同意以下声明：\n\n"
    "1. 本项目仅用于合法用途：本人声音、已获授权的配音内容或公开素材。\n"
    "2. 未经声音所有者授权，不得克隆或转换他人声音；不得用于诈骗、冒充、伪造证词等违法用途。\n"
    "3. 音频默认在本机处理，应用不会主动上传你的音频数据。\n"
    "4. 商业发布前请自行确认声音与内容的授权状态，并遵守所在地区法律。\n"
)


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle("AI 变声器")
        self.resize(1180, 760)
        self.setMinimumSize(980, 640)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(200)
        s_layout = QVBoxLayout(sidebar)
        s_layout.setContentsMargins(0, 0, 0, 0)
        s_layout.setSpacing(0)
        s_layout.addWidget(make_label("AI 变声器", "AppTitle"))
        s_layout.addWidget(make_label("本地 · 私有 · Windows", "SidebarHint"))

        self.nav = QListWidget()
        self.nav.setObjectName("Nav")
        entries = [
            ("音色库", "voices"),
            ("克隆音色", "clone"),
            ("文字转语音", "tts"),
            ("声音转换", "vc"),
            ("实时变声", "realtime"),
            ("历史记录", "history"),
            ("设置", "settings"),
        ]
        for title, key in entries:
            item = QListWidgetItem(title)
            item.setData(0x0100, key)
            self.nav.addItem(item)
        self.nav.currentRowChanged.connect(self._switch)
        s_layout.addWidget(self.nav, 1)

        self._last_tts_state = ""
        self._last_vc_state = ""
        self.tts_state = make_label("", "EngineState")
        self.vc_state = make_label("", "EngineState")
        s_layout.addWidget(self.tts_state)
        s_layout.addWidget(self.vc_state)
        root.addWidget(sidebar)

        content = QFrame()
        content.setObjectName("Content")
        self.stack = QStackedWidget(content)
        c_layout = QVBoxLayout(content)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.addWidget(self.stack)
        root.addWidget(content, 1)

        self.setCentralWidget(central)

        self.pages = {
            "voices": VoicesPage(ctx),
            "clone": ClonePage(ctx),
            "tts": TTSPage(ctx),
            "vc": VCPage(ctx),
            "realtime": RealtimePage(ctx),
            "history": HistoryPage(ctx),
            "settings": SettingsPage(ctx),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        self.pages["settings"].consent_requested.connect(self._show_consent)
        self.nav.setCurrentRow(0)

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(1200)
        self.status_timer.timeout.connect(self._update_status)
        self.status_timer.start()
        self._update_status()

    def notify(self, message: str) -> None:
        self.statusBar().showMessage(message, 6000)

    def _switch(self, row: int) -> None:
        keys = list(self.pages.keys())
        if 0 <= row < len(keys):
            page = self.pages[keys[row]]
            self.stack.setCurrentWidget(page)
            if hasattr(page, "refresh"):
                page.refresh()

    def _update_status(self) -> None:
        job = self.ctx.jobs.current_label
        if job:
            self.statusBar().showMessage(f"处理中：{job}")
        lines = self.ctx.engines.summary()
        # 文本未变化时不 setText，避免每 1.2s 反复触发重绘
        if lines[0] != self._last_tts_state:
            self._last_tts_state = lines[0]
            self.tts_state.setText(lines[0])
        if lines[1] != self._last_vc_state:
            self._last_vc_state = lines[1]
            self.vc_state.setText(lines[1])

    def _show_consent(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("授权与合规声明")
        box.setIcon(QMessageBox.Warning)
        box.setText(CONSENT_TEXT)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        result = box.exec()
        accepted = result == QMessageBox.Yes
        self.ctx.config.update(consent_accepted=accepted)
        if not accepted and not self.ctx.config.settings.consent_accepted:
            QApplication.instance().quit()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.ctx.realtime.close()
        self.ctx.player.stop()
        super().closeEvent(event)

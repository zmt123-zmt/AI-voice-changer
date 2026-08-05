from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.config import Config
from app.core.history import HistoryStore
from app.core.jobs import JobQueue
from app.core.voices import VoiceLibrary
from app.engines.registry import EngineRegistry
from app.engines.realtime import RealtimeEngine
from app.ui.context import AppContext
from app.ui.main_window import CONSENT_TEXT, MainWindow
from app.ui.theme import APP_STYLE
from app.ui.widgets import AudioPlayer


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)

    config = Config()
    voices = VoiceLibrary(config.settings)
    history = HistoryStore(config.settings.data_dir() / "db.sqlite3")
    jobs = JobQueue()
    engines = EngineRegistry(config.settings)
    realtime = RealtimeEngine(config.settings)
    player = AudioPlayer()

    ctx = AppContext(
        config=config,
        voices=voices,
        history=history,
        jobs=jobs,
        engines=engines,
        realtime=realtime,
        player=player,
        notify=lambda msg: None,
    )
    window = MainWindow(ctx)
    ctx.notify = window.notify

    if not config.settings.consent_accepted:
        box = QMessageBox(window)
        box.setWindowTitle("授权与合规声明")
        box.setIcon(QMessageBox.Warning)
        box.setText(CONSENT_TEXT)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        result = box.exec()
        accepted = result == QMessageBox.Yes
        config.update(consent_accepted=accepted)
        if not accepted:
            return 0

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

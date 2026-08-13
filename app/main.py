from __future__ import annotations

import logging
import sys
import warnings

from PySide6.QtWidgets import QApplication, QMessageBox

from app.core.config import ROOT, Config
from app.core.history import HistoryStore
from app.core.jobs import JobQueue
from app.core.voices import VoiceLibrary
from app.engines.registry import EngineRegistry
from app.engines.realtime import RealtimeEngine
from app.ui.context import AppContext
from app.ui.main_window import CONSENT_TEXT, MainWindow
from app.ui.theme import APP_STYLE
from app.ui.widgets import AudioPlayer


def _setup_logging() -> None:
    """日志全部写入文件，stderr 保持安静。

    背景（2026-08-06 修复）：exe 启动器（LaunchApp.cs）旧版用顺序 ReadToEnd 排空
    stdout，stderr 管道(默认 4KB)从未被读取 → RVC 加载 hubert 时 fairseq 日志
    (>4KB) 写满管道 → python 写日志线程永久阻塞 → 声音转换一直"转换中"。
    日志改文件 + 启动器异步排空双保险，杜绝该问题。
    """
    log_dir = ROOT / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    # 清掉所有既有 handler（含 fairseq 等库自己装的 stderr handler）
    for h in list(root.handlers):
        root.removeHandler(h)
        h.close()
    # 注意：FileHandler 是 StreamHandler 的子类，不能用 isinstance 过滤，
    # 必须显式只保留下面新建的 FileHandler。
    fh = logging.FileHandler(str(log_dir / "app.log"), mode="a", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    root.addHandler(fh)
    root.setLevel(logging.INFO)
    # 压掉第三方库的 FutureWarning / 噪音，避免刷屏与拖慢
    warnings.filterwarnings("ignore")


def main() -> int:
    _setup_logging()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)

    config = Config()
    voices = VoiceLibrary(config.settings)
    history = HistoryStore(config.settings.data_dir() / "db.sqlite3")
    jobs = JobQueue()
    engines = EngineRegistry(config.settings)
    realtime = RealtimeEngine(config.settings)
    player = AudioPlayer(config.settings)

    # RVC 模型后台预热（后台线程，首次声音转换免去 30s 加载；未配置模型则自动跳过）
    engines.rvc.warmup()

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

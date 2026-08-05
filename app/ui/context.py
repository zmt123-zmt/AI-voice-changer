from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QObject, Qt, Signal

from app.core.config import Config
from app.core.history import HistoryStore
from app.core.jobs import JobQueue
from app.core.voices import VoiceLibrary
from app.engines.registry import EngineRegistry
from app.engines.realtime import RealtimeEngine

from .widgets import AudioPlayer


@dataclass
class AppContext:
    config: Config
    voices: VoiceLibrary
    history: HistoryStore
    jobs: JobQueue
    engines: EngineRegistry
    realtime: RealtimeEngine
    player: AudioPlayer
    notify: Callable[[str], None]


class _UiBridge(QObject):
    """后台线程 → GUI 线程的信号桥。

    实例必须在主线程创建（模块在主线程 import），QueuedConnection 保证
    emit 后槽函数在 GUI 事件循环中执行。
    """

    _call = Signal(object)


_bridge = _UiBridge()


def _dispatch(payload) -> None:
    fn, args, kwargs = payload
    fn(*args, **kwargs)


_bridge._call.connect(_dispatch, Qt.QueuedConnection)


def ui_soon(fn: Callable) -> Callable:
    """把后台线程回调转到 GUI 线程。

    注意：不能用 QTimer.singleShot(0, fn) 从后台线程调用——无接收者的
    singleShot 会在调用线程执行回调，而后台线程没有事件循环，回调永远不会
    执行（这是此前“导入无反应/一直校验中”的根因）。信号桥是线程安全的。
    """

    def wrapper(*args, **kwargs):
        _bridge._call.emit((fn, args, kwargs))

    return wrapper


def run_background(
    work: Callable[[], object],
    on_done: Callable[[object], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
) -> None:
    """在独立后台线程执行 work，不经过全局任务队列。

    用于导入/校验/播放等轻量操作，避免被 JobQueue 中卡住的长任务（如
    GPT-SoVITS 启动等待、SAPI 合成超时）阻塞，导致界面无响应。
    """

    def runner():
        try:
            result = work()
            if on_done:
                on_done(result)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            if on_error:
                on_error(exc)

    threading.Thread(target=runner, daemon=True).start()

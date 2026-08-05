from __future__ import annotations

import queue
import threading
import traceback
from dataclasses import dataclass
from typing import Callable


@dataclass
class Job:
    label: str
    fn: Callable[[], object]
    on_done: Callable[[object], None] | None = None
    on_error: Callable[[Exception], None] | None = None


class JobQueue:
    """单任务队列：同一时间只执行一个生成任务，支持取消。"""

    def __init__(self) -> None:
        self._queue: queue.Queue[Job] = queue.Queue()
        self._cancel_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.current_label = ""

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            self.current_label = job.label
            self._cancel_event.clear()
            try:
                if self._cancel_event.is_set():
                    continue
                result = job.fn()
                if not self._cancel_event.is_set() and job.on_done:
                    job.on_done(result)
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                if job.on_error:
                    job.on_error(exc)
            finally:
                self.current_label = ""

    def submit(self, job: Job) -> None:
        self._queue.put(job)

    def cancel(self) -> None:
        self._cancel_event.set()

    @property
    def busy(self) -> bool:
        return bool(self.current_label)

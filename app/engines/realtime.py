from __future__ import annotations

import queue
import threading
import time

import numpy as np

from app.core import dsp
from app.core.config import Settings

from .base import RealtimeTransform


class AudioDeviceManager:
    @staticmethod
    def available() -> bool:
        try:
            import sounddevice as sd

            sd.query_devices()
            return True
        except Exception:
            return False

    @staticmethod
    def input_devices() -> list[dict]:
        import sounddevice as sd

        out = []
        for i, dev in enumerate(sd.query_devices()):
            if dev.get("max_input_channels", 0) > 0:
                out.append({"index": i, "name": dev["name"], "channels": dev["max_input_channels"]})
        return out

    @staticmethod
    def output_devices() -> list[dict]:
        import sounddevice as sd

        out = []
        for i, dev in enumerate(sd.query_devices()):
            if dev.get("max_output_channels", 0) > 0:
                out.append({"index": i, "name": dev["name"], "channels": dev["max_output_channels"]})
        return out

    @staticmethod
    def default_input() -> int:
        import sounddevice as sd

        return int(sd.default.device[0])

    @staticmethod
    def default_output() -> int:
        import sounddevice as sd

        return int(sd.default.device[1])


class RealtimeEngine:
    """麦克风 → 分块处理 → 输出设备的实时链路。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.transform: RealtimeTransform | None = None
        self.running = False
        self.bypass = False
        self.dry_wet = 1.0
        self.input_gain = 1.0
        self.output_gain = 1.0
        self.sr = 48000
        self.blocksize = 512
        self.input_device: int | None = None
        self.output_device: int | None = None
        self.in_level = 0.0
        self.out_level = 0.0
        self.latency_ms = 0.0
        self._stream = None
        self._in_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=16)
        self._out_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=16)
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()

    def set_devices(self, input_device: int, output_device: int, sr: int = 48000) -> None:
        self.input_device = input_device
        self.output_device = output_device
        self.sr = sr

    def set_transform(self, transform: RealtimeTransform | None) -> None:
        old = self.transform
        if old:
            try:
                old.close()
            except Exception:
                pass
        if transform:
            transform.load()
        self.transform = transform
        self._clear_queues()

    def _clear_queues(self) -> None:
        while not self._in_q.empty():
            try:
                self._in_q.get_nowait()
            except queue.Empty:
                break
        while not self._out_q.empty():
            try:
                self._out_q.get_nowait()
            except queue.Empty:
                break

    def _callback(self, indata, outdata, frames, time_info, status) -> None:
        raw = np.asarray(indata[:, 0], dtype=np.float32) * self.input_gain
        self.in_level = dsp.estimate_level(raw)
        if self.bypass or self.transform is None:
            out = raw
        else:
            try:
                self._in_q.put_nowait(raw)
            except queue.Full:
                try:
                    self._in_q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._in_q.put_nowait(raw)
                except queue.Full:
                    pass
            try:
                out = self._out_q.get_nowait()
            except queue.Empty:
                out = np.zeros(frames, dtype=np.float32)
        if len(out) < frames:
            out = np.pad(out, (0, frames - len(out)))
        out = out[:frames] * self.output_gain
        outdata[:, 0] = out
        self.out_level = dsp.estimate_level(out)

    def _worker_run(self) -> None:
        while not self._stop.is_set():
            try:
                chunk = self._in_q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                t0 = time.perf_counter()
                processed = self.transform.process(chunk, self.sr) if self.transform else chunk
                self.latency_ms = (time.perf_counter() - t0) * 1000
                processed = dsp.mix(chunk, np.asarray(processed, dtype=np.float32), self.dry_wet)
                try:
                    self._out_q.put_nowait(processed)
                except queue.Full:
                    try:
                        self._out_q.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        self._out_q.put_nowait(processed)
                    except queue.Full:
                        pass
            except Exception:
                try:
                    self._out_q.put_nowait(chunk)
                except queue.Full:
                    pass

    def start(self) -> None:
        import sounddevice as sd

        if self.running:
            return
        self._stop.clear()
        self._clear_queues()
        self._worker = threading.Thread(target=self._worker_run, daemon=True)
        self._worker.start()
        self._stream = sd.Stream(
            device=(self.input_device, self.output_device),
            samplerate=self.sr,
            blocksize=self.blocksize,
            channels=1,
            dtype="float32",
            callback=self._callback,
            latency="low",
        )
        self._stream.start()
        self.running = True

    def stop(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._stop.set()
        self.running = False

    def close(self) -> None:
        self.stop()
        if self.transform:
            try:
                self.transform.close()
            except Exception:
                pass
            self.transform = None

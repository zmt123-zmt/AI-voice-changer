from __future__ import annotations

import numpy as np

from app.core import dsp
from app.core.voices import Voice

from .base import EngineStatus, VCParams, RealtimeTransform


class _FallbackRealtime(RealtimeTransform):
    def __init__(self, params: VCParams) -> None:
        self.params = params
        self._tail = np.zeros(0, dtype=np.float32)

    def load(self) -> None:
        pass

    def process(self, chunk: np.ndarray, sr: int) -> np.ndarray:
        x = np.asarray(chunk, dtype=np.float32)
        y = dsp.pitch_shift(x, sr, self.params.semitones)
        y = dsp.normalize(y)
        if len(self._tail):
            n = min(len(self._tail), len(y))
            y[:n] = y[:n] * 0.5 + self._tail[:n] * 0.5
        self._tail = y[-256:].copy() if len(y) >= 256 else y.copy()
        y = dsp.mix(x, y, self.params.wet)
        return (y * self.params.volume).astype(np.float32)

    def close(self) -> None:
        pass


class FallbackVC:
    key = "dsp"
    display_name = "本地 DSP（演示）"

    def status(self) -> EngineStatus:
        return EngineStatus(
            True,
            self.display_name,
            "demo",
            "本地实时变调变声，不改变音色；安装 RVC 模型后支持音色克隆",
        )

    def convert(
        self,
        data: np.ndarray,
        sr: int,
        voice: Voice,
        params: VCParams,
        progress=None,
    ) -> tuple[int, np.ndarray]:
        x = np.asarray(data, dtype=np.float32)
        if params.denoise > 0:
            x = dsp.denoise(x, sr, params.denoise)
        y = dsp.pitch_shift(x, sr, params.semitones)
        y = dsp.normalize(y, peak=0.96)
        y = dsp.mix(x, y, params.wet)
        y = dsp.fade_edges(y, sr)
        return sr, (y * params.volume).astype(np.float32)

    def make_realtime(self, voice: Voice, params: VCParams) -> RealtimeTransform | None:
        return _FallbackRealtime(params)

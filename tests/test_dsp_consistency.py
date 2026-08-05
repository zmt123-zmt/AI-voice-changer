from __future__ import annotations

"""验证 time_stretch 向量化实现与逐帧参考实现数值一致（防止性能优化引入回归）。"""

import numpy as np

from app.core import dsp


def _reference_time_stretch(x: np.ndarray, rate: float, n_fft: int = 1024, hop: int = 256) -> np.ndarray:
    """优化前的逐帧循环实现，作为数值基准。"""
    x = np.asarray(x, dtype=np.float32)
    if abs(rate - 1.0) < 1e-6 or len(x) < n_fft + hop:
        return x.copy()
    pad = n_fft
    xp = np.pad(x, (pad, pad), mode="reflect")
    n = len(xp)
    window = np.hanning(n_fft).astype(np.float32)
    starts = np.arange(0, n - n_fft + 1, hop)
    frames = np.lib.stride_tricks.sliding_window_view(xp, n_fft)[::hop]
    frames = frames * window
    X = np.fft.rfft(frames, axis=1)
    N = X.shape[0]
    M = max(1, int(round(N * rate)))
    mag = np.abs(X)
    phase = np.angle(X)
    t_out = np.minimum(np.arange(M, dtype=np.float64) / rate, N - 1)
    i0 = np.floor(t_out).astype(np.int32)
    i1 = np.minimum(i0 + 1, N - 1)
    frac = (t_out - i0)[:, None]
    mags = (1.0 - frac) * mag[i0] + frac * mag[i1]
    dphi = phase - np.roll(phase, 1, axis=0)
    dphi[0] = 0.0
    dphi = dsp._wrap_phase(dphi)
    phase_acc = np.cumsum(dphi[i0] / rate, axis=0)
    phase_acc = phase_acc - phase_acc[0] + phase[0]
    Y = mags * np.exp(1j * phase_acc)
    out_len = n
    y = np.zeros(out_len, dtype=np.float64)
    win_sum = np.zeros(out_len, dtype=np.float64)
    for m in range(min(M, (out_len - n_fft) // hop + 1)):
        start = m * hop
        frame = np.real(np.fft.irfft(Y[m]))
        y[start : start + n_fft] += frame * window
        win_sum[start : start + n_fft] += window * window
    win_sum[win_sum < 1e-8] = 1.0
    y = y / win_sum
    y = y[pad : pad + int(round(len(x) * rate))]
    return dsp._fit_length(y, int(round(len(x) * rate))).astype(np.float32)


def _signal(sr: int = 48000, seconds: float = 2.0) -> np.ndarray:
    t = np.arange(int(sr * seconds)) / sr
    return (np.sin(2 * np.pi * 220 * t) + 0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def test_vectorized_matches_reference() -> None:
    x = _signal()
    for rate in (0.7, 1.0, 1.5):
        a = dsp.time_stretch(x, rate)
        b = _reference_time_stretch(x, rate)
        assert len(a) == len(b), f"rate={rate} 长度不一致: {len(a)} vs {len(b)}"
        diff = float(np.max(np.abs(a - b)))
        assert diff < 1e-4, f"rate={rate} 最大差异过大: {diff}"


def test_vectorized_long_audio() -> None:
    """长音频（约 30 秒）不崩溃且输出有限。"""
    x = _signal(seconds=30.0)
    y = dsp.time_stretch(x, 1.3)
    assert len(y) > 0
    assert np.all(np.isfinite(y))

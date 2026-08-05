from __future__ import annotations

from fractions import Fraction

import numpy as np
from scipy import signal


EPS = 1e-10


def _resample_rate(x: np.ndarray, rate: float) -> np.ndarray:
    """Resample by rate (>1 shortens the signal)."""
    if abs(rate - 1.0) < 1e-6:
        return np.asarray(x, dtype=np.float64).copy()
    frac = Fraction(rate).limit_denominator(512)
    up, down = frac.numerator, frac.denominator
    return signal.resample_poly(np.asarray(x, dtype=np.float64), down, up)


def _wrap_phase(p: np.ndarray) -> np.ndarray:
    return np.mod(p + np.pi, 2.0 * np.pi) - np.pi


def _fit_length(y: np.ndarray, n: int) -> np.ndarray:
    y = np.asarray(y, dtype=np.float32)
    if len(y) > n:
        return y[:n]
    if len(y) < n:
        tail = np.zeros(n - len(y), dtype=np.float32)
        return np.concatenate([y, tail])
    return y


def time_stretch(x: np.ndarray, rate: float, n_fft: int = 1024, hop: int = 256) -> np.ndarray:
    """Phase-vocoder time stretch. rate > 1 makes the signal longer, pitch preserved."""
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
    dphi = _wrap_phase(dphi)
    phase_acc = np.cumsum(dphi[i0] / rate, axis=0)
    phase_acc = phase_acc - phase_acc[0] + phase[0]
    Y = mags * np.exp(1j * phase_acc)

    out_len = n
    n_out_frames = min(M, (out_len - n_fft) // hop + 1)
    y = np.zeros(out_len, dtype=np.float64)
    win_sum = np.zeros(out_len, dtype=np.float64)
    win2 = (window.astype(np.float64) * window)
    frame_idx = np.arange(n_fft, dtype=np.int64)
    BATCH = 256
    win2_tiled = np.tile(win2, BATCH)
    for b0 in range(0, n_out_frames, BATCH):
        b1 = min(b0 + BATCH, n_out_frames)
        # 批量逆 FFT + 加窗（替代原先逐帧 Python 循环）
        frames_out = np.real(np.fft.irfft(Y[b0:b1], n=n_fft, axis=1)) * window
        starts_b = (np.arange(b0, b1) * hop)[:, None]
        idx = (starts_b + frame_idx).ravel()
        y += np.bincount(
            idx, weights=frames_out.ravel().astype(np.float64), minlength=out_len
        )
        win_sum += np.bincount(
            idx, weights=win2_tiled[: (b1 - b0) * n_fft], minlength=out_len
        )
    win_sum[win_sum < 1e-8] = 1.0
    y = y / win_sum
    y = y[pad : pad + int(round(len(x) * rate))]
    return _fit_length(y, int(round(len(x) * rate))).astype(np.float32)


def pitch_shift(x: np.ndarray, sr: int, semitones: float) -> np.ndarray:
    """Pitch shift preserving duration using phase-vocoder time stretch + resample."""
    if abs(semitones) < 1e-3:
        return np.asarray(x, dtype=np.float32).copy()
    f = 2.0 ** (semitones / 12.0)
    n = len(x)
    stretched = time_stretch(x, f)
    shifted = _resample_rate(stretched, f)
    return _fit_length(shifted, n)


def denoise(x: np.ndarray, sr: int, strength: float = 0.5) -> np.ndarray:
    """Simple spectral-gate denoise. strength in 0..1."""
    x = np.asarray(x, dtype=np.float32)
    if strength <= 0.0 or len(x) < 2048:
        return x.copy()
    n_fft = 1024
    hop = 256
    window = "hann"
    f, t, Z = signal.stft(
        x,
        fs=sr,
        window=window,
        nperseg=n_fft,
        noverlap=n_fft - hop,
        boundary="zeros",
    )
    mag = np.abs(Z)
    phase = np.angle(Z)
    noise_floor = np.median(mag, axis=1, keepdims=True) + EPS
    gain = np.clip(1.0 - strength * noise_floor / (mag + EPS), 0.0, 1.0)
    gain = signal.savgol_filter(gain, 5, 1, axis=0)
    y = signal.istft(
        gain * mag * np.exp(1j * phase),
        fs=sr,
        window=window,
        nperseg=n_fft,
        noverlap=n_fft - hop,
        boundary="zeros",
    )[1]
    return _fit_length(y, len(x)).astype(np.float32)


def normalize(x: np.ndarray, peak: float = 0.98) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    p = float(np.max(np.abs(x))) if len(x) else 0.0
    if p <= EPS:
        return x.copy()
    return x * (peak / p)


def fade_edges(x: np.ndarray, sr: int, seconds: float = 0.01) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32).copy()
    n = min(int(sr * seconds), len(x) // 2)
    if n <= 0:
        return x
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    x[:n] *= ramp
    x[-n:] *= ramp[::-1]
    return x


def mix(x: np.ndarray, y: np.ndarray, wet: float) -> np.ndarray:
    wet = float(np.clip(wet, 0.0, 1.0))
    x = np.asarray(x, dtype=np.float32)
    y = np.asarray(y, dtype=np.float32)
    n = min(len(x), len(y))
    return (x[:n] * (1.0 - wet) + y[:n] * wet).astype(np.float32)


def volume(x: np.ndarray, factor: float) -> np.ndarray:
    return np.asarray(x, dtype=np.float32) * float(factor)


def estimate_level(x: np.ndarray) -> float:
    if x is None or len(x) == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(np.asarray(x, dtype=np.float32))) + EPS))
    db = 20.0 * np.log10(rms + EPS)
    return float(np.clip((db + 60.0) / 60.0, 0.0, 1.0))


def concat_parts(parts: list[np.ndarray], sr: int, gap: float = 0.25) -> np.ndarray:
    """Concatenate audio parts with a short crossfade for seamless segmentation."""
    if not parts:
        return np.zeros(0, dtype=np.float32)
    gap_n = int(sr * gap)
    out = np.asarray(parts[0], dtype=np.float32)
    for part in parts[1:]:
        part = np.asarray(part, dtype=np.float32)
        xf = min(gap_n, len(out), len(part))
        if xf > 0:
            ramp = np.linspace(0.0, 1.0, xf, dtype=np.float32)
            out[-xf:] = out[-xf:] * (1.0 - ramp)
            part[:xf] = part[:xf] * ramp
        out = np.concatenate([out, part])
    return out.astype(np.float32)

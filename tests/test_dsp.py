from __future__ import annotations

import numpy as np

from app.core import dsp


def _signal(sr: int, seconds: float = 1.0) -> np.ndarray:
    t = np.arange(int(sr * seconds)) / sr
    return (np.sin(2 * np.pi * 220 * t) + 0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def test_pitch_shift_preserves_length() -> None:
    x = _signal(48000)
    for st in (0, 3, -4, 12):
        y = dsp.pitch_shift(x, 48000, st)
        assert len(y) == len(x)
        assert np.all(np.isfinite(y))


def test_time_stretch_duration() -> None:
    x = _signal(48000, 1.0)
    slow = dsp.time_stretch(x, 1.5)
    assert len(slow) > len(x)
    fast = dsp.time_stretch(x, 0.5)
    assert len(fast) < len(x)


def test_denoise_keeps_length() -> None:
    x = _signal(48000)
    y = dsp.denoise(x, 48000, 0.5)
    assert len(y) == len(x)
    assert np.all(np.isfinite(y))


def test_mix_and_volume() -> None:
    a = np.ones(100, dtype=np.float32)
    b = np.zeros(100, dtype=np.float32)
    m = dsp.mix(a, b, 0.5)
    assert np.allclose(m, 0.5)
    v = dsp.volume(a, 0.5)
    assert np.allclose(v, 0.5)


def test_concat_parts() -> None:
    a = np.ones(1000, dtype=np.float32)
    b = np.ones(1000, dtype=np.float32) * 2
    out = dsp.concat_parts([a, b], 48000)
    assert len(out) == 2000
    assert np.all(np.isfinite(out))

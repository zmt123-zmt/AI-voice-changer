from __future__ import annotations

import numpy as np

from app.core.validation import analyze_audio


def _sine(sr: int, seconds: float, freq: float = 200.0) -> np.ndarray:
    t = np.arange(int(sr * seconds)) / sr
    return np.sin(2 * np.pi * freq * t).astype(np.float32) * 0.5


def test_silence_is_rejected() -> None:
    report = analyze_audio(np.zeros(48000, dtype=np.float32), 48000)
    assert report.speech_ratio < 0.1
    assert report.similarity_estimate < 4.0
    assert any("短" in w for w in report.warnings)


def test_short_audio_warns() -> None:
    report = analyze_audio(_sine(16000, 1.0), 16000)
    assert any("过短" in w for w in report.warnings)


def test_long_clean_audio_scores_higher() -> None:
    x = _sine(48000, 12.0)
    # add a little silence at the edges to mimic speech pauses
    x[:48000] *= 0.01
    x[-24000:] *= 0.01
    report = analyze_audio(x, 48000)
    assert report.duration > 10.0
    assert report.similarity_estimate >= 3.5
    assert report.sample_rate == 48000


def test_clipping_detected() -> None:
    x = np.clip(_sine(48000, 6.0) * 3.0, -1.0, 1.0)
    report = analyze_audio(x, 48000)
    assert report.peak >= 0.999
    assert any("削波" in w for w in report.warnings)

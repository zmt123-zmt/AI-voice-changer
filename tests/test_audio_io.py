from __future__ import annotations

import numpy as np

from app.core import audio_io


def test_wav_roundtrip(tmp_path) -> None:
    path = tmp_path / "a.wav"
    x = np.sin(2 * np.pi * 220 * np.arange(48000) / 48000).astype(np.float32) * 0.5
    audio_io.save_wav(path, x, 48000)
    sr, y = audio_io.decode_audio(path)
    assert sr == 48000
    assert np.allclose(x, y, atol=1e-4)


def test_flac_export(tmp_path) -> None:
    path = tmp_path / "a.flac"
    x = np.zeros(9600, dtype=np.float32)
    audio_io.export_audio(path, x, 48000, fmt="flac")
    assert path.exists()


def test_resample() -> None:
    x = np.zeros(48000, dtype=np.float32)
    y = audio_io.resample_audio(x, 48000, 24000)
    assert len(y) == 24000

from __future__ import annotations

import numpy as np

from app.core import audio_io
from app.core.config import Settings
from app.core.validation import analyze_audio
from app.core.voices import VoiceLibrary


def _make_wav(path, sr: int = 48000, seconds: float = 6.0) -> None:
    t = np.arange(int(sr * seconds)) / sr
    audio_io.save_wav(path, np.sin(2 * np.pi * 220 * t).astype(np.float32), sr)


def test_add_rename_delete(tmp_path) -> None:
    lib = VoiceLibrary(Settings())
    src = tmp_path / "ref.wav"
    _make_wav(src)
    sr, data = audio_io.decode_audio(src)
    report = analyze_audio(data, sr)
    voice = lib.add_from_file("测试音色", src, report)
    assert voice.id in [v.id for v in lib.list()]
    assert lib.get(voice.id) is not None
    lib.rename(voice.id, "新名字")
    assert lib.get(voice.id).name == "新名字"
    lib.delete(voice.id)
    assert lib.get(voice.id) is None


def test_demo_voice() -> None:
    lib = VoiceLibrary(Settings())
    v = lib.add_demo("演示")
    assert v.kind == "demo"
    lib.delete(v.id)


def test_prompt_text_saved(tmp_path) -> None:
    lib = VoiceLibrary(Settings())
    src = tmp_path / "ref.wav"
    _make_wav(src)
    sr, data = audio_io.decode_audio(src)
    voice = lib.add_from_file("x", src, analyze_audio(data, sr))
    lib.save_prompt_text(voice.id, "这是参考文字")
    assert lib.get(voice.id).prompt_text == "这是参考文字"

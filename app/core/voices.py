from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from . import audio_io
from .config import Settings
from .validation import AudioReport


@dataclass
class Voice:
    id: str
    name: str
    source_name: str
    wav_path: str
    created_at: str
    duration: float = 0.0
    sample_rate: int = 0
    similarity_estimate: float = 0.0
    noise_score: float = 0.0
    kind: str = "zero_shot"  # zero_shot | rvc | demo
    prompt_text: str = ""
    rvc_model_path: str = ""
    notes: str = ""
    # 附加参考音频（GPT-SoVITS 多参考）：[{"wav_path", "prompt_text", "prompt_language"}]
    extra_refs: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Voice":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


class VoiceLibrary:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.path = settings.voices_dir() / "library.json"
        self.voices: list[Voice] = []
        # RLock：允许 _save 在外层修改锁内重入，避免死锁
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.voices = [Voice.from_dict(d) for d in data]
            except (json.JSONDecodeError, TypeError):
                self.voices = []

    def _save(self) -> None:
        with self._lock:
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps([asdict(v) for v in self.voices], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self.path)

    def _mutate(self, fn: Callable) -> None:
        """加锁执行修改并持久化，避免后台线程并发写坏 JSON。"""
        with self._lock:
            fn()
        self._save()

    def list(self) -> list[Voice]:
        return list(self.voices)

    def get(self, voice_id: str) -> Voice | None:
        for v in self.voices:
            if v.id == voice_id:
                return v
        return None

    def add_from_file(self, name: str, source: str | Path, report: AudioReport) -> Voice:
        source = Path(source)
        voice_id = uuid.uuid4().hex[:12]
        dest = self.settings.voices_dir() / f"{voice_id}.wav"
        sr, data = audio_io.decode_audio(source, self.settings)
        audio_io.save_wav(dest, data, sr)
        voice = Voice(
            id=voice_id,
            name=name.strip() or source.stem,
            source_name=source.name,
            wav_path=str(dest),
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            duration=report.duration,
            sample_rate=sr,
            similarity_estimate=report.similarity_estimate,
            noise_score=report.noise_score,
        )
        with self._lock:
            self.voices.append(voice)
            self._save()
        return voice

    def add_demo(self, name: str = "演示音色") -> Voice:
        voice_id = uuid.uuid4().hex[:12]
        voice = Voice(
            id=voice_id,
            name=name,
            source_name="演示",
            wav_path="",
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            kind="demo",
            notes="内置演示音色，用于无模型状态下体验完整流程",
        )
        with self._lock:
            self.voices.append(voice)
            self._save()
        return voice

    def update(self, voice: Voice) -> None:
        with self._lock:
            for i, v in enumerate(self.voices):
                if v.id == voice.id:
                    self.voices[i] = voice
                    break
            self._save()

    def rename(self, voice_id: str, name: str) -> None:
        v = self.get(voice_id)
        if v:
            with self._lock:
                v.name = name.strip() or v.name
                self._save()

    def delete(self, voice_id: str) -> None:
        v = self.get(voice_id)
        if not v:
            return
        with self._lock:
            self.voices = [x for x in self.voices if x.id != voice_id]
            if v.wav_path:
                try:
                    Path(v.wav_path).unlink(missing_ok=True)
                except OSError:
                    pass
            self._save()

    def save_prompt_text(self, voice_id: str, prompt_text: str) -> None:
        v = self.get(voice_id)
        if v:
            with self._lock:
                v.prompt_text = prompt_text
                self._save()

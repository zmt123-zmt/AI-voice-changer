from __future__ import annotations

from app.core.config import Settings
from app.core.voices import Voice

from .fallback_tts import FallbackTTS
from .fallback_vc import FallbackVC
from .gpt_sovits import GPTSoVITS_TTS
from .rvc import RVCAdapter


class EngineRegistry:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.fallback_tts = FallbackTTS()
        self.fallback_vc = FallbackVC()
        self.gpt_sovits = GPTSoVITS_TTS(settings)
        self.rvc = RVCAdapter(settings)

    def tts_for(self, voice: Voice | None):
        if voice and voice.kind != "demo" and self.gpt_sovits.status().available:
            return self.gpt_sovits
        return self.fallback_tts

    def vc_for(self, voice: Voice | None):
        if voice and voice.kind != "demo" and self.rvc.status(voice).available:
            return self.rvc
        return self.fallback_vc

    def summary(self) -> list[str]:
        g = self.gpt_sovits.status()
        r = self.rvc.status()
        lines = [
            f"TTS：{'AI 克隆' if g.available else '演示'}"
            f"（{'在线' if g.mode == 'ai' else 'SAPI'}）",
            f"VC：{'RVC' if r.available else 'DSP 演示'}",
        ]
        return lines

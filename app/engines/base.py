from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

import numpy as np

from app.core.voices import Voice


@dataclass
class EngineStatus:
    available: bool
    name: str
    mode: str  # demo | ai
    detail: str


@dataclass
class TTSParams:
    speed: float = 1.0
    pitch: float = 0.0
    volume: float = 1.0


@dataclass
class VCParams:
    semitones: float = 0.0
    strength: float = 0.85
    denoise: float = 0.0
    wet: float = 1.0
    volume: float = 1.0


Progress = Callable[[float, str], None] | None


class TTSEngine(Protocol):
    key: str
    display_name: str

    def status(self) -> EngineStatus: ...

    def synthesize(
        self,
        text: str,
        language: str,
        params: TTSParams,
        voice: Voice,
        progress: Progress = None,
    ) -> tuple[int, np.ndarray]: ...


class VCEngine(Protocol):
    key: str
    display_name: str

    def status(self) -> EngineStatus: ...

    def convert(
        self,
        data: np.ndarray,
        sr: int,
        voice: Voice,
        params: VCParams,
        progress: Progress = None,
    ) -> tuple[int, np.ndarray]: ...

    def make_realtime(self, voice: Voice, params: VCParams) -> "RealtimeTransform | None": ...


class RealtimeTransform(Protocol):
    def load(self) -> None: ...

    def process(self, chunk: np.ndarray, sr: int) -> np.ndarray: ...

    def close(self) -> None: ...

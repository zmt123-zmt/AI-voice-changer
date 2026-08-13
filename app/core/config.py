from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent


def _data_dir() -> Path:
    override = os.environ.get("AI_VOICE_DATA_DIR")
    d = Path(override) if override else ROOT / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Settings:
    consent_accepted: bool = False
    language: str = "zh-CN"
    output_format: str = "wav"
    output_sr: int = 48000
    output_dir: str = ""
    ffmpeg_path: str = ""
    gpt_sovits_dir: str = ""
    gpt_sovits_api_url: str = "http://127.0.0.1:9880"
    gpt_sovits_api_script: str = ""
    rvc_dir: str = ""
    rvc_model_path: str = ""
    rvc_index_path: str = ""
    rvc_f0_method: str = "rmvpe"
    rvc_f0up_key: int = 0
    rvc_index_rate: float = 0.75
    rvc_sid: int = 0
    rvc_cli_template: str = ""
    watermark_enabled: bool = False
    default_input_device: str = ""
    default_output_device: str = ""
    extra: dict = field(default_factory=dict)

    def data_dir(self) -> Path:
        return _data_dir()

    def voices_dir(self) -> Path:
        d = self.data_dir() / "voices"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def output_dir_path(self) -> Path:
        if self.output_dir:
            p = Path(self.output_dir)
        else:
            p = self.data_dir() / "output"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def models_dir(self) -> Path:
        d = ROOT / "models"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def tmp_dir(self) -> Path:
        d = self.data_dir() / "tmp"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def to_dict(self) -> dict:
        out = {
            "consent_accepted": self.consent_accepted,
            "language": self.language,
            "output_format": self.output_format,
            "output_sr": self.output_sr,
            "output_dir": self.output_dir,
            "ffmpeg_path": self.ffmpeg_path,
            "gpt_sovits_dir": self.gpt_sovits_dir,
            "gpt_sovits_api_url": self.gpt_sovits_api_url,
            "gpt_sovits_api_script": self.gpt_sovits_api_script,
            "rvc_dir": self.rvc_dir,
            "rvc_model_path": self.rvc_model_path,
            "rvc_index_path": self.rvc_index_path,
            "rvc_f0_method": self.rvc_f0_method,
            "rvc_f0up_key": self.rvc_f0up_key,
            "rvc_index_rate": self.rvc_index_rate,
            "rvc_sid": self.rvc_sid,
            "rvc_cli_template": self.rvc_cli_template,
            "watermark_enabled": self.watermark_enabled,
            "default_input_device": self.default_input_device,
            "default_output_device": self.default_output_device,
            "extra": self.extra,
        }
        return out

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


class Config:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (_data_dir() / "settings.json")
        self.settings = self._load()

    def _load(self) -> Settings:
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                return Settings.from_dict(data)
            except (json.JSONDecodeError, TypeError):
                pass
        return Settings()

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self.settings.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        self.save()


def env_ffmpeg() -> str:
    return os.environ.get("FFMPEG_PATH", "")

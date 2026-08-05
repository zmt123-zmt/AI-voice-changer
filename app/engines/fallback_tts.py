from __future__ import annotations

import subprocess
import sys
import tempfile
import xml.sax.saxutils
from pathlib import Path

import numpy as np

from app.core import audio_io
from app.core.voices import Voice

from .base import EngineStatus, TTSParams


LANG_PATTERN = {
    "zh": "Chinese|简体|中文",
    "en": "English|美国|英文",
    "ja": "Japanese|日本|日文",
}


def _ps_quote(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def _sanitize(text: str) -> str:
    return text.encode("utf-8", "ignore").decode("utf-8", "ignore")


def _decode_ps_error(raw: bytes) -> str:
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


class FallbackTTS:
    key = "sapi"
    display_name = "系统语音（演示）"

    def status(self) -> EngineStatus:
        if sys.platform != "win32":
            return EngineStatus(False, self.display_name, "demo", "仅 Windows 可用")
        return EngineStatus(
            True,
            self.display_name,
            "demo",
            "Windows 本地 SAPI 语音，不克隆音色；安装 GPT-SoVITS 后可克隆",
        )

    def synthesize(
        self,
        text: str,
        language: str,
        params: TTSParams,
        voice: Voice,
        progress=None,
    ) -> tuple[int, np.ndarray]:
        if sys.platform != "win32":
            raise RuntimeError("系统语音引擎仅支持 Windows")
        pattern = LANG_PATTERN.get(language[:2], LANG_PATTERN["zh"])
        escaped = xml.sax.saxutils.escape(text)
        escaped = escaped.replace('"', "&quot;").replace("'", "&apos;")
        rate = int(max(-10, min(10, round((params.speed - 1.0) * 10))))
        pitch_hz = int(round(220.0 * (2.0 ** (params.pitch / 12.0))))
        ssml = (
            f'<pitch absmiddle="{pitch_hz}">'
            f'<rate absspeed="{rate}">{escaped}</rate></pitch>'
        )
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()
        ssml_tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
        ssml_path = Path(ssml_tmp.name)
        ssml_tmp.close()
        try:
            ssml_path.write_text(ssml, encoding="utf-8")
            script = f"""
$ErrorActionPreference = 'Stop'
$v = New-Object -ComObject SAPI.SpVoice
$voices = @($v.GetVoices())
$pick = $voices | Where-Object {{ $_.GetDescription() -match {_ps_quote(pattern)} }} | Select-Object -First 1
if (-not $pick) {{ $pick = $voices | Select-Object -First 1 }}
if (-not $pick) {{ throw '系统未安装任何语音包' }}
$v.Voice = $pick
$v.Rate = {rate}
$v.Volume = {int(max(0, min(100, params.volume * 100)))}
$stream = New-Object -ComObject SAPI.SpFileStream
$stream.Open({_ps_quote(str(tmp_path))}, 3)
$v.AudioOutputStream = $stream
$txt = [System.IO.File]::ReadAllText({_ps_quote(str(ssml_path))}, [System.Text.Encoding]::UTF8)
$v.Speak($txt, 8)
$stream.Close()
"""
            flags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                flags = subprocess.CREATE_NO_WINDOW
            proc = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script,
                ],
                capture_output=True,
                timeout=180,
                creationflags=flags,
            )
            if proc.returncode != 0:
                err = _sanitize(_decode_ps_error(proc.stderr))[-300:]
                raise RuntimeError(f"系统语音合成失败：{err}")
            sr, data = audio_io.decode_audio(tmp_path)
            if sr < 22050:
                data = audio_io.resample_audio(data, sr, 22050)
                sr = 22050
            return sr, data
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            try:
                ssml_path.unlink(missing_ok=True)
            except OSError:
                pass

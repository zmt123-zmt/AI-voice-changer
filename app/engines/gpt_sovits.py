from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

from app.core import audio_io
from app.core.config import Settings
from app.core.voices import Voice

from .base import EngineStatus, TTSParams


LANG_MAP = {"zh": "中文", "en": "英文", "ja": "日文"}


class GPTSoVITS_TTS:
    key = "gpt_sovits"
    display_name = "GPT-SoVITS（AI 克隆）"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._server: subprocess.Popen | None = None
        # API 探测缓存：探测在后台线程进行，status()/server_alive() 只读缓存，
        # 避免在主线程（UI 状态轮询每 1.2s 一次）发起可能阻塞的网络请求。
        self._alive: bool | None = None
        self._alive_at = 0.0
        self._lock = threading.Lock()
        self._probe_thread = threading.Thread(target=self._probe_loop, daemon=True)
        self._probe_thread.start()

    @property
    def url(self) -> str:
        return self.settings.gpt_sovits_api_url.rstrip("/")

    def _script_candidates(self) -> list[Path]:
        out: list[Path] = []
        if self.settings.gpt_sovits_api_script:
            out.append(Path(self.settings.gpt_sovits_api_script))
        if self.settings.gpt_sovits_dir:
            out.append(Path(self.settings.gpt_sovits_dir) / "api.py")
            out.append(Path(self.settings.gpt_sovits_dir) / "GPT_SoVITS" / "inference_webui.py")
        return [p for p in out if p.exists()]

    def _probe(self) -> bool:
        try:
            # 本地 API 探测不走系统代理：用户可能开着代理软件（Clash 等），
            # 默认 urllib 会把 127.0.0.1 请求也转发给代理导致探测失败
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(self.url, timeout=1.0) as resp:
                return resp.status < 500
        except urllib.error.HTTPError as exc:
            # urllib 会把 4xx/5xx 以 HTTPError 异常抛出，而不是返回响应；
            # GPT-SoVITS 根路径返回 400 属于“服务器有响应”，应视为存活
            return exc.code < 500
        except Exception as exc:  # noqa: BLE001
            print(f"[GPT-SoVITS] 探测失败 {self.url}: {exc!r}", flush=True)
            return False

    def _probe_loop(self) -> None:
        """后台线程：每 5 秒探测一次 API，刷新缓存。"""
        while True:
            ok = self._probe()
            with self._lock:
                self._alive = ok
                self._alive_at = time.monotonic()
            time.sleep(5.0)

    def server_alive(self) -> bool:
        """读取最近一次后台探测结果（不发起网络请求，不阻塞）。"""
        with self._lock:
            return bool(self._alive)

    def server_alive_force(self) -> bool:
        """强制实时探测一次（仅用于服务启动等待等明确需要确认的场景）。"""
        ok = self._probe()
        with self._lock:
            self._alive = ok
            self._alive_at = time.monotonic()
        return ok

    def status(self) -> EngineStatus:
        if self.server_alive():
            return EngineStatus(True, self.display_name, "ai", f"API 已连接：{self.url}")
        scripts = self._script_candidates()
        if scripts:
            return EngineStatus(
                True,
                self.display_name,
                "ai",
                "检测到 GPT-SoVITS 服务脚本，使用时自动启动",
            )
        return EngineStatus(
            False,
            self.display_name,
            "ai",
            "未配置 GPT-SoVITS：在设置中填写目录或 API 地址",
        )

    def ensure_server(self) -> None:
        # 用户明确请求生成时强制实时探测，避免缓存滞后导致重复启动
        if self.server_alive_force():
            return
        scripts = self._script_candidates()
        if not scripts:
            raise RuntimeError("未配置 GPT-SoVITS（设置 → 模型目录）")
        script = scripts[0]
        host, port = self.url.split("//")[-1].split(":")
        port = port.split("/")[0]
        flags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags = subprocess.CREATE_NO_WINDOW
        self._server = subprocess.Popen(
            [sys.executable, str(script), "-a", host, "-p", port],
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(90):
            if self.server_alive_force():
                return
            time.sleep(1.0)
        raise RuntimeError("GPT-SoVITS 服务启动超时，请检查模型文件是否完整")

    def _synthesize_remote(
        self,
        text: str,
        language: str,
        params: TTSParams,
        voice: Voice,
    ) -> bytes:
        lang = LANG_MAP.get(language[:2], "auto")
        # 多参考：附加参考音频（dict 列表，v2pro api 的 inp_refs 格式）
        inp_refs = [
            {
                "refer_wav_path": r["wav_path"],
                "prompt_text": r.get("prompt_text", ""),
                "prompt_language": r.get("prompt_language", "") or lang,
            }
            for r in getattr(voice, "extra_refs", [])
            if r.get("wav_path") and Path(r["wav_path"]).exists()
        ]
        # 兼容 GPT-SoVITS v2pro 整合包：POST / + JSON 请求体
        payload = {
            "refer_wav_path": voice.wav_path,
            "prompt_text": voice.prompt_text or "",
            "prompt_language": lang,
            "text": text,
            "text_language": lang,
            "cut_punc": "",
            "top_k": 15,
            "top_p": 1.0,
            "temperature": 1.0,
            "speed": float(params.speed),
            "inp_refs": inp_refs,
            "sample_steps": 32,
            "if_sr": False,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.url}/",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # 本地 API 请求不走系统代理
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(req, timeout=300) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")[:300].strip()
            raise RuntimeError(
                f"GPT-SoVITS 合成失败（HTTP {exc.code}）：{body}"
            ) from exc

    @staticmethod
    def _parse_audio_response(raw: bytes) -> tuple[int, np.ndarray]:
        """解析 API 返回：优先 wav 二进制，兼容 JSON（base64 或文件路径）。"""
        try:
            return audio_io.audio_from_wav_bytes(raw)
        except Exception:
            pass
        try:
            import base64

            obj = json.loads(raw.decode("utf-8"))
            if not isinstance(obj, dict):
                raise ValueError("非 JSON 对象")
            data_field = obj.get("data") or obj.get("audio") or obj.get("audio_base64")
            if isinstance(data_field, str) and data_field.startswith("data:"):
                data_field = data_field.split(",", 1)[1]
            if isinstance(data_field, str) and Path(data_field).exists():
                return audio_io.decode_audio(data_field)
            if isinstance(data_field, str):
                wav = base64.b64decode(data_field)
                return audio_io.audio_from_wav_bytes(wav)
        except Exception:
            pass
        raise RuntimeError("无法解析 GPT-SoVITS 返回的音频数据（非 wav 且非 JSON）")

    def synthesize(
        self,
        text: str,
        language: str,
        params: TTSParams,
        voice: Voice,
        progress=None,
    ) -> tuple[int, np.ndarray]:
        if not voice.wav_path or not Path(voice.wav_path).exists():
            raise RuntimeError("该音色没有参考音频，无法用于克隆 TTS")
        if progress:
            progress(0.1, "启动 GPT-SoVITS 服务")
        self.ensure_server()
        if progress:
            progress(0.3, "正在合成")
        raw = self._synthesize_remote(text, language, params, voice)
        sr, data = self._parse_audio_response(raw)
        if progress:
            progress(1.0, "完成")
        return sr, data

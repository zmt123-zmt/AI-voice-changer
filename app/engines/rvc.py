from __future__ import annotations

import importlib.util
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from app.core import audio_io
from app.core.config import Settings
from app.core.voices import Voice

from .base import EngineStatus, VCParams, RealtimeTransform


class RVCAdapter:
    key = "rvc"
    display_name = "RVC（AI 音色转换）"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._rvc = None

    def _model_path(self, voice: Voice | None) -> str:
        if voice and voice.rvc_model_path:
            return voice.rvc_model_path
        return self.settings.rvc_model_path

    def _python_available(self) -> bool:
        return importlib.util.find_spec("rvc_python") is not None

    def _cli_available(self) -> bool:
        if self.settings.rvc_cli_template:
            return True
        return bool(self.settings.rvc_dir and (Path(self.settings.rvc_dir) / "infer_cli.py").exists())

    def status(self, voice: Voice | None = None) -> EngineStatus:
        model = self._model_path(voice)
        if self._python_available() and model:
            return EngineStatus(True, self.display_name, "ai", "rvc-python 模式（GPU/CPU）")
        if self._cli_available() and model:
            return EngineStatus(True, self.display_name, "ai", "RVC 命令行模式")
        if model:
            return EngineStatus(
                False,
                self.display_name,
                "ai",
                "未安装 rvc-python，也未配置 RVC 命令行（设置 → RVC）",
            )
        return EngineStatus(
            False,
            self.display_name,
            "ai",
            "未配置 RVC 模型文件（.pth），离线转换与实时变声不可用",
        )

    def _ensure_rvc(self, model: str):
        if self._rvc is not None:
            return self._rvc
        from rvc_python.infer import RVCInference

        self._rvc = RVCInference(device="cuda:0")
        self._rvc.load_model(model)
        return self._rvc

    def _run_cli(self, input_path: Path, output_path: Path, model: str, params: VCParams) -> None:
        if self.settings.rvc_cli_template:
            template = self.settings.rvc_cli_template
        else:
            template = (
                "{python} {rvc_dir}/infer_cli.py --model_path {model} --input_path {input} "
                "--output_path {output} --f0up_key {f0up} --f0method {f0method} "
                "--index_path {index} --index_rate {index_rate}"
            )

        def q(p: str) -> str:
            return shlex.quote(str(p))

        cmd = template.format(
            python=q(sys.executable),
            rvc_dir=q(self.settings.rvc_dir),
            model=q(model),
            input=q(input_path),
            output=q(output_path),
            f0up=int(params.semitones),
            f0method=self.settings.rvc_f0_method,
            index=q(self.settings.rvc_index_path),
            index_rate=float(self.settings.rvc_index_rate),
        )
        flags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags = subprocess.CREATE_NO_WINDOW
        proc = subprocess.run(cmd, shell=True, capture_output=True, timeout=600, creationflags=flags)
        if proc.returncode != 0:
            raise RuntimeError(f"RVC 转换失败：{proc.stderr.decode(errors='ignore')[-300:]}")

    def convert(
        self,
        data: np.ndarray,
        sr: int,
        voice: Voice,
        params: VCParams,
        progress=None,
    ) -> tuple[int, np.ndarray]:
        model = self._model_path(voice)
        if not model or not Path(model).exists():
            raise RuntimeError("未找到 RVC 模型文件，请先在设置中配置")
        tmp = tempfile.TemporaryDirectory(dir=self.settings.tmp_dir())
        try:
            in_path = Path(tmp.name) / "input.wav"
            out_path = Path(tmp.name) / "output.wav"
            audio_io.save_wav(in_path, data, sr)
            if progress:
                progress(0.1, "加载 RVC 模型")
            if self._python_available():
                rvc = self._ensure_rvc(model)
                if progress:
                    progress(0.4, "RVC 推理中")
                rvc.infer_file(
                    str(in_path),
                    str(out_path),
                    f0up_key=int(params.semitones),
                    f0method=self.settings.rvc_f0_method,
                    index_path=self.settings.rvc_index_path or "",
                    index_rate=float(self.settings.rvc_index_rate),
                )
            elif self._cli_available():
                self._run_cli(in_path, out_path, model, params)
            else:
                raise RuntimeError("RVC 不可用：请安装 rvc-python 或配置 RVC 命令行")
            out_sr, out_data = audio_io.decode_audio(out_path)
            if progress:
                progress(1.0, "完成")
            return out_sr, out_data
        finally:
            tmp.cleanup()

    def make_realtime(self, voice: Voice, params: VCParams) -> RealtimeTransform | None:
        model = self._model_path(voice)
        if not self._python_available() or not model or not Path(model).exists():
            return None
        try:
            rvc = self._ensure_rvc(model)
            probe = np.zeros(2048, dtype=np.float32)
            out = rvc.infer(
                probe,
                f0up_key=int(params.semitones),
                f0method=self.settings.rvc_f0_method,
                index_path=self.settings.rvc_index_path or "",
                index_rate=float(self.settings.rvc_index_rate),
            )
            if out is None:
                return None
            return _RVCRealtime(rvc, self.settings, params)
        except Exception:
            return None


class _RVCRealtime(RealtimeTransform):
    def __init__(self, rvc, settings: Settings, params: VCParams) -> None:
        self._rvc = rvc
        self.settings = settings
        self.params = params

    def load(self) -> None:
        pass

    def process(self, chunk: np.ndarray, sr: int) -> np.ndarray:
        try:
            out = self._rvc.infer(
                chunk,
                f0up_key=int(self.params.semitones),
                f0method=self.settings.rvc_f0_method,
                index_path=self.settings.rvc_index_path or "",
                index_rate=float(self.settings.rvc_index_rate),
            )
            return np.asarray(out, dtype=np.float32)
        except Exception:
            return np.asarray(chunk, dtype=np.float32)

    def close(self) -> None:
        pass

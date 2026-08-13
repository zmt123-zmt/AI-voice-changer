from __future__ import annotations

import importlib.util
import shlex
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import numpy as np

from app.core import audio_io
from app.core.config import Settings
from app.core.voices import Voice

from .base import EngineStatus, VCParams, RealtimeTransform


def _index_rate(settings: Settings, params: VCParams) -> float:
    """像训练样本的权重：strength>=0 时用滑杆值，否则用设置默认。
    index_rate 越高，输出越被拉向训练样本（目标音色本体）。"""
    if params.strength is not None and params.strength >= 0:
        return float(params.strength)
    return float(settings.rvc_index_rate)


class RVCAdapter:
    key = "rvc"
    display_name = "RVC（AI 音色转换）"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._rvc = None
        self._rvc_key: tuple | None = None
        self._lock = threading.Lock()

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
            return EngineStatus(
                True, self.display_name, "ai", f"rvc-python 模式（GPU/CPU）· sid={self.settings.rvc_sid}"
            )
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

    def _ensure_rvc(self, model: str, index: str):
        """rvc-python 0.1.5：RVCInference(device=...) + load_model(path, version, index_path)。
        加锁防止预热线程与转换线程并发初始化。
        版本号从 checkpoint 自动识别（v1/v2），避免硬编码 v2 导致 v1 模型加载错架构。"""
        key = (model, index)
        with self._lock:
            if self._rvc is not None and self._rvc_key == key:
                return self._rvc
            from rvc_python.infer import RVCInference

            # 自动识别模型版本：读 cpt["version"]（默认 v2）
            import torch

            cpt = torch.load(model, map_location="cpu", weights_only=False)
            version = str(cpt.get("version", "v2")).lower()
            if version not in ("v1", "v2"):
                version = "v2"
            del cpt

            rvc = RVCInference(device="cuda:0")
            if index and Path(index).exists():
                rvc.load_model(model, version=version, index_path=index)
            else:
                rvc.load_model(model, version=version)
            self._rvc = rvc
            self._rvc_key = key
            return rvc

    def _apply_params(self, rvc, params: VCParams) -> None:
        """rvc-python 0.1.5 参数是实例属性，无每次调用的参数。"""
        rvc.f0up_key = int(params.semitones)
        rvc.f0method = self.settings.rvc_f0_method
        rvc.index_rate = _index_rate(self.settings, params)
        rvc.filter_radius = 3
        rvc.resample_sr = 0
        rvc.rms_mix_rate = 1
        rvc.protect = 0.33

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
                rvc = self._ensure_rvc(model, self.settings.rvc_index_path or "")
                self._apply_params(rvc, params)
                if progress:
                    progress(0.4, "RVC 推理中")
                # 直接调 vc_single：infer_file 内部写死 sid=0，多音色模型必须可选 sid
                from scipy.io import wavfile

                wav_opt = rvc.vc.vc_single(
                    sid=int(self.settings.rvc_sid),
                    input_audio_path=str(in_path),
                    f0_up_key=int(params.semitones),
                    f0_file="",
                    f0_method=self.settings.rvc_f0_method,
                    file_index=self.settings.rvc_index_path or "",
                    file_index2="",
                    index_rate=_index_rate(self.settings, params),
                    filter_radius=3,
                    resample_sr=0,
                    rms_mix_rate=1,
                    protect=0.33,
                )
                if isinstance(wav_opt, tuple):
                    raise RuntimeError(f"RVC 推理失败：{str(wav_opt)[:300]}")
                wavfile.write(str(out_path), rvc.vc.tgt_sr, wav_opt)
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

    def warmup(self) -> None:
        """应用启动后台预热：加载 RVC 模型 + hubert + rmvpe，
        让首次声音转换不需要等 30s+。预热失败静默（不影响使用）。"""
        if not self._python_available():
            return
        model = self.settings.rvc_model_path
        if not model or not Path(model).exists():
            return

        def run() -> None:
            try:
                rvc = self._ensure_rvc(model, self.settings.rvc_index_path or "")
                self._apply_params(rvc, VCParams())
                silence = np.zeros(int(16000 * 0.5), dtype=np.float32)
                tmp = tempfile.TemporaryDirectory(dir=self.settings.tmp_dir())
                try:
                    p_in = Path(tmp.name) / "warmup_in.wav"
                    p_out = Path(tmp.name) / "warmup_out.wav"
                    audio_io.save_wav(p_in, silence, 16000)
                    rvc.infer_file(str(p_in), str(p_out))
                finally:
                    tmp.cleanup()
            except Exception:
                pass

        threading.Thread(target=run, daemon=True, name="rvc-warmup").start()

    def make_realtime(self, voice: Voice, params: VCParams) -> RealtimeTransform | None:
        model = self._model_path(voice)
        if not self._python_available() or not model or not Path(model).exists():
            return None
        try:
            rvc = self._ensure_rvc(model, self.settings.rvc_index_path or "")
            self._apply_params(rvc, params)
            return _RVCRealtime(rvc, self.settings, params)
        except Exception:
            return None


class _RVCRealtime(RealtimeTransform):
    """rvc-python 0.1.5 无流式 API，采用"缓冲整窗 + vc_single"方式：

    输入缓冲到 ~0.5s 后整窗调用 vc_single(文件路径)，再把处理结果按块节奏吐出。
    延迟 ≈ 窗口(0.5s) + 推理(~0.6s) ≈ 1.1s，属于演示级；
    追求 <300ms 需换用 RVC WebUI 整合包的实时方案。
    vc_single 返回 int16，需归一化为 float32 [-1,1]。
    """

    WINDOW_SEC = 0.5

    def __init__(self, rvc, settings: Settings, params: VCParams) -> None:
        self._rvc = rvc
        self.settings = settings
        self.params = params
        self._out_sr = int(getattr(rvc.vc, "tgt_sr", 48000))
        self._in_buf = np.zeros(0, dtype=np.float32)
        self._out_buf = np.zeros(0, dtype=np.float32)

    def load(self) -> None:
        pass

    def _process_window(self, window: np.ndarray, sr: int) -> np.ndarray:
        from scipy.signal import resample_poly

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", dir=self.settings.tmp_dir(), delete=False)
        tmp.close()
        try:
            audio_io.save_wav(Path(tmp.name), window, sr)
            out = self._rvc.vc.vc_single(
                sid=int(self.settings.rvc_sid),
                input_audio_path=tmp.name,
                f0_up_key=int(self.params.semitones),
                f0_file="",
                f0_method=self.settings.rvc_f0_method,
                file_index=self.settings.rvc_index_path or "",
                file_index2="",
                index_rate=_index_rate(self.settings, self.params),
                filter_radius=3,
                resample_sr=0,
                rms_mix_rate=1,
                protect=0.33,
            )
        finally:
            try:
                Path(tmp.name).unlink()
            except OSError:
                pass
        # vc_single 失败时返回 (info, (None, None))
        if isinstance(out, tuple):
            return np.zeros(len(window), dtype=np.float32)
        out = np.asarray(out)
        if out.dtype == np.int16:
            out = out.astype(np.float32) / 32767.0
        else:
            out = out.astype(np.float32)
        if sr != self._out_sr and len(out) > 0:
            out = resample_poly(out, sr, self._out_sr)
        return np.asarray(out, dtype=np.float32)

    def process(self, chunk: np.ndarray, sr: int) -> np.ndarray:
        try:
            chunk = np.asarray(chunk, dtype=np.float32)
            # 优先吐出已处理好的输出缓冲
            if len(self._out_buf) >= len(chunk):
                out = self._out_buf[: len(chunk)]
                self._out_buf = self._out_buf[len(chunk):]
                return out
            # 输入缓冲累计到窗口再处理
            self._in_buf = np.concatenate([self._in_buf, chunk])
            need = int(sr * self.WINDOW_SEC)
            if len(self._in_buf) < need:
                return np.zeros(len(chunk), dtype=np.float32)
            window = self._in_buf
            self._in_buf = np.zeros(0, dtype=np.float32)
            processed = self._process_window(window, sr)
            self._out_buf = np.asarray(processed, dtype=np.float32)
            if len(self._out_buf) >= len(chunk):
                out = self._out_buf[: len(chunk)]
                self._out_buf = self._out_buf[len(chunk):]
                return out
            return np.zeros(len(chunk), dtype=np.float32)
        except Exception:
            return np.asarray(chunk, dtype=np.float32)

    def close(self) -> None:
        pass

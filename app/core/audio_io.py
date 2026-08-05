from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import BinaryIO

import numpy as np
import soundfile as sf

from .config import Settings, env_ffmpeg


SUPPORTED_INPUT = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac", ".wma"}
SUPPORTED_OUTPUT = {"wav", "flac", "ogg", "mp3"}


def ffmpeg_exe(settings: Settings | None = None) -> str:
    settings = settings or Settings()
    candidates = [
        settings.ffmpeg_path.strip(),
        env_ffmpeg(),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return ""


def has_ffmpeg(settings: Settings | None = None) -> bool:
    return bool(ffmpeg_exe(settings))


def _read_sf_with_timeout(path: Path, timeout: float = 60.0) -> tuple[int, np.ndarray]:
    """soundfile 读取加超时：防止损坏/异常文件导致界面一直“校验中”。"""
    box: dict = {}

    def run() -> None:
        try:
            box["result"] = sf.read(str(path), always_2d=False, dtype="float32")
        except Exception as exc:  # noqa: BLE001
            box["error"] = exc

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError(f"音频读取超时（>{int(timeout)} 秒），文件可能过大或损坏：{path.name}")
    if "error" in box:
        raise box["error"]
    return box["result"]


def decode_audio(path: str | Path, settings: Settings | None = None) -> tuple[int, np.ndarray]:
    """Decode any supported audio to mono float32. Returns (sample_rate, data)."""
    path = Path(path)
    t0 = time.time()
    try:
        data, sr = _read_sf_with_timeout(path)
        if data.ndim > 1:
            data = data.mean(axis=1)
        return int(sr), np.asarray(data, dtype=np.float32)
    except TimeoutError:
        raise
    except Exception:
        # soundfile 失败（如 mp3/m4a 或异常 wav），回退 ffmpeg
        exe = ffmpeg_exe(settings)
        if not exe:
            raise RuntimeError(
                "无法解码该音频：缺少 ffmpeg。请在 设置 → 通用 → ffmpeg 中指定路径，"
                "或运行 setup.ps1 安装依赖（imageio-ffmpeg 自带 ffmpeg，支持 mp3/m4a）"
            )
        tmp = tempfile.NamedTemporaryFile(
            suffix=".wav", dir=(settings or Settings()).tmp_dir(), delete=False
        )
        tmp_path = Path(tmp.name)
        tmp.close()
        try:
            print(f"[解码] soundfile 失败，改用 ffmpeg 解码: {path}", flush=True)
            proc = subprocess.run(
                [
                    exe,
                    "-y",
                    "-i",
                    str(path),
                    "-ac",
                    "1",
                    "-f",
                    "wav",
                    str(tmp_path),
                ],
                capture_output=True,
                timeout=120,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"ffmpeg 解码失败：{proc.stderr.decode(errors='ignore')[-300:]}"
                )
            data, sr = _read_sf_with_timeout(tmp_path)
            print(f"[解码] ffmpeg 解码成功 sr={sr} 耗时={time.time()-t0:.1f}s", flush=True)
            return int(sr), np.asarray(data, dtype=np.float32)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass


def resample_audio(data: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr:
        return np.asarray(data, dtype=np.float32)
    from scipy.signal import resample_poly

    n_out = int(round(len(data) * dst_sr / src_sr))
    y = resample_poly(
        np.asarray(data, dtype=np.float64),
        dst_sr,
        src_sr,
    )
    if len(y) > n_out:
        y = y[:n_out]
    elif len(y) < n_out:
        y = np.pad(y, (0, n_out - len(y)))
    return np.asarray(y, dtype=np.float32)


def save_wav(path: str | Path, data: np.ndarray, sr: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.asarray(data, dtype=np.float32), sr, subtype="PCM_16")


def export_audio(
    path: str | Path,
    data: np.ndarray,
    sr: int,
    fmt: str = "wav",
    bitrate: str = "192k",
    settings: Settings | None = None,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = fmt.lower().lstrip(".")
    if fmt == "wav":
        sf.write(str(path), np.asarray(data, dtype=np.float32), sr, subtype="PCM_16")
        return
    if fmt in ("flac", "ogg"):
        sf.write(str(path), np.asarray(data, dtype=np.float32), sr)
        return
    if fmt != "mp3":
        raise ValueError(f"不支持的导出格式：{fmt}")
    exe = ffmpeg_exe(settings)
    if not exe:
        raise RuntimeError("导出 mp3 需要 ffmpeg（请在设置中指定 ffmpeg 路径）")
    raw = np.asarray(data, dtype=np.float32).tobytes()
    proc = subprocess.run(
        [
            exe,
            "-y",
            "-f",
            "f32le",
            "-ar",
            str(sr),
            "-ac",
            "1",
            "-i",
            "-",
            "-b:a",
            bitrate,
            str(path),
        ],
        input=raw,
        capture_output=True,
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"mp3 导出失败：{proc.stderr.decode(errors='ignore')[-300:]}")


def wav_bytes(data: np.ndarray, sr: int) -> bytes:
    import io

    buf = io.BytesIO()
    sf.write(buf, np.asarray(data, dtype=np.float32), sr, format="WAV")
    return buf.getvalue()


def audio_from_wav_bytes(raw: bytes) -> tuple[int, np.ndarray]:
    import io

    data, sr = sf.read(io.BytesIO(raw), always_2d=False, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    return int(sr), np.asarray(data, dtype=np.float32)


def write_audio_stream(path: str | Path, data: np.ndarray, sr: int, fmt: str = "wav") -> None:
    export_audio(path, data, sr, fmt)


def probe_duration(path: str | Path) -> float | None:
    try:
        info = sf.info(str(path))
        return float(info.duration)
    except Exception:
        return None

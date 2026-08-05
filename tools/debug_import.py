# -*- coding: utf-8 -*-
"""导入音频诊断脚本（Windows 下运行）：
   用法: python tools/debug_import.py "C:\\path\\to\\your.wav"
   它会打印解码耗时与错误信息，用于定位“导入卡住/无法导入”的问题。
"""
from __future__ import annotations

import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import audio_io  # noqa: E402
from app.core.validation import analyze_audio  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python tools/debug_import.py \"音频文件路径\"")
        return
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"文件不存在: {path}")
        return
    size = path.stat().st_size
    print(f"文件: {path}")
    print(f"大小: {size} 字节 ({size / 1024 / 1024:.1f} MB)")
    print(f"ffmpeg: {audio_io.ffmpeg_exe() or '(未找到)'}")

    t0 = time.time()
    try:
        sr, data = audio_io.decode_audio(path)
        elapsed = time.time() - t0
        print(f"[1] 解码成功: sr={sr}, 样本数={len(data)}, 时长={len(data) / sr:.1f} 秒, 耗时={elapsed:.2f}s")
    except Exception as exc:  # noqa: BLE001
        print(f"[1] 解码失败（耗时 {time.time() - t0:.1f}s）: {exc!r}")
        traceback.print_exc()
        return

    t1 = time.time()
    try:
        report = analyze_audio(data, sr, size_bytes=size)
        print(f"[2] 校验完成（耗时 {time.time() - t1:.2f}s）: ok={report.ok}")
        print(f"    时长={report.duration:.1f}s 采样率={report.sample_rate} "
              f"噪声={report.noise_score:.0f}/100 人声占比={report.speech_ratio * 100:.0f}%")
        for w in report.warnings:
            print(f"    警告: {w}")
    except Exception as exc:  # noqa: BLE001
        print(f"[2] 校验失败: {exc!r}")
        traceback.print_exc()

    print("\n完成。若 [1] 显示失败或超时，说明音频解码有问题；若 [2] 的 ok=False，说明音频未通过质量校验。")


if __name__ == "__main__":
    main()

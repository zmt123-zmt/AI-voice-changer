# -*- coding: utf-8 -*-
"""GPT-SoVITS 连接诊断脚本（Windows 下运行）：
   用法: python tools/debug_gpt_api.py
   验证应用能否探测到 http://127.0.0.1:9880 的 GPT-SoVITS API。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import Config  # noqa: E402
from app.engines.gpt_sovits import GPTSoVITS_TTS  # noqa: E402


def main() -> None:
    settings = Config().settings
    print(f"API 地址: {settings.gpt_sovits_api_url!r}")
    print(f"gpt_sovits_dir: {settings.gpt_sovits_dir!r}")
    print(f"gpt_sovits_api_script: {settings.gpt_sovits_api_script!r}")

    eng = GPTSoVITS_TTS(settings)
    print(f"url 属性: {eng.url}")

    print("\n等待后台探测线程首次探测（最多 7 秒）…")
    for i in range(7):
        time.sleep(1)
        alive = eng.server_alive()
        print(f"  第 {i + 1} 秒: server_alive={alive}")

    print("\n强制实时探测一次:", eng.server_alive_force())

    st = eng.status()
    print(f"status(): available={st.available} mode={st.mode}")
    print(f"  detail: {st.detail}")

    print("\n如果上方出现 [GPT-SoVITS] 探测失败 的日志，说明 urllib 连不上 API；")
    print("若 server_alive 始终为 False，请确认 GPT-SoVITS API 窗口仍在运行（Uvicorn running...）。")


if __name__ == "__main__":
    main()

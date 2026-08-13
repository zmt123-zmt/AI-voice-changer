"""RVC 挂起诊断脚本：复刻 app/engines/rvc.py 的完整流程，逐阶段计时。

用法（在项目根目录执行）：
  .venv\Scripts\python.exe tools\debug_rvc.py
"""
from __future__ import annotations

import logging
import sys
import time
import traceback

logging.basicConfig(level=logging.ERROR)  # 压掉 fairseq/rvc 的 INFO 噪音

_start = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - _start:7.1f}s] {msg}", flush=True)


def main() -> None:
    import numpy as np
    import torch

    log(f"torch={torch.__version__} cuda_available={torch.cuda.is_available()}")

    # 1. 创建 RVCInference（等价 _ensure_rvc 前半段）
    log("Step1: RVCInference(device='cuda:0') ...")
    from rvc_python.infer import RVCInference

    rvc = RVCInference(device="cuda:0")
    log("Step1: RVCInference OK")

    # 2. 加载模型（等价 _ensure_rvc 的 load_model）
    log("Step2: load_model(E:/rvc_models/model.pth) ...")
    rvc.load_model(r"E:\rvc_models\model.pth", version="v2", index_path=r"E:\rvc_models\model.index")
    log("Step2: model loaded")

    # 3. 设置参数（等价 _apply_params）
    rvc.f0up_key = 0
    rvc.f0method = "rmvpe"
    rvc.index_rate = 0.75
    rvc.filter_radius = 3
    rvc.resample_sr = 0
    rvc.rms_mix_rate = 1
    rvc.protect = 0.33
    log("Step3: params applied")

    # 4. 推理（等价 infer_file）
    inp = r"C:\Users\ASUS\Documents\AI换声\data\tmp\record_20260806_020613.wav"
    out = r"C:\Users\ASUS\Documents\AI换声\data\tmp\debug_rvc_out.wav"
    log(f"Step4: infer_file({inp}) ...")
    rvc.infer_file(inp, out)
    log(f"Step4: infer OK -> {out}")

    # 5. 验证输出
    from scipy.io import wavfile

    sr, data = wavfile.read(out)
    log(f"Step5: output sr={sr} frames={len(data)} dur={len(data) / sr:.2f}s")

    import os

    log(f"output size = {os.path.getsize(out)} bytes")


if __name__ == "__main__":
    try:
        main()
        log("ALL OK")
    except Exception:
        log("FAILED:")
        traceback.print_exc()

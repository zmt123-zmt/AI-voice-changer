"""快速参数排查：同一个输入，不同 index_rate / protect，听机器音变化"""
from __future__ import annotations
import logging, sys
logging.basicConfig(level=logging.ERROR)
sys.path.insert(0, r"C:\Users\ASUS\Documents\AI换声")
try:
    from app.main import _setup_logging
    _setup_logging()
except Exception:
    pass

from rvc_python.infer import RVCInference
from scipy.io import wavfile

rvc = RVCInference(device="cuda:0")
rvc.load_model(r"E:\rvc_models\doria4.pth", version="v2", index_path=r"E:\rvc_models\doria4.index")
rvc.f0method="rmvpe"; rvc.filter_radius=3; rvc.resample_sr=0; rvc.rms_mix_rate=1; rvc.protect=0.33

SRC = r"C:\Users\ASUS\Documents\AI换声\data\tmp\record_20260806_091751.wav"
OUT = r"C:\Users\ASUS\Documents\AI换声\data\output"

cases = [
    # (name, index_rate, protect)
    ("ir075_p33", 0.75, 0.33),   # 当前设置（对照）
    ("ir050_p33", 0.50, 0.33),
    ("ir030_p33", 0.30, 0.33),
    ("ir000_p33", 0.00, 0.33),   # 纯模型，完全不用索引
    ("ir075_p50", 0.75, 0.50),   # 更高辅音保护
    ("ir000_p50", 0.00, 0.50),
]
for name, ir, pr in cases:
    print(f"== {name}: index_rate={ir} protect={pr} ==", flush=True)
    wav = rvc.vc.vc_single(
        sid=0, input_audio_path=SRC, f0_up_key=0, f0_file="", f0_method="rmvpe",
        file_index=r"E:\rvc_models\doria4.index", file_index2="", index_rate=ir,
        filter_radius=3, resample_sr=0, rms_mix_rate=1, protect=pr)
    if isinstance(wav, tuple):
        print(f"  ERR: {str(wav)[:100]}", flush=True); continue
    p = rf"{OUT}\d4_{name}.wav"
    wavfile.write(p, rvc.vc.tgt_sr, wav)
    print(f"  saved: {p}", flush=True)

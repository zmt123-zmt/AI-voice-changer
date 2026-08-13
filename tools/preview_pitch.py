"""预演：把升调后的用户录音用 doria4 转换，验证音高对齐后是否更像朵莉亚"""
from __future__ import annotations
import logging, sys, time
logging.basicConfig(level=logging.ERROR)
sys.path.insert(0, r"C:\Users\ASUS\Documents\AI换声")
try:
    from app.main import _setup_logging
    _setup_logging()
except Exception:
    pass

import numpy as np, librosa
from rvc_python.infer import RVCInference
from scipy.io import wavfile

rvc = RVCInference(device="cuda:0")
rvc.load_model(r"E:\rvc_models\doria4.pth", version="v2", index_path=r"E:\rvc_models\doria4.index")
rvc.f0method="rmvpe"; rvc.index_rate=0.75; rvc.filter_radius=3; rvc.resample_sr=0; rvc.rms_mix_rate=1; rvc.protect=0.33
TMP = r"C:\Users\ASUS\Documents\AI换声\data\tmp"
OUT = r"C:\Users\ASUS\Documents\AI换声\data\output"

def median_pitch(path):
    y, sr = librosa.load(path, sr=16000)
    f0, _, _ = librosa.pyin(y, fmin=50, fmax=1100, sr=sr)
    v = f0[~np.isnan(f0)]
    return float(np.median(v)) if len(v) else 0.0

for st in (12, 18, 21, 24):
    src = rf"{TMP}\shift{st}.wav"
    print(f"== +{st}st 输入音高 {median_pitch(src):.0f}Hz ==", flush=True)
    wav = rvc.vc.vc_single(
        sid=0, input_audio_path=src, f0_up_key=0, f0_file="", f0_method="rmvpe",
        file_index=r"E:\rvc_models\doria4.index", file_index2="", index_rate=0.75,
        filter_radius=3, resample_sr=0, rms_mix_rate=1, protect=0.33)
    if isinstance(wav, tuple):
        print(f"  ERR {str(wav)[:80]}", flush=True); continue
    p = rf"{OUT}\preview_shift{st}.wav"
    wavfile.write(p, rvc.vc.tgt_sr, wav)
    print(f"  输出音高 {median_pitch(p):.0f}Hz | saved {p}", flush=True)

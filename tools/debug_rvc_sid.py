"""验证：同一输入用不同 sid 输出是否不同（确认是否多音色模型）"""
from __future__ import annotations
import logging, sys, time
logging.basicConfig(level=logging.ERROR)
sys.path.insert(0, r"C:\Users\ASUS\Documents\AI换声")
from app.main import _setup_logging
_setup_logging()

import numpy as np
from scipy.io import wavfile
from rvc_python.infer import RVCInference

start = time.time()
print("init RVC...", flush=True)
rvc = RVCInference(device="cuda:0")
rvc.load_model(r"E:\rvc_models\model.pth", version="v2", index_path=r"E:\rvc_models\model.index")
rvc.f0method = "rmvpe"; rvc.index_rate = 0.75; rvc.filter_radius = 3
rvc.resample_sr = 0; rvc.rms_mix_rate = 1; rvc.protect = 0.33
print(f"model loaded in {time.time()-start:.0f}s", flush=True)

def centroid(spec_cent):
    return spec_cent

inp = r"C:\Users\ASUS\Documents\AI换声\data\tmp\record_20260806_091751.wav"
for sid in [0, 1, 2, 50, 108]:
    out = rf"C:\Users\ASUS\Documents\AI换声\data\tmp\sid_{sid}.wav"
    t0 = time.time()
    wav = rvc.vc.vc_single(sid=sid, input_audio_path=inp, f0_up_key=0, f0_file="",
                           f0_method="rmvpe", file_index=r"E:\rvc_models\model.index",
                           file_index2="", index_rate=0.75, filter_radius=3,
                           resample_sr=0, rms_mix_rate=1, protect=0.33)
    if isinstance(wav, tuple):
        print(f"sid={sid}: ERROR {str(wav)[:100]}", flush=True); continue
    wavfile.write(out, 48000, wav)
    sr, d = wavfile.read(out)
    d = d.astype(np.float32)/32767.0
    spec = np.abs(np.fft.rfft(d[:len(d)//4*4]))
    freqs = np.fft.rfftfreq(len(d)//4*4, 1/sr)
    c = (spec*freqs).sum()/max(spec.sum(),1e-9)
    print(f"sid={sid}: {time.time()-t0:.1f}s centroid={c:.0f}Hz rms={np.sqrt((d**2).mean()):.3f}", flush=True)
print("DONE", flush=True)

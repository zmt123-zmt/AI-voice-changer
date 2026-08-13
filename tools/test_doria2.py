"""验证 doria2 转换（300轮+去BGM版）"""
from __future__ import annotations
import logging, sys, time
logging.basicConfig(level=logging.ERROR)
sys.path.insert(0, r"C:\Users\ASUS\Documents\AI换声")
from app.main import _setup_logging
_setup_logging()

import numpy as np
from app.core.config import Settings
from app.core.voices import Voice
from app.engines.base import VCParams
from app.engines.rvc import RVCAdapter
from app.core import audio_io

s = Settings(rvc_model_path=r"E:\rvc_models\doria2.pth", rvc_index_path=r"E:\rvc_models\doria2.index",
             rvc_f0_method="rmvpe", rvc_index_rate=0.75, rvc_sid=0)
adapter = RVCAdapter(s)
voice = Voice(id="x", name="t", source_name="t", wav_path="", created_at="", kind="rvc")
sr, data = audio_io.decode_audio(r"C:\Users\ASUS\Documents\AI换声\data\tmp\record_20260806_091751.wav", s)
print(f"input {len(data)/sr:.1f}s, converting ...", flush=True)
t0 = time.time()
out_sr, out = adapter.convert(data, sr, voice, VCParams())
print(f"DONE in {time.time()-t0:.1f}s | out_sr={out_sr} | dur={len(out)/out_sr:.1f}s", flush=True)
# out 是 float32 [-1,1]
rms = float(np.sqrt((out**2).mean()))
mx = float(np.abs(out).max())
print(f"rms={rms:.4f} max={mx:.3f} (正常语音: rms>0.01, max>0.1)", flush=True)
p = r"C:\Users\ASUS\Documents\AI换声\data\tmp\doria2_test_out.wav"
audio_io.save_wav(p, out, out_sr)
print(f"saved: {p}", flush=True)

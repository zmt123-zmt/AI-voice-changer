"""验证新训练的 doria 模型（sid=0）转换是否正常"""
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

s = Settings(rvc_model_path=r"E:\rvc_models\doria.pth", rvc_index_path=r"E:\rvc_models\doria.index",
             rvc_f0_method="rmvpe", rvc_index_rate=0.75, rvc_sid=0)
adapter = RVCAdapter(s)
voice = Voice(id="x", name="t", source_name="t", wav_path="", created_at="", kind="rvc")
sr, data = audio_io.decode_audio(r"C:\Users\ASUS\Documents\AI换声\data\tmp\record_20260806_091751.wav", s)
print(f"input {len(data)/sr:.1f}s, converting with doria sid=0 ...", flush=True)
t0 = time.time()
out_sr, out = adapter.convert(data, sr, voice, VCParams())
dur = len(out)/out_sr
print(f"DONE in {time.time()-t0:.1f}s | out_sr={out_sr} | dur={dur:.1f}s", flush=True)
rms = float(np.sqrt((out.astype(np.float32)/32767.0)**2).mean())
print(f"output rms={rms:.4f} (正常语音应>0.01)", flush=True)
import os
p = r"C:\Users\ASUS\Documents\AI换声\data\tmp\doria_test_out.wav"
audio_io.save_wav(p, out, out_sr)
print(f"saved: {p} ({os.path.getsize(p)} bytes)", flush=True)

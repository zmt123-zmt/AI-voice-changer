"""doria4 应用链路验证：走 app.engines.rvc.RVCAdapter，生成试听文件"""
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

s = Settings(rvc_model_path=r"E:\rvc_models\doria4.pth", rvc_index_path=r"E:\rvc_models\doria4.index",
             rvc_f0_method="rmvpe", rvc_index_rate=0.75, rvc_sid=0)
adapter = RVCAdapter(s)
voice = Voice(id="x", name="t", source_name="t", wav_path="", created_at="", kind="rvc")

cases = [
    ("朵莉亚素材", r"E:\音频\朵莉亚_clean2\击杀语音1_vocals_noreverb.wav", "doria4_self.wav"),
    ("用户录音", r"C:\Users\ASUS\Documents\AI换声\data\tmp\record_20260806_091751.wav", "doria4_user.wav"),
]
for name, src, fname in cases:
    sr, data = audio_io.decode_audio(src, s)
    print(f"[{name}] 输入 {len(data)/sr:.1f}s, 转换中 ...", flush=True)
    t0 = time.time()
    out_sr, audio_out = adapter.convert(data, sr, voice, VCParams())
    rms = float(np.sqrt((audio_out ** 2).mean()))
    mx = float(np.abs(audio_out).max())
    p = rf"C:\Users\ASUS\Documents\AI换声\data\output\{fname}"
    audio_io.save_wav(p, audio_out, out_sr)
    print(f"  DONE {time.time()-t0:.1f}s | out_sr={out_sr} | rms={rms:.4f} max={mx:.3f} | saved: {p}", flush=True)

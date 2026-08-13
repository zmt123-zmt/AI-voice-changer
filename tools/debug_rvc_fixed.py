"""验证修复后：日志写文件、stderr 安静、RVC 全流程可用"""
from __future__ import annotations
import sys, time, traceback
sys.path.insert(0, r"C:\Users\ASUS\Documents\AI换声")
from app.main import _setup_logging
_setup_logging()
_start = time.time()
def log(msg): print(f"[{time.time()-_start:6.1f}s] {msg}", flush=True)
log("setup logging OK")

from app.core.config import Settings
from app.core.voices import Voice
from app.engines.base import VCParams
from app.engines.rvc import RVCAdapter

s = Settings(rvc_model_path=r"E:\rvc_models\model.pth", rvc_index_path=r"E:\rvc_models\model.index", rvc_f0_method="rmvpe", rvc_index_rate=0.75)
adapter = RVCAdapter(s)
voice = Voice(id="x", name="t", source_name="t", wav_path="", created_at="", kind="rvc")
adapter.warmup()
log("warmup started")

import threading
def user_job():
    try:
        from app.core import audio_io
        sr, data = audio_io.decode_audio(r"C:\Users\ASUS\Documents\AI换声\data\tmp\record_20260806_015059.wav", s)
        log(f"USER: decoded {len(data)/sr:.2f}s, converting ...")
        out_sr, out = adapter.convert(data, sr, voice, VCParams())
        log(f"USER: DONE out_sr={out_sr} len={len(out)}")
    except Exception:
        log("USER FAILED:\n" + traceback.format_exc())
t = threading.Thread(target=user_job, daemon=True); t.start()
deadline = time.time() + 150
while time.time() < deadline:
    if not t.is_alive():
        log("done"); sys.exit(0)
    time.sleep(1)
log("TIMEOUT")

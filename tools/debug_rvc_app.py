"""用 app 真实代码复现：warmup 线程 + convert 并发"""
from __future__ import annotations
import logging, sys, threading, time, traceback
logging.basicConfig(level=logging.ERROR)
_start = time.time()
def log(msg): print(f"[{time.time()-_start:7.1f}s] {msg}", flush=True)

sys.path.insert(0, r"C:\Users\ASUS\Documents\AI换声")
from app.core.config import Settings
from app.core.voices import Voice
from app.engines.base import VCParams
from app.engines.rvc import RVCAdapter

s = Settings(rvc_model_path=r"E:\rvc_models\model.pth", rvc_index_path=r"E:\rvc_models\model.index", rvc_f0_method="rmvpe", rvc_index_rate=0.75)
adapter = RVCAdapter(s)
voice = Voice(id="x", name="t", source_name="t", wav_path="", created_at="", kind="rvc")

adapter.warmup()
log("warmup started")

time.sleep(3)
def user_job():
    try:
        import numpy as np
        from app.core import audio_io
        sr, data = audio_io.decode_audio(r"C:\Users\ASUS\Documents\AI换声\data\tmp\record_20260806_015059.wav", s)
        log(f"USER: decoded {len(data)/sr:.2f}s @{sr}, converting ...")
        def prog(p, m): pass
        out_sr, out = adapter.convert(data, sr, voice, VCParams(), progress=prog)
        log(f"USER: DONE out_sr={out_sr} len={len(out)}")
    except Exception:
        log("USER FAILED:\n" + traceback.format_exc())

t2 = threading.Thread(target=user_job, name="user", daemon=True); t2.start()
deadline = time.time() + 150
while time.time() < deadline:
    if not t2.is_alive():
        log("user thread finished"); sys.exit(0)
    time.sleep(1)
log("!!! TIMEOUT, dumping stacks:")
for tid, frame in list(sys._current_frames().items()):
    log(f"--- thread {tid} ---")
    for f in traceback.extract_stack(frame)[-30:]:
        log(f"    {f.filename}:{f.lineno} {f.name}")

"""doria2: 不同 sid 输出对比，判断 emb_g 是否起作用"""
from __future__ import annotations
import logging, sys
logging.basicConfig(level=logging.ERROR)
sys.path.insert(0, r"C:\Users\ASUS\Documents\AI换声")
from app.main import _setup_logging
_setup_logging()

import numpy as np, librosa
from scipy.io import wavfile
from rvc_python.infer import RVCInference

def spec_profile(path):
    y, sr = librosa.load(path, sr=16000)
    mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64, fmax=8000)
    return librosa.power_to_db(mel).mean(axis=1)
def cos(a, b): return float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-9))

rvc = RVCInference(device="cuda:0")
rvc.load_model(r"E:\rvc_models\doria2.pth", version="v2", index_path=r"E:\rvc_models\doria2.index")
rvc.f0method="rmvpe"; rvc.index_rate=0.75; rvc.filter_radius=3; rvc.resample_sr=0; rvc.rms_mix_rate=1; rvc.protect=0.33

src = r"C:\Users\ASUS\Documents\AI换声\data\tmp\record_20260806_091751.wav"
outs = {}
for sid in [0, 1, 2, 50, 100]:
    wav = rvc.vc.vc_single(sid=sid, input_audio_path=src, f0_up_key=0, f0_file="", f0_method="rmvpe",
                           file_index=r"E:\rvc_models\doria2.index", file_index2="", index_rate=0.75,
                           filter_radius=3, resample_sr=0, rms_mix_rate=1, protect=0.33)
    if isinstance(wav, tuple):
        print(f"sid={sid} ERR", str(wav)[:80], flush=True); continue
    p = rf"C:\Users\ASUS\Documents\AI换声\data\tmp\d2_sid{sid}.wav"
    wavfile.write(p, rvc.vc.tgt_sr, wav)
    outs[sid] = spec_profile(p)
    print(f"sid={sid} 转换完成", flush=True)

base = outs[0]
print("\nsid=0 vs 其他 sid 的频谱差异（越低=越不同，说明emb_g起作用）：")
for sid in [1, 2, 50, 100]:
    if sid in outs:
        print(f"  sid0 vs sid{sid}: {cos(base, outs[sid]):.4f}")
# 随机行之间对比
print(f"  sid1 vs sid100: {cos(outs[1], outs[100]):.4f}")
print("\n如果 sid0 vs sid1 < 0.95 说明 emb_g 在起作用；如果 ~1.0 说明被忽略")

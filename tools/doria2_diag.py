"""决定性实验：doria2 转换朵莉亚素材，检查音色还原 + 转换用户输入检查音色迁移"""
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

def conv(src, out):
    wav = rvc.vc.vc_single(sid=0, input_audio_path=src, f0_up_key=0, f0_file="", f0_method="rmvpe",
                           file_index=r"E:\rvc_models\doria2.index", file_index2="", index_rate=0.75,
                           filter_radius=3, resample_sr=0, rms_mix_rate=1, protect=0.33)
    if isinstance(wav, tuple):
        print("ERR:", str(wav)[:120]); return None
    wavfile.write(out, rvc.vc.tgt_sr, wav)
    return out

# 实验1：朵莉亚素材 → 转换 → 输出 vs 原素材（同内容，纯音色还原度）
src1 = r"E:\音频\朵莉亚_clean2\击杀语音1_vocals_noreverb.wav"
out1 = r"C:\Users\ASUS\Documents\AI换声\data\tmp\d2_self.wav"
conv(src1, out1)
p_src1 = spec_profile(src1); p_out1 = spec_profile(out1)
print(f"实验1 朵莉亚素材自转换: 音色还原度={cos(p_src1, p_out1):.4f}", flush=True)

# 实验2：用户输入 → 转换 → 输出 vs 朵莉亚素材（不同内容，看音色迁移）
src2 = r"C:\Users\ASUS\Documents\AI换声\data\tmp\record_20260806_091751.wav"
out2 = r"C:\Users\ASUS\Documents\AI换声\data\tmp\d2_user.wav"
conv(src2, out2)
p_user = spec_profile(src2); p_out2 = spec_profile(out2)
print(f"实验2a 用户输入 vs 用户输入转换: {cos(p_user, p_out2):.4f} (越低=改变越大)", flush=True)
print(f"实验2b 用户输入转换 vs 朵莉亚素材: {cos(p_out2, p_src1):.4f} (越高=越像朵莉亚)", flush=True)
print(f"实验2c 用户输入 vs 朵莉亚素材: {cos(p_user, p_src1):.4f} (基线)", flush=True)

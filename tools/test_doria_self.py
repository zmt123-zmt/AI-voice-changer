"""用朵莉亚自己的语音走 doria 转换：输出应保持朵莉亚音色（内容相同可对比）"""
from __future__ import annotations
import logging, sys
logging.basicConfig(level=logging.ERROR)
sys.path.insert(0, r"C:\Users\ASUS\Documents\AI换声")
from app.main import _setup_logging
_setup_logging()

import numpy as np, torch, librosa
from scipy.io import wavfile
from rvc_python.infer import RVCInference

rvc = RVCInference(device="cuda:0")
rvc.load_model(r"E:\rvc_models\doria.pth", version="v2", index_path=r"E:\rvc_models\doria.index")
rvc.f0method="rmvpe"; rvc.index_rate=0.75; rvc.filter_radius=3; rvc.resample_sr=0; rvc.rms_mix_rate=1; rvc.protect=0.33

src = r"E:\音频\朵莉亚\击杀语音1.wav"
out_path = r"C:\Users\ASUS\Documents\AI换声\data\tmp\doria_self_test.wav"
wav = rvc.vc.vc_single(sid=0, input_audio_path=src, f0_up_key=0, f0_file="", f0_method="rmvpe",
                       file_index=r"E:\rvc_models\doria.index", file_index2="", index_rate=0.75,
                       filter_radius=3, resample_sr=0, rms_mix_rate=1, protect=0.33)
print("tuple?" , isinstance(wav, tuple), flush=True)
wavfile.write(out_path, rvc.vc.tgt_sr, wav)

def hubert_mean(path):
    y, _ = librosa.load(path, sr=16000, mono=True)
    x = torch.from_numpy(y.astype(np.float32)).view(1, -1)
    if rvc.vc.pipeline.is_half: x = x.half()
    else: x = x.float()
    x = x.to(rvc.vc.config.device)
    pad = torch.BoolTensor(x.shape).to(rvc.vc.config.device).fill_(False)
    with torch.no_grad():
        feats = rvc.vc.hubert_model.extract_features(source=x, padding_mask=pad, output_layer=12)[0][0].float().cpu().numpy()
    return feats.mean(axis=0)
def cos(a,b): return float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)+1e-9))

a = hubert_mean(src)      # 原朵莉亚击杀语音
b = hubert_mean(out_path) # 转换后
print(f"原朵莉亚击杀语音 vs 转换后: {cos(a,b):.4f}  (内容相同，纯看音色保留度)", flush=True)

# 音频质量
sr0, d = wavfile.read(out_path)
d = d.astype(np.float32)/32767.0
print(f"输出: sr={sr0} dur={len(d)/sr0:.1f}s max={np.abs(d).max():.3f} rms={np.sqrt((d**2).mean()):.4f}", flush=True)

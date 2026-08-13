"""训练完成验证：doria2 模型
1) 确定正确 sid：朵莉亚素材转换输出 vs 各 sid 输出，看哪个 sid 最像朵莉亚
2) 音色还原：朵莉亚素材(clean2) → sid? 输出 vs 原素材
3) 音色迁移：用户录音 → 输出 vs 朵莉亚素材
全部用 hubert layer12 特征均值余弦相似度（RVC 内部音色空间）。
"""
from __future__ import annotations
import logging, sys, time
logging.basicConfig(level=logging.ERROR)
sys.path.insert(0, r"C:\Users\ASUS\Documents\AI换声")
try:
    from app.main import _setup_logging
    _setup_logging()
except Exception:
    pass

import numpy as np, torch, librosa
from scipy.io import wavfile
from rvc_python.infer import RVCInference

MODEL = r"E:\rvc_models\doria4.pth"
INDEX = r"E:\rvc_models\doria4.index"
DORIA_REF = r"E:\音频\朵莉亚_clean2\击杀语音1_vocals_noreverb.wav"
USER_IN = r"C:\Users\ASUS\Documents\AI换声\data\tmp\record_20260806_091751.wav"
TMP = r"C:\Users\ASUS\Documents\AI换声\data\tmp"

def hubert_mean(rvc, path):
    y, _ = librosa.load(path, sr=16000, mono=True)
    x = torch.from_numpy(y.astype(np.float32)).view(1, -1)
    if rvc.vc.pipeline.is_half: x = x.half()
    else: x = x.float()
    x = x.to(rvc.vc.config.device)
    pad = torch.BoolTensor(x.shape).to(rvc.vc.config.device).fill_(False)
    with torch.no_grad():
        feats = rvc.vc.hubert_model.extract_features(source=x, padding_mask=pad, output_layer=12)[0][0].float().cpu().numpy()
    return feats.mean(axis=0)

def cos(a, b): return float(np.dot(a, b) / (np.linalg.norm(a)*np.linalg.norm(b) + 1e-9))

def conv(rvc, src, sid, out):
    wav = rvc.vc.vc_single(sid=sid, input_audio_path=src, f0_up_key=0, f0_file="", f0_method="rmvpe",
                           file_index=INDEX, file_index2="", index_rate=0.75, filter_radius=3,
                           resample_sr=0, rms_mix_rate=1, protect=0.33)
    if isinstance(wav, tuple):
        print(f"  sid={sid} ERR: {str(wav)[:100]}", flush=True); return None
    wavfile.write(out, rvc.vc.tgt_sr, wav)
    return out

print("init RVC ...", flush=True)
rvc = RVCInference(device="cuda:0")
rvc.load_model(MODEL, version="v2", index_path=INDEX)
rvc.f0method="rmvpe"; rvc.index_rate=0.75; rvc.filter_radius=3; rvc.resample_sr=0; rvc.rms_mix_rate=1; rvc.protect=0.33
n_spk = rvc.vc.cpt["weight"]["emb_g.weight"].shape[0]
print(f"模型加载完成，speaker 数 = {n_spk}", flush=True)

# 预热 hubert/rmvpe
conv(rvc, DORIA_REF, 0, rf"{TMP}\v_hot.wav")
print("预热完成", flush=True)

# 1) sid 甄别：用朵莉亚素材转换，看哪个 sid 输出最接近朵莉亚 hubert
ref = hubert_mean(rvc, DORIA_REF)
print("\n=== 1) sid 甄别（朵莉亚素材 → 各 sid → 与朵莉亚 hubert 相似度）===", flush=True)
sids = [0, 1, 2, 50, 100]
scores = []
for sid in sids:
    out = conv(rvc, DORIA_REF, sid, rf"{TMP}\v_sid{sid}.wav")
    if not out: continue
    s = cos(hubert_mean(rvc, out), ref)
    scores.append((s, sid))
    print(f"  sid={sid:3d}  相似度={s:.4f}", flush=True)
scores.sort(reverse=True)
best_sid = scores[0][1]
print(f"  → 最佳 sid = {best_sid}", flush=True)

# 2) 音色还原：朵莉亚素材自转换（同内容），用最佳 sid
out_self = conv(rvc, DORIA_REF, best_sid, rf"{TMP}\v_self_best.wav")
sim_self = cos(hubert_mean(rvc, out_self), ref)
print(f"\n=== 2) 音色还原：同内容转换相似度 = {sim_self:.4f}（>0.95 还原度很高）===", flush=True)

# 3) 音色迁移：用户录音 → 输出 vs 朵莉亚素材
out_user = conv(rvc, USER_IN, best_sid, rf"{TMP}\v_user_best.wav")
u_in = hubert_mean(rvc, USER_IN); u_out = hubert_mean(rvc, out_user)
sim_mig = cos(u_out, ref)
sim_keep = cos(u_in, u_out)
print(f"\n=== 3) 音色迁移（用户录音转换）===", flush=True)
print(f"  转换输出 vs 朵莉亚: {sim_mig:.4f}（越高越像朵莉亚）", flush=True)
print(f"  转换输出 vs 用户原声: {sim_keep:.4f}（越低=音色改变越大）", flush=True)
print(f"  基线 用户原声 vs 朵莉亚: {cos(u_in, ref):.4f}", flush=True)
print(f"\n试听文件: {TMP}\\v_self_best.wav / v_user_best.wav", flush=True)

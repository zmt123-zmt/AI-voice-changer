"""对比转换输出与朵莉亚素材/输入声音的 hubert 特征相似度"""
from __future__ import annotations
import logging, sys
logging.basicConfig(level=logging.ERROR)
sys.path.insert(0, r"C:\Users\ASUS\Documents\AI换声")
from app.main import _setup_logging
_setup_logging()

import numpy as np, torch, librosa
from rvc_python.infer import RVCInference

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

print("init...", flush=True)
rvc = RVCInference(device="cuda:0")
rvc.load_model(r"E:\rvc_models\doria.pth", version="v2", index_path=r"E:\rvc_models\doria.index")
rvc.f0method="rmvpe"; rvc.index_rate=0.75; rvc.filter_radius=3; rvc.resample_sr=0; rvc.rms_mix_rate=1; rvc.protect=0.33
# warmup hubert
rvc.vc.vc_single(sid=0, input_audio_path=r"E:\音频\朵莉亚\大厅语音1.wav", f0_up_key=0, f0_file="", f0_method="rmvpe",
                 file_index=r"E:\rvc_models\doria.index", file_index2="", index_rate=0.75, filter_radius=3,
                 resample_sr=0, rms_mix_rate=1, protect=0.33)
print("hubert ready", flush=True)

targets = {
    "朵莉亚素材(大厅语音1)": r"E:\音频\朵莉亚\大厅语音1.wav",
    "朵莉亚素材(击杀语音1)": r"E:\音频\朵莉亚\击杀语音1.wav",
    "用户输入(12.6s录音)": r"C:\Users\ASUS\Documents\AI换声\data\tmp\record_20260806_091751.wav",
}
refs = {k: hubert_mean(rvc, v) for k, v in targets.items()}
out = hubert_mean(rvc, r"C:\Users\ASUS\Documents\AI换声\data\tmp\doria_test_out.wav")
print("\n转换输出(doria) 与各参考的相似度：")
for k, v in refs.items():
    print(f"  {k}: {cos(out, v):.4f}")
print("\n朵莉亚素材彼此相似度(参考基线)：")
print(f"  大厅语音1 vs 击杀语音1: {cos(refs['朵莉亚素材(大厅语音1)'], refs['朵莉亚素材(击杀语音1)']):.4f}")

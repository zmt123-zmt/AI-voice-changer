"""v2：用 hubert 特征（RVC 内部音色空间）重新给 109 个 sid 打分。

复用 find_rvc_sid.py 生成的 data/tmp/sid_out/sid_XXX.wav，
比较每个输出的 hubert 特征均值 与 参考音频的余弦相似度。
"""
from __future__ import annotations

import logging
import os
import sys

logging.basicConfig(level=logging.ERROR)
sys.path.insert(0, r"C:\Users\ASUS\Documents\AI换声")
try:
    from app.main import _setup_logging

    _setup_logging()
except Exception:
    pass

import numpy as np
import torch
import librosa

REF = r"E:\音频\元歌\元歌_无间傀儡_挑衅.wav"
OUT_DIR = r"C:\Users\ASUS\Documents\AI换声\data\tmp\sid_out"
MODEL = r"E:\rvc_models\model.pth"
INDEX = r"E:\rvc_models\model.index"


def hubert_mean(rvc, path: str) -> np.ndarray:
    """复刻 pipeline：16k 音频 → hubert layer12 → 特征均值 (768,)"""
    y, _ = librosa.load(path, sr=16000, mono=True)
    x = torch.from_numpy(y.astype(np.float32)).view(1, -1)
    if rvc.vc.pipeline.is_half:
        x = x.half()
    else:
        x = x.float()
    x = x.to(rvc.vc.config.device)
    padding = torch.BoolTensor(x.shape).to(rvc.vc.config.device).fill_(False)
    with torch.no_grad():
        logits = rvc.vc.hubert_model.extract_features(
            source=x, padding_mask=padding, output_layer=12
        )
        feats = logits[0][0].float().cpu().numpy()  # (T, 768)
    return feats.mean(axis=0)


def main() -> None:
    print("初始化 RVC（加载 hubert）...", flush=True)
    from rvc_python.infer import RVCInference

    rvc = RVCInference(device="cuda:0")
    rvc.load_model(MODEL, version="v2", index_path=INDEX)
    rvc.f0method = "rmvpe"
    rvc.index_rate = 0.75
    # 触发 hubert 加载
    rvc.vc.vc_single(sid=0, input_audio_path=REF, f0_up_key=0, f0_file="",
                     f0_method="rmvpe", file_index=INDEX, file_index2="",
                     index_rate=0.75, filter_radius=3, resample_sr=0,
                     rms_mix_rate=1, protect=0.33)
    print("hubert 就绪，计算参考特征...", flush=True)
    ref = hubert_mean(rvc, REF)
    print(f"参考特征维度: {ref.shape}", flush=True)

    results = []
    for fn in sorted(os.listdir(OUT_DIR)):
        if not fn.startswith("sid_"):
            continue
        sid = int(fn.split("_")[1].split(".")[0])
        out = hubert_mean(rvc, os.path.join(OUT_DIR, fn))
        cos = float(np.dot(ref, out) / (np.linalg.norm(ref) * np.linalg.norm(out) + 1e-9))
        results.append((cos, sid))
    results.sort(reverse=True)

    print("\n=== hubert 特征相似度 TOP 15 ===", flush=True)
    for cos, sid in results[:15]:
        print(f"  sid={sid:3d}  相似度={cos:.4f}", flush=True)
    print("\n=== 最低 5 ===", flush=True)
    for cos, sid in results[-5:]:
        print(f"  sid={sid:3d}  相似度={cos:.4f}", flush=True)
    best_cos, best_sid = results[0]
    print(f"\n最佳: sid={best_sid}（{best_cos:.4f}）", flush=True)
    print(f"试听: {OUT_DIR}\\sid_{best_sid:03d}.wav", flush=True)


if __name__ == "__main__":
    main()

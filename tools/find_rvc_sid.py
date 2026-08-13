"""多音色模型自动匹配工具：找出最像目标音色的 sid。

原理：同一段输入（用目标音色的参考音频本身），依次用 0..n_spk-1 个 sid 转换，
转换输出与原始输入的 MFCC 特征越接近 → 该 sid 越可能是目标音色。
（多音色模型如"王者全英雄合集"，每个英雄对应一个 sid。）

用法：.venv\\Scripts\\python.exe tools\\find_rvc_sid.py [参考音频] [模型] [索引]
"""
from __future__ import annotations

import logging
import os
import sys
import time

logging.basicConfig(level=logging.ERROR)
sys.path.insert(0, r"C:\Users\ASUS\Documents\AI换声")
try:
    from app.main import _setup_logging

    _setup_logging()
except Exception:
    pass

import numpy as np
import librosa


def mfcc(path: str) -> np.ndarray:
    """返回 13 维 MFCC 每帧 (13, T)"""
    y, sr = librosa.load(path, sr=16000)
    m = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, n_fft=1024, hop_length=256)
    return m


def frame_cos(m1: np.ndarray, m2: np.ndarray) -> float:
    """把两个 MFCC 序列缩放到同长，逐帧余弦相似度取平均"""
    n = min(m1.shape[1], m2.shape[1])
    m1, m2 = m1[:, :n], m2[:, :n]
    eps = 1e-9
    cos = (m1 * m2).sum(axis=0) / (
        np.linalg.norm(m1, axis=0) * np.linalg.norm(m2, axis=0) + eps
    )
    return float(cos.mean())


def main() -> None:
    ref = sys.argv[1] if len(sys.argv) > 1 else r"E:\音频\元歌\元歌_无间傀儡_挑衅.wav"
    model = sys.argv[2] if len(sys.argv) > 2 else r"E:\rvc_models\model.pth"
    index = sys.argv[3] if len(sys.argv) > 3 else r"E:\rvc_models\model.index"

    if not os.path.exists(ref):
        print(f"参考音频不存在: {ref}")
        return
    print(f"参考音频: {ref}", flush=True)
    print("初始化 RVC（约 20s）...", flush=True)
    t0 = time.time()
    from rvc_python.infer import RVCInference

    rvc = RVCInference(device="cuda:0")
    rvc.load_model(model, version="v2", index_path=index)
    rvc.f0method = "rmvpe"
    rvc.index_rate = 0.75
    rvc.filter_radius = 3
    rvc.resample_sr = 0
    rvc.rms_mix_rate = 1
    rvc.protect = 0.33
    n_spk = rvc.vc.cpt["weight"]["emb_g.weight"].shape[0]
    print(f"模型加载完成（{time.time()-t0:.0f}s），共 {n_spk} 个音色(sid 0~{n_spk-1})", flush=True)

    # 先转换一次热身（加载 hubert/rmvpe）
    print("预热（加载 hubert/rmvpe，约 10s）...", flush=True)
    tmp_in = r"C:\Users\ASUS\Documents\AI换声\data\tmp\sid_find_hot.wav"
    rvc.vc.vc_single(sid=0, input_audio_path=tmp_in if os.path.exists(tmp_in) else ref,
                     f0_up_key=0, f0_file="", f0_method="rmvpe", file_index=index,
                     file_index2="", index_rate=0.75, filter_radius=3, resample_sr=0,
                     rms_mix_rate=1, protect=0.33)
    print("预热完成", flush=True)

    ref_mfcc = mfcc(ref)
    results = []
    from scipy.io import wavfile

    out_dir = r"C:\Users\ASUS\Documents\AI换声\data\tmp\sid_out"
    os.makedirs(out_dir, exist_ok=True)
    t_start = time.time()
    for sid in range(n_spk):
        wav = rvc.vc.vc_single(
            sid=sid, input_audio_path=ref, f0_up_key=0, f0_file="",
            f0_method="rmvpe", file_index=index, file_index2="", index_rate=0.75,
            filter_radius=3, resample_sr=0, rms_mix_rate=1, protect=0.33,
        )
        if isinstance(wav, tuple):
            continue
        out = os.path.join(out_dir, f"sid_{sid:03d}.wav")
        wavfile.write(out, 48000, wav)
        sim = frame_cos(mfcc(out), ref_mfcc)
        results.append((sim, sid))
        if sid % 10 == 0:
            print(f"  已测试 {sid+1}/{n_spk}，用时 {time.time()-t_start:.0f}s", flush=True)

    results.sort(reverse=True)
    print("\n=== 相似度 TOP 10（越接近 1.0 越像目标音色）===", flush=True)
    for sim, sid in results[:10]:
        print(f"  sid={sid:3d}  相似度={sim:.4f}", flush=True)
    best = results[0]
    print(f"\n最佳: sid={best[1]}（相似度 {best[0]:.4f}）", flush=True)
    print(f"输出文件: {out_dir}\\sid_{best[1]:03d}.wav", flush=True)
    print("\n提示：在应用设置 → RVC → 说话人 sid 里填这个数字即可", flush=True)


if __name__ == "__main__":
    main()

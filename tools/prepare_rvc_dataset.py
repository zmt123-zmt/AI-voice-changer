"""RVC 训练数据预处理 v3：短句整段保留，长句按停顿切 3~10s。

用法：.venv\\Scripts\\python.exe tools/prepare_rvc_dataset.py [素材目录] [输出目录] [采样率]
示例：.venv\\Scripts\\python.exe tools/prepare_rvc_dataset.py "E:\\音频\\朵莉亚_clean2" "E:\\rvc_train\\doria2" 48000

v3（针对 77s 太少的问题）：
- 不再按"整段静音占比"丢弃——短语音里的停顿是正常的
- trim 头尾后：<=10s 整段保留（>=2.5s）；>10s 按静音切分
- 只丢弃整段平均能量过低的（纯环境音/空白）
"""
from __future__ import annotations

import os
import sys

import numpy as np
import librosa
import soundfile as sf

SR = int(sys.argv[3]) if len(sys.argv) > 3 else 48000
SRC = sys.argv[1] if len(sys.argv) > 1 else r"E:\音频\朵莉亚_clean2"
DST = sys.argv[2] if len(sys.argv) > 2 else r"E:\rvc_train\doria2"

MIN_SEG_SEC = 2.5
MAX_SEC = 10.0
TRIM_DB = 35
MIN_RMS = 0.02  # 整段平均能量低于此值视为无效

os.makedirs(DST, exist_ok=True)
total_in = total_out = 0.0
dropped = {"太短": 0, "能量过低": 0, "解码失败": 0}


def segments_of(y: np.ndarray, sr: int) -> list[np.ndarray]:
    """按静音切分，每段 2.5~10s"""
    if len(y) / sr <= MAX_SEC:
        return [y] if len(y) / sr >= MIN_SEG_SEC else []
    hop = 512
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop)[0]
    sil = rms < np.percentile(rms, 20) * 0.5
    cuts = []
    for i in range(1, len(sil)):
        if sil[i] and not sil[i - 1]:
            cuts.append(i * hop)
    out = []
    start = 0
    for c in cuts:
        if c - start >= MIN_SEG_SEC * sr and c - start <= MAX_SEC * sr:
            out.append(y[start:c])
            start = c
        elif c - start > MAX_SEC * sr:
            out.append(y[start : start + int(MAX_SEC * sr)])
            start = start + int(MAX_SEC * sr)
    if len(y) - start >= MIN_SEG_SEC * sr:
        out.append(y[start:])
    return out


for fn in sorted(os.listdir(SRC)):
    if not fn.lower().endswith((".wav", ".mp3", ".flac", ".m4a", ".ogg")):
        continue
    path = os.path.join(SRC, fn)
    try:
        y, sr = librosa.load(path, sr=SR, mono=True)
    except Exception as e:
        print(f"[跳过] {fn}: {e}")
        dropped["解码失败"] += 1
        continue
    total_in += len(y) / sr
    y, _ = librosa.effects.trim(y, top_db=TRIM_DB, frame_length=2048, hop_length=512)
    if len(y) / sr < MIN_SEG_SEC:
        dropped["太短"] += 1
        continue
    if np.sqrt((y**2).mean()) < MIN_RMS:
        dropped["能量过低"] += 1
        continue
    for i, seg in enumerate(segments_of(y, sr)):
        out = os.path.join(DST, f"{os.path.splitext(fn)[0][:20]}_{i:02d}.wav")
        sf.write(out, seg, SR, subtype="PCM_16")
        total_out += len(seg) / sr

print(f"\n输入 {total_in:.0f}s → 输出 {total_out:.0f}s（{SR}Hz，2.5~{MAX_SEC:.0f}s 切片）")
print(f"输出目录：{DST}")
print(f"丢弃：{dropped}")

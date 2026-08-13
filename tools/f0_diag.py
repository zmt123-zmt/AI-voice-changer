# -*- coding: utf-8 -*-
# F0 基频诊断：分析输入/输出的平均音高
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, r"F:\AI变声\AI换声\.venv\Lib\site-packages")
from rvc_python.lib.rmvpe import RMVPE

RMVPE_PATH = Path(r"F:\AI变声\AI换声\.venv\Lib\site-packages\rvc_python\base_model\rmvpe.pt")
rmvpe = RMVPE(RMVPE_PATH, is_half=True, device="cuda:0")

FILES = [
    ("01_复活1_原声(朵莉亚)", r"F:\AI变声\音频\朵莉亚试听\01_复活1_原声.wav"),
    ("01_复活1_转换", r"F:\AI变声\音频\朵莉亚试听\01_复活1_转换.wav"),
    ("04_录音123_输入(用户)", r"F:\AI变声\音频\朵莉亚试听\04_你自己的录音123_输入原声.wav"),
    ("04_录音123_变朵莉亚", r"F:\AI变声\音频\朵莉亚试听\04_你自己的录音123_变朵莉亚.wav"),
    ("05_元歌男声_输入", r"F:\AI变声\音频\朵莉亚试听\05_元歌男声_输入原声.wav"),
    ("05_元歌男声_变朵莉亚", r"F:\AI变声\音频\朵莉亚试听\05_元歌男声_变朵莉亚.wav"),
    ("06_姬小满_输入", r"F:\AI变声\音频\朵莉亚试听\06_姬小满女声_输入原声.wav"),
    ("06_姬小满_变朵莉亚", r"F:\AI变声\音频\朵莉亚试听\06_姬小满女声_变朵莉亚.wav"),
]

def f0_stats(wav_path):
    sr, data = wavfile.read(wav_path)
    if data.dtype != np.int16:
        data = (data * 32767).astype(np.int16)
    x = data.astype(np.float32) / 32768.0
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != 16000:
        import librosa
        x = librosa.resample(x, orig_sr=sr, target_sr=16000)
    f0 = rmvpe.infer_from_audio(x, thred=0.05)
    voiced = f0[f0 > 0]
    if len(voiced) == 0:
        return None, None, len(f0)
    # 只统计 50~500Hz 的人声范围
    v = voiced[(voiced >= 50) & (voiced <= 500)]
    return float(np.median(v)) if len(v) else None, float(np.mean(v)) if len(v) else None, len(f0)

for tag, p in FILES:
    if not Path(p).exists():
        print(f"{tag}: 文件不存在")
        continue
    med, mean, n = f0_stats(p)
    if med:
        print(f"{tag}: 中位F0={med:.0f}Hz 均值={mean:.0f}Hz (voiced {n} 帧)")
    else:
        print(f"{tag}: 无有效F0")

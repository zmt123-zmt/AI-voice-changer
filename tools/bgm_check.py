# -*- coding: utf-8 -*-
import soundfile as sf, numpy as np, glob, os
import sys
sys.stdout.reconfigure(encoding='utf-8')

def analyze(f):
    x, sr = sf.read(f, dtype='float32')
    if x.ndim > 1: x = x.mean(axis=1)
    n = len(x)
    # 找最低能量1s窗
    win = int(sr)
    nwin = n // win
    xw = x[:nwin*win].reshape(nwin, win)
    rms_w = np.sqrt((xw**2).mean(axis=1))
    min_i = int(rms_w.argmin())
    # 静音段频谱（最低窗的前后各取一半）
    seg = xw[min_i]
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freq = np.fft.rfftfreq(len(seg), 1/sr)
    low = spec[(freq > 50) & (freq < 300)].sum()
    mid = spec[(freq >= 300) & (freq < 4000)].sum()
    high = spec[(freq >= 4000)].sum()
    total = low + mid + high + 1e-9
    # 整段静音比例
    sil = (np.abs(x) < 0.01).mean() * 100
    print(f"{os.path.basename(f)[:38]:40s} 最低窗rms={rms_w[min_i]:.4f} 低频占比={low/total*100:5.1f}% 静音比例={sil:4.1f}% 判断: ", end="")
    if rms_w[min_i] < 0.003:
        print("真静音→无持续BGM")
    elif low/total > 0.25:
        print("⚠️静音窗有低频能量→疑似BGM/音效")
    else:
        print("静音窗能量以中高频为主→疑似语音尾音/短音效")

for f in [
    r"E:\音频\姬小满\武道奇才 姬小满\姬小满-拾年声藏贺文.wav",
    r"E:\音频\姬小满\武道奇才 姬小满\姬小满_武道奇才_回城1.wav",
    r"E:\音频\姬小满\武道奇才 姬小满\姬小满_武道奇才_开场语音1.wav",
    r"E:\音频\姬小满\武道奇才 姬小满\姬小满_武道奇才_挑衅1.wav",
    r"E:\音频\姬小满\武道奇才 姬小满\姬小满_武道奇才_移动语音10.wav",
    r"E:\音频\姬小满\武道奇才 姬小满\姬小满_武道奇才_购买装备-暗影战斧.wav",
]:
    analyze(f)

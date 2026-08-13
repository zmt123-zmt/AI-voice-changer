# -*- coding: utf-8 -*-
import soundfile as sf, numpy as np, glob, os, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def check(f):
    x, sr = sf.read(f, dtype='float32')
    if x.ndim > 1: x = x.mean(axis=1)
    n = len(x)
    win = int(sr)
    nwin = n // win
    if nwin < 2: return None
    xw = x[:nwin*win].reshape(nwin, win)
    rms_w = np.sqrt((xw**2).mean(axis=1))
    min_i = int(rms_w.argmin())
    seg = xw[min_i]
    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    freq = np.fft.rfftfreq(len(seg), 1/sr)
    low = spec[(freq > 50) & (freq < 300)].sum()
    mid = spec[(freq >= 300) & (freq < 4000)].sum()
    high = spec[(freq >= 4000)].sum()
    total = low + mid + high + 1e-9
    return rms_w[min_i], low/total*100

for d in ['E:/音频/姬小满/战舞者 姬小满', 'E:/音频/姬小满/灵喵仙官 姬小满']:
    print(f"=== {os.path.basename(d)} ===")
    bgm = []
    for f in sorted(glob.glob(d + '/*.wav')):
        r = check(f)
        if r is None: continue
        min_rms, low_pct = r
        if min_rms < 0.003:
            verdict = "真静音"
        elif low_pct > 0.25:
            verdict = "⚠️疑似BGM/音效"
            bgm.append(os.path.basename(f))
        else:
            verdict = "OK"
        print(f"  {os.path.basename(f)[:36]:38s} min_rms={min_rms:.4f} 低频={low_pct:5.1f}% {verdict}")
    if bgm:
        print(f"  ⚠️ 需注意: {bgm}")

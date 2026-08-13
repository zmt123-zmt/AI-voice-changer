# -*- coding: utf-8 -*-
"""VB-Cable 环路测试：播 440Hz 到 CABLE Input，从 CABLE Output 录音，验证链路。"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import numpy as np
import sounddevice as sd

devs = sd.query_devices()
in_idx = out_idx = None
for i, d in enumerate(devs):
    n = d["name"]
    if "CABLE Output" in n and d.get("max_input_channels", 0) > 0 and in_idx is None:
        in_idx = i
    if "CABLE Input" in n and d.get("max_output_channels", 0) > 0 and out_idx is None:
        out_idx = i
print(f"录音设备: [{in_idx}] {devs[in_idx]['name']}")
print(f"播放设备: [{out_idx}] {devs[out_idx]['name']}")

sr = 16000
t = np.arange(sr) / sr
tone = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

recorded = sd.playrec(tone, samplerate=sr, device=(in_idx, out_idx),
                      channels=1)
sd.wait()
rms = float(np.sqrt((recorded**2).mean()))
peak = float(np.abs(recorded).max())
print(f"录音 rms={rms:.4f} peak={peak:.4f}")
if rms > 0.01:
    print("✅ 环路正常：CABLE Input 播放 → CABLE Output 能录到声音")
else:
    print("❌ 没录到声音，检查驱动或设备配对")

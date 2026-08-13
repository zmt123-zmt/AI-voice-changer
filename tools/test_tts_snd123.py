# -*- coding: utf-8 -*-
"""验证 snd123 API 合成（用 list 第一条样本做参考）。"""
import json, urllib.request, sys, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# 取 list 第一条（路径+台词）
line = open(r"E:\无名\123_train.list", encoding="utf-8").readline().strip()
ref_path, spk, lan, prompt = line.split("|")
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
req = {
    "refer_wav_path": ref_path,
    "prompt_text": prompt,
    "prompt_language": "zh",
    "text": "你好，这是音色验证测试。",
    "text_language": "zh",
    "speed": 1.0,
    "inp_refs": [],
    "sample_steps": 32,
    "if_sr": False,
}
r = opener.open(urllib.request.Request("http://127.0.0.1:9880/", json.dumps(req).encode(), {"Content-Type": "application/json"}), timeout=60)
data = r.read()
out = "data/output/tts_snd123_verify.wav"
os.makedirs(os.path.dirname(out), exist_ok=True)
if data[:4] == b"RIFF":
    open(out, "wb").write(data)
    print(f"OK 合成成功: {out} ({len(data)} 字节)")
else:
    print("非wav:", data[:100])

# -*- coding: utf-8 -*-
# doria6 真人转朵莉亚测试：把非朵莉亚语音转换成朵莉亚音色，输出到 F:/AI变声/音频/朵莉亚试听/
import time
from pathlib import Path

from rvc_python.infer import RVCInference

OUT = Path(r"F:\AI变声\音频\朵莉亚试听")
OUT.mkdir(parents=True, exist_ok=True)

SAMPLES = [
    ("04_你自己的录音123", r"F:\AI变声\AI换声\data\voices\d119158a14f0.wav"),
    ("05_元歌男声", r"F:\AI变声\AI换声\data\voices\3fe55aeadde8.wav"),
    ("06_姬小满女声", r"F:\AI变声\AI换声\data\voices\29637ad4b3f6.wav"),
]

rvc = RVCInference(device="cuda:0")
rvc.load_model(r"E:\rvc_models\doria6.pth", version="v2", index_path=r"E:\rvc_models\doria6.index")
rvc.f0method = "rmvpe"
rvc.index_rate = 0.75
rvc.f0up_key = 0

for tag, src in SAMPLES:
    if not Path(src).exists():
        print(f"[跳过] {tag}: 源文件不存在 {src}")
        continue
    t0 = time.time()
    out = OUT / f"{tag}_变朵莉亚.wav"
    rvc.infer_file(src, str(out))
    print(f"[完成] {tag} -> {out.name} ({time.time()-t0:.1f}s)", flush=True)

print("ALL DONE")

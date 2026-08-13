# -*- coding: utf-8 -*-
# doria6 推理参数调优：用用户真实声音(123)生成多个变体对比
import time
from pathlib import Path

from rvc_python.infer import RVCInference

OUT = Path(r"F:\AI变声\音频\朵莉亚试听\调优")
OUT.mkdir(parents=True, exist_ok=True)

SRC = r"F:\AI变声\AI换声\data\voices\d119158a14f0.wav"  # 用户真实声音

VARIANTS = [
    ("V1_idx0.75_up0", 0.75, 0),    # 当前应用默认
    ("V2_idx1.0_up0", 1.00, 0),     # 索引拉满
    ("V3_idx0.75_up3", 0.75, 3),    # 音高提到朵莉亚区间
    ("V4_idx1.0_up3", 1.00, 3),     # 索引+音高都拉
    ("V5_idx0.9_up2", 0.90, 2),     # 折中
]

rvc = RVCInference(device="cuda:0")
rvc.load_model(r"E:\rvc_models\doria6.pth", version="v2", index_path=r"E:\rvc_models\doria6.index")
rvc.f0method = "rmvpe"
rvc.protect = 0.5

for tag, idx, up in VARIANTS:
    rvc.index_rate = idx
    rvc.f0up_key = up
    out = OUT / f"{tag}.wav"
    t0 = time.time()
    rvc.infer_file(SRC, str(out))
    print(f"[完成] {tag} idx={idx} up={up} ({time.time()-t0:.1f}s)", flush=True)

print("ALL DONE")

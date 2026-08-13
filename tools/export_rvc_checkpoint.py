"""把 RVC WebUI 训练产物（原始 checkpoint，含优化器状态）导出为推理格式。

用法：.venv\\Scripts\\python.exe tools\\export_rvc_checkpoint.py <G_xxx.pth> <输出路径> <epoch> <sr> <f0> [config.json]
示例：.venv\\Scripts\\python.exe tools\\export_rvc_checkpoint.py ^
      "E:\\RVC20260718Nvidia\\RVC20260718Nvidia\\logs\\doria4\\G_20400.pth" ^
      "E:\\rvc_models\\doria4.pth" 300 40k 0

导出格式与 WebUI tools/process_ckpt.py 一致：
{weight(fp16, 去掉 enc_q), config, info, sr, f0, version}
"""
from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path

import torch

def main() -> None:
    if len(sys.argv) < 6:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2]
    epoch = int(sys.argv[3])
    sr = sys.argv[4]          # "40k" / "48k"
    f0 = int(sys.argv[5])     # 0 无f0 / 1 带f0
    cfg_path = sys.argv[6] if len(sys.argv) > 6 else None

    print(f"加载 checkpoint: {src}", flush=True)
    ckpt = torch.load(src, map_location="cpu", weights_only=False)
    if "model" in ckpt:
        ckpt = ckpt["model"]
    print(f"state_dict keys: {len(ckpt)}，emb_g.weight: {tuple(ckpt['emb_g.weight'].shape)}", flush=True)

    # 用 config.json 组装 hps（未提供时按默认 v2 结构）
    if cfg_path and Path(cfg_path).exists():
        with open(cfg_path, encoding="utf-8") as f:
            hps = json.load(f)
        data, model = hps["data"], hps["model"]
    else:
        data = {"filter_length": 2048, "sampling_rate": 40000}
        model = {
            "inter_channels": 192, "hidden_channels": 192, "filter_channels": 768,
            "n_heads": 2, "n_layers": 6, "kernel_size": 3, "p_dropout": 0,
            "resblock": "1", "resblock_kernel_sizes": [3, 7, 11],
            "resblock_dilation_sizes": [[1, 3, 5], [1, 3, 5], [1, 3, 5]],
            "upsample_rates": [10, 10, 2, 2], "upsample_initial_channel": 512,
            "upsample_kernel_sizes": [16, 16, 4, 4],
            "spk_embed_dim": int(ckpt["emb_g.weight"].shape[0]),
            "gin_channels": 256,
        }

    opt = OrderedDict()
    opt["weight"] = OrderedDict()
    for key, v in ckpt.items():
        if "enc_q" in key:
            continue
        opt["weight"][key] = v.half()
    opt["config"] = [
        data["filter_length"] // 2 + 1,
        32,
        model["inter_channels"],
        model["hidden_channels"],
        model["filter_channels"],
        model["n_heads"],
        model["n_layers"],
        model["kernel_size"],
        model["p_dropout"],
        model["resblock"],
        model["resblock_kernel_sizes"],
        model["resblock_dilation_sizes"],
        model["upsample_rates"],
        model["upsample_initial_channel"],
        model["upsample_kernel_sizes"],
        model["spk_embed_dim"],
        model["gin_channels"],
        data["sampling_rate"],
    ]
    opt["info"] = f"{epoch}epoch"
    opt["sr"] = sr
    opt["f0"] = f0
    opt["version"] = "v2"

    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    torch.save(opt, dst)
    print(f"导出成功: {dst} ({Path(dst).stat().st_size/1024/1024:.1f} MB)", flush=True)
    print(f"  config={opt['config'][:4]}... sr={sr} f0={f0} version=v2 info={opt['info']}", flush=True)

if __name__ == "__main__":
    main()

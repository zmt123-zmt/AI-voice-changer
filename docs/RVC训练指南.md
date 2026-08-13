# RVC 模型自训指南（RTX 4060 8GB）

> 目标：用 `F:\AI变声\音频\朵莉亚`（5.8 分钟游戏语音）训练一个**单音色 RVC v2 模型**，
> 训练完接回 AI 变声器应用。
> 前提：数据集已预处理完毕 → `E:\rvc_train\doria\doria_001~055.wav`（55 段，276s，48kHz 单声道）。

---

## 0. 为什么先训朵莉亚，不训元歌

| 素材 | 时长 | 问题 |
|---|---|---|
| 朵莉亚 | 5.8 分钟 | 达标（官方建议 3~10 分钟），推荐 |
| 元歌 | 56 秒 | 太短 + 全部带混响音效，训练效果会很差 |

想训元歌：先收集 3 分钟以上**干净**（去 BGM/混响）元歌语音再做。

---

## 1. 下载 RVC WebUI（含训练功能）

rvc-python（本项目 .venv）**只有推理，没有训练**。训练必须用官方 WebUI：

- GitHub：https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI
- 在 **Release** 页面下载整合包（名字类似 `WebUI_go-webui-vX.Y.Z.7z`，自带 Python 3.10 + CUDA + 依赖 + 预训练底模），解压即用
- GitHub 慢的话：
  - 加速前缀：`https://ghproxy.com/` + 原链接（或 `https://mirror.ghproxy.com/`）
  - 或中文社区分享的整合包（百度网盘），认准 **RVC WebUI**（不是 RVC-python、不是 GPT-SoVITS）

> 不需要重装 CUDA/驱动——你的项目 .venv 已验证 torch 2.5.1+cu121 可用，说明驱动没问题；
> WebUI 整合包自带独立环境，和本项目互不干扰。

---

## 2. 启动 WebUI

解压后双击 **go-webui.bat**（或 start_webui.bat / 一键启动.bat），等待浏览器自动打开
`http://127.0.0.1:7865`（首次启动要初始化模型下载，可能要等几分钟）。

> 之后每一步做完，**等页面右侧日志出现“完成”**再进下一步。

---

## 3. 训练（三步）

### 第 1 步：训练-预处理

页面顶部切到 **“训练”**，选 **“训练-预处理”**：

| 字段 | 填什么 |
|---|---|
| 实验/模型名称 | `doria`（**不能有中文/空格**） |
| 训练数据文件夹 | `E:\rvc_train\doria` |
| 采样率 | `40000` 或 `48000`（4060 8G 建议 40000 更稳；48000 也能跑） |
| 特征提取 | 勾选 **hubert_base** 和 **rmvpe** |
| 是否切片 | 不需要（已切好 3~10s），可不勾 |

点 **“处理数据”**，等日志完成。

### 第 2 步：训练-特征提取

选 **“训练-特征提取”**，直接点 **“处理数据”**（提取 hubert 特征 + rmvpe 基频），等完成。

### 第 3 步：训练-训练

选 **“训练-训练”**：

| 字段 | 建议值 |
|---|---|
| 训练轮次 epoch | 先 **100** |
| batch_size | **8**（48k 显存紧就 4） |
| 学习率 | `1e-4` |

点 **“开始训练”**。RTX 4060 上 100 轮约 **15~40 分钟**（数据越多越久）。

- 日志里看 **loss**：从 ~1.x 一路降到 **0.1 以下**基本就成型了；还降就继续
- 训练完成后，页面会保存 `G_*.pth` 模型，并自动生成 index 特征文件
- 模型位置：`logs\doria\`（`G_xxxx.pth`、`added_doria.index` 或 `trained\*.index`）

---

## 4. 接回 AI 变声器应用（当前状态：doria4 已完成）

> ✅ 2026-08-07 doria4 训练完成：300 轮 / 20400 步，batch=4，40k，去BGM纯净数据集（267 段，IVF833 索引）。
> ✅ 已导出 `E:\rvc_models\doria4.pth`（推理格式，fp16，**已裁剪为单音色** emb_g=1 行，sid=0）
> ✅ 已复制索引 `E:\rvc_models\doria4.index`（added_IVF833）
> ✅ 设置页全局模型 + 朵莉亚音色绑定均已指向 doria4

1. 把 `logs\doria4\` 里的 **G_20400.pth** 用 `tools/export_rvc_checkpoint.py` 导出为推理格式，
   再把 `added_IVF833_Flat_nprobe_1_doria4_v2.index` 复制到 `E:\rvc_models\`（改名为 `doria4.pth` / `doria4.index`）：
   ```bash
   .venv\Scripts\python.exe tools/export_rvc_checkpoint.py ^
     "F:\AI变声\RVC20260718Nvidia\RVC20260718Nvidia\logs\doria4\G_20400.pth" ^
     "E:\rvc_models\doria4.pth" 300 40k 0 ^
     "F:\AI变声\RVC20260718Nvidia\RVC20260718Nvidia\logs\doria4\config.json"
   ```
2. 打开应用 → **音色库** → 朵莉亚卡片 → 点 **“RVC 模型”** 按钮 → 选择 `doria4.pth`
3. 打开应用 → **设置 → RVC**：模型信息应显示 **“1 个音色”**（不再是 109！），说话人 sid 保持 0
4. 声音转换页选朵莉亚 → 转换试听

> ⚠️ 导出后建议把 emb_g 裁成单音色（只留训练过的 sid=0，其余 108 行是随机未训练值）：
> ```python
> cpt = torch.load(r"E:\rvc_models\doria4.pth", map_location="cpu")
> cpt["weight"]["emb_g.weight"] = cpt["weight"]["emb_g.weight"][0:1].contiguous()
> cpt["config"][-3] = 1
> torch.save(cpt, r"E:\rvc_models\doria4.pth")
> ```

> 全局模型（设置里那个）建议也换成 doria4.pth，这样任意音色转换都走朵莉亚模型。
> （注意：doria2 是“继承底模 emb_g”的旧版，因说话人条件被底模固定、转换不像朵莉亚，
> 已被 doria4“重置 emb_g 从零学习”版本取代。doria/doria2/doria3 均为中间产物，可删。）

---

## 5. 效果不满意怎么办（按优先级）

1. **去 BGM/混响再训**：游戏语音大多带音效。WebUI 自带 **“UVR5”** 标签页（人声分离），
   或下载 UVR5 独立版，把朵莉亚音频全部处理成纯人声后，重新跑 `prepare_rvc_dataset.py` 再训。
   这是**相似度提升最大**的一步。
2. **多训几轮**：100 轮后从 checkpoint 继续训练（WebUI 支持“继续训练”），到 loss 不再明显下降。
3. **换采样率**：40k 训完试听，不满意用 48k 重训（或反之）。
4. **加数据**：多找几段朵莉亚语音（记得去混响）。
5. **调推理参数**：应用设置里索引比率 0.5~0.75 之间试；转换页“音调”按需微调。

---

## 6. 附：数据集预处理脚本

已就绪：`tools/prepare_rvc_dataset.py`

```bash
.venv\Scripts\python.exe tools\prepare_rvc_dataset.py "F:\AI变声\音频\朵莉亚" "E:\rvc_train\doria" 48000
# 参数：素材目录 输出目录 采样率
```

功能：统一采样率/单声道 → 去头尾静音 → 按静音切成 3~10s 片段 → 丢弃过短片段。

> ⚠️ 重训时先清空输出目录再跑，避免旧片段混入。

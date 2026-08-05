# AI 变声器（本地桌面版）

Windows 本地运行的声音克隆 / TTS / 声音转换 / 实时变声工具。界面为中文，默认使用本地演示引擎，安装 GPT-SoVITS 或 RVC 后可切换到真实 AI 模型，音频数据不出本机。

## 环境要求

- Windows 10/11 x64
- Python 3.10+（开发环境为 3.12）
- NVIDIA 显卡（推荐 RTX 4060 8GB，演示引擎不需要 GPU）

## 快速开始

```powershell
.\setup.ps1
.\run.ps1
```

`setup.ps1` 会创建 `.venv` 并安装依赖。依赖包括 PySide6、sounddevice、soundfile、scipy、imageio-ffmpeg（自带 ffmpeg 用于 mp3/m4a 解码）。

如果依赖已经装到系统 Python（例如本仓库开发环境），可以跳过 `setup.ps1`，直接 `.\run.ps1` 或 `python -m app.main` 启动。

## 功能

- 音色库：导入 wav/mp3/m4a/flac，自动校验时长、采样率、噪声与削波，可命名/删除/复用
- 克隆：显示音质报告与相似度预估，保存零样本参考音色或 RVC 训练音色入口
- 文字转语音：≤ 1000 字，语速/音调/音量，中文/英文/日文
- 声音转换：上传或录制，转换强度、升降调、干湿比、去噪，前后对比
- 实时变声：设备选择、原声/变声开关、干湿比、输入输出音量、电平表
- 历史记录：回听、删除、重新导出
- 设置：ffmpeg、GPT-SoVITS、RVC、输出目录、语音水印

## 真实模型接入

见 [模型接入指南](docs/模型接入指南.md)。

## 项目结构

```text
app/
  core/      配置、音色库、历史、音频 IO、DSP、任务队列
  engines/   演示引擎与 GPT-SoVITS / RVC 适配器
  ui/        PySide6 桌面界面
tests/       单元测试
docs/        需求评审与模型接入文档
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

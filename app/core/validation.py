from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class AudioReport:
    duration: float = 0.0
    sample_rate: int = 0
    rms_db: float = -90.0
    peak: float = 0.0
    noise_score: float = 0.0
    speech_duration: float = 0.0
    speech_ratio: float = 0.0
    similarity_estimate: float = 0.0
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len([w for w in self.warnings if w.startswith("错误")]) == 0


def analyze_audio(data: np.ndarray, sr: int, size_bytes: int | None = None) -> AudioReport:
    x = np.asarray(data, dtype=np.float32)
    report = AudioReport()
    if len(x) == 0 or sr <= 0:
        report.warnings.append("错误：音频内容为空")
        return report

    report.duration = len(x) / sr
    report.sample_rate = sr
    rms = float(np.sqrt(np.mean(np.square(x)) + 1e-10))
    report.rms_db = 20.0 * np.log10(rms + 1e-10)
    report.peak = float(np.max(np.abs(x)))

    frame_len = max(1, int(sr * 0.03))
    hop = max(1, frame_len // 2)
    if len(x) < frame_len:
        # 音频短于一个分析帧，无法分帧，按整段统计
        frame_rms = np.sqrt(np.mean(np.square(x)) + 1e-10).reshape(1)
        if len(x) > 0 and float(np.max(np.abs(x))) > 1e-8:
            report.speech_ratio = 1.0
        else:
            report.speech_ratio = 0.0
        report.speech_duration = report.duration
    else:
        frames = np.lib.stride_tricks.sliding_window_view(x, frame_len)[::hop]
        frame_rms = np.sqrt(np.mean(np.square(frames), axis=1) + 1e-10)
    if len(frame_rms) == 0:
        report.speech_ratio = 0.0
    else:
        threshold = max(0.02, 0.25 * float(np.percentile(frame_rms, 90)))
        active = frame_rms > threshold
        report.speech_duration = float(np.sum(active) * hop / sr)
        report.speech_ratio = float(np.sum(active) / len(frame_rms))

    if len(frame_rms) >= 4:
        background = float(np.percentile(frame_rms, 10)) + 1e-10
        signal_rms = float(np.percentile(frame_rms, 90)) + 1e-10
        snr_db = 20.0 * np.log10(signal_rms / background)
        report.noise_score = float(np.clip(round((45.0 - snr_db) * 2.0), 0.0, 100.0))

    estimate = 4.5
    if report.duration < 5.0:
        estimate -= 0.8
    elif report.duration < 10.0:
        estimate -= 0.35
    if report.noise_score > 45:
        estimate -= 0.7
    elif report.noise_score > 25:
        estimate -= 0.3
    if report.speech_ratio < 0.35:
        estimate -= 0.6
    if report.peak >= 0.999:
        estimate -= 0.5
    report.similarity_estimate = round(float(np.clip(estimate, 0.0, 4.8)), 1)

    if report.duration < 3.0:
        report.warnings.append("错误：音频过短（<3 秒），无法作为参考音色")
    elif report.duration < 5.0:
        report.warnings.append("警告：零样本克隆建议 5~30 秒")
    elif report.duration > 30.0 and report.duration < 180.0:
        report.warnings.append("提示：若用于实时变声（RVC），3~10 分钟更佳")
    elif report.duration > 600:
        report.warnings.append("错误：音频过长（>10 分钟），请截取主要人声段落")
    if report.sample_rate < 22050:
        report.warnings.append("警告：采样率低于 22050Hz，效果可能受影响")
    if report.noise_score > 45:
        report.warnings.append("警告：环境噪声明显，建议使用干净录音")
    if report.speech_ratio < 0.35:
        report.warnings.append("警告：有效人声占比低，请检查是否混有长段静音或纯音乐")
    if report.peak >= 0.999:
        report.warnings.append("警告：存在削波（爆音），建议降低录音音量")
    if size_bytes and size_bytes > 100 * 1024 * 1024:
        report.warnings.append("错误：文件超过 100MB 上限")
    return report


def validate_for_tts(text: str, max_chars: int = 1000) -> list[str]:
    warnings: list[str] = []
    if not text.strip():
        warnings.append("错误：请输入文字")
    elif len(text) > max_chars:
        warnings.append(f"错误：文字长度超过 {max_chars} 字")
    return warnings

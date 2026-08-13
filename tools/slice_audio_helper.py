# -*- coding: utf-8 -*-
"""长音频切片工具（GPT-SoVITS 训练数据准备用）。

用法（Windows）：
    python slice_audio_helper.py 素材文件夹 [输出文件夹] [长音频阈值秒]

- 自动扫描文件夹内所有音频（wav/mp3/flac 等）
- 长音频（默认 >= 15 秒）：按静音切片成 4~8s 短句（32kHz 单声道 16bit）
- 短音频（< 15 秒）：原样复制（预处理会自动重采样，无需转换）
- 输出默认放在素材文件夹同级：`素材文件夹名_train`
- 结束后打印每段时长与总时长，可直接用于 GPT-SoVITS 训练

依赖：项目 .venv（numpy / scipy / soundfile / librosa）
切片算法内嵌自 GPT-SoVITS 整合包 tools/slicer2.py（静音检测切割）。
"""
import os
import shutil
import sys
import traceback

import numpy as np
import soundfile as sf

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

TARGET_SR = 32000  # GPT-SoVITS 训练统一采样率
AUDIO_EXTS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac", ".wma"}

# ---------------- 切片算法（来自 GPT-SoVITS tools/slicer2.py） ----------------
def get_rms(y, frame_length=2048, hop_length=512, pad_mode="constant"):
    padding = (int(frame_length // 2), int(frame_length // 2))
    y = np.pad(y, padding, mode=pad_mode)
    axis = -1
    out_strides = y.strides + tuple([y.strides[axis]])
    x_shape_trimmed = list(y.shape)
    x_shape_trimmed[axis] -= frame_length - 1
    out_shape = tuple(x_shape_trimmed) + tuple([frame_length])
    xw = np.lib.stride_tricks.as_strided(y, shape=out_shape, strides=out_strides)
    if axis < 0:
        target_axis = axis - 1
    else:
        target_axis = axis + 1
    xw = np.moveaxis(xw, -1, target_axis)
    slices = [slice(None)] * xw.ndim
    slices[axis] = slice(0, None, hop_length)
    x = xw[tuple(slices)]
    power = np.mean(np.abs(x) ** 2, axis=-2, keepdims=True)
    return np.sqrt(power)


class Slicer:
    def __init__(self, sr, threshold=-40.0, min_length=4000, min_interval=300,
                 hop_size=10, max_sil_kept=500):
        if not min_length >= min_interval >= hop_size:
            raise ValueError("必须满足: min_length >= min_interval >= hop_size")
        if not max_sil_kept >= hop_size:
            raise ValueError("必须满足: max_sil_kept >= hop_size")
        min_interval = sr * min_interval / 1000
        self.threshold = 10 ** (threshold / 20.0)
        self.hop_size = round(sr * hop_size / 1000)
        self.win_size = min(round(min_interval), 4 * self.hop_size)
        self.min_length = round(sr * min_length / 1000 / self.hop_size)
        self.min_interval = round(min_interval / self.hop_size)
        self.max_sil_kept = round(sr * max_sil_kept / 1000 / self.hop_size)

    def _apply_slice(self, waveform, begin, end):
        return waveform[begin * self.hop_size: min(waveform.shape[0], end * self.hop_size)]

    def slice(self, waveform):
        if len(waveform.shape) > 1:
            samples = waveform.mean(axis=0)
        else:
            samples = waveform
        if samples.shape[0] <= self.min_length:
            return [waveform]
        rms_list = get_rms(y=samples, frame_length=self.win_size, hop_length=self.hop_size).squeeze(0)
        sil_tags = []
        silence_start = None
        clip_start = 0
        for i, rms in enumerate(rms_list):
            if rms < self.threshold:
                if silence_start is None:
                    silence_start = i
                continue
            if silence_start is None:
                continue
            is_leading_silence = silence_start == 0 and i > self.max_sil_kept
            need_slice_middle = i - silence_start >= self.min_interval and i - clip_start >= self.min_length
            if not is_leading_silence and not need_slice_middle:
                silence_start = None
                continue
            if i - silence_start <= self.max_sil_kept:
                pos = rms_list[silence_start: i + 1].argmin() + silence_start
                if silence_start == 0:
                    sil_tags.append((0, pos))
                else:
                    sil_tags.append((pos, pos))
                clip_start = pos
            elif i - silence_start <= self.max_sil_kept * 2:
                pos = rms_list[i - self.max_sil_kept: silence_start + self.max_sil_kept + 1].argmin()
                pos += i - self.max_sil_kept
                pos_l = rms_list[silence_start: silence_start + self.max_sil_kept + 1].argmin() + silence_start
                pos_r = rms_list[i - self.max_sil_kept: i + 1].argmin() + i - self.max_sil_kept
                if silence_start == 0:
                    sil_tags.append((0, pos_r))
                    clip_start = pos_r
                else:
                    sil_tags.append((min(pos_l, pos), max(pos_r, pos)))
                    clip_start = max(pos_r, pos)
            else:
                pos_l = rms_list[silence_start: silence_start + self.max_sil_kept + 1].argmin() + silence_start
                pos_r = rms_list[i - self.max_sil_kept: i + 1].argmin() + i - self.max_sil_kept
                if silence_start == 0:
                    sil_tags.append((0, pos_r))
                else:
                    sil_tags.append((pos_l, pos_r))
                clip_start = pos_r
            silence_start = None
        total_frames = rms_list.shape[0]
        if silence_start is not None and total_frames - silence_start >= self.min_interval:
            silence_end = min(total_frames, silence_start + self.max_sil_kept)
            pos = rms_list[silence_start: silence_end + 1].argmin() + silence_start
            sil_tags.append((pos, total_frames + 1))
        if len(sil_tags) == 0:
            return [waveform]
        chunks = []
        if sil_tags[0][0] > 0:
            chunks.append(self._apply_slice(waveform, 0, sil_tags[0][0]))
        for i in range(len(sil_tags) - 1):
            chunks.append(self._apply_slice(waveform, sil_tags[i][1], sil_tags[i + 1][0]))
        if sil_tags[-1][1] < total_frames:
            chunks.append(self._apply_slice(waveform, sil_tags[-1][1], total_frames))
        return chunks


# ---------------- 音频读写 ----------------
def load_audio(path, target_sr):
    """读任意音频 -> 单声道 float32 -> 重采样到 target_sr。"""
    try:
        data, sr = sf.read(path, dtype="float32", always_2d=True)
        if data.shape[1] > 1:
            data = data.mean(axis=1)
        else:
            data = data[:, 0]
    except Exception:
        import librosa
        data, sr = librosa.load(path, sr=None, mono=True)
    if sr != target_sr:
        import librosa
        data = librosa.resample(data, orig_sr=sr, target_sr=target_sr)
    return data.astype(np.float32)


def save_wav_32k(path, chunk, max_amp=0.9, alpha=0.25):
    """响度处理（与整合包 slice_audio.py 一致）+ 写 32kHz 16bit 单声道。"""
    tmp_max = np.abs(chunk).max()
    if tmp_max > 1:
        chunk = chunk / tmp_max
    if tmp_max > 0:
        chunk = (chunk / tmp_max * (max_amp * alpha)) + (1 - alpha) * chunk
    sf.write(path, (chunk * 32767).astype(np.int16), TARGET_SR)


# ---------------- 主流程 ----------------
def collect_audio_files(folder):
    files = []
    for name in sorted(os.listdir(folder)):
        ext = os.path.splitext(name)[1].lower()
        if ext in AUDIO_EXTS:
            files.append(os.path.join(folder, name))
    return files


def main():
    if len(sys.argv) < 2:
        print("用法: python slice_audio_helper.py 素材文件夹 [输出文件夹] [长音频阈值秒]")
        sys.exit(1)

    input_path = sys.argv[1].strip().strip('"')
    if not os.path.exists(input_path):
        print(f"路径不存在: {input_path}")
        sys.exit(1)

    long_threshold = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0  # 超过则切片

    if os.path.isfile(input_path):
        files = [input_path]
        out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
            os.path.dirname(input_path), os.path.splitext(os.path.basename(input_path))[0] + "_train")
    else:
        files = collect_audio_files(input_path)
        out_dir = sys.argv[2] if len(sys.argv) > 2 else input_path.rstrip("\\/") + "_train"

    if not files:
        print(f"文件夹里没有找到音频文件: {input_path}")
        sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)
    slicer = Slicer(sr=TARGET_SR, threshold=-40, min_length=4000, min_interval=300,
                    hop_size=10, max_sil_kept=500)

    print("=" * 60)
    print(f"输入 : {input_path}")
    print(f"输出 : {out_dir}")
    print(f"长音频阈值 : {long_threshold:g} 秒（超过则切片，否则原样复制）")
    print(f"切片参数 : -40dB 静音 / 最短4s / 切点间隔300ms / 留边500ms")
    print("=" * 60)

    n_sliced, n_copied = 0, 0
    total_out = 0.0
    for f in files:
        name = os.path.basename(f)
        try:
            import soundfile as _sf
            info = _sf.info(f)
            dur = info.frames / info.samplerate
        except Exception:
            import librosa
            dur = librosa.get_duration(path=f)
        print(f"\n[{dur:7.1f}s] {name}", flush=True)

        if dur < long_threshold:
            # 短音频：原样复制
            shutil.copy2(f, os.path.join(out_dir, name))
            n_copied += 1
            total_out += dur
            print(f"   -> 短音频，原样复制 ({dur:.1f}s)", flush=True)
            continue

        try:
            audio = load_audio(f, TARGET_SR)
        except Exception:
            print(f"  !! 读取失败，跳过: {traceback.format_exc().splitlines()[-1]}", flush=True)
            continue

        chunks = slicer.slice(audio)
        for idx, chunk in enumerate(chunks):
            sec = len(chunk) / TARGET_SR
            if sec < 2.0:  # 过短的段丢弃（静音残留）
                continue
            out_name = f"{os.path.splitext(name)[0]}_seg{idx:03d}_{int(sum(len(c)/TARGET_SR for c in chunks[:idx])*TARGET_SR)}_{int(sum(len(c)/TARGET_SR for c in chunks[:idx+1])*TARGET_SR)}.wav"
            out_path = os.path.join(out_dir, out_name)
            save_wav_32k(out_path, chunk)
            total_out += sec
            print(f"   -> {sec:5.1f}s  {out_name}", flush=True)
        n_sliced += 1

    print("\n" + "=" * 60)
    print(f"完成：切片 {n_sliced} 个长音频，复制 {n_copied} 个短音频")
    print(f"输出共 {len(os.listdir(out_dir))} 个文件，总时长 {total_out:.1f}s ({total_out/60:.1f} 分钟)")
    print(f"输出目录：{out_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()

@echo off
chcp 936 >nul
title 音频切片工具（GPT-SoVITS 训练数据准备）
cd /d F:\AI变声\AI换声

if "%~1"=="" (
    echo ============================================================
    echo  音频切片工具
    echo  用法1：把「素材文件夹」拖到这个图标上松手，自动开始
    echo  用法2：双击后，手动输入文件夹路径
    echo ============================================================
    echo.
    set /p FOLDER=请输入素材文件夹路径（拖拽到此窗口也可）：
) else (
    set "FOLDER=%~1"
)

echo.
echo 正在处理：%FOLDER%
echo.
.venv\Scripts\python.exe tools\slice_audio_helper.py "%FOLDER%"
echo.
echo 处理完毕，按任意键关闭...
pause >nul

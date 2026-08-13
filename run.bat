@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
if exist ".venv\Lib\site-packages" (
    set "PYTHONPATH=%CD%\.venv\Lib\site-packages"
    python -m app.main
) else (
    python -m app.main
)

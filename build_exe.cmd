@echo off
rem Build AI voice changer launcher exe (double-click this file once)
cd /d "%~dp0"

set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe
if not exist "%CSC%" (
    echo [ERROR] csc.exe not found. .NET Framework 4.x is required.
    pause
    exit /b 1
)

echo Compiling launcher...
"%CSC%" /nologo /out:AI-change-voice.exe /target:winexe /r:System.Windows.Forms.dll tools\LaunchApp.cs
if errorlevel 1 (
    echo [ERROR] Compile failed.
    pause
    exit /b 1
)

echo.
echo SUCCESS: AI-change-voice.exe created in project root.
echo Double-click AI-change-voice.exe to start the app.
pause

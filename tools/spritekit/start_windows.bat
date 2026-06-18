@echo off
REM Double-click launcher for the spritekit GUI (Windows).
title spritekit
cd /d "%~dp0"

REM Find Python.
where python >nul 2>nul
if errorlevel 1 (
    echo Python 3 was not found on your PATH.
    echo Install it from https://www.python.org/downloads/ ^(tick "Add to PATH"^) and retry.
    pause
    exit /b 1
)

REM Install dependencies only if they are missing.
python -c "import numpy, scipy, PIL, jurigged" >nul 2>nul
if errorlevel 1 (
    echo Installing dependencies, one moment...
    python -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo Dependency install failed. See the messages above.
        pause
        exit /b 1
    )
)

REM Launch under jurigged so edits to the engine hot-reload live (no restart).
echo Launching spritekit (hot reload)...
python -m jurigged "%~dp0__main__.py" gui
if errorlevel 1 pause
exit /b 0

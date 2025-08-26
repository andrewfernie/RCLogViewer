@echo off
REM RC Log Viewer PySide6 Launcher
REM This script launches the application with proper error handling

echo Starting RC Log Viewer...

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from https://python.org
    pause
    exit /b 1
)


REM Launch the application
echo Launching application...
python main.py

REM Keep window open if there was an error
if errorlevel 1 (
    echo Application exited with error code %errorlevel%

    echo Try installing required packages...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Error: Failed to install dependencies
        echo Please run: pip install -r requirements.txt
        pause
        exit /b 1
    )
    pause
)

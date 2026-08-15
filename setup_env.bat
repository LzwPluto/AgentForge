@echo off
setlocal enabledelayedexpansion

echo ======================================================
echo    OpenCode Multi-Agent Platform - Setup
echo ======================================================

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Please install Python 3.10+.
    pause
    exit /b 1
)

REM Create virtual environment if not exists
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creating virtual environment (.venv)...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
) else (
    echo [1/3] Virtual environment .venv already exists.
)

REM Upgrade pip
echo [2/3] Upgrading pip...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip

REM Install requirements
echo [3/3] Installing dependencies from requirements.txt...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
if errorlevel 1 (
    echo Retrying with default PyPI index...
    pip install -r requirements.txt
)

REM Initialize .env if missing
if not exist ".env" (
    if exist ".env.example" (
        echo Initializing .env from .env.example...
        copy .env.example .env >nul
    )
)

echo ======================================================
echo Setup completed successfully!
echo You can now launch the app by running: run.bat
echo ======================================================
pause

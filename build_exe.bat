@echo off
setlocal

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Virtual environment not found. Running setup_env.bat first...
    call setup_env.bat
)

echo [INFO] Starting PyInstaller build for AgentForge.exe...
call .venv\Scripts\activate.bat
python build_exe.py

pause

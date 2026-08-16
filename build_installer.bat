@echo off
setlocal

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Virtual environment not found. Running setup_env.bat first...
    call setup_env.bat
)

echo [INFO] Starting AgentForge Inno Setup Builder...
call .venv\Scripts\activate.bat
python build_installer.py

pause

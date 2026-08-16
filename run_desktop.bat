@echo off
setlocal

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Virtual environment not found. Running setup_env.bat first...
    call setup_env.bat
)

echo [INFO] Starting AgentForge Multi-Agent Desktop App...
call .venv\Scripts\activate.bat
python main.py --app %*

if errorlevel 1 (
    echo.
    echo [INFO] Process finished or exited.
    pause
)

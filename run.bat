@echo off
setlocal

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Virtual environment not found. Running setup_env.bat first...
    call setup_env.bat
)

echo [INFO] Starting OpenCode Multi-Agent Platform...
call .venv\Scripts\activate.bat
python main.py %*

if errorlevel 1 (
    echo.
    echo [INFO] Process finished or exited.
    pause
)

# OpenCode Multi-Agent WebUI Launcher for PowerShell

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[INFO] Virtual environment not found. Running setup_env.ps1 first..." -ForegroundColor Yellow
    & ".\setup_env.ps1"
}

Write-Host "[INFO] Starting OpenCode Multi-Agent WebUI & GUI Edition..." -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" main.py --gui $args

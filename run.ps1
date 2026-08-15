# OpenCode Multi-Agent Platform - PowerShell Run Script
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[提示] 未检测到虚拟环境，正在执行 setup_env.ps1 初始化..." -ForegroundColor Yellow
    & .\setup_env.ps1
}

Write-Host "[启动] 正在启动 OpenCode Multi-Agent Platform..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe main.py $args

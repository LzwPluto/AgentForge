# OpenCode Multi-Agent Platform - PowerShell Setup Script
$ErrorActionPreference = "Stop"

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "   OpenCode Multi-Agent Platform - 环境初始化" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan

# 1. 检查 Python
try {
    $pyVer = python --version
    Write-Host "[1/3] 检测到 Python: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "[错误] 未找到 Python，请确保已安装 Python 3.10+ 并加入 PATH" -ForegroundColor Red
    Read-Host "按回车键退出..."
    exit 1
}

# 2. 创建虚拟环境
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[2/3] 正在创建虚拟环境 (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "[2/3] 虚拟环境 .venv 已存在。" -ForegroundColor Green
}

# 3. 安装依赖
Write-Host "[3/3] 正在激活虚拟环境并安装依赖..." -ForegroundColor Yellow
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "已从 .env.example 初始化 .env" -ForegroundColor Green
    }
}

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "初始化完成！运行 .\run.ps1 或 run.bat 即可启动平台。" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Cyan
Read-Host "按回车键继续..."

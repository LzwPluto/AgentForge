import os
import sys
import subprocess
from pathlib import Path
import shutil

def main():
    root = Path(__file__).parent.resolve()
    venv_dir = root / ".venv"
    python_exe = venv_dir / "Scripts" / "python.exe" if os.name == "nt" else venv_dir / "bin" / "python"
    pip_exe = venv_dir / "Scripts" / "pip.exe" if os.name == "nt" else venv_dir / "bin" / "pip"

    print("=" * 60)
    print("   OpenCode Multi-Agent Platform - Python Setup")
    print("=" * 60)

    # 1. 检查/创建虚拟环境
    if not python_exe.exists():
        print("[1/3] 正在创建虚拟环境 (.venv)...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    else:
        print("[1/3] 虚拟环境 .venv 已存在。")

    # 2. 升级 pip
    print("[2/3] 正在升级 pip...")
    subprocess.run([str(python_exe), "-m", "pip", "install", "--upgrade", "pip"], check=False)

    # 3. 安装依赖
    print("[3/3] 正在安装 requirements.txt 依赖...")
    req_file = root / "requirements.txt"
    cmd = [
        str(pip_exe), "install", "-r", str(req_file),
        "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
        "--trusted-host", "pypi.tuna.tsinghua.edu.cn"
    ]
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print("镜像源安装受阻，尝试使用官方 PyPI 源...")
        subprocess.run([str(pip_exe), "install", "-r", str(req_file)], check=True)

    # 4. 初始化 .env
    env_file = root / ".env"
    env_example = root / ".env.example"
    if not env_file.exists() and env_example.exists():
        shutil.copy(str(env_example), str(env_file))
        print("已从 .env.example 初始化 .env 配置文件。")

    print("=" * 60)
    print("🎉 环境配置全部就绪！")
    print("运行方式：")
    print("  1. 双击 run.bat 或运行 .\\run.ps1")
    print(f"  2. 终端直接运行: {python_exe} main.py")
    print("=" * 60)

if __name__ == "__main__":
    main()

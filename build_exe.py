import os
import sys
import shutil
import subprocess
from pathlib import Path

# 确保控制台支持 UTF-8 打印
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).parent.resolve()
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
ICON_PATH = PROJECT_ROOT / "assets" / "icon.ico"


def build_executable():
    print("=======================================================")
    print("   AgentForge Windows Standalone EXE Build Script")
    print("=======================================================\n")

    py_exe = sys.executable
    print(f"[1/4] Python Interpreter: {py_exe}")

    # 1. 确保安装了打包依赖
    try:
        import PyInstaller
        import webview
    except ImportError:
        print("[INFO] Installing pyinstaller and pywebview...")
        subprocess.run([py_exe, "-m", "pip", "install", "pyinstaller>=6.0.0", "pywebview>=5.0.0", "pillow"], check=True)

    # 确保图标存在
    if not ICON_PATH.exists():
        print("[INFO] Generating application icons...")
        subprocess.run([py_exe, str(PROJECT_ROOT / "create_icon.py")], check=True)

    # 2. 构造 PyInstaller 打包命令
    sep = ";" if os.name == "nt" else ":"

    cmd = [
        py_exe, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name=AgentForge",
        "--onedir",
        "--windowed",
        f"--icon={ICON_PATH}",
        f"--add-data={PROJECT_ROOT / 'gui' / 'static'}{sep}gui/static",
        f"--add-data={PROJECT_ROOT / 'gui' / 'templates'}{sep}gui/templates",
        f"--add-data={PROJECT_ROOT / 'plugins'}{sep}plugins",
        f"--add-data={PROJECT_ROOT / 'assets'}{sep}assets",
        "--hidden-import=uvicorn",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespans",
        "--hidden-import=uvicorn.lifespans.on",
        "--hidden-import=fastapi",
        "--hidden-import=starlette",
        "--hidden-import=websockets",
        "--hidden-import=webview",
        "--hidden-import=webview.platforms.winforms",
        "--hidden-import=clr",
        "--hidden-import=pythonnet",
        "--hidden-import=dotenv",
        "--hidden-import=pydantic",
        str(PROJECT_ROOT / "main.py")
    ]

    print(f"[2/4] Running PyInstaller compilation with custom icon...")
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if res.returncode != 0:
        print("[ERROR] PyInstaller compilation failed.")
        sys.exit(1)

    # 3. 复制运行时配置文件到输出目录
    target_dir = DIST_DIR / "AgentForge"
    print(f"[3/4] Copying config files & pre-building sandbox_env in: {target_dir}")
    target_dir.mkdir(parents=True, exist_ok=True)

    files_to_copy = [
        "agentforge_config.json",
        "agentforge_config.example.json",
        "agentforge_plugins.json",
        ".env.example",
        "README.md",
        "LICENSE"
    ]
    for fn in files_to_copy:
        src = PROJECT_ROOT / fn
        if src.exists():
            shutil.copy(str(src), str(target_dir / fn))

    (target_dir / "history").mkdir(exist_ok=True)
    (target_dir / "测试软件").mkdir(exist_ok=True)

    # 预构建独立的 sandbox_env 虚拟环境
    sb_target = target_dir / "sandbox_env"
    if not (sb_target / "Scripts" / "python.exe").exists():
        print(f"  + Pre-building bundled AI sandbox environment: {sb_target}")
        try:
            subprocess.run([sys.executable, "-m", "venv", str(sb_target)], check=True, capture_output=True)
        except Exception as e:
            print(f"  [WARN] Pre-building sandbox_env failed: {e}")

    # 4. 完成总结
    exe_path = target_dir / "AgentForge.exe"
    print("\n=======================================================")
    print("   [SUCCESS] Standalone AgentForge.exe generated successfully!")
    print(f"   Directory: {target_dir}")
    print(f"   Executable: {exe_path}")
    print("   Double-click AgentForge.exe to launch the native desktop application!")
    print("=======================================================\n")


if __name__ == "__main__":
    build_executable()

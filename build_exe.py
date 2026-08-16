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

    # 预构建完全自包含独立的便携式 sandbox_env Python 沙箱环境 (真正免外部 Python 安装)
    sb_target = target_dir / "sandbox_env"
    print(f"  + Pre-building fully self-contained portable Python sandbox in: {sb_target}")
    try:
        import zipfile
        embed_zip = PROJECT_ROOT / "python-3.12.9-embed-amd64.zip"
        if not embed_zip.exists():
            zips = list(PROJECT_ROOT.glob("python-*-embed-amd64.zip"))
            if zips:
                embed_zip = zips[0]

        if embed_zip.exists():
            print(f"  + Extracting portable embedded Python from: {embed_zip.name}")
            if sb_target.exists():
                shutil.rmtree(sb_target, ignore_errors=True)
            sb_target.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(embed_zip, "r") as z:
                z.extractall(sb_target)

            # 配置 ._pth 启用 site 机制与 Lib 模块自动检索
            for pth_file in sb_target.glob("*._pth"):
                with open(pth_file, "w", encoding="utf-8") as f:
                    f.write("python312.zip\n.\nLib\nLib/site-packages\nScripts\n\nimport site\n")

            (sb_target / "Lib" / "site-packages").mkdir(parents=True, exist_ok=True)

        # 补全基础 Lib 标准模块库与 Scripts 工具
        base_py_dir = Path(getattr(sys, "base_prefix", sys.prefix))
        if (base_py_dir / "Lib").exists():
            shutil.copytree(
                str(base_py_dir / "Lib"),
                str(sb_target / "Lib"),
                ignore=shutil.ignore_patterns("__pycache__", "test", "idlelib", "tkinter", "turtledemo"),
                dirs_exist_ok=True
            )
        if (base_py_dir / "Scripts").exists() and not (sb_target / "Scripts").exists():
            shutil.copytree(str(base_py_dir / "Scripts"), str(sb_target / "Scripts"), dirs_exist_ok=True)

        # 快速测试独立沙箱 Python 解释器
        test_py = sb_target / "python.exe"
        if test_py.exists():
            chk = subprocess.run(
                [str(test_py), "-c", "import sys, json, math, os; print(f'Portable Embedded Python Verified: {sys.version}')"],
                capture_output=True,
                text=True
            )
            print(f"  + {chk.stdout.strip()}")
        print("  + Portable Python sandbox bundled successfully!")
    except Exception as e:
        print(f"  [WARN] Pre-building portable sandbox failed: {e}")

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

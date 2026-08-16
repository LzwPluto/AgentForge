import os
import re
import json
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
ZIP_OUTPUT = PROJECT_ROOT / "AgentForge_Release.zip"

INCLUDE_ROOT_FILES = [
    "main.py",
    "desktop.py",
    "config.py",
    "create_icon.py",
    "requirements.txt",
    "README.md",
    "LICENSE",
    ".env.example",
    "run.bat",
    "run.ps1",
    "run_desktop.bat",
    "run_gui.bat",
    "run_gui.ps1",
    "run_tui.bat",
    "build_exe.py",
    "build_exe.bat",
    "build_installer.py",
    "build_installer.bat",
    "AgentForge_Setup.iss",
    "setup_env.bat",
    "setup_env.ps1",
    "setup_env.py",
]

INCLUDE_DIRS = [
    "assets",
    "core",
    "agents",
    "gui",
    "plugins",
    "tui",
    "tests",
]

def sanitize_config(json_path: Path) -> str:
    """清理配置中的个人私有密钥"""
    if not json_path.exists():
        return "{}"
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for p in data.get("providers", []):
            p["api_key"] = ""
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception:
        return "{}"

def make_zip():
    print(f"[1/3] Preparing release archive: {ZIP_OUTPUT.name}...")
    if ZIP_OUTPUT.exists():
        ZIP_OUTPUT.unlink()

    with zipfile.ZipFile(ZIP_OUTPUT, "w", zipfile.ZIP_DEFLATED) as zipf:
        # 1. 根目录必要文件
        for fn in INCLUDE_ROOT_FILES:
            fp = PROJECT_ROOT / fn
            if fp.exists():
                print(f"  + Packing root file: {fn}")
                zipf.write(fp, arcname=f"AgentForge/{fn}")

        # 2. 清理后的配置文件
        cfg_source = PROJECT_ROOT / "agentforge_config.json"
        if not cfg_source.exists():
            cfg_source = PROJECT_ROOT / "opencode_config.json"
        clean_cfg = sanitize_config(cfg_source)
        zipf.writestr("AgentForge/agentforge_config.json", clean_cfg)
        zipf.writestr("AgentForge/agentforge_config.example.json", clean_cfg)
        print("  + Packing sanitized agentforge_config.json & agentforge_config.example.json")

        # 3. 必要代码子目录
        for d in INCLUDE_DIRS:
            dp = PROJECT_ROOT / d
            if dp.exists():
                for root, dirs, files in os.walk(dp):
                    dirs[:] = [x for x in dirs if x != "__pycache__" and not x.startswith(".")]
                    for file in files:
                        if file.endswith((".pyc", ".pyo")):
                            continue
                        full_p = Path(root) / file
                        rel_p = full_p.relative_to(PROJECT_ROOT)
                        print(f"  + Packing: {rel_p}")
                        zipf.write(full_p, arcname=f"AgentForge/{rel_p.as_posix()}")

        # 4. 创建初始空目录与占位符
        zipf.writestr("AgentForge/history/.gitkeep", "")
        zipf.writestr("AgentForge/测试软件/README.txt", "此目录为 AgentForge 默认工作区沙箱目录，AI 编写与测试的文件将保存在此处。\n")
        print("  + Packing placeholder directories: history/, 测试软件/")

    size_mb = ZIP_OUTPUT.stat().st_size / (1024 * 1024)
    print(f"\n[SUCCESS] Successfully generated release package:")
    print(f"  -> Path: {ZIP_OUTPUT}")
    print(f"  -> Size: {size_mb:.2f} MB")

if __name__ == "__main__":
    make_zip()

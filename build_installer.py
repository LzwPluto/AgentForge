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
ISS_FILE = PROJECT_ROOT / "AgentForge_Setup.iss"
DIST_EXE = PROJECT_ROOT / "dist" / "AgentForge" / "AgentForge.exe"
OUTPUT_DIR = PROJECT_ROOT / "output"


def find_iscc_compiler() -> Path | None:
    """自动搜索系统中的 Inno Setup 编译器 ISCC.exe (支持全盘检索与各版本 5/6/7)"""
    # 1. 检查环境变量 PATH
    iscc_path = shutil.which("iscc") or shutil.which("ISCC")
    if iscc_path:
        return Path(iscc_path)

    # 2. 检查常见安装位置
    specific_locations = [
        Path(r"D:\Inno Setup 7\ISCC.exe"),
        Path(r"D:\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Inno Setup 7\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 7\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 7\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 5\ISCC.exe"),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe")),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe")),
        Path(os.path.expandvars(r"%ProgramFiles%\Inno Setup 7\ISCC.exe")),
        Path(os.path.expandvars(r"%ProgramFiles%\Inno Setup 6\ISCC.exe")),
    ]

    for loc in specific_locations:
        if loc.exists():
            return loc

    # 3. 动态搜索所有常见盘符根目录与常用路径
    for drive in ["D", "C", "E", "F", "G"]:
        for folder in ["Inno Setup 7", "Inno Setup 6", "Inno Setup 5", "Inno Setup", "InnoSetup", "InnoSetup7", "InnoSetup6"]:
            p = Path(f"{drive}:\\{folder}\\ISCC.exe")
            if p.exists():
                return p
            p2 = Path(f"{drive}:\\Program Files\\{folder}\\ISCC.exe")
            if p2.exists():
                return p2
            p3 = Path(f"{drive}:\\Program Files (x86)\\{folder}\\ISCC.exe")
            if p3.exists():
                return p3

    # 4. 尝试通过 Windows 注册表查找
    try:
        import winreg
        for subkey in [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 7_is1",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 5_is1",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 7_is1",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1",
        ]:
            for hkey in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                try:
                    with winreg.OpenKey(hkey, subkey) as key:
                        install_loc, _ = winreg.QueryValueEx(key, "InstallLocation")
                        if install_loc:
                            cand = Path(install_loc) / "ISCC.exe"
                            if cand.exists():
                                return cand
                except Exception:
                    pass
    except Exception:
        pass

    return None


def build_installer():
    print("=======================================================")
    print("   AgentForge Inno Setup 安装包一键构建工具")
    print("=======================================================\n")

    # 1. 检查 dist 目录下是否已生成 AgentForge.exe
    if not DIST_EXE.exists():
        print("[INFO] 未检测到 dist/AgentForge/AgentForge.exe，正在先执行 build_exe.py 打包主程序...")
        subprocess.run([sys.executable, str(PROJECT_ROOT / "build_exe.py")], check=True)

    if not DIST_EXE.exists():
        print("[ERROR] 生成 AgentForge.exe 失败，无法继续制作安装包。")
        sys.exit(1)

    # 2. 寻找 Inno Setup 编译器
    iscc = find_iscc_compiler()
    if not iscc:
        print("[WARNING] 未在系统中检测到 Inno Setup 编译器 (ISCC.exe)！")
        print("\n💡 您可以通过以下两种方式生成 Setup.exe 安装包：")
        print("  1. 【推荐】下载并安装 Inno Setup 6/7 (免费开源):")
        print("     官网下载地址: https://jrsoftware.org/isdl.php")
        print("     安装后再次双击运行 build_installer.bat 即可全自动构建！")
        print("  2. 手动打开脚本编译:")
        print(f"     使用 Inno Setup 编译器打开: {ISS_FILE}")
        print("     点击菜单栏 [Build] -> [Compile] 即可。\n")
        return

    print(f"[1/2] 找到 Inno Setup 编译器: {iscc}")
    print(f"[2/2] 正在编译安装包: {ISS_FILE.name} ...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [str(iscc), str(ISS_FILE)]
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if res.returncode == 0:
        print("\n=======================================================")
        print("   🎉 [构建成功] AgentForge Windows 安装包已生成！")
        print(f"   📂 输出目录: {OUTPUT_DIR}")
        print("   🚀 安装程序: AgentForge_v1.0.0_Windows_Setup.exe")
        print("=======================================================\n")
    else:
        print(f"\n[ERROR] Inno Setup 编译退出，错误码: {res.returncode}")


if __name__ == "__main__":
    build_installer()

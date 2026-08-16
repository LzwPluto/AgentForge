import sys
import os
import io
import platform
import argparse
import asyncio
from pathlib import Path

# 确保在 PyInstaller 无控制台模式下 sys.stdout/stderr 具备 isatty 属性
class _SafeStreamWriter:
    def write(self, s): pass
    def flush(self): pass
    def isatty(self): return False

if sys.stdout is None:
    sys.stdout = _SafeStreamWriter()
if sys.stderr is None:
    sys.stderr = _SafeStreamWriter()
if sys.stdin is None:
    sys.stdin = io.StringIO()

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Windows 平台专用：消除 Python 3.8+ Windows ProactorEventLoop 退出时管道关闭析构告警异常
if platform.system() == "Windows":
    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport
        _orig_pipe_del = _ProactorBasePipeTransport.__del__
        def _silent_pipe_del(self, *args, **kwargs):
            try:
                _orig_pipe_del(self, *args, **kwargs)
            except Exception:
                pass
        _ProactorBasePipeTransport.__del__ = _silent_pipe_del
    except Exception:
        pass

    try:
        from asyncio.base_subprocess import BaseSubprocessTransport
        _orig_subp_del = BaseSubprocessTransport.__del__
        def _silent_subp_del(self, *args, **kwargs):
            try:
                _orig_subp_del(self, *args, **kwargs)
            except Exception:
                pass
        BaseSubprocessTransport.__del__ = _silent_subp_del
    except Exception:
        pass

from config import config
from core.memory import SharedMemory, EventType, AgentMessage
from core.orchestrator import Orchestrator


def parse_args():
    parser = argparse.ArgumentParser(
        description="AgentForge Multi-Agent Platform (Desktop App / WebUI / TUI / CLI Multi-Modal Edition)"
    )
    parser.add_argument("--app", "--desktop", action="store_true", help="启动独立原生桌面窗口程序 (基于 WebView2)")
    parser.add_argument("--gui", "--web", action="store_true", help="启动 WebUI 浏览器端模式")
    parser.add_argument("--tui", action="store_true", help="启动 Textual 终端全屏 TUI 界面")
    parser.add_argument("--cli", action="store_true", help="以无头 CLI 模式运行")
    parser.add_argument("--goal", "-g", type=str, help="直接指定开发目标（用于 CLI 模式）")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="WebUI 绑定主机 (默认 127.0.0.1)")
    parser.add_argument("--port", "-p", type=int, default=None, help="WebUI 端口号 (默认自动探测 8000+)")
    parser.add_argument("--no-browser", action="store_true", help="启动 WebUI 时不自动打开浏览器")
    parser.add_argument("--workspace", "-w", type=str, help="设置工作区根目录")
    parser.add_argument("--model", "-m", type=str, help="快速设置全局主模型")
    parser.add_argument("--api-key", type=str, help="快速设置首选 API Key")
    parser.add_argument("--base-url", type=str, help="快速设置首选 API Base URL")
    return parser.parse_args()


async def run_cli_mode(goal: str):
    """以简洁的 CLI 控制台模式运行多 Agent 协同开发"""
    enabled_slots = config.get_enabled_slots()
    print(f"\n=======================================================")
    print(f"   AgentForge Multi-Agent 协同创作平台 [CLI 模式]")
    print(f"   工作区: {config.workspace_root}")
    print(f"   活跃成员数量: {len(enabled_slots)}/5 位")
    for s in enabled_slots:
        print(f"     - [{s.slot_id}] {s.icon} {s.name} (供应商: {s.provider_id}, 模型: {s.model})")
    print(f"   开发目标: {goal}")
    print(f"=======================================================\n")

    memory = SharedMemory()
    
    def cli_event_listener(event_type: EventType, data):
        if event_type == EventType.MESSAGE_LOGGED:
            msg: AgentMessage = data
            sender_tag = f"[{msg.sender_name}]"
            print(f"{sender_tag:18} {msg.content}")
        elif event_type == EventType.TASK_UPDATED:
            print(f"  📌 [任务状态更新] {data.title} -> {data.status.value}")

    memory.subscribe(cli_event_listener)
    orchestrator = Orchestrator(memory)
    
    success = await orchestrator.run_goal(goal)
    print(f"\n=======================================================")
    if success:
        print("🎉 [成功] 多 Agent 协同开发全流程已顺利完成！")
    else:
        print("⚠️ [结束] 流程未完全通过或被中止。")
    print(f"=======================================================\n")


def run_tui_mode():
    """以 Textual 终端全屏 TUI 模式运行"""
    try:
        from tui.app import OpenCodeApp
        app = OpenCodeApp()
        app.run()
    except ImportError as e:
        print(f"[错误] 无法导入 TUI 模块 ({e})，请确认已安装依赖：pip install -r requirements.txt")
        print("正在降级为 CLI 交互模式...\n")
        goal = input("请输入开发目标 (Goal): ").strip()
        if goal:
            asyncio.run(run_cli_mode(goal))


def run_desktop_mode():
    """启动独立原生桌面窗口程序"""
    try:
        from desktop import run_desktop_app
        run_desktop_app()
    except Exception as e:
        print(f"[提示] 原生窗口模式启动异常 ({e})，正在回退至 WebUI 浏览器模式...")
        run_gui_mode(open_browser=True)


def run_gui_mode(host: str = "127.0.0.1", port: int = None, open_browser: bool = True):
    """启动现代化 WebUI / GUI 交互界面"""
    try:
        from gui.server import start_server
        start_server(host=host, port=port, open_browser=open_browser)
    except ImportError as e:
        print(f"[错误] 无法启动 WebUI 模块 ({e})，请确认已安装依赖：pip install -r requirements.txt")
        print("正在降级为 TUI 终端模式...\n")
        run_tui_mode()


def main():
    args = parse_args()

    if args.workspace:
        config.workspace_root = str(Path(args.workspace).resolve())
    if args.api_key and config.providers:
        config.providers[0].api_key = args.api_key
    if args.base_url and config.providers:
        config.providers[0].base_url = args.base_url
    if args.model:
        for s in config.agent_slots:
            s.model = args.model

    # 如果通过 PyInstaller 打包为独立可执行文件，优先进入原生桌面窗口模式
    is_frozen = getattr(sys, "frozen", False)

    if args.cli or args.goal:
        goal = args.goal
        if not goal:
            goal = input("请输入开发目标 (Goal): ").strip()
        if goal:
            asyncio.run(run_cli_mode(goal))
    elif args.tui:
        run_tui_mode()
    elif args.app or is_frozen:
        run_desktop_mode()
    else:
        # 默认模式：如果安装了 pywebview 则拉起原生独立窗口，否则启动 WebUI 浏览器端
        try:
            import webview
            run_desktop_mode()
        except ImportError:
            run_gui_mode(
                host=args.host,
                port=args.port,
                open_browser=not args.no_browser
            )


if __name__ == "__main__":
    main()

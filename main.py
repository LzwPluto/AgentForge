import sys
import os
import platform
import argparse
import asyncio
from pathlib import Path

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
    parser = argparse.ArgumentParser(description="OpenCode Multi-Agent Platform (Multi-API & Custom Roles)")
    parser.add_argument("--goal", "-g", type=str, help="直接指定开发目标（用于 CLI 模式）")
    parser.add_argument("--cli", action="store_true", help="以无头 CLI 模式运行而非 TUI 界面")
    parser.add_argument("--workspace", "-w", type=str, help="设置工作区根目录")
    parser.add_argument("--model", "-m", type=str, help="快速设置全局主模型")
    parser.add_argument("--api-key", type=str, help="快速设置首选 API Key")
    parser.add_argument("--base-url", type=str, help="快速设置首选 API Base URL")
    return parser.parse_args()


async def run_cli_mode(goal: str):
    """以简洁的 CLI 控制台模式运行多 Agent 协同开发"""
    enabled_slots = config.get_enabled_slots()
    print(f"\n=======================================================")
    print(f"   OpenCode Multi-Agent 协同开发平台 [CLI 模式]")
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

    if args.cli or args.goal:
        goal = args.goal
        if not goal:
            goal = input("请输入开发目标 (Goal): ").strip()
        if goal:
            asyncio.run(run_cli_mode(goal))
    else:
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


if __name__ == "__main__":
    main()

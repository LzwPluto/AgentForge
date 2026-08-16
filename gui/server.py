import os
import sys
import json
import asyncio
import logging
import socket
import webbrowser
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import PROJECT_ROOT, config, AppConfig, AgentSlotConfig, APIProviderConfig
from core.memory import SharedMemory, EventType, AgentMessage, TaskItem, AgentStatus
from core.orchestrator import Orchestrator
from core.history_manager import HistoryManager
from core.tools import SandboxTools
from plugins.manager import plugin_manager

logger = logging.getLogger("agentforge.gui")

# 路径定义
GUI_DIR = Path(__file__).parent.resolve()
STATIC_DIR = GUI_DIR / "static"
TEMPLATES_DIR = GUI_DIR / "templates"

from contextlib import asynccontextmanager

_main_event_loop: Optional[asyncio.AbstractEventLoop] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _main_event_loop
    _main_event_loop = asyncio.get_running_loop()
    yield

app = FastAPI(title="AgentForge Multi-Agent Platform", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 全局共享单例
shared_memory = SharedMemory()
orchestrator = Orchestrator(shared_memory)
_current_task_future: Optional[asyncio.Task] = None


class ConnectionManager:
    """管理活跃的 WebSocket 连接并进行事件实时广播"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        async with self._lock:
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)
            for d in disconnected:
                if d in self.active_connections:
                    self.active_connections.remove(d)


ws_manager = ConnectionManager()
_main_event_loop: Optional[asyncio.AbstractEventLoop] = None


def _on_bus_event(event_type: EventType, data: Any):
    """黑板事件总线监听器：将所有事件转化为 JSON 并通过 WebSocket 推送至前端"""
    payload = {
        "event_type": event_type.value if hasattr(event_type, "value") else str(event_type),
        "data": None
    }

    if isinstance(data, BaseModel):
        payload["data"] = data.model_dump()
    elif isinstance(data, (dict, list, str, int, float, bool)) or data is None:
        payload["data"] = data
    else:
        payload["data"] = str(data)

    if _main_event_loop and _main_event_loop.is_running():
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(payload), _main_event_loop)


shared_memory.subscribe(_on_bus_event)





@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # 发送初始全量状态
        await websocket.send_json({
            "event_type": "INIT_STATE",
            "data": get_full_state_dict()
        })
        while True:
            # 保持心跳连接与接收客户端指令
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                cmd = msg.get("command")
                if cmd == "PING":
                    await websocket.send_json({"event_type": "PONG"})
            except Exception:
                pass
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


def get_full_state_dict() -> Dict[str, Any]:
    workflow_state = "IDLE"
    if orchestrator.is_running:
        workflow_state = "PAUSED" if orchestrator.is_paused else "RUNNING"

    return {
        "workflow_state": workflow_state,
        "user_goal": shared_memory.user_goal,
        "current_round": shared_memory.current_round,
        "max_rounds": shared_memory.max_rounds,
        "current_speaker": shared_memory.current_speaker,
        "agent_states": shared_memory.agent_states,
        "tasks": [t.model_dump() for t in shared_memory.tasks],
        "messages": [m.model_dump() for m in shared_memory.group_chat_history],
        "config": config.model_dump(),
        "workspace": config.workspace_root,
    }


# ==========================================
# REST API 接口
# ==========================================

@app.get("/api/status")
async def api_get_status():
    return get_full_state_dict()


class RunGoalRequest(BaseModel):
    goal: str


@app.post("/api/action/run")
async def api_run_goal(req: RunGoalRequest):
    global _current_task_future
    goal = req.goal.strip()
    if not goal:
        raise HTTPException(status_code=400, detail="目标内容不能为空")

    if orchestrator.is_running:
        raise HTTPException(status_code=400, detail="已有正在运行中的协同流程")

    async def _runner():
        try:
            await orchestrator.run_goal(goal)
        except Exception as e:
            logger.exception(f"协同运行异常: {e}")

    _current_task_future = asyncio.create_task(_runner())
    return {"status": "ok", "message": "协同任务已启动"}


class ResumeRequest(BaseModel):
    feedback: Optional[str] = ""


@app.post("/api/action/pause")
async def api_pause():
    if not orchestrator.is_running:
        raise HTTPException(status_code=400, detail="当前没有正在运行的协同流程")
    orchestrator.pause()
    return {"status": "ok", "message": "工作流已暂停"}


@app.post("/api/action/resume")
async def api_resume(req: ResumeRequest):
    if not orchestrator.is_paused:
        raise HTTPException(status_code=400, detail="当前未处于暂停挂起状态")
    await orchestrator.resume(steering_feedback=req.feedback or "")
    return {"status": "ok", "message": "已恢复协同接力"}


@app.post("/api/action/cancel")
async def api_cancel():
    global _current_task_future
    if orchestrator.is_running:
        orchestrator.cancel()
        if _current_task_future and not _current_task_future.done():
            _current_task_future.cancel()
    return {"status": "ok", "message": "已终止当前任务"}


@app.get("/api/config")
async def api_get_config():
    return config.model_dump()


@app.post("/api/config")
async def api_update_config(new_config: Dict[str, Any]):
    try:
        updated_cfg = AppConfig.model_validate(new_config)
        updated_cfg.sanitize()
        
        # 覆写当前内存全局配置
        config.providers = updated_cfg.providers
        config.agent_slots = updated_cfg.agent_slots
        config.workspace_root = updated_cfg.workspace_root
        config.sandbox_env_dir = updated_cfg.sandbox_env_dir
        config.max_loops_per_task = updated_cfg.max_loops_per_task
        config.command_timeout_seconds = updated_cfg.command_timeout_seconds
        
        config.save_to_file()
        shared_memory.sync_slots_from_config()
        shared_memory.publish(EventType.CONFIG_RELOADED, config.model_dump())
        return {"status": "ok", "config": config.model_dump()}
    except Exception as e:
        logger.exception("配置更新异常")
        raise HTTPException(status_code=400, detail=f"保存配置失败: {str(e)}")


@app.get("/api/history")
async def api_list_history():
    sessions = HistoryManager.list_sessions()
    return {"status": "ok", "sessions": sessions}


@app.get("/api/history/{session_id}")
async def api_get_history(session_id: str):
    md_content = HistoryManager.get_session_markdown(session_id)
    json_path = HISTORY_DIR = PROJECT_ROOT / "history" / f"session_{session_id}.json"
    session_data = {}
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                session_data = json.load(f)
        except Exception:
            pass

    return {
        "status": "ok",
        "session_id": session_id,
        "markdown": md_content,
        "data": session_data
    }


@app.delete("/api/history/{session_id}")
async def api_delete_history(session_id: str):
    success = HistoryManager.delete_session(session_id)
    return {"status": "ok", "deleted": success}


@app.delete("/api/history")
async def api_clear_all_history():
    success = HistoryManager.clear_all_sessions()
    return {"status": "ok", "cleared": success}


@app.get("/api/diff")
async def api_get_diff(file: Optional[str] = None):
    try:
        res = SandboxTools.get_git_diff(path=file)
        output = res.output if res.success else (res.error or "无代码变更")
        return {"status": "ok", "diff": output}
    except Exception as e:
        return {"status": "error", "diff": f"获取 Diff 失败: {e}"}


@app.get("/api/sandbox/check")
async def api_sandbox_check():
    py_path = config.get_sandbox_python_path()
    exists = py_path is not None and py_path.exists()
    return {
        "status": "ok",
        "ready": exists,
        "python_path": str(py_path) if exists else None,
        "sandbox_env_dir": str(config.get_resolved_sandbox_env())
    }


@app.post("/api/sandbox/build")
async def api_sandbox_build():
    ok, msg = config.ensure_sandbox_env()
    return {
        "status": "ok" if ok else "error",
        "ready": ok,
        "message": msg
    }


@app.get("/api/files")
async def api_list_files(sub_path: Optional[str] = ""):
    try:
        ws = config.get_resolved_workspace()
        target = (ws / sub_path).resolve() if sub_path else ws
        if not str(target).startswith(str(ws)):
            raise HTTPException(status_code=403, detail="越界访问工作区外部目录")
        
        items = []
        if target.exists() and target.is_dir():
            for entry in target.iterdir():
                if entry.name.startswith((".git", "__pycache__", ".venv")):
                    continue
                items.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size": entry.stat().st_size if entry.is_file() else 0,
                    "rel_path": str(entry.relative_to(ws)).replace("\\", "/")
                })
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return {"status": "ok", "workspace": str(ws), "current": str(target.relative_to(ws)), "items": items}
    except Exception as e:
        return {"status": "error", "items": [], "error": str(e)}


@app.get("/api/files/read")
async def api_read_file(path: str = Query(...)):
    try:
        ws = config.get_resolved_workspace()
        target = (ws / path).resolve()
        if not str(target).startswith(str(ws)):
            raise HTTPException(status_code=403, detail="越界访问工作区外部目录")
        if not target.exists() or not target.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(50000)
        return {"status": "ok", "path": path, "content": content}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/plugins")
async def api_list_plugins():
    plugins = plugin_manager.list_plugins()
    return {"status": "ok", "plugins": [p.model_dump() for p in plugins]}


@app.post("/api/plugins/{plugin_id}/toggle")
async def api_toggle_plugin(plugin_id: str):
    p = plugin_manager.toggle_plugin(plugin_id)
    if not p:
        raise HTTPException(status_code=404, detail="插件不存在")
    return {"status": "ok", "plugin": p.model_dump()}


@app.post("/api/plugins/{plugin_id}/settings")
async def api_update_plugin_settings(plugin_id: str, payload: Dict[str, Any]):
    p = plugin_manager.update_plugin_settings(plugin_id, payload.get("settings", {}))
    if not p:
        raise HTTPException(status_code=404, detail="插件不存在")
    return {"status": "ok", "plugin": p.model_dump()}


def find_free_port(start_port: int = 8000, max_tries: int = 50) -> int:
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port


def start_server(host: str = "127.0.0.1", port: Optional[int] = None, open_browser: bool = True):
    import uvicorn
    actual_port = port or find_free_port(8000)
    url = f"http://{host}:{actual_port}"

    print(f"\n=======================================================")
    print(f"   🚀 OpenCode Multi-Agent WebUI & GUI 平台")
    print(f"   🌐 访问地址: {url}")
    print(f"   📁 工作区:   {config.workspace_root}")
    print(f"   💡 按 Ctrl+C 可停止 WebUI 服务")
    print(f"=======================================================\n")

    if open_browser:
        def _open():
            import time
            time.sleep(1.0)
            webbrowser.open(url)
        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run(app, host=host, port=actual_port, log_level="warning")


if __name__ == "__main__":
    start_server()

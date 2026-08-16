import sys
import os
import io
import time
import socket
import threading
import urllib.request
from pathlib import Path

# 确保在 PyInstaller 无控制台模式下 sys.stdout/stderr 具备 isatty 属性，避免 Uvicorn 报错
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

from config import config


def find_free_port(start_port: int = 8000, max_tries: int = 50) -> int:
    for port in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port


def wait_for_server(url: str, timeout: float = 8.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as res:
                if res.status == 200:
                    return True
        except Exception:
            time.sleep(0.15)
    return False


def run_desktop_app():
    """启动本地 FastAPI 并在独立 PyWebView 原生窗口中呈现，免浏览器标签页独立运行"""
    try:
        import webview
    except ImportError:
        print("[错误] 未安装 pywebview，正在回退至系统浏览器模式...")
        from gui.server import start_server
        start_server(open_browser=True)
        return

    import uvicorn
    from gui.server import app

    port = find_free_port(8000)
    host = "127.0.0.1"
    server_url = f"http://{host}:{port}"

    # 1. 后台线程启动 FastAPI Uvicorn 服务
    server_config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
        log_config=None
    )
    server = uvicorn.Server(server_config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # 2. 等待后端 HTTP 启动就绪
    wait_for_server(server_url)

    # 3. 创建原生桌面窗口 (Windows 基于 Edge WebView2 引擎，超低内存占用)
    window = webview.create_window(
        title="AgentForge - Multi-Agent Collaborative Platform",
        url=server_url,
        width=1280,
        height=820,
        min_size=(960, 600),
        background_color="#fcf9f2",
        text_select=True,
        zoomable=True
    )

    def on_closed():
        server.should_exit = True

    window.events.closed += on_closed

    # 4. 启动 WebView GUI 事件循环 (GUI 线程阻塞直至窗口关闭)
    webview.start(debug=False)

    # 窗口关闭后清理退出
    server.should_exit = True
    sys.exit(0)


if __name__ == "__main__":
    run_desktop_app()

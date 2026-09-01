"""TikTokDownloader Server 启动入口 — 供 uvicorn 直接调用。

使用方式：
    uvicorn server:app --host 0.0.0.0 --port 5555 --app-dir .
"""

import asyncio
import os
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

from src.application.main_server import APIServer
from src.config.settings import Settings
from src.custom import SERVER_HOST, SERVER_PORT

# 加载 .env（MySQL 参数等）
_env_file = Path(__file__).parent / ".env"
if _env_file.is_file():
    load_dotenv(_env_file)

# ── 模块级 FastAPI app ──────────────────────────────────────────────
# uvicorn 需要一个模块级的 FastAPI 实例。
# 这里通过 _build_app() 创建 APIServer 并暴露其内部的 server 属性。

def _build_app() -> APIServer:
    """构建 APIServer 实例（用于部署模式）。"""

    class _FakeConsole:
        def info(self, msg): pass
        def error(self, msg): pass
        def warning(self, msg): pass
        def print(self, *a, **k): pass

    root = Path(__file__).resolve().parent
    settings = Settings(root, _FakeConsole())

    server_instance = APIServer(
        parameter=None,
        database=None,
        server_mode=True,
    )
    # 将 MySQL 参数注入到 server 实例，供 spider_repository 使用
    server_instance.mysql_host = os.getenv("MYSQL_HOST", "127.0.0.1")
    server_instance.mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
    server_instance.mysql_user = os.getenv("MYSQL_USER", "root")
    server_instance.mysql_password = os.getenv("MYSQL_PASSWORD", "")
    server_instance.mysql_database = os.getenv("MYSQL_DATABASE", "spider_tiktok")
    return server_instance


# 暴露给 uvicorn：uvicorn server:app
app = _build_app().server  # FastAPI 实例

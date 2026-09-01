"""Spider_XHS 兼容的 REST API 端点 — 提供列表查询、聚合统计、异步任务管理等能力。"""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..models import DataResponse
from ..translation import _

__all__ = ["setup_spider_routes"]


def setup_spider_routes(
    server,
    repository,
    parameter=None,
    database=None,
    token_header: str = None,
):
    """注册 Spider_XHS 兼容的 API 端点到 FastAPI server。

    Parameters
    ----------
    server : FastAPI
        目标 FastAPI 实例（APIServer.server）
    repository : SpiderDouyinRepository
        MySQL 数据访问层实例
    parameter : Parameter, optional
        配置参数（用于爬虫操作时需要）
    database : Database, optional
        应用数据库（用于 token 验证）
    token_header : str, optional
        全局 token（来自 custom/function.py）
    """

    router = APIRouter(prefix="/internal/v1", tags=["Spider API"])

    # ---- 作品查询端点 ----

    @router.get(
        "/notes",
        summary=_("获取作品列表（分页）"),
        response_model=DataResponse,
    )
    async def get_notes(
        keyword: str = None,
        sort: str = "latest",
        page: int = 1,
        pagesize: int = 20,
    ):
        notes, total = await repository.list_notes(
            keyword=keyword, sort_by=sort, page=page, page_size=pagesize
        )
        return DataResponse(
            message=_("获取数据成功！"),
            data={"notes": notes, "total": total, "page": page, "pagesize": pagesize},
            params={"keyword": keyword, "sort": sort, "page": page, "pagesize": pagesize},
        )

    @router.get(
        "/notes/{note_id}",
        summary=_("获取单个作品详情"),
        response_model=DataResponse,
    )
    async def get_note(note_id: str):
        note = await repository.get_note(note_id)
        if note is None:
            return DataResponse(
                message=_("作品不存在！"),
                data=None,
                params={"note_id": note_id},
            )
        return DataResponse(message=_("获取数据成功！"), data=note, params={"note_id": note_id})

    @router.post(
        "/notes/by-id",
        summary=_("批量获取作品"),
        response_model=DataResponse,
    )
    async def batch_notes(body: dict):
        note_ids = body.get("note_ids", [])
        notes = await repository.batch_notes(note_ids)
        return DataResponse(
            message=_("获取数据成功！"),
            data=notes,
            params={"note_ids": note_ids},
        )

    # ---- 作品保存（爬虫结果写入） ----

    @router.post(
        "/notes/save",
        summary=_("保存作品数据"),
        response_model=DataResponse,
    )
    async def save_note(body: dict):
        note = body.get("note")
        if not note or not note.get("note_id"):
            return DataResponse(message=_("缺少作品数据！"), data=None, params=body)
        success = await repository.save_note(note)
        status = _("成功") if success else _("失败")
        return DataResponse(message=f"保存作品{status}！", data=note, params={"note_id": note.get("note_id")})

    # ---- 快照查询端点 ----

    @router.post(
        "/snapshots/by-task",
        summary=_("按任务ID获取快照"),
        response_model=DataResponse,
    )
    async def get_snapshots(body: dict):
        crawl_task_id = body.get("crawl_task_id", "")
        page = body.get("page", 1)
        pagesize = body.get("pagesize", 50)
        snapshots, total = await repository.snapshots_by_task(
            crawl_task_id, page=page, page_size=pagesize
        )
        return DataResponse(
            message=_("获取数据成功！"),
            data={"snapshots": snapshots, "total": total},
            params={"crawl_task_id": crawl_task_id, "page": page, "pagesize": pagesize},
        )

    @router.get(
        "/snapshots/aggregate",
        summary=_("聚合统计快照"),
        response_model=DataResponse,
    )
    async def get_aggregate(crawl_task_id: str = ""):
        agg = await repository.aggregate_snapshots(crawl_task_id)
        if agg is None:
            return DataResponse(
                message=_("未找到任务快照！"),
                data=None,
                params={"crawl_task_id": crawl_task_id},
            )
        return DataResponse(message=_("获取数据成功！"), data=agg, params={"crawl_task_id": crawl_task_id})

    @router.get(
        "/metrics/overview",
        summary=_("全局概览统计"),
        response_model=DataResponse,
    )
    async def get_overview():
        stats = await repository.overview()
        return DataResponse(message=_("获取数据成功！"), data=stats, params={})

    @router.get(
        "/metrics/daily-count",
        summary=_("每日新作品数"),
        response_model=DataResponse,
    )
    async def get_daily_count(days: int = 30):
        daily = await repository.daily_count(days)
        return DataResponse(message=_("获取数据成功！"), data=daily, params={"days": days})

    # ---- 异步任务端点 ----

    @router.post(
        "/crawl-jobs",
        summary=_("提交异步爬取任务"),
        response_model=DataResponse,
    )
    async def submit_crawl_job(body: dict):
        import uuid

        job_id = body.get("job_id") or str(uuid.uuid4())
        job_type = body.get("job_type", "search")
        parameters = {k: v for k, v in body.items() if k not in ("job_id", "job_type")}

        await repository.create_job(job_id, job_type, parameters)
        return DataResponse(
            message=_("任务已提交！"),
            data={"job_id": job_id, "status": "pending"},
            params={"job_id": job_id, "job_type": job_type},
        )

    @router.get(
        "/crawl-jobs/{job_id}",
        summary=_("获取任务状态"),
        response_model=DataResponse,
    )
    async def get_crawl_job(job_id: str):
        job = await repository.get_job(job_id)
        if job is None:
            return DataResponse(
                message=_("任务不存在！"),
                data=None,
                params={"job_id": job_id},
            )
        return DataResponse(message=_("获取数据成功！"), data=job, params={"job_id": job_id})

    @router.get(
        "/crawl-jobs/{job_id}/results",
        summary=_("获取任务结果"),
        response_model=DataResponse,
    )
    async def get_crawl_results(
        job_id: str,
        page: int = 1,
        pagesize: int = 20,
    ):
        # 从作品表中查询与该任务相关的数据
        # 通过快照表关联
        snapshots, total = await repository.snapshots_by_task(job_id, page=page, page_size=pagesize)

        # 获取这些快照对应的作品详情
        note_ids = [s["note_id"] for s in snapshots if s.get("note_id")]
        notes = []
        if note_ids:
            notes = await repository.batch_notes(note_ids)

        return DataResponse(
            message=_("获取数据成功！"),
            data={"notes": notes, "snapshots": snapshots, "total": total},
            params={"job_id": job_id, "page": page, "pagesize": pagesize},
        )

    # ---- Cookie 验证端点 ----

    @router.post(
        "/douyin/cookie-validation",
        summary=_("验证抖音 Cookie"),
        response_model=DataResponse,
    )
    async def validate_douyin_cookie(body: dict):
        cookie = body.get("cookie", "")
        if not parameter:
            return DataResponse(
                message=_("未配置 Parameter，无法验证 Cookie"),
                data=None,
                params=body,
            )
        try:
            state = parameter.__check_cookie_state()
            # 尝试设置提供的 cookie
            if cookie:
                parameter.cookie_dict, parameter.cookie_str = parameter._Parameter__check_cookie(cookie)
                state = parameter._Parameter__check_cookie_state()
            return DataResponse(
                message=_("Cookie 有效") if state else _("Cookie 无效"),
                data={"valid": state},
                params={"has_cookie": bool(cookie)},
            )
        except Exception as e:
            return DataResponse(message=f"验证失败: {str(e)}", data=None, params=body)

    # ---- 客户端注册端点 ----

    @router.get(
        "/clients/register",
        summary=_("注册 API 客户端"),
        response_model=DataResponse,
    )
    async def register_client(body: dict):
        import secrets

        client_id = body.get("client_id", "")
        if not client_id:
            return DataResponse(
                message=_("缺少 client_id！"),
                data=None,
                params=body,
            )

        client_key = secrets.token_urlsafe(32)
        permissions = body.get("permissions", ["read", "crawl"])

        result = await repository.register_client(client_id, client_key, permissions)
        return DataResponse(
            message=_("注册成功！请保存 client_key，后续请求需要用到。"),
            data=result,
            params={"client_id": client_id},
        )

    # 将 router 的所有路由注册到 server
    for route in router.routes:
        server.router.routes.append(route)

"""异步爬取任务后台 Worker — 从 MySQL 拉取待执行任务并调用 TikTokDownloader 爬虫执行。"""

import asyncio
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

__all__ = ["CrawlWorker"]


class CrawlWorker:
    """异步爬取任务后台 Worker。

    持续从 MySQL 的 crawl_job 表中拉取 pending 状态的任务，
    调用 TikTokDownloader 的爬虫接口执行爬取，
    将结果写入 spider_douyin_note 和 spider_douyin_note_snapshot 表。
    """

    def __init__(
        self,
        repository,
        tiktok_instance=None,
        poll_interval: int = 5,
        batch_size: int = 5,
    ):
        self._repository = repository
        self._tiktok = tiktok_instance  # TikTok 实例（用于调用爬虫接口）
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._running = False

    async def start(self) -> None:
        """启动后台 Worker 循环。"""
        self._running = True
        while self._running:
            try:
                jobs = await self._repository.get_pending_jobs(limit=self._batch_size)
                for job in jobs:
                    await self._process_job(job)
            except Exception as e:
                # 记录错误但不崩溃
                try:
                    print(f"[CrawlWorker] 轮询错误: {e}")
                except Exception:
                    pass
            await asyncio.sleep(self._poll_interval)

    async def stop(self) -> None:
        """停止后台 Worker。"""
        self._running = False

    async def _process_job(self, job: dict[str, Any]) -> None:
        """处理单个爬取任务。"""
        job_id = job["job_id"]
        job_type = job["job_type"]
        parameters = job.get("parameters", {}) or {}

        # 标记为 running
        await self._repository.update_job_status(job_id, "running")

        try:
            completed = 0
            if job_type == "search":
                completed = await self._handle_search(job_id, parameters)
            elif job_type == "account":
                completed = await self._handle_account(job_id, parameters)
            elif job_type == "detail":
                completed = await self._handle_detail(job_id, parameters)
            elif job_type == "mix":
                completed = await self._handle_mix(job_id, parameters)
            else:
                await self._repository.fail_job(
                    job_id, f"不支持的任务类型: {job_type}"
                )
                return

            # 标记完成
            await self._repository.complete_job(
                job_id, total_notes=completed, completed_notes=completed
            )
        except Exception as e:
            await self._repository.fail_job(job_id, str(e))

    async def _handle_search(self, job_id: str, params: dict) -> int:
        """执行搜索爬取。"""
        if not self._tiktok:
            await self._repository.fail_job(job_id, "TikTok 实例未配置")
            return 0

        keyword = params.get("keyword", "")
        if not keyword:
            await self._repository.fail_job(job_id, "缺少 keyword 参数")
            return 0

        cursor = params.get("cursor", 0)
        count = params.get("count", 20)
        pages = params.get("pages", 1)
        sort_type = params.get("sort_type", "")
        publish_time = params.get("publish_time", "")

        completed = 0
        for i in range(pages):
            try:
                data = await self._tiktok.deal_search_data(
                    type="general",
                    keyword=keyword,
                    cursor=cursor + i * count,
                    count=count,
                    sort_type=sort_type,
                    publish_time=publish_time,
                    source=False,
                    cookie=params.get("cookie"),
                    proxy=params.get("proxy"),
                )
                if not data:
                    break

                for item in data:
                    note = self._extract_note_from_search(item)
                    if note:
                        await self._repository.save_note(note)
                        completed += 1

                # 更新进度
                await self._repository.update_job_progress(job_id, completed)

            except Exception:
                break

        return completed

    async def _handle_account(self, job_id: str, params: dict) -> int:
        """执行账号爬取。"""
        if not self._tiktok:
            await self._repository.fail_job(job_id, "TikTok 实例未配置")
            return 0

        sec_user_id = params.get("sec_user_id", "")
        if not sec_user_id:
            await self._repository.fail_job(job_id, "缺少 sec_user_id 参数")
            return 0

        tab = params.get("tab", "post")
        pages = params.get("pages", 1)
        cursor = params.get("cursor", 0)
        count = params.get("count", 20)

        completed = 0
        try:
            data = await self._tiktok.deal_account_detail(
                0,
                sec_user_id,
                tab=tab,
                api=True,
                source=False,
                cookie=params.get("cookie"),
                proxy=params.get("proxy"),
                cursor=cursor,
                count=count,
            )
            if data:
                for item in data:
                    note = self._extract_note_from_detail(item)
                    if note:
                        await self._repository.save_note(note)
                        completed += 1

            await self._repository.update_job_progress(job_id, completed)
        except Exception:
            await self._repository.fail_job(job_id, str(Exception))

        return completed

    async def _handle_detail(self, job_id: str, params: dict) -> int:
        """执行单作品爬取。"""
        if not self._tiktok:
            await self._repository.fail_job(job_id, "TikTok 实例未配置")
            return 0

        detail_id = params.get("detail_id", "")
        if not detail_id:
            await self._repository.fail_job(job_id, "缺少 detail_id 参数")
            return 0

        try:
            result = await self._tiktok._handle_detail(
                [detail_id],
                tiktok=False,
                record=None,
                api=True,
                source=False,
                cookie=params.get("cookie"),
                proxy=params.get("proxy"),
            )
            if result:
                note = self._extract_note_from_detail(result[0])
                if note:
                    await self._repository.save_note(note)
                    return 1
            return 0
        except Exception as e:
            await self._repository.fail_job(job_id, str(e))
            return 0

    async def _handle_mix(self, job_id: str, params: dict) -> int:
        """执行合集爬取。"""
        if not self._tiktok:
            await self._repository.fail_job(job_id, "TikTok 实例未配置")
            return 0

        mix_id = params.get("mix_id", "")
        detail_id = params.get("detail_id", "")

        is_mix, id_ = self._tiktok.generate_mix_params(mix_id, detail_id)
        if not isinstance(is_mix, bool):
            await self._repository.fail_job(job_id, "参数错误！")
            return 0

        try:
            data = await self._tiktok.deal_mix_detail(
                is_mix,
                id_,
                api=True,
                source=False,
                cookie=params.get("cookie"),
                proxy=params.get("proxy"),
            )
            if data:
                completed = 0
                for item in data:
                    note = self._extract_note_from_detail(item)
                    if note:
                        await self._repository.save_note(note)
                        completed += 1
                return completed
            return 0
        except Exception as e:
            await self._repository.fail_job(job_id, str(e))
            return 0

    @staticmethod
    def _extract_note_from_detail(item: dict) -> dict | None:
        """从详情页数据提取 Spider_Douyin 格式。"""
        if not item:
            return None

        author = item.get("author", {})
        statistics = item.get("statistics", {})

        # 处理 JSON 字段
        def to_json(val):
            if val is None:
                return None
            if isinstance(val, (dict, list)):
                import json
                return json.dumps(val, ensure_ascii=False)
            return val

        return {
            "note_id": item.get("id") or item.get("group_id"),
            "note_url": item.get("share_url"),
            "note_type": item.get("type", "video"),
            "user_id": author.get("sec_uid") or author.get("uid"),
            "home_url": author.get("custom_verify") or author.get("short_id"),
            "nickname": author.get("nickname"),
            "avatar": (author.get("avatar_larger", {}) or {}).get("url_list", [""])[0]
            if isinstance(author.get("avatar_larger"), dict)
            else "",
            "title": (item.get("desc", "") or "").split("\n")[0][:512],
            "desc": item.get("desc", ""),
            "liked_count": statistics.get("digg_count", 0),
            "collected_count": statistics.get("collect_count", 0),
            "comment_count": statistics.get("comment_count", 0),
            "share_count": statistics.get("share_count", 0),
            "video_cover": (
                (item.get("static_cover", {}) or {}).get("url_list", [""])
            )[0] if isinstance(item.get("static_cover"), dict) else "",
            "video_addr": (
                (item.get("downloads", {}) or {}).get("url_list", [""])
            )[-1] if isinstance(item.get("downloads"), dict) else "",
            "image_list": to_json(
                item.get("images") or item.get("slide_info", [])
            ),
            "tags": to_json(
                [t.get("hashtag_name") for t in item.get("text_extra", [])]
            ),
            "raw_data": to_json(item),
            "upload_time": datetime.fromtimestamp(
                item.get("create_time", 0)
            ).strftime("%Y-%m-%d %H:%M:%S")
            if item.get("create_time")
            else "",
            "ip_location": "",
        }

    @staticmethod
    def _extract_note_from_search(item: dict) -> dict | None:
        """从搜索结果提取 Spider_Douyin 格式（复用 detail 提取逻辑）。"""
        return CrawlWorker._extract_note_from_detail(item)

"""MySQL 数据访问层 — 为 Spider_XHS 兼容 API 提供异步 CRUD 操作。"""

from datetime import datetime, timedelta
from typing import Any, Optional

__all__ = ["SpiderDouyinRepository"]


class SpiderDouyinRepository:
    """抖音数据 MySQL 仓库（异步）"""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 3306,
        user: str = "root",
        password: str = "",
        database: str = "spider_douyin",
    ):
        self._pool: Any | None = None
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database

    async def initialize(self) -> None:
        import aiomysql

        self._pool = await aiomysql.create_pool(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            database=self._database,
            autocommit=False,
            charset="utf8mb4",
        )

    async def close(self) -> None:
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()

    # ------------------------------------------------------------------
    # 作品查询
    # ------------------------------------------------------------------

    async def list_notes(
        self,
        keyword: str | None = None,
        sort_by: str = "latest",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """分页查询作品列表。

        Returns
        -------
        tuple[list[dict], int]
            (作品列表, 总数)
        """
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                where_clauses = ["1=1"]
                params: list[Any] = []

                if keyword:
                    where_clauses.append(
                        "(`desc` LIKE %s OR `title` LIKE %s OR `nickname` LIKE %s)"
                    )
                    kw = f"%{keyword}%"
                    params.extend([kw, kw, kw])

                count_sql = "SELECT COUNT(*) FROM `spider_douyin_note` WHERE " + " AND ".join(
                    where_clauses
                )
                await cursor.execute(count_sql, params)
                total = (await cursor.fetchone())[0]

                order_map = {
                    "latest": "upload_time DESC",
                    "likes": "liked_count DESC",
                    "comments": "comment_count DESC",
                    "shares": "share_count DESC",
                }
                order = order_map.get(sort_by, "upload_time DESC")

                offset = max(0, (page - 1) * page_size)
                query_sql = (
                    f"SELECT * FROM `spider_douyin_note` "
                    f"WHERE {' AND '.join(where_clauses)} "
                    f"ORDER BY {order} LIMIT %s OFFSET %s"
                )
                params.extend([page_size, offset])

                await cursor.execute(query_sql, params)
                columns = [desc[0] for desc in cursor.description]
                rows = [dict(zip(columns, row)) for row in await cursor.fetchall()]

                # 将 JSON 字段保持为 dict 类型
                json_fields = {"image_list", "tags", "raw_data"}
                for row in rows:
                    for field in json_fields:
                        val = row.get(field)
                        if isinstance(val, str):
                            import json
                            row[field] = json.loads(val)

                return rows, total
            finally:
                await cursor.close()

    async def get_note(self, note_id: str) -> dict[str, Any] | None:
        """根据 note_id 获取单个作品。"""
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                await cursor.execute(
                    "SELECT * FROM `spider_douyin_note` WHERE `note_id` = %s",
                    (note_id,),
                )
                row = await cursor.fetchone()
                if not row:
                    return None
                columns = [desc[0] for desc in cursor.description]
                result = dict(zip(columns, row))
                # JSON 字段反序列化
                json_fields = {"image_list", "tags", "raw_data"}
                for field in json_fields:
                    val = result.get(field)
                    if isinstance(val, str):
                        import json
                        result[field] = json.loads(val)
                return result
            finally:
                await cursor.close()

    async def batch_notes(self, note_ids: list[str]) -> list[dict[str, Any]]:
        """批量获取多个作品。"""
        if not note_ids:
            return []
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                placeholders = ", ".join(["%s"] * len(note_ids))
                await cursor.execute(
                    f"SELECT * FROM `spider_douyin_note` WHERE `note_id` IN ({placeholders})",
                    note_ids,
                )
                columns = [desc[0] for desc in cursor.description]
                rows = [dict(zip(columns, row)) for row in await cursor.fetchall()]
                json_fields = {"image_list", "tags", "raw_data"}
                for row in rows:
                    for field in json_fields:
                        val = row.get(field)
                        if isinstance(val, str):
                            import json
                            row[field] = json.loads(val)
                return rows
            finally:
                await cursor.close()

    async def save_note(self, note: dict[str, Any]) -> bool:
        """保存或更新单个作品（upsert）。"""
        note_id = note.get("note_id")
        if not note_id:
            return False
        fields = [
            "note_id", "note_url", "note_type", "user_id", "home_url",
            "nickname", "avatar", "title", "desc",
            "liked_count", "collected_count", "comment_count", "share_count",
            "video_cover", "video_addr", "image_list", "tags",
            "raw_data", "upload_time", "ip_location", "last_update_time",
        ]
        columns = ", ".join(f"`{f}`" for f in fields)
        placeholders = ", ".join(f"%s" for _ in fields)
        updates = ", ".join(f"`{f}`=VALUES(`{f}`)" for f in fields)
        sql = (
            f"INSERT INTO `spider_douyin_note` ({columns}) "
            f"VALUES ({placeholders}) "
            f"ON DUPLICATE KEY UPDATE {updates}"
        )
        values = [note.get(f) for f in fields]
        # JSON 序列化
        import json
        json_fields = {"image_list", "tags", "raw_data"}
        for f in json_fields:
            val = values[fields.index(f)]
            if val is not None and not isinstance(val, str):
                values[fields.index(f)] = json.dumps(val, ensure_ascii=False)

        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                await cursor.execute(sql, values)
                await conn.commit()
                return True
            except Exception:
                await conn.rollback()
                raise
            finally:
                await cursor.close()

    # ------------------------------------------------------------------
    # 快照查询
    # ------------------------------------------------------------------

    async def snapshots_by_task(
        self, crawl_task_id: str, page: int = 1, page_size: int = 50
    ) -> tuple[list[dict[str, Any]], int]:
        """按任务ID获取快照。"""
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                await cursor.execute(
                    "SELECT COUNT(*) FROM `spider_douyin_note_snapshot` WHERE `crawl_task_id` = %s",
                    (crawl_task_id,),
                )
                total = (await cursor.fetchone())[0]

                offset = max(0, (page - 1) * page_size)
                await cursor.execute(
                    "SELECT * FROM `spider_douyin_note_snapshot` "
                    "WHERE `crawl_task_id` = %s ORDER BY crawl_time DESC LIMIT %s OFFSET %s",
                    (crawl_task_id, page_size, offset),
                )
                columns = [desc[0] for desc in cursor.description]
                rows = [dict(zip(columns, row)) for row in await cursor.fetchall()]
                return rows, total
            finally:
                await cursor.close()

    async def aggregate_snapshots(self, crawl_task_id: str) -> dict[str, Any] | None:
        """聚合统计快照。"""
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                await cursor.execute(
                    """SELECT
                        COUNT(*) as total,
                        SUM(detail_crawl_succeeded) as succeeded,
                        SUM(liked_count) as total_likes,
                        SUM(comment_count) as total_comments,
                        SUM(share_count) as total_shares,
                        SUM(collected_count) as total_collected,
                        MIN(crawl_time) as first_crawl,
                        MAX(crawl_time) as last_crawl
                    FROM `spider_douyin_note_snapshot`
                    WHERE `crawl_task_id` = %s""",
                    (crawl_task_id,),
                )
                row = await cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return None
            finally:
                await cursor.close()

    async def overview(self) -> dict[str, Any]:
        """全局概览统计。"""
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                today = datetime.now().strftime("%Y-%m-%d")
                await cursor.execute(
                    "SELECT COUNT(*) FROM `spider_douyin_note`"
                )
                total_notes = (await cursor.fetchone())[0]

                await cursor.execute(
                    "SELECT COUNT(*) FROM `spider_douyin_note` "
                    "WHERE DATE(created_at) = %s", (today,)
                )
                today_new = (await cursor.fetchone())[0]

                await cursor.execute(
                    "SELECT COUNT(*) FROM `spider_douyin_note` "
                    "WHERE DATE(updated_at) = %s AND updated_at IS NOT NULL", (today,)
                )
                today_updated = (await cursor.fetchone())[0]

                return {
                    "total_notes": total_notes,
                    "today_new": today_new,
                    "today_updated": today_updated,
                }
            finally:
                await cursor.close()

    async def daily_count(self, days: int = 30) -> list[dict[str, Any]]:
        """最近 N 天每日新作品数。"""
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                await cursor.execute(
                    """SELECT DATE(created_at) as day, COUNT(*) as count
                       FROM `spider_douyin_note`
                       WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                       GROUP BY DATE(created_at)
                       ORDER BY day"""
                    , (days,)
                )
                return [{"day": str(row[0]), "count": row[1]} for row in await cursor.fetchall()]
            finally:
                await cursor.close()

    # ------------------------------------------------------------------
    # 异步任务管理
    # ------------------------------------------------------------------

    async def create_job(
        self, job_id: str, job_type: str, parameters: dict[str, Any] | None = None
    ) -> str:
        """创建一个新的爬取任务。"""
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                import json
                await cursor.execute(
                    "INSERT INTO `spider_douyin_crawl_job` "
                    "(job_id, job_type, parameters, status) VALUES (%s, %s, %s, 'pending')",
                    (
                        job_id,
                        job_type,
                        json.dumps(parameters, ensure_ascii=False) if parameters else None,
                    ),
                )
                await conn.commit()
                return job_id
            finally:
                await cursor.close()

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """获取任务状态。"""
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                await cursor.execute(
                    "SELECT * FROM `spider_douyin_crawl_job` WHERE `job_id` = %s",
                    (job_id,),
                )
                row = await cursor.fetchone()
                if not row:
                    return None
                columns = [desc[0] for desc in cursor.description]
                result = dict(zip(columns, row))
                # parameters 是 JSON 字段，反序列化
                if isinstance(result.get("parameters"), str):
                    import json
                    result["parameters"] = json.loads(result["parameters"])
                return result
            finally:
                await cursor.close()

    async def update_job_status(
        self, job_id: str, status: str, error_message: str | None = None
    ) -> bool:
        """更新任务状态。"""
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                import json
                set_clauses = ["`status` = %s"]
                params: list[Any] = [status]

                if error_message is not None:
                    set_clauses.append("`error_message` = %s")
                    params.append(error_message)

                if status == "running" and "`started_at`" not in str(
                    await self.get_job(job_id)
                ):
                    # 需要设置 started_at，但已经在 update 里处理
                    pass

                set_sql = ", ".join(set_clauses)
                params.append(job_id)
                await cursor.execute(
                    f"UPDATE `spider_douyin_crawl_job` SET {set_sql} WHERE `job_id` = %s",
                    params,
                )
                await conn.commit()
                return True
            except Exception:
                await conn.rollback()
                raise
            finally:
                await cursor.close()

    async def update_job_progress(
        self, job_id: str, completed_notes: int
    ) -> bool:
        """更新任务完成进度。"""
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                await cursor.execute(
                    "UPDATE `spider_douyin_crawl_job` "
                    "SET `completed_notes` = %s, `status` = 'running' "
                    "WHERE `job_id` = %s AND `status` = 'running'",
                    (completed_notes, job_id),
                )
                await conn.commit()
                return True
            finally:
                await cursor.close()

    async def complete_job(
        self, job_id: str, total_notes: int, completed_notes: int
    ) -> bool:
        """标记任务完成。"""
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                await cursor.execute(
                    "UPDATE `spider_douyin_crawl_job` "
                    "SET `status` = 'completed', `total_notes` = %s, "
                    "`completed_notes` = %s, `completed_at` = NOW() "
                    "WHERE `job_id` = %s",
                    (total_notes, completed_notes, job_id),
                )
                await conn.commit()
                return True
            finally:
                await cursor.close()

    async def fail_job(
        self, job_id: str, error_message: str, completed_notes: int = 0
    ) -> bool:
        """标记任务失败。"""
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                await cursor.execute(
                    "UPDATE `spider_douyin_crawl_job` "
                    "SET `status` = 'failed', `error_message` = %s, "
                    "`completed_notes` = %s, `completed_at` = NOW() "
                    "WHERE `job_id` = %s",
                    (error_message, completed_notes, job_id),
                )
                await conn.commit()
                return True
            finally:
                await cursor.close()

    async def get_pending_jobs(self, limit: int = 10) -> list[dict[str, Any]]:
        """获取待执行的任务（供后台 Worker 使用）。"""
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                await cursor.execute(
                    "SELECT * FROM `spider_douyin_crawl_job` "
                    "WHERE `status` = 'pending' "
                    "ORDER BY `created_at` ASC LIMIT %s",
                    (limit,),
                )
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in await cursor.fetchall()]
            finally:
                await cursor.close()

    # ------------------------------------------------------------------
    # 客户端管理
    # ------------------------------------------------------------------

    async def register_client(
        self, client_id: str, client_key: str, permissions: list[str] | None = None
    ) -> dict[str, Any]:
        """注册 API 客户端。"""
        import json
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                await cursor.execute(
                    "INSERT INTO `spider_douyin_client` "
                    "(client_id, client_key, permissions) VALUES (%s, %s, %s)",
                    (
                        client_id,
                        client_key,
                        json.dumps(permissions, ensure_ascii=False)
                        if permissions
                        else None,
                    ),
                )
                await conn.commit()
                return {"client_id": client_id, "client_key": client_key}
            finally:
                await cursor.close()

    async def validate_client(self, client_id: str, client_key: str) -> bool:
        """验证客户端密钥。"""
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                await cursor.execute(
                    "SELECT `is_active` FROM `spider_douyin_client` "
                    "WHERE `client_id` = %s AND `client_key` = %s",
                    (client_id, client_key),
                )
                row = await cursor.fetchone()
                return row is not None and row[0] == 1
            finally:
                await cursor.close()

    async def get_client(self, client_id: str) -> dict[str, Any] | None:
        """获取客户端信息。"""
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor()
            try:
                await cursor.execute(
                    "SELECT * FROM `spider_douyin_client` WHERE `client_id` = %s",
                    (client_id,),
                )
                row = await cursor.fetchone()
                if not row:
                    return None
                columns = [desc[0] for desc in cursor.description]
                result = dict(zip(columns, row))
                if isinstance(result.get("permissions"), str):
                    import json
                    result["permissions"] = json.loads(result["permissions"])
                return result
            finally:
                await cursor.close()

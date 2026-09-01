# TikTokDownloader dev 分支相对于 master 分支的功能差异

本文档记录 TikTokDownloader 的 `dev` 分支相对于 `master` 分支新增的功能。

## 1. 数据库存储

**master**: 数据仅下载到本地文件目录，无持久化存储。

**dev**: 新增 MySQL 存储支持，包含以下能力：

- 完整的数据库 Schema（`sql/init_mysql.sql`），包含 4 张表：
  - `spider_douyin_note` — 作品数据
  - `spider_douyin_note_snapshot` — 数值快照
  - `spider_douyin_crawl_job` — 异步任务
  - `spider_douyin_client` — API 客户端
- 通过 `DATABASE_URL` 环境变量配置数据库连接（连接字符串格式：`mysql+aiomysql://user:pass@host:port/db`）
- `src/storage/mysql.py` — MySQL 存储层
- `src/storage/spider_repository.py` — 数据访问层

## 2. FastAPI Server 模式

**master**: 仅提供交互式 CLI 启动（`python main.py`）。

**dev**: 新增 Server 模式，支持远程 API 调用：

- `server.py` — uvicorn 启动入口
- `src/application/main_server.py` — FastAPI 路由定义
- 支持 `python main.py server` 或 `uvicorn server:app --host 0.0.0.0 --port 5555` 启动
- 自动生成 API 文档：`http://127.0.0.1:5555/docs`

## 3. 功能 API 端点

**master**: 无 API 端点。

**dev** 新增以下端点：

| 端点 | 说明 |
|------|------|
| `POST /internal/v1/clients/register` | 注册 API 客户端 |
| `POST /internal/v1/crawl-jobs` | 提交爬取任务（search/account/mix/detail） |
| `GET /internal/v1/crawl-jobs/{job_id}` | 查询任务状态 |
| `GET /internal/v1/crawl-jobs/{job_id}/results` | 查询任务结果 |
| `GET /internal/v1/notes` | 作品列表查询 |
| `GET /internal/v1/notes/{note_id}` | 单条作品查询 |
| `POST /internal/v1/notes/by-id` | 批量查询 |
| `POST /internal/v1/notes/save` | 保存作品数据 |
| `GET /internal/v1/snapshots/aggregate` | 聚合统计 |
| `GET /internal/v1/snapshots/by-task` | 按任务查询快照 |
| `GET /internal/v1/metrics/overview` | 概览统计 |
| `GET /internal/v1/metrics/daily-count` | 每日统计 |
| `GET /internal/v1/douyin/cookie-validation` | Cookie 校验 |

## 4. 异步爬取 Worker

**master**: 同步执行爬取操作。

**dev**: 内置后台爬取 Worker（`src/application/crawl_worker.py`），从 MySQL 的 `spider_douyin_crawl_job` 表中轮取 pending 任务并执行，支持 `search`、`account`、`detail`、`mix` 四种任务类型。

## 5. Spider_XHS 兼容 API

**master**: 无此功能。

**dev**: `src/application/spider_api.py` 提供与 Spider_XHS 兼容的 API 端点，使现有 Spider_XHS 客户端无需修改即可调用 TikTokDownloader。

## 6. 配置系统

**master**: 仅使用 `settings.json` 配置文件。

**dev**: 增强配置系统：

- 支持 `.env` 文件覆盖数据库配置（`DATABASE_URL` 连接字符串）
- `src/config/settings.py` 中 `_merge_env()` 方法解析连接字符串并优先于 `settings.json`
- `python-dotenv` 依赖，`.env` 文件不提交到 git

## 7. 部署基础设施

**master**: 无部署脚本。

**dev**: 完整的部署工具链（`deploy/` 目录）：

- `spider-tiktok-api.winzyy.com.conf` — Nginx 配置（含 SSL 终止）
- `startup.sh` — 启动 Server + 发布 Nginx 配置
- `stop.sh` — 停止 Server
- `restart.sh` — 重启
- `deploy.sh` — 本地到远程服务器部署（tar → scp → 解压）

## 8. 依赖变更

**master**: 原始依赖列表。

**dev** 新增：

- `python-dotenv==1.0.1` — `.env` 文件解析
- `fastapi` / `uvicorn` — Server 模式
- `aiomysql` — 异步 MySQL 连接

## 关键文件对照

| 文件 | master | dev |
|------|--------|-----|
| 启动方式 | `python main.py` | `python main.py` + `python main.py server` |
| 配置 | `settings.json` | `settings.json` + `.env` |
| 数据存储 | 本地文件 | MySQL 数据库 |
| API 端点 | 无 | 20+ 个 REST API |
| 部署脚本 | 无 | Nginx + systemd 脚本 |

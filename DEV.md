# TikTokDownloader 本地开发启动指南

## 环境准备

```bash
# 1. 克隆项目（如已在 repo 内则跳过）
git clone <repository-url>
cd TikTokDownloader

# 2. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
```

## 配置

### 1. 复制环境变量模板

```bash
cp .env.example .env
```

编辑 `.env` 填入实际的 MySQL 连接信息：

```ini
# MySQL 连接配置
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=spider_douyin
```

### 2. 初始化数据库

```bash
mysql -u root -p < sql/init_mysql.sql
```

这将创建 `spider_douyin` 数据库及 4 张表：
- `spider_douyin_note` — 作品数据
- `spider_douyin_note_snapshot` — 数值快照
- `spider_douyin_crawl_job` — 异步任务
- `spider_douyin_client` — API 客户端

### 3. 修改 settings.json（可选）

`settings.json` 用于配置抖音 Cookie、代理、下载路径等。
MySQL 相关配置优先从 `.env` 读取，未在 `.env` 中设置的参数回退到 `settings.json`。

## 启动方式

### 方式一：交互式 CLI（默认）

```bash
python main.py
```

在菜单中选择功能进行爬取、下载等操作。

### 方式二：Server 模式（推荐用于开发/部署）

```bash
python main.py server
```

或直接使用 uvicorn 启动：

```bash
uvicorn server:app --host 0.0.0.0 --port 5555 --env-file .env
```

启动后访问：
- API 文档：`http://127.0.0.1:5555/docs`
- ReDoc 文档：`http://127.0.0.1:5555/redoc`

### 方式三：后台部署（生产环境）

```bash
cd deploy
./startup.sh   # 启动 Server + 发布 Nginx 配置
./stop.sh      # 停止 Server
./restart.sh   # 重启
```

本地到远程部署：

```bash
bash deploy/deploy.sh
```

默认推送到 `root@47.117.143.70:/opt/TikTokDownloader`，可通过环境变量覆盖：

```bash
REMOTE_HOST=user@other-server REMOTE_DIR=/opt/app bash deploy/deploy.sh
```

## API 使用

### 注册客户端

```bash
curl -X POST 'http://127.0.0.1:5555/internal/v1/clients/register' \
  -H 'Content-Type: application/json' \
  -d '{"client_id": "my-client", "permissions": ["read", "write"]}'
```

### 提交爬取任务

```bash
curl -X POST 'http://127.0.0.1:5555/internal/v1/crawl-jobs' \
  -H 'Content-Type: application/json' \
  -d '{
    "job_type": "search",
    "parameters": {
      "keyword": "宠物",
      "pages": 3,
      "sort_type": "latest"
    }
  }'
```

### 查询作品

```bash
# 分页列表
curl 'http://127.0.0.1:5555/internal/v1/notes?keyword=宠物&page=1&pagesize=20'

# 单条作品
curl 'http://127.0.0.1:5555/internal/v1/notes/<note_id>'
```

### 查看聚合统计

```bash
curl 'http://127.0.0.1:5555/internal/v1/snapshots/aggregate'
```

## 文件结构

```
TikTokDownloader/
├── .env.example              # 环境变量模板（提交到 git）
├── .env                      # 本地环境配置（不提交到 git）
├── main.py                   # CLI 入口
├── server.py                 # uvicorn 启动入口
├── settings.json             # 应用配置（Cookie、代理等）
├── sql/
│   └── init_mysql.sql        # 数据库 Schema
├── deploy/
│   ├── spider-tiktok-api.winzyy.com.conf  # Nginx 配置
│   ├── startup.sh            # 启动 Server + Nginx
│   ├── stop.sh               # 停止 Server
│   ├── restart.sh            # 重启
│   └── deploy.sh             # 本地到远程部署
└── src/
    ├── config/
    │   └── settings.py       # 配置加载（含 .env 合并）
    ├── storage/
    │   ├── mysql.py          # MySQL 存储层
    │   └── spider_repository.py  # 数据访问层
    └── application/
        ├── main_server.py    # FastAPI 路由
        ├── spider_api.py     # Spider_XHS 兼容 API
        └── crawl_worker.py   # 异步爬取 Worker
```

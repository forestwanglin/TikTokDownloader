#!/usr/bin/env bash
# TikTokDownloader 本地发布脚本。使用方式：bash deploy/deploy.sh
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-root@47.117.143.70}"
REMOTE_DIR="${REMOTE_DIR:-/opt/TikTokDownloader}"
LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARBALL="$(mktemp -t tiktokdownloader-deploy.XXXXXX.tar.gz)"

cleanup() {
    rm -f "${TARBALL}"
}
trap cleanup EXIT

echo "=== TikTokDownloader 代码同步 ==="
echo "本地目录: ${LOCAL_DIR}"
echo "远程主机: ${REMOTE_HOST}"
echo "远程目录: ${REMOTE_DIR}"

ssh "${REMOTE_HOST}" "mkdir -p '${REMOTE_DIR}'"

echo "--- 打包本地代码 ---"
cd "${LOCAL_DIR}"
COPYFILE_DISABLE=1 COPY_EXTENDED_ATTRIBUTES_DISABLE=1 tar --format=ustar -czf "${TARBALL}" \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='venv' \
    --exclude='env' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.env' \
    --exclude='.runtime' \
    --exclude='logs' \
    --exclude='datas' \
    --exclude='data' \
    --exclude='docs' \
    --exclude='tests' \
    .

echo "--- 传输到远程服务器 ---"
scp "${TARBALL}" "${REMOTE_HOST}:/tmp/tiktokdownloader-deploy.tar.gz"
ssh "${REMOTE_HOST}" "tar xzf /tmp/tiktokdownloader-deploy.tar.gz -C '${REMOTE_DIR}' && rm -f /tmp/tiktokdownloader-deploy.tar.gz && rm -f '${REMOTE_DIR}/startup.sh' '${REMOTE_DIR}/stop.sh' '${REMOTE_DIR}/restart.sh' && chmod +x '${REMOTE_DIR}'/deploy/*.sh"

echo
echo "=== 代码同步完成 ==="
echo "请到远程服务器执行："
echo "  cd ${REMOTE_DIR}/deploy"
echo "  ./startup.sh   # 启动 Server、发布 Nginx 配置"
echo "  ./stop.sh      # 停止 TikTokDownloader Server"

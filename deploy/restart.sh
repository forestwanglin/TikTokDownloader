#!/usr/bin/env bash
# TikTokDownloader Server 与公网反向代理重启脚本。使用方式：./restart.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${APP_DIR}/deploy/startup.sh"

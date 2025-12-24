#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

npm install

# 生产建议同域 /api（由 Nginx 反代到后端）
export VITE_API_BASE="${VITE_API_BASE:-/api}"

npm run build

echo "Build done: ./dist"



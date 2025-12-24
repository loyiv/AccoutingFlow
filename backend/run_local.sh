#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate

python -m pip install -U pip
pip install -r requirements.txt

if [ -z "${DATABASE_URL:-}" ]; then
  echo "请先设置 DATABASE_URL，例如："
  echo "export DATABASE_URL='mysql+pymysql://accountingflow:accountingflow@127.0.0.1:3306/accountingflow?charset=utf8mb4'"
  exit 1
fi

echo "[backend] migrate..."
alembic upgrade head

echo "[backend] seed..."
python -m app.scripts.init_db

echo "[backend] start (dev) ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers



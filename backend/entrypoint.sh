#!/usr/bin/env sh
set -e

echo "[backend] Running migrations..."
alembic upgrade head

echo "[backend] Seeding default data (idempotent)..."
python -m app.scripts.init_db

echo "[backend] Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers



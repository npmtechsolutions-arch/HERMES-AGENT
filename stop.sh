#!/usr/bin/env bash
# Stop HERMUS services (backend, frontend, isolated Postgres).
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PATH="/usr/local/opt/postgresql@15/bin:$PATH"
echo "Stopping FastAPI…";  pkill -f "uvicorn app.main:app" 2>/dev/null || true
echo "Stopping Vite…";     pkill -f "vite" 2>/dev/null || true
echo "Stopping Postgres…"; pg_ctl -D "$ROOT/backend/.pgdata" stop 2>/dev/null || true
echo "Done."

#!/usr/bin/env bash
# HERMUS — one-command launcher (isolated Postgres + FastAPI + Vite).
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
PGBIN="/usr/local/opt/postgresql@15/bin"
PGDATA="$ROOT/backend/.pgdata"
PGPORT=5544
export PATH="$PGBIN:$PATH"

echo "▶ 1/4  Starting isolated PostgreSQL (port $PGPORT)…"
if [ ! -f "$PGDATA/PG_VERSION" ]; then
  initdb -D "$PGDATA" -U hermus --auth=trust --encoding=UTF8 >/dev/null
fi
if ! pg_isready -h 127.0.0.1 -p $PGPORT >/dev/null 2>&1; then
  pg_ctl -D "$PGDATA" -o "-p $PGPORT -k $PGDATA -c listen_addresses='127.0.0.1'" \
    -l "$PGDATA/server.log" start
  sleep 2
fi
createdb -h 127.0.0.1 -p $PGPORT -U hermus hermus 2>/dev/null || true

echo "▶ 0/4  Checking local LLM (Ollama)…"
if curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "      Ollama online — CEO Agent, embeddings & drafts will use it."
else
  echo "      Ollama not detected — HERMUS will use deterministic fallbacks."
  echo "      (optional: 'ollama pull llama3.2:3b && ollama pull nomic-embed-text')"
fi

echo "▶ 2/4  Preparing backend (venv + deps)…"
cd "$ROOT/backend"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
python -m app.seed

echo "▶ 3/4  Starting FastAPI on http://127.0.0.1:7700 …"
(uvicorn app.main:app --host 127.0.0.1 --port 7700 >/tmp/hermus_api.log 2>&1 &)

echo "▶ 4/4  Starting React (Vite) on http://localhost:5173 …"
cd "$ROOT/frontend"
[ -d node_modules ] || npm install
echo ""
echo "──────────────────────────────────────────────"
echo "  HERMUS is up:  http://localhost:5173"
echo "  Account Owner: user@gmail.com  / user"
echo "  Product Admin: admin@gmail.com / admin"
echo "  API docs:      http://127.0.0.1:7700/docs"
echo "──────────────────────────────────────────────"
npm run dev

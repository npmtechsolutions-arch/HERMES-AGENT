#!/usr/bin/env bash
# Launch the HERMUS desktop (Electron) app in development.
# It will bring up the local PostgreSQL + FastAPI core service itself, and load
# the built React UI. Build the UI first so the app has something to serve.
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "▶ Building the UI…"
cd "$ROOT/frontend" && [ -d node_modules ] || npm install
npm run build >/dev/null

echo "▶ Ensuring backend deps…"
cd "$ROOT/backend" && [ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate && pip install -q -r requirements.txt

echo "▶ Installing desktop deps…"
cd "$ROOT/desktop" && [ -d node_modules ] || npm install

echo "▶ Launching HERMUS desktop…"
# ELECTRON_RUN_AS_NODE must be unset for the GUI to start.
unset ELECTRON_RUN_AS_NODE
# Dev mode loads the Vite dev server; start it if not already running.
if ! curl -s -o /dev/null http://localhost:5173/ 2>/dev/null; then
  ( cd "$ROOT/frontend" && npm run dev >/tmp/hermus_vite.log 2>&1 & )
  sleep 3
fi
HERMUS_DEV=1 npm start

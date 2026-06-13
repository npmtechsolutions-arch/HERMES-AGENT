# HERMUS Desktop (Electron)

The native desktop app — HERMUS's **local execution plane**. The user installs and runs
*everything* here: installing the local AI runtime, creating agents, building pipelines,
running their AI crew — all on their own machine with local LLMs. Activity lives in the
local core service and is reflected in the user's web dashboard (same account).

## What it does

- **Boots the local stack on launch** — starts an isolated PostgreSQL and the FastAPI
  **Core Service** (`backend/`) as child processes, waits for health, seeds first‑run data.
- **Setup / dependency wizard** (first run) — checks your hardware, detects **Ollama**
  (the local AI runtime), helps you **download the required models** with live progress,
  and verifies the core service. No cloud, no API keys.
- **Loads the React UI** and attaches a secure preload bridge (`window.hermus`) so the UI
  can query system info, Ollama status, pull models, and fire native notifications.
- **Native desktop features:** app menu, system tray, **global push‑to‑talk**
  (`Cmd/Ctrl + Shift + Space`) to talk to HERMUS from anywhere, native **approval
  notifications**, frameless macOS title bar.
- **Voice + text input** — the Voice Orb (Web Speech API where available) plus a text box;
  the hotkey/tray open voice instantly.

## Run it (development)

```bash
# from the repo root — builds the UI + backend deps, then launches the app
./run-desktop.sh
```

or manually:

```bash
cd desktop && npm install
unset ELECTRON_RUN_AS_NODE        # required: the GUI won't start otherwise
HERMUS_DEV=1 npm start            # dev: loads the Vite dev server at :5173
```

> **Note:** if `ELECTRON_RUN_AS_NODE=1` is set in your shell, Electron runs as plain Node
> and won't open a window — `unset` it first.

## Package installers

```bash
cd frontend && npm run build      # produce the static UI
cd ../desktop && npm run dist     # electron-builder → dmg / nsis / AppImage
```

`electron-builder` (configured in `package.json`) bundles the built UI and the backend
into the app resources. **Production packaging still needs a self‑contained Python**
for the core service (e.g. PyInstaller the FastAPI app, or ship an embedded interpreter)
and a bundled PostgreSQL (or switch the local core to embedded SQLite). In dev the app
uses the repo's `backend/.venv` and the Homebrew PostgreSQL, which is enough to run and
demo the full desktop experience today.

## Architecture (this app vs. the cloud)

```
  Electron window (React UI)
        │  http://127.0.0.1:7700  (loopback)
        ▼
  Local Core Service (FastAPI)  ──►  local PostgreSQL + Ollama (local LLMs)
        │
        └─ (account identity / heartbeat)  ──►  Cloud (web dashboard, same account)
```

The desktop and the web dashboard share the user's account, so what you do in the desktop
app shows up in the web **User Dashboard**. Business data (agents, tasks, memory) stays
local; only identity/usage crosses to the cloud (privacy invariant SRS‑INV‑1).

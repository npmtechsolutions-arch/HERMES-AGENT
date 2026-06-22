"""
HERMUS — AI Office Assistant.
Unified FastAPI service exposing the Cloud control-plane API and the Local
Core-Service API for this runnable demo. React frontend talks to this service.
"""
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS
from .database import Base, engine
from .events import hub
from .routers import (admin, agents_advanced, agents_profile, agentsphere, ask, assistant, auth, billing, brain, chatbots,
                      comms, company, compliance, connections, dictate, dual, editions, feature_schedules,
                      journey, leads, mvp, onboarding, org, pipelines, platform, pricing, recipes, remote, setup, skills,
                      solutions, tasks, universal, verticals, voice, workflows)
from .security import decode_token

app = FastAPI(title="HERMUS — AI Office Assistant API", version="1.0.0",
              description="Voice-first AI Workforce platform — Cloud + Local Core API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    # Allow local dev (http://localhost:port) and any hosted frontend on
    # *.onrender.com. Add a custom domain via the HERMUS_CORS env var.
    allow_origin_regex=r"^(http://(localhost|127\.0\.0\.1):\d+|https://[a-z0-9-]+\.onrender\.com)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API = "/api/v1"
app.include_router(auth.router, prefix=API)
app.include_router(company.router, prefix=API)
app.include_router(chatbots.router, prefix=API)
app.include_router(skills.router, prefix=API)
app.include_router(remote.router, prefix=API)
app.include_router(platform.router, prefix=API)
app.include_router(compliance.router, prefix=API)
app.include_router(leads.router, prefix=API)
app.include_router(mvp.router, prefix=API)
app.include_router(universal.router, prefix=API)
app.include_router(recipes.router, prefix=API)
app.include_router(dual.router, prefix=API)
app.include_router(solutions.router, prefix=API)
app.include_router(verticals.router, prefix=API)
app.include_router(ask.router, prefix=API)
app.include_router(agentsphere.router, prefix=API)
app.include_router(pipelines.router, prefix=API)
app.include_router(org.router, prefix=API)
app.include_router(tasks.router, prefix=API)
app.include_router(workflows.router, prefix=API)
app.include_router(brain.router, prefix=API)
app.include_router(comms.router, prefix=API)
app.include_router(voice.router, prefix=API)
app.include_router(voice.system_router, prefix=API)
app.include_router(setup.router, prefix=API)
app.include_router(billing.router, prefix=API)
app.include_router(billing.analytics, prefix=API)
app.include_router(admin.router, prefix=API)
app.include_router(editions.router, prefix=API)
app.include_router(editions.admin, prefix=API)
app.include_router(dictate.router, prefix=API)
app.include_router(connections.router, prefix=API)
app.include_router(assistant.router, prefix=API)
app.include_router(onboarding.router, prefix=API)
app.include_router(agents_profile.router, prefix=API)
app.include_router(agents_advanced.router, prefix=API)
app.include_router(journey.router, prefix=API)
app.include_router(feature_schedules.router, prefix=API)
app.include_router(pricing.router, prefix=API)
app.include_router(pricing.admin, prefix=API)


def _migrate():
    """Idempotent lightweight migrations for columns added to EXISTING tables
    (create_all only creates new tables, never alters existing ones). Safe to run
    on every boot — Postgres' ADD COLUMN IF NOT EXISTS is a no-op when present."""
    from sqlalchemy import text
    stmts = [
        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS active_edition_id VARCHAR",
        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS plan_tier VARCHAR DEFAULT 'personal'",
        # Doc 29 §5.1(b) — feature-schedule columns on the existing schedules table.
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS feature_key VARCHAR",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS user_id VARCHAR",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS params JSON",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS instructions TEXT",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS cadence VARCHAR",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS cadence_spec JSON",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'active'",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS label VARCHAR",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS agent VARCHAR",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMPTZ",
        "ALTER TABLE schedules ADD COLUMN IF NOT EXISTS last_status VARCHAR",
    ]
    try:
        with engine.begin() as conn:
            for s in stmts:
                try:
                    conn.execute(text(s))
                except Exception as e:  # one bad statement shouldn't block the rest
                    print(f"[migrate] skip: {e}")
    except Exception as e:
        print(f"[migrate] error: {e}")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    _migrate()
    # Seed demo/login data on first boot of a fresh (e.g. hosted) database so the
    # app is usable immediately. Idempotent; set HERMUS_AUTO_SEED=0 to disable.
    import os
    if os.getenv("HERMUS_AUTO_SEED", "1") != "0":
        try:
            from .seed import seed
            seed()
        except Exception as e:  # never let seeding crash startup
            print(f"[startup] seed skipped: {e}")
    hub.bind_loop()
    # Doc 29 §5.1b executor — fire due feature schedules on a background tick.
    # Disable with HERMUS_SCHEDULER=0 (tests call run_due_schedules directly).
    try:
        from .scheduler_exec import start_scheduler
        start_scheduler()
    except Exception as e:
        print(f"[startup] scheduler not started: {e}")


@app.get("/")
def root():
    return {"service": "HERMUS API", "status": "ok", "docs": "/docs", "health": "/api/v1/health"}


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "hermus", "plane": "cloud+local"}


@app.get("/api/v1/health/plain")
def health_plain():
    return {"status": "ok"}


@app.websocket("/ws/v1/events")
async def events_ws(websocket: WebSocket, token: str = ""):
    """Live event stream (agent.status, task.status_changed, approval.* …)."""
    tenant_id = None
    try:
        claims = decode_token(token)
        tenant_id = claims.get("tenant_id")
    except Exception:
        await websocket.close(code=4401)
        return
    if not tenant_id:
        await websocket.close(code=4400)
        return
    await hub.connect(tenant_id, websocket)
    try:
        await websocket.send_json({"topic": "connected", "payload": {"tenant_id": tenant_id}})
        while True:
            await websocket.receive_text()   # keep-alive / ignore client pings
    except WebSocketDisconnect:
        hub.disconnect(tenant_id, websocket)
    except Exception:
        hub.disconnect(tenant_id, websocket)

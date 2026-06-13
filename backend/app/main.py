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
from .routers import (admin, agentsphere, ask, auth, billing, brain, chatbots,
                      comms, company, compliance, dual, leads, mvp, org,
                      pipelines, platform, recipes, remote, setup, skills, solutions,
                      tasks, universal, verticals, voice, workflows)
from .security import decode_token

app = FastAPI(title="HERMUS — AI Office Assistant API", version="1.0.0",
              description="Voice-first AI Workforce platform — Cloud + Local Core API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
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


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    hub.bind_loop()


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "hermus", "plane": "cloud+local"}


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

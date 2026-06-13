"""In-process WebSocket event hub.

Implements the WebSocket Event Catalog (API Spec §4): agent.status,
task.status_changed, approval.requested/decided, bus.message,
voice.state_changed, comms.message_received, workflow.run_update,
healing.incident, etc. Events are broadcast to all connected clients of a
tenant.
"""
import asyncio
import json
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import WebSocket


class EventHub:
    def __init__(self):
        self._clients: dict[str, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self):
        self._loop = asyncio.get_event_loop()

    async def connect(self, tenant_id: str, ws: WebSocket):
        await ws.accept()
        self._clients[tenant_id].add(ws)

    def disconnect(self, tenant_id: str, ws: WebSocket):
        self._clients[tenant_id].discard(ws)

    async def _broadcast(self, tenant_id: str, message: dict):
        dead = []
        for ws in list(self._clients.get(tenant_id, set())):
            try:
                await ws.send_text(json.dumps(message, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(tenant_id, ws)

    def emit(self, tenant_id: str, topic: str, payload: dict):
        """Thread/sync-safe emit usable from regular request handlers."""
        message = {
            "topic": topic,
            "payload": payload,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._broadcast(tenant_id, message), self._loop
            )


hub = EventHub()

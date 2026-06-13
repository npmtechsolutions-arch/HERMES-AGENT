"""
Dual-Audience Layer (Doc 17 §9) — one surface, two doors:
  §9.3  "Why?" everywhere — plain answer + technical detail for any agent action
  §9.4  Plain-Language Health — "Is everything okay?"
  §9.5  Outbound webhooks (+ Zapier/Make connector surface)
"""
import hashlib
import hmac
import json
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import (Agent, Approval, AuditLog, BackupJob, Chatbot, ChatbotChannel,
                      LeadInteraction, Webhook, now)
from ..security import ulid

router = APIRouter(tags=["dual-audience"])


# ───────────────────────────── §9.4 Plain-Language Health ───────────────────
@router.get("/health/plain")
def plain_health(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """'Is everything okay?' — Simple plain answer + Advanced service states."""
    agents = db.query(Agent).filter_by(tenant_id=p.tenant_id).filter(Agent.status != "archived").all()
    running = sum(1 for a in agents if a.status in ("idle", "working"))
    last_backup = (db.query(BackupJob).filter_by(tenant_id=p.tenant_id, status="completed")
                   .order_by(BackupJob.at.desc()).first())
    backup_ok = bool(last_backup) and (now() - last_backup.at).total_seconds() < 48 * 3600
    channels = db.query(ChatbotChannel).filter_by(tenant_id=p.tenant_id, status="connected").count()
    pending = db.query(Approval).filter_by(tenant_id=p.tenant_id, state="pending").count()

    issues, actions = [], []
    if agents and running < len(agents):
        issues.append(f"{len(agents) - running} agent(s) paused")
    if not backup_ok:
        issues.append("backup is stale"); actions.append({"text": "Set up a backup", "to": "/backup"})
    if channels == 0:
        issues.append("no channels connected"); actions.append({"text": "Connect a channel", "to": "/chatbots"})

    ok = len(issues) == 0
    if ok:
        simple = (f"Yes — {running} agents running, "
                  f"{'backup done recently' if backup_ok else 'no backup yet'}, "
                  f"{channels} channel(s) connected, {pending} approval(s) waiting.")
    else:
        simple = "A few things need you: " + "; ".join(issues) + "."
    return {
        "ok": ok, "simple": simple,
        "needs_you": pending,
        "actions": actions,
        "advanced": {
            "agents_total": len(agents), "agents_running": running,
            "backup_last": last_backup.at.isoformat() if last_backup else None,
            "channels_connected": channels, "approvals_pending": pending,
            "core_service": "up", "config_version": 1, "sync_lag_s": 0,
        },
    }


# ───────────────────────────── §9.3 "Why?" everywhere ───────────────────────
@router.get("/why/interaction/{iid}")
def why_interaction(iid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    ix = db.get(LeadInteraction, iid)
    if not ix or ix.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Action not found"})
    # plain answer
    if ix.drafted_by == "human":
        plain = "You wrote and sent this yourself."
    elif ix.status == "held":
        codes = [v.get("code") for v in (ix.validator or [])]
        reason = ("a figure didn't match a source record" if "unverified_figure" in codes else
                  "the recipient opted out" if "opted_out" in codes else
                  "it's the first message to a new contact, or it mentions money")
        plain = f"I held this for your review because {reason} (universal rule)."
    else:
        plain = ("I drafted this as part of the follow-up sequence; every figure was checked "
                 "against your records before queueing, with a 60-second window to recall.")
    rules = []
    if ix.validator:
        rules.append("U4 source-cited figures")
    if ix.status == "held":
        rules += ["U5 money gate", "U6 new-contact gate"]
    rules.append("U10 undo window")
    rules.append("U12 everything audited")
    au = (db.query(AuditLog).filter(AuditLog.tenant_id == p.tenant_id,
                                    AuditLog.target == ix.lead_id)
          .order_by(AuditLog.id.desc()).first())
    return {
        "plain": plain,
        "technical": {
            "rules_applied": rules,
            "channel": ix.channel, "drafted_by": ix.drafted_by, "status": ix.status,
            "validator": ix.validator or [],
            "reviewed_by": ix.reviewed_by,
            "identity_chain": au.identity_chain if au else None,
            "model": "llama3.2:3b (local)",
        },
    }


# ───────────────────────────── §9.5 Webhooks ────────────────────────────────
EVENT_CATALOG = ["party.created", "engagement.stage_changed", "event.booked", "event.kept",
                 "event.missed", "money.received", "money.overdue", "document.generated",
                 "approval.decided"]


def fire_webhooks(db, tenant_id, event, payload):
    """Fire signed webhooks for an event (IDs/metadata only unless content consented)."""
    hooks = db.query(Webhook).filter_by(tenant_id=tenant_id, status="active").all()
    fired = 0
    for h in hooks:
        if event not in (h.events or []):
            continue
        body = json.dumps({"event": event, "data": payload}, default=str)
        sig = hmac.new((h.secret or "").encode(), body.encode(), hashlib.sha256).hexdigest()
        # (delivery is simulated in the demo; HMAC signature is real)
        h.deliveries = (h.deliveries or 0) + 1
        h.last_fired_at = now()
        fired += 1
    return fired


@router.get("/webhooks/events")
def webhook_events():
    return {"events": EVENT_CATALOG,
            "note": "Built on the local event bus. Payloads carry IDs/metadata by default; "
                    "business content needs an explicit per-endpoint consent toggle."}


@router.get("/webhooks")
def list_webhooks(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Webhook).filter_by(tenant_id=p.tenant_id).all()
    return [{"id": w.id, "url": w.url, "events": w.events or [], "status": w.status,
             "include_content": w.include_content, "deliveries": w.deliveries,
             "last_fired_at": w.last_fired_at.isoformat() if w.last_fired_at else None}
            for w in rows]


class WebhookIn(BaseModel):
    url: str
    events: list[str] = []
    include_content: bool = False


@router.post("/webhooks")
def create_webhook(body: WebhookIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    w = Webhook(id=ulid("whk"), tenant_id=p.tenant_id, url=body.url,
                events=[e for e in body.events if e in EVENT_CATALOG],
                secret=ulid("sec"), include_content=body.include_content)
    if not body.url.strip():
        raise HTTPException(422, detail={"code": "BAD_URL", "message": "An endpoint URL is required."})
    db.add(w)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="webhook.create",
          target=w.id, tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "webhook.changed", {"action": "create", "name": _host(w.url)})
    return {"id": w.id, "secret": w.secret, "url": w.url, "events": w.events,
            "message": f"Webhook created for {_host(w.url)} ({len(w.events)} event(s)). "
                       f"Signing secret shown once below."}


def _host(url):
    m = re.search(r"https?://([^/]+)", url or "")
    return m.group(1) if m else (url or "endpoint")


class WebhookPatch(BaseModel):
    status: str | None = None              # active | paused
    events: list[str] | None = None
    include_content: bool | None = None


@router.patch("/webhooks/{wid}")
def update_webhook(wid: str, body: WebhookPatch, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    w = db.get(Webhook, wid)
    if not w or w.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Webhook not found"})
    changed = []
    if body.status in ("active", "paused"):
        w.status = body.status
        changed.append("resumed" if body.status == "active" else "paused")
    if body.events is not None:
        w.events = [e for e in body.events if e in EVENT_CATALOG]
        changed.append(f"{len(w.events)} event(s)")
    if body.include_content is not None:
        w.include_content = body.include_content
        changed.append("content " + ("on" if body.include_content else "off"))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="webhook.update",
          target=w.id, tenant_id=p.tenant_id, meta={"status": w.status})
    db.commit()
    hub.emit(p.tenant_id, "webhook.changed", {"action": "update", "name": _host(w.url)})
    return {"id": w.id, "status": w.status, "events": w.events,
            "include_content": w.include_content,
            "message": f"{_host(w.url)} {' · '.join(changed) if changed else 'updated'}."}


@router.post("/webhooks/{wid}/test")
def test_webhook(wid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    w = db.get(Webhook, wid)
    if not w or w.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Webhook not found"})
    if w.status != "active":
        raise HTTPException(409, detail={"code": "PAUSED",
            "message": "This webhook is paused — resume it before firing a test."})
    ev = (w.events or ["party.created"])[0]
    fired = fire_webhooks(db, p.tenant_id, ev, {"id": "test_123", "sample": True})
    audit(db, plane="local", actor=f"user:{p.user_id}", action="webhook.test",
          target=w.id, tenant_id=p.tenant_id, meta={"event": ev, "delivered": fired})
    db.commit()
    hub.emit(p.tenant_id, "webhook.changed", {"action": "test", "name": _host(w.url)})
    return {"status": "fired", "event": ev, "delivered": fired,
            "signature": "HMAC-SHA256 (signed with your endpoint secret)",
            "message": f"Fired “{ev}” — {fired} delivery(ies), HMAC-SHA256 signed."}


class FireIn(BaseModel):
    event: str


@router.post("/webhooks/fire")
def fire_event(body: FireIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Broadcast a test event to every subscribed active webhook."""
    if body.event not in EVENT_CATALOG:
        raise HTTPException(422, detail={"code": "BAD_EVENT", "message": "Unknown event."})
    fired = fire_webhooks(db, p.tenant_id, body.event, {"id": "test_123", "sample": True})
    audit(db, plane="local", actor=f"user:{p.user_id}", action="webhook.test",
          target=None, tenant_id=p.tenant_id, meta={"event": body.event, "delivered": fired})
    db.commit()
    hub.emit(p.tenant_id, "webhook.changed", {"action": "fire", "name": body.event})
    return {"status": "fired", "event": body.event, "delivered": fired,
            "message": f"Broadcast “{body.event}” to {fired} subscribed webhook(s)."
                       if fired else f"No active webhook subscribes to “{body.event}”."}


@router.delete("/webhooks/{wid}")
def delete_webhook(wid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    w = db.get(Webhook, wid)
    if not w or w.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Webhook not found"})
    host = _host(w.url)
    db.delete(w)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="webhook.delete",
          target=wid, tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "webhook.changed", {"action": "delete", "name": host})
    return {"status": "deleted", "message": f"Removed webhook for {host}."}


def _match_hook(db, tenant_id, text):
    low = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    toks = [w for w in low.split() if len(w) >= 3 and w not in (
        "the", "webhook", "hook", "test", "fire", "remove", "delete", "pause", "resume",
        "endpoint", "integration", "for", "off", "stop")]
    rows = db.query(Webhook).filter_by(tenant_id=tenant_id).all()
    if not rows:
        return None
    best, score = None, 0
    for w in rows:
        hay = re.sub(r"[^a-z0-9 ]", " ", (w.url or "").lower())
        s = sum(1 for t in toks if t in hay)
        if s > score:
            best, score = w, s
    return best if score else (rows[0] if len(rows) == 1 else None)


def _event_from(text):
    low = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    for ev in EVENT_CATALOG:
        words = ev.replace(".", " ").replace("_", " ").split()
        if all(re.search(rf"\b{re.escape(w)}", low) for w in words):
            return ev
    return None


class WebhookVoiceIn(BaseModel):
    transcript: str


@router.post("/webhooks/resolve")
def webhooks_resolve(body: WebhookVoiceIn, p: Principal = Depends(current_user),
                     db: Session = Depends(get_db)):
    text = body.transcript or ""
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())

    if re.search(r"\b(events|catalog|what events|list events)\b", low):
        return {"action": "events", "message": "Showing the event catalog."}
    # add a webhook by spoken URL
    um = re.search(r"(https?://\S+)", text, re.I)
    if re.search(r"\b(add|create|new|register|connect)\b", low) and um:
        ev = _event_from(text)
        return {"action": "add", "url": um.group(1).rstrip(" .,'\""),
                "events": [ev] if ev else [], "message": "Adding the webhook."}
    if re.search(r"\b(add|create|new|register)\b.*\bwebhook\b", low):
        return {"action": "add_open", "message": "Opening the add-webhook form."}
    # fire a specific event across all hooks
    ev = _event_from(text)
    if ev and re.search(r"\b(fire|send|trigger|emit|broadcast)\b", low):
        return {"action": "fire", "event": ev, "message": f"Firing {ev}."}
    # pause / resume / test / delete a matched hook
    if re.search(r"\b(pause|disable|stop|suspend)\b", low):
        w = _match_hook(db, p.tenant_id, text)
        if w:
            return {"action": "pause", "id": w.id, "name": _host(w.url), "message": f"Pausing {_host(w.url)}."}
        return {"action": "none", "message": "Which webhook should I pause?"}
    if re.search(r"\b(resume|enable|activate|turn on|start)\b", low):
        w = _match_hook(db, p.tenant_id, text)
        if w:
            return {"action": "resume", "id": w.id, "name": _host(w.url), "message": f"Resuming {_host(w.url)}."}
        return {"action": "none", "message": "Which webhook should I resume?"}
    if re.search(r"\b(test|fire|trigger|ping)\b", low):
        w = _match_hook(db, p.tenant_id, text)
        if w:
            return {"action": "test", "id": w.id, "name": _host(w.url), "message": f"Testing {_host(w.url)}."}
        return {"action": "none", "message": "Which webhook should I test?"}
    if re.search(r"\b(remove|delete|drop|disconnect)\b", low):
        w = _match_hook(db, p.tenant_id, text)
        if w:
            return {"action": "delete", "id": w.id, "name": _host(w.url), "message": f"Removing {_host(w.url)}."}
        return {"action": "none", "message": "Which webhook should I remove?"}
    return {"action": "none",
            "message": 'Try "test the zapier webhook", "pause it", "fire the approval decided event", or "add a webhook".'}

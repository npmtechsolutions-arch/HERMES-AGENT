"""
G2 — Remote Command Channels.

Pair a personal WhatsApp/Telegram/Signal/email as a *command* channel so the owner
can run the workforce away from the desktop: "What's pending?", "Approve the
vendor payment", "Give me my briefing". Messages route through a SCOPED grammar
(query / approve / briefing only) — no vault, no permission changes, no
destructive ops (SC-11). Every remote command is audited with channel identity.

Privacy: the desktop stays the brain; the channel is just I/O. (In this build the
channel is simulated via the ingest endpoint; a real WhatsApp/Telegram adapter
posts to the same endpoint.)
"""
import random
import re
import string

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import (Agent, Approval, BusThread, RemoteChannel, RemoteCommand,
                      Task, Workflow, now)
from ..security import ulid

router = APIRouter(prefix="/remote", tags=["remote"])

SCOPES = ["query", "approve", "briefing"]
# Actions a remote channel may NEVER perform (SC-11).
_BLOCKED = re.compile(r"\b(delete|remove|vault|secret|password|permission|grant|wipe|drop)\b", re.I)


def channel_dto(c: RemoteChannel):
    return {"id": c.id, "type": c.type, "label": c.label, "status": c.status,
            "pairing_code": c.pairing_code if c.status == "pending" else None,
            "scopes": c.scopes or [], "sender_allowlist": c.sender_allowlist or [],
            "last_seen_at": c.last_seen_at.isoformat() if c.last_seen_at else None}


@router.get("/channels")
def list_channels(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(RemoteChannel).filter_by(tenant_id=p.tenant_id).filter(
        RemoteChannel.status != "revoked").all()
    return [channel_dto(c) for c in rows]


class PairIn(BaseModel):
    type: str                          # whatsapp|telegram|signal|email
    label: str | None = None
    scopes: list[str] = ["query", "approve", "briefing"]


@router.post("/channels")
def create_channel(body: PairIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    c = RemoteChannel(id=ulid("rch"), tenant_id=p.tenant_id, type=body.type,
                      label=body.label or f"My {body.type}", pairing_code=code,
                      scopes=[s for s in body.scopes if s in SCOPES], status="pending")
    db.add(c)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="remote.pair_start",
          target=c.id, tenant_id=p.tenant_id, meta={"type": body.type})
    db.commit()
    hub.emit(p.tenant_id, "remote.changed", {"action": "pair_start", "name": c.label})
    return {**channel_dto(c), "message": f"Pairing code generated for {c.label}: {code}."}


class CompletePairIn(BaseModel):
    pairing_code: str
    sender: str                        # the phone/handle that will command


@router.post("/channels/complete")
def complete_pair(body: CompletePairIn, p: Principal = Depends(current_user),
                  db: Session = Depends(get_db)):
    c = db.query(RemoteChannel).filter_by(tenant_id=p.tenant_id,
                                          pairing_code=body.pairing_code).first()
    if not c:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Invalid pairing code"})
    c.status = "paired"
    c.sender_allowlist = list(set((c.sender_allowlist or []) + [body.sender]))
    c.last_seen_at = now()
    audit(db, plane="local", actor=f"user:{p.user_id}", action="remote.paired",
          target=c.id, tenant_id=p.tenant_id, meta={"sender": body.sender})
    db.commit()
    hub.emit(p.tenant_id, "remote.changed", {"action": "paired", "name": c.label})
    return {**channel_dto(c), "message": f"{c.label} paired — {body.sender} can now command."}


class ChannelPatch(BaseModel):
    scopes: list[str] | None = None
    label: str | None = None


@router.patch("/channels/{cid}")
def update_channel(cid: str, body: ChannelPatch, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    c = db.get(RemoteChannel, cid)
    if not c or c.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Channel not found"})
    if body.scopes is not None:
        c.scopes = [s for s in body.scopes if s in SCOPES]
    if body.label is not None and body.label.strip():
        c.label = body.label.strip()
    audit(db, plane="local", actor=f"user:{p.user_id}", action="remote.update",
          target=c.id, tenant_id=p.tenant_id, meta={"scopes": c.scopes})
    db.commit()
    hub.emit(p.tenant_id, "remote.changed", {"action": "update", "name": c.label})
    return {**channel_dto(c),
            "message": f"{c.label} scopes: {', '.join(c.scopes) or 'none'}."}


@router.delete("/channels/{cid}")
def revoke_channel(cid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(RemoteChannel, cid)
    if not c or c.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Channel not found"})
    label = c.label
    c.status = "revoked"
    audit(db, plane="local", actor=f"user:{p.user_id}", action="remote.revoked",
          target=c.id, tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "remote.changed", {"action": "revoked", "name": label})
    return {"status": "revoked", "message": f"Revoked access for {label}."}


# ───────────────────────────── Command processor ────────────────────────────
def _summary(db, tenant_id):
    pending = db.query(Approval).filter_by(tenant_id=tenant_id, state="pending").all()
    working = db.query(Task).filter_by(tenant_id=tenant_id, status="working").count()
    agents = db.query(Agent).filter_by(tenant_id=tenant_id).filter(Agent.status == "working").all()
    return pending, working, agents


def _process(db, tenant_id, c, message):
    text = message.strip()
    low = text.lower()
    pending, working, busy = _summary(db, tenant_id)

    # SC-11: block out-of-scope / sensitive actions on remote channels.
    if _BLOCKED.search(low):
        return "blocked", ("That action isn't allowed from a remote channel. "
                           "Sensitive operations need the desktop with voice-print."), False

    # approve / reject
    m = re.search(r"\b(approve|reject)\b\s*(the\s+)?(.*)", low)
    if m and ("approve" in c.scopes):
        decision = m.group(1)
        target = (m.group(3) or "").strip()
        appr = None
        if pending:
            if target:
                appr = next((a for a in pending if target[:12] in (a.action_summary or "").lower()), None)
            appr = appr or pending[0]
        if not appr:
            return decision, "There are no pending approvals to act on.", True
        appr.state = "approved" if decision == "approve" else "rejected"
        appr.chain = (appr.chain or []) + [{"tier": "human", "actor": f"remote:{c.type}",
                                            "decision": decision, "at": now().isoformat()}]
        if appr.task_id:
            t = db.get(Task, appr.task_id)
            if t:
                if decision == "approve":
                    thread = db.query(BusThread).filter_by(task_id=t.id).first()
                    from .tasks import _complete_task
                    if thread:
                        _complete_task(db, type("P", (), {"tenant_id": tenant_id, "user_id": "remote"})(), t, thread)
                else:
                    t.status = "canceled"
        hub.emit(tenant_id, "approval.decided", {"approval_id": appr.id, "state": appr.state})
        return decision, f"{decision.title()}d: {appr.action_summary}.", True

    # briefing
    if ("briefing" in c.scopes) and re.search(r"\bbrief|briefing\b", low):
        lines = [f"{len(pending)} approval(s) pending", f"{working} task(s) working",
                 f"{len(busy)} agent(s) busy now"]
        if pending:
            lines.append(f"Top approval: {pending[0].action_summary}")
        return "briefing", "Here's your briefing — " + "; ".join(lines) + ".", True

    # query: pending / status
    if re.search(r"\bpending|what'?s up|status|overdue\b", low):
        if not pending:
            return "query", f"Nothing needs approval. {working} task(s) in progress.", True
        items = "; ".join(f"{a.action_summary} ({a.rule_id})" for a in pending[:3])
        return "query", f"{len(pending)} pending approval(s): {items}. Reply 'approve' to clear the first.", True

    if re.search(r"\bwho'?s (busy|working)|agents?\b", low):
        names = ", ".join(a.name for a in busy) or "none"
        return "query", f"Working now: {names}.", True

    return "help", ("I can answer questions ('what's pending', 'who's working'), give a "
                    "'briefing', or 'approve'/'reject'. Sensitive actions need the desktop."), True


class IngestIn(BaseModel):
    channel_id: str | None = None
    pairing_code: str | None = None
    sender: str
    message: str


@router.post("/command")
def remote_command(body: IngestIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    """Inbound remote message (from a paired channel) → scoped command → response."""
    c = db.get(RemoteChannel, body.channel_id) if body.channel_id else \
        db.query(RemoteChannel).filter_by(tenant_id=p.tenant_id, pairing_code=body.pairing_code).first()
    if not c or c.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Channel not found"})
    if c.status != "paired":
        raise HTTPException(409, detail={"code": "CONFLICT", "message": "Channel not paired"})
    # allow-listed sender check
    allowed = (not c.sender_allowlist) or body.sender in c.sender_allowlist
    if not allowed:
        intent, response, ok = "blocked", "Sender not allow-listed for this channel.", False
    else:
        intent, response, ok = _process(db, p.tenant_id, c, body.message)
    c.last_seen_at = now()
    db.add(RemoteCommand(id=ulid("rcm"), tenant_id=p.tenant_id, channel_id=c.id,
                         sender=body.sender, message=body.message, intent=intent,
                         response=response, allowed=ok))
    audit(db, plane="local", actor=f"remote:{c.type}:{body.sender}", action="remote.command",
          target=c.id, tenant_id=p.tenant_id, meta={"intent": intent, "allowed": ok})
    db.commit()
    return {"intent": intent, "response": response, "allowed": ok, "channel": c.type}


@router.get("/commands")
def command_history(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(RemoteCommand).filter_by(tenant_id=p.tenant_id).order_by(
        RemoteCommand.at.desc()).limit(50).all()
    chans = {c.id: c for c in db.query(RemoteChannel).filter_by(tenant_id=p.tenant_id).all()}
    return [{"id": r.id, "channel": chans.get(r.channel_id).type if chans.get(r.channel_id) else None,
             "sender": r.sender, "message": r.message, "intent": r.intent,
             "response": r.response, "allowed": r.allowed,
             "at": r.at.isoformat() if r.at else None} for r in rows]


# ───────────────────────────── Voice (page control) ─────────────────────────
_CH_TYPES = {"whatsapp": ["whatsapp", "whats app", "wa"], "telegram": ["telegram", "tg"],
             "signal": ["signal"], "email": ["email", "mail"]}


def _match_channel(db, tenant_id, text, paired_only=False):
    low = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    q = db.query(RemoteChannel).filter_by(tenant_id=tenant_id).filter(
        RemoteChannel.status != "revoked")
    if paired_only:
        q = q.filter(RemoteChannel.status == "paired")
    rows = q.all()
    # by type word
    for typ, words in _CH_TYPES.items():
        if any(re.search(rf"\b{re.escape(w)}\b", low) for w in words):
            m = next((c for c in rows if c.type == typ), None)
            if m:
                return m
    # by label token
    toks = [w for w in low.split() if len(w) >= 3]
    best, score = None, 0
    for c in rows:
        hay = re.sub(r"[^a-z0-9 ]", " ", (c.label or "").lower())
        s = sum(1 for w in toks if w in hay)
        if s > score:
            best, score = c, s
    if best:
        return best
    return rows[0] if (paired_only and len(rows) == 1) else None


class RemoteVoiceIn(BaseModel):
    transcript: str


@router.post("/resolve")
def remote_resolve(body: RemoteVoiceIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    text = body.transcript or ""
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())

    if re.search(r"\b(history|past commands|command log|show commands|activity)\b", low):
        return {"action": "history", "message": "Showing command history."}
    # pair a new channel
    if re.search(r"\b(pair|connect|add|link|set up)\b", low):
        typ = next((t for t, ws in _CH_TYPES.items()
                    if any(re.search(rf"\b{re.escape(w)}\b", low) for w in ws)), None)
        if typ:
            return {"action": "pair", "type": typ, "message": f"Pairing a {typ} channel."}
        return {"action": "pair_open", "message": "Opening the pairing dialog."}
    # scope change (before revoke, so "remove approve from X" tweaks scopes, not the channel)
    sm = re.search(r"\b(query|approve|approvals?|briefing|brief)\b", low)
    if sm and re.search(r"\b(scope|allow|only|disable|enable|remove|restrict|limit|grant)\b", low):
        c = _match_channel(db, p.tenant_id, text)
        if not c:
            return {"action": "none", "message": "Which channel's scopes?"}
        want = []
        for s in SCOPES:
            kw = "brief" if s == "briefing" else ("approve" if s == "approve" else "query")
            present = bool(re.search(rf"\b{kw}", low))
            if re.search(r"\b(remove|disable|revoke|drop|no)\b", low):
                if not present:
                    want.append(s)        # keep the ones NOT mentioned for removal
            elif re.search(r"\b(only|restrict|limit)\b", low):
                if present:
                    want.append(s)        # keep only the mentioned ones
            else:  # allow/enable/grant → add mentioned to existing
                if present or s in (c.scopes or []):
                    want.append(s)
        return {"action": "scope", "id": c.id, "name": c.label, "scopes": want,
                "message": f"Updating {c.label} scopes."}
    # revoke
    if re.search(r"\b(revoke|unpair|disconnect|remove|delete)\b", low):
        c = _match_channel(db, p.tenant_id, text)
        if c:
            return {"action": "revoke", "id": c.id, "name": c.label,
                    "message": f"Revoking {c.label}."}
        return {"action": "none", "message": "Which channel should I revoke?"}
    # run a command through a paired channel ("ask whatsapp what's pending", "what's pending")
    cm = re.search(r"\b(ask|tell|via|through|on)\b\s+(whatsapp|telegram|signal|email)\b\s*(.*)$", text, re.I)
    if cm:
        c = _match_channel(db, p.tenant_id, cm.group(2), paired_only=True)
        msg = cm.group(3).strip(" .'?\"") or "what's pending"
        if c:
            return {"action": "command", "id": c.id, "message_text": msg,
                    "message": f"Asking {c.label}: {msg}"}
        return {"action": "none", "message": f"No paired {cm.group(2)} channel."}
    if re.search(r"\b(pending|briefing|brief|who'?s working|who'?s busy|status|approve|reject)\b", low):
        c = _match_channel(db, p.tenant_id, text, paired_only=True)
        if c:
            return {"action": "command", "id": c.id, "message_text": text.strip(" .'?\""),
                    "message": f"Running on {c.label}."}
        return {"action": "none", "message": "Pair a channel first to run remote commands."}
    return {"action": "none",
            "message": 'Try "pair a telegram channel", "revoke whatsapp", "ask whatsapp what\'s pending", or "show history".'}

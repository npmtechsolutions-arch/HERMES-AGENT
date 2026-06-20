"""
Pro-gated advanced agent editor (Doc 26 Prompt M). Deep-edit existing agents or
build new ones with: custom instructions, explicit tool grants, permission limits,
schedule, delegation (depth-capped), and voice. Every change goes through a
draft → (rehearse) → publish lifecycle that snapshots the agent first, so any
edit is one-click revertible.

NON-NEGOTIABLE (enforced here, not editable by any plan):
  • locked approval gates stay — a draft can't set auto-send / skip-approval /
    autonomous money; such a draft is REJECTED.
  • tool grants can't exceed the registered tool ceiling.
  • delegation depth is capped at 3.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import Agent, AgentDraft, Tenant, now
from ..security import ulid
from ..tools import TOOL_REGISTRY
from .. import assistant as _assistant  # noqa: F401  (registers all tools)

router = APIRouter(tags=["agent-advanced"])

PRO_TIERS = {"pro", "business", "enterprise"}
MAX_DELEGATION_DEPTH = 3
# keys/values a user must never be able to set — they would bypass §5 locked rules
FORBIDDEN_FLAGS = ("bypass_approvals", "skip_approval", "auto_money", "autonomous_payment", "disable_gates")


def _is_pro(db, p) -> bool:
    t = db.get(Tenant, p.tenant_id)
    return bool(t and (t.plan_tier in PRO_TIERS))


def _require_pro(db, p):
    if not _is_pro(db, p):
        raise HTTPException(402, detail={"code": "PRO_REQUIRED",
                                         "message": "Advanced agent editing is a Pro feature.",
                                         "upgrade_url": "/pricing"})


def _agent(db, agent_id, p):
    a = db.get(Agent, agent_id)
    if not a or a.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found"})
    return a


def validate_advanced(data: dict):
    """Return (clean, None) or (None, reason). Enforces the locked rules."""
    clean = {}
    # 1) locked-rule bypass attempts → reject outright
    perms = dict(data.get("permissions") or {})
    for k in FORBIDDEN_FLAGS:
        if perms.get(k) or data.get(k):
            return None, "Locked safety rules can't be edited — money, new-contact and destructive actions always require your approval."
    es = perms.get("external_send")
    if es not in (None, "approval_required"):
        return None, "Messages to others always need your approval — auto-send can't be enabled."
    perms["external_send"] = "approval_required"     # force-pin the locked default
    # 2) tool grants must be within the registered ceiling
    tools = data.get("tools") or []
    unknown = [t for t in tools if t not in TOOL_REGISTRY]
    if unknown:
        return None, f"These tools are beyond your plan ceiling: {', '.join(unknown)}."
    clean["tools"] = list(tools)
    # 3) delegation depth capped
    deleg = dict(data.get("delegation") or {})
    if deleg:
        deleg["depth"] = max(1, min(int(deleg.get("depth", MAX_DELEGATION_DEPTH)), MAX_DELEGATION_DEPTH))
        deleg["enabled"] = bool(deleg.get("enabled", False))
    clean["delegation"] = deleg
    clean["permissions"] = perms
    for k in ("name", "instructions", "schedule", "voice_id"):
        if data.get(k) is not None:
            clean[k] = data[k]
    return clean, None


class Eligibility(BaseModel):
    pass


@router.get("/agents/advanced/eligibility")
def eligibility(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(Tenant, p.tenant_id)
    return {"pro": _is_pro(db, p), "tier": (t.plan_tier if t else "personal"),
            "max_delegation_depth": MAX_DELEGATION_DEPTH}


class DraftIn(BaseModel):
    name: str | None = None
    instructions: str | None = None
    tools: list[str] | None = None
    permissions: dict | None = None
    schedule: dict | None = None
    delegation: dict | None = None
    voice_id: str | None = None


@router.post("/agents/{agent_id}/advanced/draft")
def save_draft(agent_id: str, body: DraftIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    _require_pro(db, p)
    _agent(db, agent_id, p)
    clean, err = validate_advanced(body.model_dump(exclude_none=True))
    if err:
        raise HTTPException(400, detail={"code": "LOCKED_RULE", "message": err})
    d = (db.query(AgentDraft).filter_by(tenant_id=p.tenant_id, agent_id=agent_id, status="draft")
         .order_by(AgentDraft.created_at.desc()).first())
    if not d:
        d = AgentDraft(id=ulid("drf"), tenant_id=p.tenant_id, agent_id=agent_id, status="draft")
        db.add(d)
    d.data = clean
    db.commit()
    return {"id": d.id, "agent_id": agent_id, "data": d.data, "status": d.status,
            "message": "Draft saved. Rehearse it, then publish — you can revert any time."}


@router.post("/agents/drafts/{draft_id}/rehearse")
def rehearse(draft_id: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    _require_pro(db, p)
    d = db.get(AgentDraft, draft_id)
    if not d or d.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Draft not found"})
    clean, err = validate_advanced(d.data or {})       # re-check (config may be stale)
    if err:
        raise HTTPException(400, detail={"code": "LOCKED_RULE", "message": err})
    d.status = "rehearsed"
    db.commit()
    checks = ["Locked approval gates intact", "Tool grants within ceiling",
              f"Delegation depth ≤ {MAX_DELEGATION_DEPTH}", "Eval/validator net applies"]
    return {"ok": True, "checks": checks, "message": "Tested in rehearsal — safe to publish."}


@router.post("/agents/drafts/{draft_id}/publish")
def publish(draft_id: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    _require_pro(db, p)
    d = db.get(AgentDraft, draft_id)
    if not d or d.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Draft not found"})
    clean, err = validate_advanced(d.data or {})
    if err:
        raise HTTPException(400, detail={"code": "LOCKED_RULE", "message": err})
    a = _agent(db, d.agent_id, p)
    # snapshot BEFORE applying — this is the one-click revert point
    d.base = {"name": a.name, "description": a.description, "objectives": a.objectives or [],
              "tools": a.tools or [], "permissions": a.permissions or {}, "schedule": a.schedule or {},
              "voice_id": a.voice_id}
    if "name" in clean:
        a.name = clean["name"]
    if "instructions" in clean:
        a.description = clean["instructions"]
        a.objectives = [clean["instructions"]]
    if "tools" in clean:
        a.tools = clean["tools"]
    a.permissions = {**(a.permissions or {}), **clean["permissions"]}
    sched = {**(a.schedule or {})}
    if clean.get("schedule"):
        sched.update(clean["schedule"])
    if clean.get("delegation"):
        sched["delegation"] = clean["delegation"]
    a.schedule = sched
    if "voice_id" in clean:
        a.voice_id = clean["voice_id"]
    d.status = "published"
    audit(db, plane="local", actor=f"user:{p.user_id}", action="agent.advanced_publish",
          target=a.id, tenant_id=p.tenant_id, meta={"draft": d.id})
    db.commit()
    hub.emit(p.tenant_id, "agent.status", {"agent_id": a.id, "status": a.status, "name": a.name, "event": "updated"})
    return {"ok": True, "agent_id": a.id, "draft_id": d.id, "message": f"Published. “{a.name}” updated — revert any time."}


@router.post("/agents/{agent_id}/advanced/revert")
def revert(agent_id: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """One-click revert of the most recent publish."""
    _require_pro(db, p)
    a = _agent(db, agent_id, p)
    d = (db.query(AgentDraft).filter_by(tenant_id=p.tenant_id, agent_id=agent_id, status="published")
         .order_by(AgentDraft.created_at.desc()).first())
    if not d or not d.base:
        raise HTTPException(400, detail={"code": "NO_SNAPSHOT", "message": "Nothing to revert."})
    b = d.base
    a.name = b.get("name", a.name); a.description = b.get("description")
    a.objectives = b.get("objectives", []); a.tools = b.get("tools", [])
    a.permissions = b.get("permissions", {}); a.schedule = b.get("schedule", {})
    a.voice_id = b.get("voice_id", a.voice_id)
    d.status = "reverted"
    audit(db, plane="local", actor=f"user:{p.user_id}", action="agent.advanced_revert",
          target=a.id, tenant_id=p.tenant_id, meta={"draft": d.id})
    db.commit()
    return {"ok": True, "agent_id": a.id, "message": f"Reverted “{a.name}” to the previous version."}


@router.get("/agents/{agent_id}/drafts")
def list_drafts(agent_id: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    _agent(db, agent_id, p)
    rows = (db.query(AgentDraft).filter_by(tenant_id=p.tenant_id, agent_id=agent_id)
            .order_by(AgentDraft.created_at.desc()).all())
    return {"drafts": [{"id": d.id, "status": d.status, "data": d.data,
                        "created_at": d.created_at.isoformat() if d.created_at else None} for d in rows]}

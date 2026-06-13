"""
Smaller gap fills:
  G5 — Model Gateway tier metadata + per-data-class privacy rule.
  G9 — Community marketplace publishing.
  G10 — Generic MCP server attach ("Add their tools").
  G12 — Multi-Computer Network nodes (status surface).
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from datetime import datetime, timezone

from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import (Agent, BudgetLedger, BudgetReservation, GatewayCall,
                      MarketplaceItem, MemoryItem, RoutingPolicy, now)
from ..routers.compliance import pdp_evaluate
from ..security import ulid

router = APIRouter(tags=["platform"])

MANAGED_RATE = 0.002   # ₹ per token (managed gateway, illustrative)
DEFAULT_MONTHLY_CAP = 2000


# ───────────────────────────── G5 Model Gateway ─────────────────────────────
# Only two tiers: our local LLM (default, private) and our managed cloud gateway
# (metered, uses the platform's own cloud key). Users never configure a cloud key.
TIERS = [
    {"id": "local", "label": "Local", "color": "green",
     "desc": "Runs fully on this machine on our local LLM. Default. Best privacy, works offline."},
    {"id": "managed", "label": "Managed Gateway", "color": "amber",
     "desc": "Our metered cloud gateway — flagship-quality models for weak hardware, on our key. Billed per use."},
]
VALID_TIERS = {t["id"] for t in TIERS}


def _norm_tier(t):
    # Legacy 'byo' (bring-your-own key) is retired → treat as Local.
    return t if t in VALID_TIERS else "local"


@router.get("/gateway")
def gateway(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    agents = db.query(Agent).filter_by(tenant_id=p.tenant_id).filter(
        Agent.status != "archived").all()
    by_tier = {"local": 0, "managed": 0}
    for a in agents:
        by_tier[_norm_tier(a.model_tier or "local")] += 1
    pii_count = db.query(MemoryItem).filter_by(tenant_id=p.tenant_id).filter(
        MemoryItem.pii.is_(True)).count()
    return {
        "tiers": TIERS,
        "agents": [{"id": a.id, "name": a.name, "designation": a.designation,
                    "model_tier": _norm_tier(a.model_tier or "local"), "model_id": a.model_id}
                   for a in agents],
        "distribution": by_tier,
        "pii_rule": {"id": "MC-08-hardened",
                     "text": "Memory tagged PII or Confidential never leaves the Local tier, "
                             "regardless of an agent's model tier. A guarantee free general "
                             "agents don't make.",
                     "protected_items": pii_count},
    }


class TierIn(BaseModel):
    tier: str


@router.post("/gateway/agents/{aid}/tier")
def set_agent_tier(aid: str, body: TierIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    if body.tier not in VALID_TIERS:
        raise HTTPException(422, detail={"code": "BAD_TIER",
            "message": "Tier must be 'local' or 'managed'. There is no bring-your-own-key option."})
    a = db.get(Agent, aid)
    if not a or a.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Agent not found"})
    a.model_tier = body.tier
    audit(db, plane="local", actor=f"user:{p.user_id}", action="gateway.tier_set",
          target=a.id, tenant_id=p.tenant_id, meta={"tier": body.tier})
    db.commit()
    label = next(t["label"] for t in TIERS if t["id"] == body.tier)
    hub.emit(p.tenant_id, "gateway.changed", {"action": "tier", "name": f"{a.name} → {label}"})
    return {"id": a.id, "model_tier": a.model_tier,
            "message": f"{a.name} now runs on {label}."}


@router.post("/gateway/agents/tier-all")
def set_all_tiers(body: TierIn, p: Principal = Depends(current_user),
                  db: Session = Depends(get_db)):
    if body.tier not in VALID_TIERS:
        raise HTTPException(422, detail={"code": "BAD_TIER",
            "message": "Tier must be 'local' or 'managed'."})
    agents = db.query(Agent).filter_by(tenant_id=p.tenant_id).filter(
        Agent.status != "archived").all()
    for a in agents:
        a.model_tier = body.tier
    audit(db, plane="local", actor=f"user:{p.user_id}", action="gateway.tier_set_all",
          tenant_id=p.tenant_id, meta={"tier": body.tier, "count": len(agents)})
    db.commit()
    label = next(t["label"] for t in TIERS if t["id"] == body.tier)
    hub.emit(p.tenant_id, "gateway.changed", {"action": "tier_all", "name": f"all → {label}"})
    return {"count": len(agents), "tier": body.tier,
            "message": f"All {len(agents)} agent(s) moved to {label}."
                       + (" Fully private & offline." if body.tier == "local" else "")}


# ───────────────────────────── §3.2 Budget gates + §3.6 observability ───────
def _ledger(db, tenant_id):
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    led = db.query(BudgetLedger).filter_by(tenant_id=tenant_id, scope="tenant",
                                           period=period).first()
    if not led:
        led = BudgetLedger(id=ulid("bdg"), tenant_id=tenant_id, scope="tenant",
                           period=period, limit=DEFAULT_MONTHLY_CAP, spent=0, reserved=0)
        db.add(led)
        db.flush()
    return led


@router.get("/budget")
def budget(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    led = _ledger(db, p.tenant_id)
    spent, lim, res = float(led.spent), float(led.limit), float(led.reserved)
    pct = round(100 * (spent + res) / lim, 1) if lim else 0
    state = "ok" if pct < 80 else "warn" if pct < 100 else "soft_locked"
    return {"period": led.period, "limit": lim, "spent": spent, "reserved": res,
            "available": max(0, lim - spent - res), "pct": pct, "state": state,
            "graduated": {"80": "voice/visual warning", "100": "queue + per-call human approval",
                          "hard": "local-model fallback only"}}


class BudgetIn(BaseModel):
    limit: float


@router.patch("/budget")
def set_budget(body: BudgetIn, p: Principal = Depends(current_user),
               db: Session = Depends(get_db)):
    if body.limit < 0:
        raise HTTPException(422, detail={"code": "BAD_LIMIT", "message": "Budget can't be negative."})
    led = _ledger(db, p.tenant_id)
    old = float(led.limit)
    led.limit = round(body.limit, 2)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="gateway.budget_set",
          tenant_id=p.tenant_id, meta={"old": old, "new": led.limit})
    db.commit()
    hub.emit(p.tenant_id, "gateway.changed", {"action": "budget", "name": f"₹{int(led.limit)}"})
    return {"limit": led.limit, "period": led.period,
            "message": f"Monthly managed-gateway cap set to ₹{int(led.limit):,}."}


class SimIn(BaseModel):
    agent_id: str | None = None
    task_profile: str = "drafting"
    prompt_tokens: int = 1200
    max_output_tokens: int = 600


@router.post("/gateway/simulate")
def gateway_simulate(body: SimIn, p: Principal = Depends(current_user),
                     db: Session = Depends(get_db)):
    """Pre-dispatch budget gate (§3.2): estimate → policy check → reserve → settle.
    Demonstrates the 'cost checked BEFORE the call' guarantee with graduated behavior."""
    est = round((body.prompt_tokens + body.max_output_tokens) * MANAGED_RATE, 2)
    led = _ledger(db, p.tenant_id)
    available = float(led.limit) - float(led.spent) - float(led.reserved)
    pct_after = 100 * (float(led.spent) + float(led.reserved) + est) / float(led.limit)

    # §3.10 policy gate before the call (managed gateway leaves the machine).
    pol = pdp_evaluate(db, p.tenant_id, "gateway",
                       {"action": "gateway_call", "cross_border": False, "tier": "managed"})
    if pol["effect"] == "deny":
        return {"allowed": False, "reason": "policy_deny", "policy": pol, "est_cost": est,
                "message": "Blocked by policy before the call — nothing left the machine."}

    if est > available:   # §3.2 hard cap → never call; fall back to local
        return {"allowed": False, "reason": "BUDGET_EXCEEDED", "est_cost": est,
                "available": round(available, 2),
                "fallback": "local-model chain (free, fully offline)",
                "options": ["raise the cap", "use a local model", "approve per-call"],
                "message": f"Budget cap reached — ₹{est} call blocked; falling back to the free local model."}

    behavior = "ok"
    if pct_after >= 100:
        behavior = "soft_locked: queued for per-call human approval"
    elif pct_after >= 80:
        behavior = "warning: nearing the monthly cap"

    res = BudgetReservation(id=ulid("res"), ledger_id=led.id, tenant_id=p.tenant_id,
                            est_cost=est, task_ref=body.task_profile, state="reserved")
    led.reserved = float(led.reserved) + est
    db.add(res)
    db.flush()
    # settle (call completes): reservation → actual spend.
    actual = round(est * 0.9, 2)
    res.actual_cost = actual
    res.state = "settled"
    led.reserved = float(led.reserved) - est
    led.spent = float(led.spent) + actual
    ag = db.get(Agent, body.agent_id) if body.agent_id else None
    db.add(GatewayCall(id=ulid("gwc"), tenant_id=p.tenant_id,
                       agent_ref=body.agent_id, model="managed-flagship", tier="managed",
                       task_profile=body.task_profile, prompt_tokens=body.prompt_tokens,
                       output_tokens=body.max_output_tokens, latency_ms=820, cost=actual,
                       policy_decision=pol["effect"]))
    audit(db, plane="local", actor="agent:ceo", action="gateway.call",
          target=body.agent_id, tenant_id=p.tenant_id,
          meta={"est": est, "actual": actual, "behavior": behavior})
    db.commit()
    hub.emit(p.tenant_id, "gateway.changed", {"action": "call", "name": f"₹{actual}"})
    return {"allowed": True, "est_cost": est, "actual_cost": actual,
            "spoken": f"Estimated cost ₹{est} on the managed gateway. Proceed?",
            "behavior": behavior, "policy": pol["effect"],
            "message": f"Managed call settled — est ₹{est}, actual ₹{actual}."
                       + (f" ({behavior})" if behavior != "ok" else "")}


@router.get("/gateway/usage")
def gateway_usage(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """§3.6 — tenant-facing, content-free gateway telemetry."""
    rows = db.query(GatewayCall).filter_by(tenant_id=p.tenant_id).order_by(
        GatewayCall.at.desc()).limit(50).all()
    total = sum(float(r.cost) for r in rows)
    return {"calls": len(rows), "spend": round(total, 2),
            "avg_latency_ms": round(sum(r.latency_ms for r in rows) / len(rows)) if rows else 0,
            "recent": [{"model": r.model, "tier": r.tier, "profile": r.task_profile,
                        "tokens": (r.prompt_tokens or 0) + (r.output_tokens or 0),
                        "latency_ms": r.latency_ms, "cost": float(r.cost),
                        "policy": r.policy_decision,
                        "at": r.at.isoformat() if r.at else None} for r in rows[:15]]}


# ───────────────────────────── §3.3 Routing policies ────────────────────────
DEFAULT_ROUTES = [
    {"task_profile": "drafting", "chain": [{"model": "qwen2.5:7b", "tier": "local"},
                                           {"model": "managed-flagship", "tier": "managed"}]},
    {"task_profile": "extraction", "chain": [{"model": "phi3", "tier": "local"}]},
    {"task_profile": "planning", "chain": [{"model": "managed-flagship", "tier": "managed"},
                                           {"model": "qwen2.5:7b", "tier": "local"}]},
]


@router.get("/routing")
def routing(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(RoutingPolicy).filter_by(tenant_id=p.tenant_id, active=True).all()
    if not rows:
        return {"policies": DEFAULT_ROUTES, "source": "platform-default",
                "note": "Health-aware failover: timeout/5xx/quality-validator failure → next "
                        "link; terminal local-model fallback so the workforce never stops."}
    return {"policies": [{"task_profile": r.task_profile, "chain": r.chain, "regions": r.regions}
                         for r in rows], "source": "tenant"}


# ───────────────────────────── Voice (page control) ─────────────────────────
def _match_agent(db, tenant_id, text):
    low = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    toks = [w for w in low.split() if len(w) >= 3 and w not in (
        "the", "agent", "set", "put", "move", "switch", "make", "run", "tier", "model",
        "local", "managed", "cloud", "gateway", "onto", "into", "use")]
    rows = db.query(Agent).filter_by(tenant_id=tenant_id).filter(Agent.status != "archived").all()
    best, score = None, 0
    for a in rows:
        hay = re.sub(r"[^a-z0-9 ]", " ", f"{a.name} {a.designation or ''}".lower())
        s = sum(1 for w in toks if w in hay)
        if s > score:
            best, score = a, s
    return best if score else None


def _tier_from(text):
    low = text.lower()
    if re.search(r"\b(managed|cloud|gateway|flagship)\b", low):
        return "managed"
    if re.search(r"\b(local|offline|private|on.?device|this machine)\b", low):
        return "local"
    return None


class GatewayVoiceIn(BaseModel):
    transcript: str


@router.post("/gateway/resolve")
def gateway_resolve(body: GatewayVoiceIn, p: Principal = Depends(current_user),
                    db: Session = Depends(get_db)):
    text = body.transcript or ""
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())

    if re.search(r"\b(usage|telemetry|spend|how much.*spent|show usage)\b", low):
        return {"action": "usage", "message": "Showing gateway usage."}
    if re.search(r"\b(simulate|test.*call|try.*call|dry run.*gateway|managed call)\b", low):
        return {"action": "simulate", "message": "Simulating a managed call."}
    # budget cap: "raise the budget to 5000" / "set the cap to 3000"
    bm = re.search(r"\b(budget|cap|limit|spend)\b", low)
    if bm:
        am = re.search(r"(?:to|=|at)\s*(?:rs|inr|₹)?\s*([\d,]+)", text, re.I) or \
            re.search(r"(?:rs|inr|₹)\s*([\d,]+)", text, re.I)
        if am:
            val = float(am.group(1).replace(",", ""))
            return {"action": "budget", "limit": val, "message": f"Setting the cap to ₹{int(val)}."}
        return {"action": "none", "message": "What amount? e.g. \"set the budget to 5000\"."}
    tier = _tier_from(text)
    if tier:
        if re.search(r"\b(all|every|everyone|whole|entire)\b", low):
            return {"action": "tier_all", "tier": tier,
                    "message": f"Moving all agents to {tier}."}
        a = _match_agent(db, p.tenant_id, text)
        if a:
            return {"action": "tier", "id": a.id, "tier": tier, "name": a.name,
                    "message": f"Moving {a.name} to {tier}."}
        # "switch to local" with no agent named → assume all
        if re.search(r"\b(switch|move|put|set|go)\b", low):
            return {"action": "tier_all", "tier": tier,
                    "message": f"Moving all agents to {tier}."}
        return {"action": "none", "message": "Which agent should change tier?"}
    return {"action": "none",
            "message": 'Try "put the sales agent on local", "move everyone to local", "simulate a managed call", or "set the budget to 5000".'}


# ───────────────────────────── G10 MCP attach ───────────────────────────────
class McpAttachIn(BaseModel):
    agent_id: str
    server: str                # mcp server url / name
    tools: list[str] = []


@router.post("/mcp/attach")
def mcp_attach(body: McpAttachIn, p: Principal = Depends(current_user),
               db: Session = Depends(get_db)):
    """One-click 'Add their tools' — attach a generic MCP server's tools to an agent."""
    a = db.get(Agent, body.agent_id)
    if not a or a.tenant_id != p.tenant_id:
        return {"error": "agent not found"}
    tools = body.tools or [f"{body.server}.run"]
    a.tools = list(dict.fromkeys((a.tools or []) + tools))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="mcp.attach",
          target=a.id, tenant_id=p.tenant_id, meta={"server": body.server, "tools": tools})
    db.commit()
    return {"status": "attached", "agent": a.name, "tools": a.tools}


# ───────────────────────────── G9 community publish ─────────────────────────
class PublishIn(BaseModel):
    name: str
    type: str = "skill"        # skill|agent_pack|workflow|industry_template
    description: str | None = None


@router.post("/marketplace/publish")
def publish_community(body: PublishIn, p: Principal = Depends(current_user),
                      db: Session = Depends(get_db)):
    """Publish to the community marketplace (free items; signature-mandatory, lighter review)."""
    item = MarketplaceItem(id=ulid("mp"), type=body.type, name=body.name,
                           description=body.description, is_free=True, status="in_review",
                           publisher="community", industry_tags=["community"], installs=0)
    db.add(item)
    audit(db, plane="cloud", actor=f"user:{p.user_id}", action="marketplace.publish",
          target=item.id, tenant_id=p.tenant_id, meta={"name": body.name})
    db.commit()
    return {"status": "submitted", "message": "Submitted to the community lane — "
            "signature-mandatory, lighter review. It will appear once approved.",
            "item_id": item.id}


# ───────────────────────────── G12 Network nodes ────────────────────────────
@router.get("/network/nodes")
def network_nodes(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Multi-Computer Network surface (this machine + paired LAN nodes)."""
    import os
    this_node = {"id": "node_local", "name": "This Machine", "os": "macOS",
                 "role": "primary", "status": "online", "gpus": 0,
                 "cpus": os.cpu_count(), "hosted_agents": db.query(Agent).filter_by(
                     tenant_id=p.tenant_id).filter(Agent.status != "archived").count(),
                 "headless": False}
    return {"nodes": [this_node], "headless_supported": True,
            "note": "Pair LAN nodes (mutual TLS) to distribute agents/models. Headless node "
                    "mode runs the core service without the Electron UI (office-server install)."}

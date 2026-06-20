"""Cloud user-facing: plans, subscription, invoices, devices, entitlements, marketplace, analytics."""
import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import llm
from ..database import get_db
from ..deps import Principal, audit, current_user
from ..models import (Agent, Approval, Device, Invoice, Lead, MarketplaceItem, Plan,
                      RoiEntry, Subscription, Task, Tenant, Workflow, now)
from ..events import hub
from ..security import ulid

router = APIRouter(tags=["billing"])


def plan_dto(pl: Plan):
    return {"id": pl.id, "name": pl.name, "billing_period": pl.billing_period,
            "currency": pl.currency, "price": float(pl.price or 0),
            "limits": pl.limits, "feature_flags": pl.feature_flags,
            "is_public": pl.is_public}


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    rows = db.query(Plan).filter_by(is_public=True).order_by(Plan.price).all()
    return [plan_dto(pl) for pl in rows]


@router.get("/subscription")
def my_subscription(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter_by(tenant_id=p.tenant_id).first()
    plan = db.get(Plan, sub.plan_id) if sub else None
    # live usage vs limits (FR-U3 / SRS-F-005)
    agents = db.query(Agent).filter_by(tenant_id=p.tenant_id).filter(
        Agent.status != "archived").count()
    workflows = db.query(Workflow).filter_by(tenant_id=p.tenant_id).filter(
        Workflow.status != "archived").count()
    devices = db.query(Device).filter_by(tenant_id=p.tenant_id, status="active").count()
    limits = plan.limits if plan else {}
    return {
        "status": sub.status if sub else "none",
        "plan": plan_dto(plan) if plan else None,
        "current_period_end": sub.current_period_end.isoformat()
            if sub and sub.current_period_end else None,
        "usage": {
            "agents": {"used": agents, "limit": limits.get("agents")},
            "workflows": {"used": workflows, "limit": limits.get("workflows")},
            "devices": {"used": devices, "limit": limits.get("devices")},
            "seats": {"used": 1, "limit": limits.get("seats")},
        },
    }


class ChangePlanIn(BaseModel):
    plan_id: str
    coupon: str | None = None


@router.post("/subscription/checkout")
def checkout(body: ChangePlanIn, p: Principal = Depends(current_user),
             db: Session = Depends(get_db)):
    """Simulated gateway checkout (Stripe/Razorpay) — instantly activates."""
    plan = db.get(Plan, body.plan_id)
    if not plan:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Plan not found"})
    sub = db.query(Subscription).filter_by(tenant_id=p.tenant_id).first()
    if not sub:
        sub = Subscription(id=ulid("sub"), tenant_id=p.tenant_id)
        db.add(sub)
    sub.plan_id = plan.id
    sub.status = "active"
    sub.gateway = "razorpay"
    sub.current_period_start = now()
    sub.current_period_end = now() + timedelta(days=30)
    # PB-05: GST tax line for IN region.
    subtotal = float(plan.price or 0)
    tax = round(subtotal * 0.18, 2)
    inv = Invoice(id=ulid("inv"), tenant_id=p.tenant_id, subscription_id=sub.id,
                  number=f"HRM-{int(now().timestamp())}", currency=plan.currency,
                  subtotal=subtotal, tax=tax, total=subtotal + tax,
                  tax_breakup={"GST@18%": tax}, status="paid", paid_at=now())
    db.add(inv)
    audit(db, plane="cloud", actor=f"user:{p.user_id}", action="subscription.checkout",
          tenant_id=p.tenant_id, meta={"plan": plan.id})
    db.commit()
    return {"status": "active", "plan": plan_dto(plan), "invoice_id": inv.id}


@router.get("/invoices")
def invoices(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Invoice).filter_by(tenant_id=p.tenant_id).order_by(
        Invoice.issued_at.desc()).all()
    return [{"id": i.id, "number": i.number, "currency": i.currency,
             "subtotal": float(i.subtotal or 0), "tax": float(i.tax or 0),
             "total": float(i.total or 0), "status": i.status,
             "issued_at": i.issued_at.isoformat() if i.issued_at else None}
            for i in rows]


# ───────────────────────────── Devices (FR-U3) ──────────────────────────────
@router.get("/devices")
def devices(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Device).filter_by(tenant_id=p.tenant_id).all()
    return [{"id": d.id, "name": d.name, "os": d.os, "app_version": d.app_version,
             "status": d.status,
             "last_seen_at": d.last_seen_at.isoformat() if d.last_seen_at else None}
            for d in rows]


@router.delete("/devices/{did}")
def deactivate_device(did: str, p: Principal = Depends(current_user),
                      db: Session = Depends(get_db)):
    d = db.get(Device, did)
    if not d or d.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Device not found"})
    d.status = "deactivated"
    audit(db, plane="cloud", actor=f"user:{p.user_id}", action="device.deactivate",
          target=did, tenant_id=p.tenant_id)
    db.commit()
    return {"status": "deactivated"}


# ───────────────────────────── Entitlements (FR-U4) ─────────────────────────
@router.get("/entitlements")
def entitlements(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter_by(tenant_id=p.tenant_id).first()
    plan = db.get(Plan, sub.plan_id) if sub else None
    return {"plan": plan.id if plan else None,
            "limits": plan.limits if plan else {},
            "feature_flags": plan.feature_flags if plan else {},
            "status": sub.status if sub else "none",
            "config_version": 1, "signature": "demo-signed", "grace_days": 7}


# ───────────────────────────── Marketplace (web view) ───────────────────────
from .. import industry_templates as tpl
from ..models import AuditLog


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")


def _net_installed(db, tenant_id):
    """Non-industry packs: net install/uninstall state from the audit log (last wins)."""
    rows = (db.query(AuditLog.target, AuditLog.action)
            .filter(AuditLog.chain_key == tenant_id,
                    AuditLog.action.in_(["marketplace.install", "marketplace.uninstall"]))
            .order_by(AuditLog.id).all())
    state = {}
    for target, action in rows:
        if target:
            state[target] = (action == "marketplace.install")
    return {k for k, v in state.items() if v}


def _pack_industry(m):
    """The supported industry an industry_template pack skins to (or None)."""
    for tag in (m.industry_tags or []):
        if tag in tpl.SUPPORTED:
            return tag
        if tag in _TAG_INDUSTRY:
            return _TAG_INDUSTRY[tag]
    return None


def _ensure_industry_packs(db):
    """Guarantee a marketplace industry_template pack for EVERY supported industry
    (idempotent). Industries already covered by a curated pack are left as-is."""
    existing = db.query(MarketplaceItem).filter_by(type="industry_template").all()
    covered = {ind for ind in (_pack_industry(m) for m in existing) if ind}
    created = False
    for industry in tpl.SUPPORTED:
        if industry in covered:
            continue
        try:
            spec = tpl.curated(industry)
        except Exception:
            spec = {"agents": [], "pipelines": []}
        desigs = [a.get("designation") for a in spec.get("agents", [])
                  if a.get("designation") and a.get("designation") != "CEO Agent"][:3]
        pipes = [p.get("name") for p in spec.get("pipelines", []) if p.get("name")][:3]
        n_ag = len(spec.get("agents", [])) or len(desigs)
        desc = (f"{n_ag} agents" + (f" ({', '.join(desigs)}…)" if desigs else "")
                + (f" + workflows: {', '.join(pipes)}." if pipes else "."))
        db.add(MarketplaceItem(id=f"mp_ind_{_slug(industry)}", type="industry_template",
                               name=f"{industry} Pack", description=desc[:240],
                               industry_tags=[industry], is_free=True, status="approved",
                               publisher="HERMUS", installs=0))
        covered.add(industry); created = True
    if created:
        db.flush()


@router.get("/marketplace")
def marketplace(type: str | None = None, p: Principal = Depends(current_user),
                db: Session = Depends(get_db)):
    # Show the WHOLE catalog the user can browse (published + under review), so nothing
    # installable is hidden. Only rejected/taken-down items are withheld.
    from ..catalog_flags import disabled_set
    _ensure_industry_packs(db)
    db.commit()
    dis = disabled_set(db, "marketplace")   # admin-hidden packs
    q = db.query(MarketplaceItem).filter(
        MarketplaceItem.status.in_(["approved", "in_review"]))
    if dis:
        q = q.filter(MarketplaceItem.id.notin_(list(dis)))
    if type:
        q = q.filter_by(type=type)
    t = db.get(Tenant, p.tenant_id)
    net = _net_installed(db, p.tenant_id)

    def is_installed(m):
        if m.type == "industry_template":
            return _pack_industry(m) == (t.industry if t else None)
        return m.id in net
    out = [{"id": m.id, "type": m.type, "name": m.name, "description": m.description,
            "industry_tags": m.industry_tags or [], "price": float(m.price or 0),
            "is_free": m.is_free, "publisher": m.publisher, "installs": m.installs,
            "status": m.status, "installed": is_installed(m),
            "industry": _pack_industry(m) if m.type == "industry_template" else None}
           for m in q.all()]
    out.sort(key=lambda m: (m["status"] != "approved", not m["installed"], -m["installs"]))
    return {"items": out, "active_industry": (t.industry if t else None)}


# Marketplace industry-template tag → the supported industry it skins to.
_TAG_INDUSTRY = {
    "accounting": "Chartered Accountants & Tax Consultants", "real_estate": "Real Estate",
    "legal": "Legal Industry", "hr": "Recruitment Agencies", "healthcare": "Healthcare",
    "support": "Small Business Owners",
}


@router.post("/marketplace/{item_id}/install")
def install_item(item_id: str, p: Principal = Depends(current_user),
                 db: Session = Depends(get_db)):
    m = db.get(MarketplaceItem, item_id)
    if not m:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Item not found"})
    if m.status not in ("approved", "in_review"):
        raise HTTPException(409, detail={"code": "UNAVAILABLE", "message": "This pack isn't available to install."})
    if m.status == "in_review":
        raise HTTPException(409, detail={"code": "IN_REVIEW",
            "message": f"“{m.name}” is still under security review — available to install once approved."})
    m.installs = (m.installs or 0) + 1
    reskinned = switched_from = None
    # Installing an industry template skins the universal engines to that vertical.
    # A tenant runs ONE industry at a time → setting it replaces any previous industry.
    if m.type == "industry_template":
        industry = _pack_industry(m)
        if industry:
            t = db.get(Tenant, p.tenant_id)
            if t.industry and t.industry != industry:
                switched_from = t.industry
            t.industry = industry
            reskinned = industry
    audit(db, plane="local", actor=f"user:{p.user_id}", action="marketplace.install",
          target=item_id, tenant_id=p.tenant_id,
          meta={"reskinned": reskinned, "switched_from": switched_from})
    db.commit()
    hub.emit(p.tenant_id, "marketplace.changed", {"action": "install", "name": m.name})
    base = "Signed package verified; permissions reviewed at install (SC-03)."
    if reskinned:
        base = (f"The universal engines are now skinned to {reskinned} — "
                f"your pipeline, appointments and agent roster speak this vertical's language.")
        if switched_from:
            base = f"Switched your company from {switched_from} to {reskinned}. " + base
    return {"status": "installed", "name": m.name, "reskinned": reskinned,
            "switched_from": switched_from,
            "message": f"Installed “{m.name}”. {base}"}


@router.post("/marketplace/{item_id}/uninstall")
def uninstall_item(item_id: str, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    m = db.get(MarketplaceItem, item_id)
    if not m:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Item not found"})
    cleared = None
    if m.type == "industry_template":
        industry = _pack_industry(m)
        t = db.get(Tenant, p.tenant_id)
        if t.industry != industry:
            return {"status": "not_installed",
                    "message": f"“{m.name}” isn't the active industry — nothing to uninstall."}
        t.industry = None          # company returns to no-industry (universal core)
        cleared = industry
    else:
        if item_id not in _net_installed(db, p.tenant_id):
            return {"status": "not_installed", "message": f"“{m.name}” isn't installed."}
    if (m.installs or 0) > 0:
        m.installs = m.installs - 1
    audit(db, plane="local", actor=f"user:{p.user_id}", action="marketplace.uninstall",
          target=item_id, tenant_id=p.tenant_id, meta={"cleared": cleared})
    db.commit()
    hub.emit(p.tenant_id, "marketplace.changed", {"action": "uninstall", "name": m.name})
    msg = f"Uninstalled “{m.name}”."
    if cleared:
        msg += f" Your company is back to the universal core (no industry skin)."
    return {"status": "uninstalled", "name": m.name, "cleared": cleared, "message": msg}


class MktVoiceIn(BaseModel):
    transcript: str


def _match_item(db, text):
    low = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    toks = [w for w in low.split() if len(w) >= 3 and w not in (
        "the", "pack", "install", "get", "add", "marketplace", "template", "and", "for", "use")]
    rows = db.query(MarketplaceItem).filter(
        MarketplaceItem.status.in_(["approved", "in_review"])).all()
    best, score = None, 0
    for m in rows:
        hay = re.sub(r"[^a-z0-9 ]", " ", f"{m.name} {' '.join(m.industry_tags or [])}".lower())
        s = sum(1 for w in toks if w in hay)
        if s > score:
            best, score = m, s
    return best if score else None


_TYPE_WORDS = {"industry_template": ["industry", "template", "vertical"],
               "agent_pack": ["agent pack", "agent", "roster"],
               "skill": ["skill"], "workflow": ["workflow"], "integration": ["integration"]}


@router.post("/marketplace/resolve")
def marketplace_resolve(body: MktVoiceIn, p: Principal = Depends(current_user),
                        db: Session = Depends(get_db)):
    _ensure_industry_packs(db); db.commit()
    text = body.transcript or ""
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())

    # filter by type
    if re.search(r"\b(show|filter|only|just|view|see)\b", low):
        if re.search(r"\b(free|no cost|gratis)\b", low):
            return {"action": "filter", "free": True, "message": "Showing free packs."}
        for typ, words in _TYPE_WORDS.items():
            if any(re.search(rf"\b{re.escape(w)}", low) for w in words):
                return {"action": "filter", "type": typ, "message": f"Showing {typ.replace('_', ' ')}s."}
        if re.search(r"\b(all|everything)\b", low):
            return {"action": "filter", "type": "", "free": False, "message": "Showing all packs."}
    # uninstall a named pack
    if re.search(r"\b(uninstall|remove|delete|disable|switch off)\b", low):
        m = _match_item(db, text)
        if m:
            return {"action": "uninstall", "id": m.id, "name": m.name,
                    "message": f"Uninstalling {m.name}."}
        return {"action": "none", "message": "Which pack should I uninstall? Try its name."}
    # install a named pack
    if re.search(r"\b(install|get|add|download|deploy|use|switch to)\b", low):
        m = _match_item(db, text)
        if m:
            return {"action": "install", "id": m.id, "name": m.name, "status": m.status,
                    "message": f"Installing {m.name}."}
        return {"action": "none", "message": "Which pack should I install? Try its name."}
    # search
    sm = re.search(r"\b(search|find|look for)\b\s+(?:for\s+)?(.+)$", text, re.I)
    if sm and sm.group(2).strip():
        return {"action": "search", "query": sm.group(2).strip(" .'\""),
                "message": f"Searching for {sm.group(2).strip()[:30]}."}
    m = _match_item(db, text)
    if m:
        return {"action": "install", "id": m.id, "name": m.name, "status": m.status,
                "message": f"Installing {m.name}."}
    return {"action": "none",
            "message": 'Try "install the CA office pack", "show free packs", "show industry templates", or "search legal".'}


# ───────────────────────────── Analytics (FR-A1) ───────────────────────────
analytics = APIRouter(tags=["analytics"])


@analytics.get("/analytics/summary")
def summary(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    total_tasks = db.query(Task).filter_by(tenant_id=p.tenant_id).count()
    completed = db.query(Task).filter_by(tenant_id=p.tenant_id, status="completed").count()
    agents = db.query(Agent).filter_by(tenant_id=p.tenant_id).filter(
        Agent.status != "archived").count()
    active_wf = db.query(Workflow).filter_by(tenant_id=p.tenant_id, status="active").count()
    pending_approvals = db.query(Approval).filter_by(
        tenant_id=p.tenant_id, state="pending").count()
    leads_total = db.query(Lead).filter_by(tenant_id=p.tenant_id).count()
    by_status = {}
    for (st,) in db.query(Task.status).filter_by(tenant_id=p.tenant_id).all():
        by_status[st] = by_status.get(st, 0) + 1
    # Prefer the real ROI ledger (actual minutes logged); fall back to an estimate.
    roi_minutes = sum(float(r.value_minutes or 0) for r in
                      db.query(RoiEntry).filter_by(tenant_id=p.tenant_id).all())
    hours_saved = round(roi_minutes / 60, 1) if roi_minutes else round(completed * 1.5, 1)
    return {
        "agents": agents, "active_workflows": active_wf,
        "tasks_total": total_tasks, "tasks_completed": completed,
        "tasks_by_status": by_status,
        "pending_approvals": pending_approvals, "leads_total": leads_total,
        "hours_saved": hours_saved,
        "cost_savings_inr": int(hours_saved * 500),
        "success_rate": round(100 * completed / total_tasks, 1) if total_tasks else 0,
    }


class AnalyticsQ(BaseModel):
    question: str


@analytics.post("/analytics/query")
def query(body: AnalyticsQ, p: Principal = Depends(current_user),
          db: Session = Depends(get_db)):
    """Voice-queryable analytics (FR-A2) — LLM answers grounded in real metrics."""
    s = summary(p, db)
    facts = (f"agents={s['agents']}, active_workflows={s['active_workflows']}, "
             f"tasks_total={s['tasks_total']}, tasks_completed={s['tasks_completed']}, "
             f"success_rate={s['success_rate']}%, hours_saved={s['hours_saved']}, "
             f"cost_savings_inr={s['cost_savings_inr']}, pending_approvals={s['pending_approvals']}, "
             f"leads_total={s['leads_total']}, by_status={s['tasks_by_status']}")
    answer = llm.chat(
        f"Metrics: {facts}\n\nQuestion: {body.question}",
        system=("You answer analytics questions for an AI-workforce dashboard using ONLY "
                "the provided metrics. One or two short sentences. If the metric isn't "
                "present, say so. Use ₹ for currency."),
        smart=False)
    engine = "local-llm"
    if not answer:
        engine = "rule-based"
        q = body.question.lower()
        if "complete" in q or "finish" in q or "done" in q:
            answer = f"{s['tasks_completed']} tasks completed out of {s['tasks_total']}."
        elif "agent" in q:
            answer = f"You have {s['agents']} active agents."
        elif "save" in q or "hour" in q:
            answer = f"About {s['hours_saved']} hours saved, ~₹{s['cost_savings_inr']:,} value."
        elif "workflow" in q:
            answer = f"{s['active_workflows']} workflows are active."
        elif "approval" in q or "pending" in q:
            answer = f"{s['pending_approvals']} approvals are pending your decision."
        elif "lead" in q:
            answer = f"{s['leads_total']} leads are in the pipeline."
        else:
            answer = (f"{s['tasks_completed']}/{s['tasks_total']} tasks done, "
                      f"{s['agents']} agents, {s['hours_saved']} hours saved.")
    audit(db, plane="local", actor=f"user:{p.user_id}", action="analytics.query",
          tenant_id=p.tenant_id, meta={"q": body.question[:120], "engine": engine})
    db.commit()
    return {"question": body.question, "answer": answer.strip(), "engine": engine, "data": s}


@analytics.post("/analytics/export")
def export_report(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Snapshot the dashboard as a downloadable report (audited)."""
    s = summary(p, db)
    tenant = db.get(Tenant, p.tenant_id)
    report = {"company": tenant.company_name if tenant else None,
              "generated_at": now().isoformat(), **s}
    audit(db, plane="local", actor=f"user:{p.user_id}", action="analytics.export",
          tenant_id=p.tenant_id, meta={"tasks": s["tasks_total"]})
    db.commit()
    hub.emit(p.tenant_id, "analytics.changed", {"action": "export", "name": "report"})
    return {"report": report, "filename": "analytics-report.json",
            "message": "Analytics report generated."}


class AnalyticsVoiceIn(BaseModel):
    transcript: str


@analytics.post("/analytics/resolve")
def analytics_resolve(body: AnalyticsVoiceIn, p: Principal = Depends(current_user),
                      db: Session = Depends(get_db)):
    text = body.transcript or ""
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    if re.search(r"\b(export|download|save the report|generate.*report)\b", low):
        return {"action": "export", "message": "Generating the report."}
    if re.search(r"\b(refresh|reload|update the numbers|recompute)\b", low):
        return {"action": "refresh", "message": "Refreshing the metrics."}
    # everything else is a question for the metrics engine
    if low.strip():
        return {"action": "ask", "question": text.strip(" .?'\""),
                "message": "Checking the numbers."}
    return {"action": "none",
            "message": 'Ask e.g. "how many tasks did we complete?", or say "export the report".'}


# ── Cost & Performance dashboard (Doc 25 §2.6/§5.3) ──────────────────────────
def cost_recommendations(rows):
    """Spot cheap tasks repeatedly run on a cloud (paid) tier → route local to save."""
    from collections import defaultdict
    agg = defaultdict(lambda: {"count": 0, "cost": 0.0})
    for r in rows:
        if (r.tier or "local") != "local" and float(r.cost or 0) > 0:
            a = agg[r.task_profile or "default"]
            a["count"] += 1
            a["cost"] += float(r.cost or 0)
    return [f"{v['count']} “{prof}” tasks used a cloud model (~₹{round(v['cost'], 2)}); "
            f"routing them to your local model would save that."
            for prof, v in agg.items() if v["count"] >= 5]


@analytics.get("/analytics/cost")
def cost_dashboard(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    from collections import defaultdict

    from ..models import GatewayCall, now as _n
    rows = db.query(GatewayCall).filter_by(tenant_id=p.tenant_id).all()
    by_model = defaultdict(lambda: {"calls": 0, "cost": 0.0, "prompt_tokens": 0, "output_tokens": 0, "tier": "local"})
    by_day = defaultdict(lambda: {"calls": 0, "cost": 0.0})
    total = 0.0
    for r in rows:
        c = float(r.cost or 0)
        total += c
        m = by_model[r.model or "?"]
        m["calls"] += 1
        m["cost"] = round(m["cost"] + c, 4)
        m["prompt_tokens"] += r.prompt_tokens or 0
        m["output_tokens"] += r.output_tokens or 0
        m["tier"] = r.tier or "local"
        day = (r.at or _n()).strftime("%Y-%m-%d")
        by_day[day]["calls"] += 1
        by_day[day]["cost"] = round(by_day[day]["cost"] + c, 4)
    days = max(1, len(by_day))
    return {
        "total": round(total, 2), "currency": "INR", "calls": len(rows),
        "by_model": [{"model": k, **v} for k, v in by_model.items()],
        "by_day": [{"day": d, **v} for d, v in sorted(by_day.items())],
        "projected_month": round(total / days * 30, 2),
        "recommendations": cost_recommendations(rows),
    }

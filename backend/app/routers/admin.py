"""Product Admin API (/admin/*) — admin JWT + role scopes; four-eyes on destructive."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, audit, current_admin, require_role
import hashlib
import json

from ..models import (AdminApproval, AuditLog, ConfigBundle, ConfigItem, Invoice,
                      MarketplaceItem, Plan, Release, Subscription, Tenant, User, now)
from ..security import ulid

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/me")
def admin_me(p: Principal = Depends(current_admin)):
    return {"id": p.user_id, "email": p.email, "roles": p.roles}


@router.get("/analytics")
def admin_analytics(p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    tenants = db.query(Tenant).count()
    active = db.query(Tenant).filter_by(status="active").count()
    pending = db.query(Tenant).filter_by(status="pending_approval").count()
    paid_subs = db.query(Subscription).filter(
        Subscription.status.in_(["active", "past_due"])).all()
    mrr = 0.0
    for sub in paid_subs:
        pl = db.get(Plan, sub.plan_id)
        if pl and pl.billing_period == "monthly":
            mrr += float(pl.price or 0)
        elif pl and pl.billing_period == "yearly":
            mrr += float(pl.price or 0) / 12
    revenue = db.query(func.coalesce(func.sum(Invoice.total), 0)).filter_by(
        status="paid").scalar()
    plan_mix = {}
    for sub in db.query(Subscription).all():
        pl = db.get(Plan, sub.plan_id)
        nm = pl.name if pl else sub.plan_id
        plan_mix[nm] = plan_mix.get(nm, 0) + 1
    return {"tenants": tenants, "active_tenants": active, "pending_approval": pending,
            "mrr": round(mrr, 2), "arr": round(mrr * 12, 2),
            "total_revenue": float(revenue or 0), "plan_mix": plan_mix,
            "open_admin_approvals": db.query(AdminApproval).filter_by(
                state="pending").count()}


@router.get("/tenants")
def tenants(status: str | None = None, search: str | None = None,
            p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    require_role(p, "support", "finance", "catalog")
    q = db.query(Tenant)
    if status:
        q = q.filter_by(status=status)
    if search:
        q = q.filter(Tenant.company_name.ilike(f"%{search}%"))
    out = []
    for t in q.order_by(Tenant.created_at.desc()).all():
        sub = db.query(Subscription).filter_by(tenant_id=t.id).first()
        pl = db.get(Plan, sub.plan_id) if sub else None
        owner = db.get(User, t.owner_user_id)
        out.append({"id": t.id, "company_name": t.company_name, "industry": t.industry,
                    "region": t.region, "status": t.status,
                    "owner_email": owner.email if owner else None,
                    "plan": pl.name if pl else None,
                    "sub_status": sub.status if sub else None,
                    "created_at": t.created_at.isoformat() if t.created_at else None})
    return out


@router.post("/tenants/{tid}/{action}")
def tenant_action(tid: str, action: str, p: Principal = Depends(current_admin),
                  db: Session = Depends(get_db)):
    require_role(p, "support")
    t = db.get(Tenant, tid)
    if not t:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Tenant not found"})
    mapping = {"approve": "active", "reject": "closed", "suspend": "suspended",
               "reactivate": "active"}
    if action not in mapping:
        raise HTTPException(422, detail={"code": "VALIDATION_ERROR", "message": "Bad action"})
    t.status = mapping[action]
    audit(db, plane="cloud", actor=f"admin:{p.user_id}", action=f"tenant.{action}",
          target=tid)
    db.commit()
    return {"id": tid, "status": t.status}


# ───────────────────────────── Plans (UC-S10) ───────────────────────────────
@router.get("/plans")
def admin_plans(p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    return [{"id": pl.id, "name": pl.name, "billing_period": pl.billing_period,
             "currency": pl.currency, "price": float(pl.price or 0),
             "limits": pl.limits, "feature_flags": pl.feature_flags,
             "is_public": pl.is_public} for pl in db.query(Plan).all()]


class PlanIn(BaseModel):
    name: str
    billing_period: str = "monthly"
    currency: str = "INR"
    price: float = 0
    limits: dict
    feature_flags: dict
    is_public: bool = True


@router.post("/plans")
def create_plan(body: PlanIn, p: Principal = Depends(current_admin),
                db: Session = Depends(get_db)):
    require_role(p, "finance")
    pl = Plan(id=ulid("pln"), name=body.name, billing_period=body.billing_period,
              currency=body.currency, price=body.price, limits=body.limits,
              feature_flags=body.feature_flags, is_public=body.is_public)
    db.add(pl)
    audit(db, plane="cloud", actor=f"admin:{p.user_id}", action="plan.create", target=pl.id)
    db.commit()
    return {"id": pl.id, "name": pl.name}


class PlanPatch(BaseModel):
    price: float | None = None
    limits: dict | None = None
    feature_flags: dict | None = None
    is_public: bool | None = None


@router.patch("/plans/{pid}")
def update_plan(pid: str, body: PlanPatch, p: Principal = Depends(current_admin),
                db: Session = Depends(get_db)):
    require_role(p, "finance")
    pl = db.get(Plan, pid)
    if not pl:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Plan not found"})
    for f, v in body.model_dump(exclude_none=True).items():
        setattr(pl, f, v)
    audit(db, plane="cloud", actor=f"admin:{p.user_id}", action="plan.update", target=pid)
    db.commit()
    return {"id": pid, "name": pl.name}


# ───────────────────────────── Common Config (UC-S12) ───────────────────────
@router.get("/configs")
def configs(p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    rows = db.query(ConfigItem).filter_by(active=True).all()
    grouped = {}
    for c in rows:
        grouped.setdefault(c.domain, []).append(
            {"id": c.id, "key": c.key, "value": c.value, "scope": c.scope})
    return grouped


class ConfigIn(BaseModel):
    domain: str
    key: str
    value: dict
    scope: str = "overridable"


@router.put("/configs")
def upsert_config(body: ConfigIn, p: Principal = Depends(current_admin),
                  db: Session = Depends(get_db)):
    require_role(p, "catalog")
    c = db.query(ConfigItem).filter_by(domain=body.domain, key=body.key).first()
    if not c:
        c = ConfigItem(id=ulid("cfg"), domain=body.domain, key=body.key)
        db.add(c)
    c.value = body.value
    c.scope = body.scope
    c.active = True
    audit(db, plane="cloud", actor=f"admin:{p.user_id}", action="config.upsert",
          target=f"{body.domain}/{body.key}")
    db.commit()
    return {"id": c.id, "domain": c.domain, "key": c.key, "scope": c.scope,
            "message": f"Saved {body.domain}/{body.key} ({body.scope})."}


class PublishIn(BaseModel):
    stage: str = "canary"   # canary | publish


@router.post("/configs/publish")
def publish_bundle(body: PublishIn, p: Principal = Depends(current_admin),
                   db: Session = Depends(get_db)):
    """Snapshot all active config items into a signed, versioned bundle (canary→publish)."""
    require_role(p, "catalog")
    items = db.query(ConfigItem).filter_by(active=True).all()
    manifest = {"items": [{"domain": c.domain, "key": c.key, "value": c.value,
                           "scope": c.scope} for c in items]}
    sha = hashlib.sha256(json.dumps(manifest, sort_keys=True, default=str).encode()).hexdigest()
    last = db.query(ConfigBundle).order_by(ConfigBundle.version.desc()).first()
    ver = (last.version + 1) if last else 1
    state = "canary" if body.stage == "canary" else "published"
    b = ConfigBundle(version=ver, manifest=manifest, sha256=sha, state=state,
                     published_at=now() if state == "published" else None)
    db.add(b)
    audit(db, plane="cloud", actor=f"admin:{p.user_id}", action=f"config.{state}",
          target=f"bundle-v{ver}", meta={"sha256": sha[:16], "items": len(items)})
    db.commit()
    return {"version": ver, "state": state, "sha256": sha[:16], "items": len(items),
            "message": (f"Bundle v{ver} rolled to canary (5%) — auto-halts if error rate exceeds threshold."
                        if state == "canary" else f"Bundle v{ver} published to the fleet ({len(items)} items, signed {sha[:12]}).")}


@router.get("/configs/bundles")
def list_bundles(p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    rows = db.query(ConfigBundle).order_by(ConfigBundle.version.desc()).limit(10).all()
    return [{"version": b.version, "state": b.state, "sha256": (b.sha256 or "")[:16],
             "published_at": b.published_at.isoformat() if b.published_at else None} for b in rows]


# ───────────────────────────── Hermes Agent fleet defaults ───────────────────
# The product-admin sets the DEFAULT Hermes agent configuration every tenant
# inherits (tenants override per-tenant in Settings). Reuses the same schema,
# options and validation as the per-tenant config (voice.py).
def _hermes_row(db):
    return db.query(ConfigItem).filter_by(domain="hermes_defaults", key="agent_config").first()


@router.get("/hermes")
def get_hermes_defaults(p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    from .voice import DEFAULT_AGENT_CONFIG, _OPTIONS, platform_agent_defaults
    from .. import llm
    platform = platform_agent_defaults(db)
    effective = {**DEFAULT_AGENT_CONFIG, **platform}
    row = _hermes_row(db)
    return {
        "code_defaults": DEFAULT_AGENT_CONFIG,   # the built-in baseline
        "platform": platform,                    # admin overrides (only changed keys)
        "effective": effective,                  # what new tenants actually inherit
        "options": _OPTIONS,
        "installed_models": llm.list_models(),
        "runtime_online": llm.available(),
        "customized": bool(row and row.value),
    }


class HermesPatch(BaseModel):
    config: dict


@router.patch("/hermes")
def patch_hermes_defaults(body: HermesPatch, p: Principal = Depends(current_admin),
                          db: Session = Depends(get_db)):
    require_role(p, "catalog")
    from .voice import DEFAULT_AGENT_CONFIG, _coerce
    row = _hermes_row(db)
    current = dict(row.value) if (row and isinstance(row.value, dict)) else {}
    changed = []
    for k, v in (body.config or {}).items():
        if k not in DEFAULT_AGENT_CONFIG:
            continue
        try:
            current[k] = _coerce(k, v)
            changed.append(k)
        except (ValueError, TypeError) as e:
            raise HTTPException(422, detail={"code": "BAD_VALUE", "message": str(e)})
    if not row:
        row = ConfigItem(id=ulid("cfg"), domain="hermes_defaults", key="agent_config",
                         scope="overridable", active=True)
        db.add(row)
    row.value = current
    row.active = True
    audit(db, plane="cloud", actor=f"admin:{p.user_id}", action="hermes.defaults_update",
          target="hermes_defaults/agent_config", meta={"fields": changed})
    db.commit()
    return {"platform": current, "fields": changed,
            "message": f"Fleet default(s) updated: {', '.join(changed) or 'none'}. "
                       f"Every tenant inherits these (unless they override)."}


@router.post("/hermes/reset")
def reset_hermes_defaults(p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    require_role(p, "catalog")
    row = _hermes_row(db)
    if row:
        row.value = {}
    audit(db, plane="cloud", actor=f"admin:{p.user_id}", action="hermes.defaults_reset", target="hermes_defaults")
    db.commit()
    from .voice import DEFAULT_AGENT_CONFIG
    return {"platform": {}, "effective": DEFAULT_AGENT_CONFIG,
            "message": "Fleet Hermes defaults reset to the built-in baseline."}


# ───────────────────────────── Releases (UC-S14) ────────────────────────────
@router.get("/releases")
def releases(p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    rows = db.query(Release).order_by(Release.created_at.desc()).all()
    return [{"id": r.id, "version": r.version, "channel": r.channel,
             "rollout_percent": r.rollout_percent, "state": r.state,
             "force_floor": r.force_floor, "notes_md": r.notes_md} for r in rows]


class RolloutIn(BaseModel):
    rollout_percent: int
    state: str | None = None


@router.patch("/releases/{rid}/rollout")
def rollout(rid: str, body: RolloutIn, p: Principal = Depends(current_admin),
            db: Session = Depends(get_db)):
    require_role(p, "super")
    r = db.get(Release, rid)
    if not r:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Release not found"})
    r.rollout_percent = max(0, min(100, body.rollout_percent))
    r.state = body.state or ("complete" if r.rollout_percent >= 100 else "rolling")
    audit(db, plane="cloud", actor=f"admin:{p.user_id}", action="release.rollout",
          target=rid, meta={"pct": r.rollout_percent})
    db.commit()
    return {"id": rid, "rollout_percent": r.rollout_percent, "state": r.state,
            "message": f"v{r.version} rollout set to {r.rollout_percent}% ({r.state})."}


# ───────────────────────────── Marketplace Admin (UC-S13) ───────────────────
@router.get("/marketplace")
def admin_marketplace(p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    rows = db.query(MarketplaceItem).all()
    return [{"id": m.id, "name": m.name, "type": m.type, "status": m.status,
             "publisher": m.publisher, "installs": m.installs,
             "price": float(m.price or 0)} for m in rows]


@router.post("/marketplace/{item_id}/review")
def review_item(item_id: str, decision: str, p: Principal = Depends(current_admin),
                db: Session = Depends(get_db)):
    require_role(p, "catalog")
    m = db.get(MarketplaceItem, item_id)
    if not m:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Item not found"})
    m.status = "approved" if decision == "approve" else "rejected"
    audit(db, plane="cloud", actor=f"admin:{p.user_id}", action=f"marketplace.{m.status}",
          target=item_id)
    db.commit()
    return {"id": item_id, "status": m.status,
            "message": f"“{m.name}” {m.status}."}


# ───────────────────────────── Catalog control (all 4 sections) ─────────────
# The admin's master switches: what's visible/usable across verticals, solutions,
# universal engines and marketplace. Plus admin can publish new marketplace packs.
@router.get("/catalog")
def admin_catalog(p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    from ..catalog_flags import disabled_set
    from .verticals import VERTICALS
    from .solutions import SOLUTIONS
    from .universal import ENGINES
    dv, ds, de, dm = (disabled_set(db, s) for s in ("verticals", "solutions", "engines", "marketplace"))
    mk = db.query(MarketplaceItem).all()
    return {
        "verticals": [{"id": v["id"], "name": v["name"], "industry": v.get("industry"),
                       "enabled": v["id"] not in dv} for v in VERTICALS],
        "solutions": [{"id": s["id"], "name": s["name"], "target": s.get("target"),
                       "enabled": s["id"] not in ds} for s in SOLUTIONS],
        "engines": [{"id": e[0], "name": e[1], "status": e[4], "enabled": e[0] not in de}
                    for e in ENGINES],
        "marketplace": [{"id": m.id, "name": m.name, "type": m.type, "status": m.status,
                         "publisher": m.publisher, "installs": m.installs,
                         "enabled": m.id not in dm} for m in mk],
    }


class CatalogToggleIn(BaseModel):
    enabled: bool


@router.post("/catalog/{section}/{item_id}/toggle")
def toggle_catalog(section: str, item_id: str, body: CatalogToggleIn,
                   p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    require_role(p, "catalog")
    from ..catalog_flags import SECTIONS, set_enabled
    if section not in SECTIONS:
        raise HTTPException(404, detail={"code": "BAD_SECTION", "message": "Unknown catalog section."})
    set_enabled(db, section, item_id, body.enabled)
    audit(db, plane="cloud", actor=f"admin:{p.user_id}",
          action=f"catalog.{'enable' if body.enabled else 'disable'}",
          target=f"{section}/{item_id}")
    db.commit()
    return {"section": section, "id": item_id, "enabled": body.enabled,
            "message": f"{section[:-1].capitalize()} “{item_id}” {'enabled — now visible to users' if body.enabled else 'disabled — hidden from all users'}."}


class MarketCreateIn(BaseModel):
    name: str
    type: str = "skill"          # industry_template|agent_pack|skill|workflow|integration
    description: str = ""
    industry_tags: list[str] = []
    is_free: bool = True
    price: float = 0
    publish: bool = True         # straight to approved (admin-published) vs in_review


@router.post("/marketplace")
def admin_create_market_item(body: MarketCreateIn, p: Principal = Depends(current_admin),
                             db: Session = Depends(get_db)):
    """Admin authors & publishes a marketplace pack → instantly available to all tenants."""
    require_role(p, "catalog")
    if not body.name.strip():
        raise HTTPException(422, detail={"code": "BAD_NAME", "message": "A name is required."})
    m = MarketplaceItem(id=ulid("mp"), type=body.type, name=body.name.strip(),
                        description=body.description, industry_tags=body.industry_tags,
                        is_free=body.is_free, price=body.price,
                        status="approved" if body.publish else "in_review",
                        publisher="HERMUS", installs=0)
    db.add(m)
    audit(db, plane="cloud", actor=f"admin:{p.user_id}", action="marketplace.create",
          target=m.id, meta={"name": body.name, "published": body.publish})
    db.commit()
    return {"id": m.id, "status": m.status,
            "message": f"“{m.name}” {'published — live for all tenants' if body.publish else 'created (in review)'}."}


# ───────────────────────────── Audit (B6) ───────────────────────────────────
@router.get("/audit")
def admin_audit(limit: int = 100, p: Principal = Depends(current_admin),
                db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(AuditLog.at.desc()).limit(limit).all()
    return [{"id": a.id, "plane": a.plane, "actor": a.actor, "action": a.action,
             "target": a.target, "tenant_id": a.tenant_id, "meta": a.meta,
             "at": a.at.isoformat() if a.at else None} for a in rows]

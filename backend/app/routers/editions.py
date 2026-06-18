"""
Editions — sub-products of the one engine (Docs 19/20). An Edition is a packaged
configuration (roster + module flags + branding skin + price book), defined and
published from the product admin dashboard. "HERMUS Personal", industry editions
and role apps are all Editions — no code fork.

User side: list published editions, activate one (deploys its roster + skin).
Admin side: create / edit / publish / retire editions — the "everything is
configurable from admin" factory.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import industry_templates as tpl
from ..database import get_db
from ..deps import Principal, audit, current_admin, current_user, require_role
from ..models import (Agent, Edition, EditionDeployment, Pipeline, Recipe,
                      Tenant)
from ..routers.company import ApplyIn, apply_suggestion
from ..routers.recipes import _BYID as RECIPE_BYID
from ..security import ulid

router = APIRouter(tags=["editions"])

# ── The module catalog (Doc 19 Part 2) — every Edition is a subset of these ───
# Each module is a flag; the admin Edition builder toggles them on/off.
MODULES = [
    ("M1", "Voice Interface", "core"), ("M2", "CEO-Agent Orchestrator", "core"),
    ("M3", "Agent Roster & Org Chart", "core"), ("M4", "Approval Chains", "core"),
    ("M5", "Second Brain (memory)", "core"), ("M6", "Knowledge Graph", "core"),
    ("M7", "Agent Messaging Bus", "core"), ("M8", "Daily Briefing + ROI Ledger", "core"),
    ("M9", "Subscription/Billing", "core"), ("M10", "Local-LLM Runtime", "core"),
    ("M11", "Workflow Engine", "functional"), ("M12", "Scheduling / Autonomous tasks", "functional"),
    ("M13", "Communication Hub", "functional"), ("M14", "Channel Connectors", "functional"),
    ("M15", "AI Call Center", "premium"), ("M16", "Document Factory", "functional"),
    ("M17", "Receivables / Collections", "functional"), ("M18", "Compliance Calendar", "functional"),
    ("M19", "Analytics + ROI", "functional"), ("M20", "Marketplace", "functional"),
    ("M21", "Skill Builder", "pro"), ("M22", "Browser & Computer Automation", "pro"),
    ("M23", "Integrations (MCP)", "functional"), ("M24", "Rehearsal Mode", "functional"),
    ("M25", "Import Wizard", "functional"), ("M26", "Backup & Restore", "functional"),
    ("M27", "Eval / Quality Layer", "functional"), ("M28", "Multi-User RBAC", "business"),
    ("M29", "Multi-Computer Agent Network", "enterprise"), ("M30", "Offline Enterprise Mode", "enterprise"),
    ("M31", "BYOK — Bring Your Own Key", "cross"), ("M32", "Model Gateway tiers", "cross"),
    ("M33", "Remote Command Channels", "functional"), ("M34", "Glass-Box Agent Console", "pro"),
    ("M35", "Confidential / Tamper-evident pack", "enterprise"),
    ("M36", "Dictation (Voice Type)", "functional"),   # the daily-habit hook (chat addition)
]
MODULE_BYID = {m[0]: {"id": m[0], "name": m[1], "group": m[2]} for m in MODULES}

# Universal engines (kept in sync with universal.py) for the builder's picker.
ENGINES = [
    ("E1", "Inquiry Pipeline"), ("E2", "Follow-Up Sequencer"), ("E3", "Appointment Engine"),
    ("E4", "Document Factory"), ("E5", "Receivables Engine"), ("E6", "Compliance Calendar"),
    ("E7", "Front Desk"), ("E8", "Daily Briefing + ROI Ledger"),
]


# ── seed: HERMUS Personal + the Wave-1 profession packs (Docs 19/20 + chat) ───
# Each pack is the universal personal core, skinned and rule-locked for a solo
# professional. All are Editions — no code fork.
_BASE_MODULES = ["M1", "M2", "M3", "M4", "M5", "M6", "M8", "M11", "M12", "M13",
                 "M16", "M20", "M24", "M25", "M26", "M31", "M33", "M36"]
_PRO_HIDDEN = ["/verticals", "/solutions", "/gateway", "/reliability"]
_CONSUMER_HIDDEN = _PRO_HIDDEN + ["/leads", "/visits", "/compliance", "/remote"]
_ROLE_PRICE = {
    "plans": [
        {"name": "Free", "price_inr": 0, "price_usd": 0, "scope": "1 agent, limited tasks/mo, local only"},
        {"name": "Personal", "price_inr": 1999, "price_usd": 29, "scope": "Full pack, 1 device, BYOK allowed"},
        {"name": "Pro", "price_inr": 3999, "price_usd": 59, "scope": "+ call answering / automation, 2 devices"},
    ],
    "byok_discount_pct": 18,
}

# slug, name, template_key, layer, tagline, brand, engines, +modules, locked_rules, hidden_nav, price, default, sort
_EDITIONS = [
    dict(slug="personal", name="HERMUS Personal", template_key="Personal Productivity Assistant",
         tagline="Your private AI assistant — captures, remembers, reminds and briefs you. Runs on your machine.",
         brand="HERMUS Personal", engines=["E2", "E3", "E4", "E7", "E8"], add=[],
         locked=["PP-R2", "PP-R3", "PP-R4"], hidden=["/leads", "/visits", "/compliance", "/remote"] + _PRO_HIDDEN,
         price=_ROLE_PRICE, default=True, sort=10),
    dict(slug="doctors", name="HERMUS for Doctors", template_key="Healthcare",
         tagline="Your AI front desk + dictation + recall — answers the phone while you're with a patient. 100% on your machine.",
         brand="HERMUS · Doctor", engines=["E1", "E2", "E3", "E7", "E8"], add=["M15"],
         locked=["HC-R1", "HC-R2", "HC-R3", "HC-R4"], hidden=_PRO_HIDDEN, price=_ROLE_PRICE, sort=20),
    dict(slug="ca", name="HERMUS for Accountants", template_key="Chartered Accountants & Tax Consultants",
         tagline="Chase client documents, never miss a GST/TDS deadline, and chase fees — every figure source-cited.",
         brand="HERMUS · CA", engines=["E1", "E2", "E4", "E5", "E6", "E8"], add=["M17", "M18"],
         locked=[], hidden=_PRO_HIDDEN, price=_ROLE_PRICE, sort=30),
    dict(slug="realtor", name="HERMUS for Realtors", template_key="Real Estate",
         tagline="Answer every lead in 5 minutes, follow up forever, and book site visits — by voice.",
         brand="HERMUS · Realtor", engines=["E1", "E2", "E3", "E4", "E7", "E8"], add=["M14"],
         locked=["RE-03"], hidden=_PRO_HIDDEN, price=_ROLE_PRICE, sort=40),
    dict(slug="lawyer", name="HERMUS for Lawyers", template_key="Legal Industry",
         tagline="Dictate drafts, track hearing dates, and chase fees — a limitation-period sentinel no tier can snooze.",
         brand="HERMUS · Legal", engines=["E2", "E3", "E4", "E6", "E8"], add=["M18"],
         locked=[], hidden=_PRO_HIDDEN, price=_ROLE_PRICE, sort=50),
    dict(slug="therapist", name="HERMUS for Therapists", template_key="Healthcare",
         tagline="Booking, reminders, intake and notes — privacy-critical, kept entirely on your machine.",
         brand="HERMUS · Therapy", engines=["E1", "E2", "E3", "E7", "E8"], add=["M15"],
         locked=["HC-R1", "HC-R2", "HC-R3", "HC-R4"], hidden=_PRO_HIDDEN, price=_ROLE_PRICE, sort=55),
    dict(slug="eldercare", name="HERMUS for Seniors & Family", template_key="Senior Citizens",
         tagline="A gentle, private voice assistant for an older adult — medication & appointment reminders, daily check-ins, and peace-of-mind family briefings.",
         brand="HERMUS · Seniors & Family", engines=["E2", "E3", "E7", "E8"], add=["M33"],
         locked=["SC-R1", "SC-R2", "SC-R3", "SC-R4", "SC-R5", "SC-R6"], hidden=_CONSUMER_HIDDEN,
         price={"plans": [
             {"name": "Free", "price_inr": 0, "price_usd": 0, "scope": "Reminders + daily check-in, local only"},
             {"name": "Senior", "price_inr": 1499, "price_usd": 19, "scope": "Full senior assistant, voice-first, 1 device"},
             {"name": "Family", "price_inr": 2999, "price_usd": 39, "scope": "+ family dashboard, briefings & crisis routing (dual-payer)"},
         ], "byok_discount_pct": 18}, sort=60),
]


def _seed_editions(db: Session):
    for e in _EDITIONS:
        if db.query(Edition).filter_by(slug=e["slug"]).first():
            continue
        db.add(Edition(
            id=ulid("edn"), slug=e["slug"], name=e["name"], layer="role_app",
            template_key=e["template_key"], tagline=e["tagline"],
            description=e.get("description", e["tagline"]),
            enabled_engines=e["engines"], enabled_modules=_BASE_MODULES + e["add"],
            skin={"brand": e["brand"], "color": "violet", "hidden_nav": e["hidden"], "onboarding": e["slug"]},
            price_book=e["price"], locked_rules=e["locked"],
            status="published", is_default=e.get("default", False), sort=e["sort"],
        ))
    db.commit()


def _dto(e: Edition, active_id=None):
    return {
        "id": e.id, "slug": e.slug, "name": e.name, "layer": e.layer,
        "template_key": e.template_key, "tagline": e.tagline, "description": e.description,
        "enabled_engines": e.enabled_engines or [], "enabled_modules": e.enabled_modules or [],
        "modules_detail": [MODULE_BYID.get(m, {"id": m, "name": m, "group": "?"})
                           for m in (e.enabled_modules or [])],
        "skin": e.skin or {}, "price_book": e.price_book or {}, "locked_rules": e.locked_rules or [],
        "status": e.status, "is_default": e.is_default, "version": e.version, "sort": e.sort,
        "active": active_id == e.id,
    }


# ───────────────────────────── user endpoints ───────────────────────────────
@router.get("/editions")
def list_editions(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    _seed_editions(db)
    t = db.get(Tenant, p.tenant_id)
    rows = db.query(Edition).filter_by(status="published").order_by(Edition.sort).all()
    return {"items": [_dto(e, t.active_edition_id) for e in rows],
            "active_edition_id": t.active_edition_id}


@router.get("/editions/active")
def active_edition(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    _seed_editions(db)
    t = db.get(Tenant, p.tenant_id)
    e = db.get(Edition, t.active_edition_id) if t.active_edition_id else None
    if not e:
        e = db.query(Edition).filter_by(is_default=True, status="published").first()
    return _dto(e, t.active_edition_id) if e else {"active": False}


@router.post("/editions/{slug}/activate")
def activate_edition(slug: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Activate an Edition for this tenant: set it active, skin the workspace to its
    industry, and deploy its roster. Records a manifest for clean switching."""
    e = db.query(Edition).filter_by(slug=slug, status="published").first()
    if not e:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Edition not found or not published"})
    t = db.get(Tenant, p.tenant_id)

    before_agents = {a.id for a in db.query(Agent.id).filter_by(tenant_id=p.tenant_id).all()}
    before_pipes = {x.id for x in db.query(Pipeline.id).filter_by(tenant_id=p.tenant_id).all()}

    t.active_edition_id = e.id
    if e.template_key:
        t.industry = e.template_key
        sug = tpl.curated(e.template_key)
        apply_suggestion(ApplyIn(suggestion=sug, adopt_agents=True, adopt_pipelines=True,
                                 adopt_tasks=False, product_name=e.name), p, db)
        db.flush()

    # Enable a couple of universally-useful recipes (best-effort).
    recipes_created = []
    for rid in ("daily_briefing",):
        if rid in RECIPE_BYID and not db.query(Recipe).filter_by(tenant_id=p.tenant_id, recipe_id=rid).first():
            r = Recipe(id=ulid("rcp"), tenant_id=p.tenant_id, recipe_id=rid,
                       params=RECIPE_BYID.get(rid, {}).get("params", {}), enabled=True)
            db.add(r); db.flush(); recipes_created.append(r.id)

    new_agents = [a.id for a in db.query(Agent.id).filter_by(tenant_id=p.tenant_id).all()
                  if a.id not in before_agents]
    new_pipes = [x.id for x in db.query(Pipeline.id).filter_by(tenant_id=p.tenant_id).all()
                 if x.id not in before_pipes]
    manifest = {"agents": new_agents, "pipelines": new_pipes, "recipes_created": recipes_created}
    db.add(EditionDeployment(id=ulid("eddp"), tenant_id=p.tenant_id, edition_id=e.id,
                             slug=e.slug, name=e.name, manifest=manifest))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="edition.activate",
          target=e.slug, tenant_id=p.tenant_id, meta={"agents": len(new_agents)})
    db.commit()
    return {"status": "activated", "edition": _dto(e, e.id),
            "created": {"agents": len(new_agents), "pipelines": len(new_pipes)},
            "message": f"{e.name} is now your active product — roster and screens are set up."}


# ───────────────────────────── admin endpoints ──────────────────────────────
admin = APIRouter(prefix="/admin", tags=["admin-editions"])


class EditionIn(BaseModel):
    slug: str
    name: str
    layer: str = "role_app"
    template_key: str | None = None
    tagline: str | None = None
    description: str | None = None
    enabled_engines: list[str] = []
    enabled_modules: list[str] = []
    skin: dict = {}
    price_book: dict = {}
    locked_rules: list[str] = []
    is_default: bool = False
    sort: int = 100


@admin.get("/editions/catalog")
def editions_catalog(p: Principal = Depends(current_admin)):
    """The building blocks the admin Edition builder offers."""
    require_role(p, "catalog")
    return {"modules": [MODULE_BYID[m[0]] for m in MODULES],
            "engines": [{"id": e[0], "name": e[1]} for e in ENGINES],
            "templates": tpl.SUPPORTED if hasattr(tpl, "SUPPORTED") else list(tpl.INDUSTRIES.keys()),
            "layers": ["universal", "edition", "role_app"]}


@admin.get("/editions")
def admin_list_editions(p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    require_role(p, "catalog")
    _seed_editions(db)
    rows = db.query(Edition).order_by(Edition.sort).all()
    return {"items": [_dto(e) for e in rows]}


@admin.post("/editions")
def admin_create_edition(body: EditionIn, p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    require_role(p, "catalog")
    if db.query(Edition).filter_by(slug=body.slug).first():
        raise HTTPException(409, detail={"code": "CONFLICT", "message": "An edition with that slug exists"})
    e = Edition(id=ulid("edn"), status="draft", **body.model_dump())
    db.add(e)
    audit(db, plane="cloud", actor=f"admin:{p.user_id}", action="edition.create", target=body.slug)
    db.commit()
    return {"edition": _dto(e), "message": f"Edition “{e.name}” created as a draft."}


@admin.patch("/editions/{eid}")
def admin_update_edition(eid: str, body: EditionIn, p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    require_role(p, "catalog")
    e = db.get(Edition, eid)
    if not e:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Edition not found"})
    for k, v in body.model_dump().items():
        setattr(e, k, v)
    e.version = (e.version or 1) + 1
    audit(db, plane="cloud", actor=f"admin:{p.user_id}", action="edition.update", target=e.slug)
    db.commit()
    return {"edition": _dto(e), "message": f"Edition “{e.name}” updated."}


@admin.post("/editions/{eid}/publish")
def admin_publish_edition(eid: str, p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    require_role(p, "catalog")
    e = db.get(Edition, eid)
    if not e:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Edition not found"})
    e.status = "draft" if e.status == "published" else "published"
    audit(db, plane="cloud", actor=f"admin:{p.user_id}",
          action=f"edition.{e.status}", target=e.slug)
    db.commit()
    verb = "published — users can now adopt it" if e.status == "published" else "unpublished — hidden from users"
    return {"edition": _dto(e), "message": f"Edition “{e.name}” {verb}."}


@admin.delete("/editions/{eid}")
def admin_delete_edition(eid: str, p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    require_role(p, "catalog")
    e = db.get(Edition, eid)
    if not e:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Edition not found"})
    name = e.name
    db.delete(e)
    audit(db, plane="cloud", actor=f"admin:{p.user_id}", action="edition.delete", target=eid)
    db.commit()
    return {"message": f"Edition “{name}” deleted."}

"""
Universal Core (Doc 17) — the cross-vertical layer built once, inherited by every
industry: 8 engines, 7 universal agents, the 6-entity data model, the 12 universal
rules (U1-U12), the universal voice grammar, and one universal scoreboard.

Verticals contribute only words, templates and thresholds — the "re-skin" demo
proves it: the same roster and stages, re-labelled live into any industry.
"""
import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import industry_templates as tpl
from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import (Agent, Clarification, EngineDeployment, EvalRun, Lead,
                      LeadInteraction, Recipe, RoiEntry, SiteVisit, Tenant,
                      UniversalRule, now)
from ..routers.recipes import _BYID as RECIPE_BYID
from ..security import ulid

router = APIRouter(prefix="/universal", tags=["universal"])

# ───────────────────────────── 8 engines (Doc 17 §2) ────────────────────────
ENGINES = [
    ("E1", "Inquiry Pipeline", "Capture from any channel → dedupe → qualify → respond fast → route",
     "Lead / patient inquiry / client intake / RFP", "live"),
    ("E2", "Follow-Up Sequencer", "Multi-step nurture with stop conditions, opt-outs, human-pause",
     "Lead nurture / recall / document chase / proposal follow-up", "live"),
    ("E3", "Appointment Engine", "Slot offering, confirmations, T-24h/T-2h reminders, no-show recovery, voice outcome",
     "Site visit / consultation / meeting / hearing", "live"),
    ("E4", "Document Factory", "Template + data + validation (source-cited) + approval gate + send + archive",
     "Proposal / letters / GST pack / client report", "partial"),
    ("E5", "Receivables Engine", "Dues tracking → escalating reminders → human escalation → reconciliation",
     "Milestone payments / billing / fee collection / retainers", "partial"),
    ("E6", "Compliance Calendar", "Recurring dates → prep checklists → escalating alerts → evidence archive",
     "RERA QPR / license renewals / GST-TDS / contract renewals", "partial"),
    ("E7", "Front Desk", "Inbound voice/WhatsApp/email reception: identify, answer, book, route, escalate",
     "Receptionist in every vertical, 24x7", "live"),
    ("E8", "Daily Briefing + ROI Ledger", "Morning spoken summary + weekly value note — the renewal engine",
     "Identical everywhere", "live"),
]

# ───────────────────────────── 7 universal agents (§3) ──────────────────────
UNIVERSAL_AGENTS = [
    ("front_desk", "Front Desk Agent", ["E7", "E1"],
     "Answers every inbound within minutes, any hour; identifies, answers, books, routes"),
    ("follow_up", "Follow-Up Agent", ["E2"],
     "Never lets a conversation die; respects opt-outs; pauses the instant a human steps in"),
    ("scheduler", "Scheduler Agent", ["E3"],
     "Owns the calendar: offers, confirms, reminds, recovers no-shows, captures outcomes"),
    ("document", "Document Agent", ["E4"],
     "Drafts from templates with validated data; nothing leaves without its approval stamp chain"),
    ("collections", "Collections Agent", ["E5"],
     "Tracks every rupee owed; firm but polite; knows when to hand to a human"),
    ("compliance", "Compliance Agent", ["E6"],
     "Keeps the statutory calendar; nags with escalating urgency; archives proof"),
    ("ceo", "Chief of Staff (CEO) Agent", ["E8"],
     "Briefs the owner, decomposes big asks, assigns the others, escalates, reports value"),
]

# ───────────────────────────── re-skin maps (§3, §8.3) ──────────────────────
RESKIN = {
    "Real Estate": {"front_desk": "Lead Qualifier", "follow_up": "Follow-Up Agent",
                    "scheduler": "Site Visit Coordinator", "document": "Proposal Agent",
                    "collections": "Payment Milestone Agent", "compliance": "RERA Compliance",
                    "ceo": "Sales Head"},
    "Healthcare": {"front_desk": "Patient Coordinator", "follow_up": "Recall Agent",
                   "scheduler": "Appointment Coordinator", "document": "Records Agent",
                   "collections": "Billing & Insurance Agent", "compliance": "Compliance & Records",
                   "ceo": "Practice Manager"},
    "Legal Industry": {"front_desk": "Intake Agent", "follow_up": "Client Comms Agent",
                       "scheduler": "Court Diary Agent", "document": "Paralegal Agent",
                       "collections": "Billing & Trust Agent", "compliance": "Compliance Agent",
                       "ceo": "Managing Partner"},
    "Chartered Accountants & Tax Consultants": {"front_desk": "Client Coordinator",
        "follow_up": "Document Chaser", "scheduler": "Meeting Coordinator",
        "document": "Filing Agent", "collections": "Fee Collection Agent",
        "compliance": "Compliance Calendar Agent", "ceo": "Engagement Lead"},
    "Marketing / Digital Agency": {"front_desk": "Account Manager", "follow_up": "Nurture Agent",
        "scheduler": "Meeting Scheduler", "document": "Reporting Agent",
        "collections": "Retainer Billing Agent", "compliance": "Brand-Safety Agent",
        "ceo": "Agency Lead"},
}


def reskin_for(industry):
    return RESKIN.get(industry, {k: name for k, name, *_ in UNIVERSAL_AGENTS})


# ── Vocabulary skin (§1): the engines are universal; only the WORDS change ───
# A "lead" is a "patient inquiry" is a "client intake"; a "site visit" is an
# "appointment" is a "hearing". Driven by the installed industry template.
VOCAB = {
    "Real Estate": {"pipeline": "Lead Pipeline", "inquiry": "Lead", "inquiry_plural": "Leads",
                    "appointments": "Site Visits", "appointment": "Site Visit", "party": "Buyer"},
    "Healthcare": {"pipeline": "Patient Inquiries", "inquiry": "Patient", "inquiry_plural": "Patients",
                   "appointments": "Appointments", "appointment": "Appointment", "party": "Patient"},
    "Legal Industry": {"pipeline": "Matter Intake", "inquiry": "Matter", "inquiry_plural": "Matters",
                       "appointments": "Hearings", "appointment": "Hearing", "party": "Client"},
    "Chartered Accountants & Tax Consultants": {"pipeline": "Client Intake", "inquiry": "Client",
        "inquiry_plural": "Clients", "appointments": "Meetings", "appointment": "Meeting", "party": "Client"},
    "Marketing / Digital Agency": {"pipeline": "Lead Pipeline", "inquiry": "Lead", "inquiry_plural": "Leads",
        "appointments": "Meetings", "appointment": "Meeting", "party": "Client"},
    "Schools & Colleges": {"pipeline": "Admission Inquiries", "inquiry": "Applicant", "inquiry_plural": "Applicants",
        "appointments": "Tours", "appointment": "Tour", "party": "Parent"},
    "Recruitment Agencies": {"pipeline": "Candidate Pipeline", "inquiry": "Candidate", "inquiry_plural": "Candidates",
        "appointments": "Interviews", "appointment": "Interview", "party": "Candidate"},
    "Hospitality / Restaurant": {"pipeline": "Reservations", "inquiry": "Guest", "inquiry_plural": "Guests",
        "appointments": "Bookings", "appointment": "Booking", "party": "Guest"},
}
GENERIC_VOCAB = {"pipeline": "Inquiry Pipeline", "inquiry": "Inquiry", "inquiry_plural": "Inquiries",
                 "appointments": "Appointments", "appointment": "Appointment", "party": "Contact"}


def vocab_for(industry):
    return VOCAB.get(industry, GENERIC_VOCAB)


# ───────────────────────────── 12 universal rules (§5) ──────────────────────
RULES = [
    ("U1", "Speed-to-response SLA", "Revenue physics in every industry", "inquiry", False, {"minutes": 5}),
    ("U2", "No double-texting", "Trust killer everywhere", "outbound", True, {}),
    ("U3", "Ask-don't-guess", "One wrong fact ends adoption", "all", True, {"confidence": 0.7}),
    ("U4", "Source-cited figures", "Money & dates are universal liabilities", "outbound", True, {}),
    ("U5", "Money gate", "Universal legal exposure", "outbound", False, {"amount": 50000}),
    ("U6", "New-contact gate", "Anti-mistake, anti-spam", "outbound", False, {}),
    ("U7", "Opt-out is sacred", "Law + decency everywhere", "outbound", True, {}),
    ("U8", "Quiet hours", "Universal etiquette/compliance", "outbound", False, {"start": "21:00", "end": "08:00"}),
    ("U9", "Three-strike escalation", "Prevents robotic harassment", "outbound", False, {"strikes": 3}),
    ("U10", "Undo window", "Mistakes recoverable in every vertical", "outbound", True, {"seconds": 60}),
    ("U11", "Destructive ops are human-only", "Universal blast-radius control", "all", True, {}),
    ("U12", "Everything audited", "Trust, liability, compliance everywhere", "all", True, {}),
]


def _seed_rules(db, tenant_id):
    if db.query(UniversalRule).filter_by(tenant_id=tenant_id).count() == 0:
        for rid, title, why, scope, locked, thr in RULES:
            db.add(UniversalRule(id=ulid("urule"), tenant_id=tenant_id, rule_id=rid, title=title,
                                 why=why, scope=scope, locked=locked, enabled=True, threshold=thr))
        db.flush()


def rules_map(db, tenant_id):
    _seed_rules(db, tenant_id)
    return {r.rule_id: r for r in db.query(UniversalRule).filter_by(tenant_id=tenant_id).all()}


# ───────────────────────────── endpoints ────────────────────────────────────
@router.get("/skin")
def skin(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """The tenant's vocabulary skin — universal engines, words from the installed template."""
    from ..models import Tenant
    ind = (db.get(Tenant, p.tenant_id).industry) or None
    v = vocab_for(ind)
    return {"industry": ind, "group_label": ind or "Pipeline", **v}


# Each engine, when deployed, switches on its automations (recipes) + an engine worker agent.
ENGINE_RECIPES = {
    "E1": ["speed_to_lead", "missed_call_wa"],
    "E2": ["stale_revival", "quote_followup"],
    "E3": ["confirm_appts", "noshow_prevent"],
    "E4": ["onboarding"],
    "E5": ["chase_invoices"],
    "E6": [],                                   # compliance calendar — agent-only
    "E7": ["missed_call_wa", "review_request"],
    "E8": ["daily_briefing"],
}
_ENG_BY = {e[0]: e for e in ENGINES}


def _engine_deployed(db, tenant_id):
    return {d.eid for d in db.query(EngineDeployment).filter_by(tenant_id=tenant_id).all()}


def _pub(tenant_id, topic, action, name):
    hub.emit(tenant_id, topic, {"action": action, "name": name})


@router.get("/engines")
def engines(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    from ..catalog_flags import disabled_set
    dep = _engine_deployed(db, p.tenant_id)
    dis = disabled_set(db, "engines")   # admin-hidden engines
    return [{"id": e[0], "name": e[1], "what": e[2], "example": e[3], "status": e[4],
             "recipes": ENGINE_RECIPES.get(e[0], []), "deployed": e[0] in dep}
            for e in ENGINES if e[0] not in dis]


@router.post("/engines/{eid}/deploy")
def deploy_engine(eid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Switch on a single universal engine — its automations + an engine worker agent."""
    e = _ENG_BY.get(eid)
    if not e:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Engine not found"})
    if eid in _engine_deployed(db, p.tenant_id):
        raise HTTPException(409, detail={"code": "ALREADY_DEPLOYED",
                            "message": f"{e[1]} is already deployed."})
    recipes_created, recipes_enabled = [], []
    for rid in ENGINE_RECIPES.get(eid, []):
        r = db.query(Recipe).filter_by(tenant_id=p.tenant_id, recipe_id=rid).first()
        if not r:
            r = Recipe(id=ulid("rcp"), tenant_id=p.tenant_id, recipe_id=rid,
                       params=RECIPE_BYID.get(rid, {}).get("params", {}))
            db.add(r); db.flush()
            recipes_created.append(r.id)
        else:
            recipes_enabled.append(r.id)
        r.enabled = True
    agent = Agent(id=ulid("agt"), tenant_id=p.tenant_id, name=f"{e[1]} Engine", designation=e[1],
                  description=e[2], objectives=[f"engine:{eid}"], status="idle",
                  model_id="mdl_gemma9b", skills=[eid])
    db.add(agent); db.flush()
    db.add(EngineDeployment(id=ulid("edp"), tenant_id=p.tenant_id, eid=eid, name=e[1],
                            manifest={"agent_id": agent.id, "recipes_created": recipes_created,
                                      "recipes_enabled": recipes_enabled}))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="engine.deploy",
          target=eid, tenant_id=p.tenant_id, meta={"recipes": ENGINE_RECIPES.get(eid, [])})
    db.commit()
    _pub(p.tenant_id, "engine.changed", "deploy", e[1])
    return {"status": "deployed", "id": eid, "name": e[1],
            "recipes_enabled": ENGINE_RECIPES.get(eid, []),
            "message": f"{e[1]} engine is live — its automations are on and a worker agent is running."}


@router.post("/engines/{eid}/undeploy")
def undeploy_engine(eid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Switch off a single universal engine — recipes other deployments still need are kept."""
    from .solutions import recipe_rows_in_use
    e = _ENG_BY.get(eid)
    dep = db.query(EngineDeployment).filter_by(tenant_id=p.tenant_id, eid=eid).first()
    if not dep:
        raise HTTPException(409, detail={"code": "NOT_DEPLOYED",
                            "message": f"{(e[1] if e else eid)} is not deployed."})
    m = dep.manifest or {}
    removed = {"agent": False, "recipes_deleted": 0, "recipes_disabled": 0, "recipes_kept": 0}
    still_used = recipe_rows_in_use(db, p.tenant_id, skip_engine=dep.id)
    if m.get("agent_id"):
        removed["agent"] = bool(db.query(Agent).filter_by(id=m["agent_id"]).delete(synchronize_session=False))
    for rid in m.get("recipes_created", []):
        if rid in still_used:
            removed["recipes_kept"] += 1
        else:
            removed["recipes_deleted"] += db.query(Recipe).filter_by(id=rid).delete(synchronize_session=False)
    for rid in m.get("recipes_enabled", []):
        if rid in still_used:
            removed["recipes_kept"] += 1
        else:
            db.query(Recipe).filter_by(id=rid).update({"enabled": False}, synchronize_session=False)
            removed["recipes_disabled"] += 1
    db.flush()
    db.query(EngineDeployment).filter_by(id=dep.id).delete(synchronize_session=False)
    name = dep.name
    audit(db, plane="local", actor=f"user:{p.user_id}", action="engine.undeploy",
          target=eid, tenant_id=p.tenant_id, meta={"removed": removed})
    db.commit()
    _pub(p.tenant_id, "engine.changed", "undeploy", name)
    return {"status": "undeployed", "id": eid, "name": name, "removed": removed,
            "message": f"{name} engine has been switched off."}


@router.get("/agents")
def universal_agents(industry: str | None = None, p: Principal = Depends(current_user)):
    skin = reskin_for(industry) if industry else {}
    return [{"role": k, "universal_name": name, "engines": eng, "job": job,
             "vertical_name": skin.get(k, name)} for k, name, eng, job in UNIVERSAL_AGENTS]


@router.post("/deploy")
def deploy_roster(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Install the 7-agent universal roster — the optimum default for ANY business."""
    existing = {(" ".join(a.objectives or [])) for a in
                db.query(Agent).filter_by(tenant_id=p.tenant_id).all()}
    created = 0
    for k, name, eng, job in UNIVERSAL_AGENTS:
        tag = f"universal:{k}"
        if any(tag in e for e in existing):
            continue
        db.add(Agent(id=ulid("agt"), tenant_id=p.tenant_id, name=name, designation=name,
                     description=job, objectives=[tag], is_ceo=(k == "ceo"), status="idle",
                     model_id="mdl_gemma9b", skills=eng))
        created += 1
    audit(db, plane="local", actor=f"user:{p.user_id}", action="universal.deploy",
          tenant_id=p.tenant_id, meta={"created": created})
    db.commit()
    _pub(p.tenant_id, "roster.changed", "deploy", "Universal roster")
    return {"status": "deployed", "created": created,
            "message": (f"Deployed {created} universal agent(s)." if created
                        else "The universal roster is already deployed.")}


@router.post("/undeploy")
def undeploy_roster(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Remove the universal roster (the 7 agents tagged universal:*)."""
    agents = [a for a in db.query(Agent).filter_by(tenant_id=p.tenant_id).all()
              if any((t or "").startswith("universal:") for t in (a.objectives or []))]
    ids = [a.id for a in agents]
    if not ids:
        raise HTTPException(409, detail={"code": "NOT_DEPLOYED",
                            "message": "The universal roster isn't deployed."})
    # clear self-referential manager links first, then delete
    for aid in ids:
        db.query(Agent).filter_by(id=aid).update({"reporting_manager_id": None}, synchronize_session=False)
    db.flush()
    removed = sum(db.query(Agent).filter_by(id=aid).delete(synchronize_session=False) for aid in ids)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="universal.undeploy",
          tenant_id=p.tenant_id, meta={"removed": removed})
    db.commit()
    _pub(p.tenant_id, "roster.changed", "undeploy", "Universal roster")
    return {"status": "undeployed", "removed": removed,
            "message": f"Removed {removed} universal agent(s)."}


class ReskinIn(BaseModel):
    industry: str


@router.get("/reskin")
def reskin_preview(industry: str, p: Principal = Depends(current_user)):
    skin = reskin_for(industry)
    stages = tpl.curated(industry).get("lifecycle", []) if industry in tpl.SUPPORTED else \
        ["Lead", "Engage", "Deliver", "Retain"]
    return {"industry": industry,
            "roster": [{"role": k, "from": name, "to": skin.get(k, name)}
                       for k, name, *_ in UNIVERSAL_AGENTS],
            "stages": stages}


@router.post("/reskin/apply")
def reskin_apply(body: ReskinIn, p: Principal = Depends(current_user),
                 db: Session = Depends(get_db)):
    """The 'watch — now it's a clinic' moment: rename the deployed universal roster live."""
    skin = reskin_for(body.industry)
    agents = db.query(Agent).filter_by(tenant_id=p.tenant_id).all()
    renamed = 0
    for a in agents:
        for tag in (a.objectives or []):
            if tag.startswith("universal:"):
                role = tag.split(":", 1)[1]
                new = skin.get(role)
                if new:
                    a.name, a.designation = new, new
                    renamed += 1
    t = db.query(Agent).first()  # noqa (touch)
    from ..models import Tenant
    tn = db.get(Tenant, p.tenant_id)
    if body.industry in tpl.SUPPORTED:
        tn.industry = body.industry
    audit(db, plane="local", actor=f"user:{p.user_id}", action="universal.reskin",
          tenant_id=p.tenant_id, meta={"industry": body.industry, "renamed": renamed})
    db.commit()
    _pub(p.tenant_id, "vertical.changed", "deploy", f"{body.industry} skin")
    return {"status": "reskinned", "industry": body.industry, "renamed": renamed,
            "message": f"Re-skinned {renamed} agent(s) into {body.industry} — same engines, new vocabulary."}


@router.get("/rules")
def list_rules(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rmap = rules_map(db, p.tenant_id)
    db.commit()
    return [{"rule_id": r.rule_id, "title": r.title, "why": r.why, "scope": r.scope,
             "locked": r.locked, "enabled": r.enabled, "threshold": r.threshold or {}}
            for r in sorted(rmap.values(), key=lambda x: int(x.rule_id[1:]))]


class RulePatch(BaseModel):
    enabled: bool | None = None
    threshold: dict | None = None


@router.patch("/rules/{rule_id}")
def patch_rule(rule_id: str, body: RulePatch, p: Principal = Depends(current_user),
               db: Session = Depends(get_db)):
    rmap = rules_map(db, p.tenant_id)
    r = rmap.get(rule_id)
    if not r:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Rule not found"})
    if body.enabled is False and r.locked:
        raise HTTPException(409, detail={"code": "LOCKED",
            "message": f"{rule_id} is a locked rule and cannot be disabled."})
    if body.enabled is not None:
        r.enabled = body.enabled
    if body.threshold is not None:
        r.threshold = {**(r.threshold or {}), **body.threshold}
    audit(db, plane="local", actor=f"user:{p.user_id}", action="universal.rule.tune",
          target=rule_id, tenant_id=p.tenant_id)
    db.commit()
    _pub(p.tenant_id, "rule.changed", "tune", f"{rule_id} {'on' if r.enabled else 'off'}")
    return {"rule_id": rule_id, "enabled": r.enabled, "threshold": r.threshold,
            "message": f"{rule_id} ({r.title}) turned {'on' if r.enabled else 'off'}."}


class EvalCtx(BaseModel):
    message: str = ""
    amount: float | None = None
    confidence: float = 1.0
    first_contact: bool = False
    opt_out: bool = False
    human_active: bool = False
    strikes: int = 0
    hour: int | None = None
    destructive: bool = False


@router.post("/rules/evaluate")
def evaluate_rules(ctx: EvalCtx, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    """Run an action through all 12 universal rules — the cross-vertical decision point."""
    import re
    rmap = rules_map(db, p.tenant_id)
    db.commit()
    hour = ctx.hour if ctx.hour is not None else now().hour
    decisions = []

    def add(rid, applies, decision, detail):
        decisions.append({"rule_id": rid, "title": rmap[rid].title, "applies": applies,
                          "decision": decision, "detail": detail,
                          "enabled": rmap[rid].enabled, "locked": rmap[rid].locked})

    add("U2", ctx.human_active, "hold" if ctx.human_active else "allow",
        "Human active on thread → agent paused." if ctx.human_active else "No human activity.")
    add("U3", ctx.confidence < rmap["U3"].threshold.get("confidence", 0.7),
        "clarify" if ctx.confidence < rmap["U3"].threshold.get("confidence", 0.7) else "allow",
        f"Confidence {ctx.confidence} vs {rmap['U3'].threshold.get('confidence')}.")
    figs = [int(x.replace(",", "")) for x in re.findall(r"[\d,]{4,}", ctx.message)]
    add("U4", bool(figs), "hold" if figs else "allow",
        f"Figures {figs} must match a source record." if figs else "No figures.")
    money_amt = ctx.amount or 0
    add("U5", money_amt >= rmap["U5"].threshold.get("amount", 50000),
        "require_approval" if money_amt >= rmap["U5"].threshold.get("amount", 50000) else "allow",
        f"Amount ₹{money_amt:,.0f} vs gate ₹{rmap['U5'].threshold.get('amount'):,}.")
    add("U6", ctx.first_contact, "require_approval" if ctx.first_contact else "allow",
        "First outbound to a new party." if ctx.first_contact else "Known party.")
    add("U7", ctx.opt_out, "block" if ctx.opt_out else "allow",
        "Recipient opted out — blocked permanently." if ctx.opt_out else "Not opted out.")
    qh = rmap["U8"].threshold
    quiet = hour >= int(qh.get("start", "21:00").split(":")[0]) or hour < int(qh.get("end", "08:00").split(":")[0])
    add("U8", quiet, "defer" if quiet else "allow",
        f"Hour {hour} in quiet window {qh.get('start')}–{qh.get('end')} → defer." if quiet else "Within contact hours.")
    add("U9", ctx.strikes >= rmap["U9"].threshold.get("strikes", 3),
        "escalate" if ctx.strikes >= rmap["U9"].threshold.get("strikes", 3) else "allow",
        f"{ctx.strikes} unanswered attempts vs {rmap['U9'].threshold.get('strikes')}-strike limit.")
    add("U10", True, "queue", f"Outbound queues {rmap['U10'].threshold.get('seconds', 60)}s, recallable.")
    add("U11", ctx.destructive, "human_only" if ctx.destructive else "allow",
        "Destructive op — human-only, never auto-approved." if ctx.destructive else "Non-destructive.")
    add("U1", False, "allow", f"New inquiry must be answered ≤ {rmap['U1'].threshold.get('minutes')} min.")
    add("U12", True, "audit", "Five-layer identity chain recorded for this action.")

    # strongest blocking outcome
    order = {"block": 6, "human_only": 5, "hold": 4, "require_approval": 3, "escalate": 3,
             "defer": 2, "clarify": 2, "queue": 1, "audit": 0, "allow": 0}
    active = [d for d in decisions if d["applies"] and d["enabled"]]
    verdict = max(active, key=lambda d: order.get(d["decision"], 0))["decision"] if active else "allow"
    return {"verdict": verdict, "decisions": sorted(decisions, key=lambda d: int(d["rule_id"][1:]))}


@router.get("/metrics")
def universal_metrics(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """One scoreboard, every vertical (Doc 17 §7)."""
    leads = db.query(Lead).filter_by(tenant_id=p.tenant_id).all()
    outs = db.query(LeadInteraction).filter_by(tenant_id=p.tenant_id, direction="out").all()
    held = sum(1 for i in outs if i.status == "held")
    visits = db.query(SiteVisit).filter_by(tenant_id=p.tenant_id).all()
    no_show = sum(1 for v in visits if v.status == "no_show")
    clar = db.query(Clarification).filter_by(tenant_id=p.tenant_id).count()
    paused = sum(1 for l in leads if l.agent_paused)
    optout = sum(1 for l in leads if l.opt_out)
    roi = db.query(RoiEntry).filter_by(tenant_id=p.tenant_id).all()
    last_eval = (db.query(EvalRun).filter_by(tenant_id=p.tenant_id)
                 .order_by(EvalRun.at.desc()).first())
    eruns = db.query(EvalRun).filter_by(suite_run_id=last_eval.suite_run_id).all() if last_eval else []
    pass_rate = round(100 * sum(1 for r in eruns if r.passed) / len(eruns)) if eruns else None
    n = max(1, len(leads))
    return {
        "owner": {
            "inquiries_answered": len(leads),
            "follow_ups": sum(1 for r in roi if r.kind == "followup"),
            "events_booked": len(visits), "no_show_rate": round(100 * no_show / max(1, len(visits))),
            "documents_produced": 0,
            "after_hours_actions": sum(1 for r in roi if r.after_hours),
            "staff_hours_replaced": round(sum(float(r.value_minutes or 0) for r in roi) / 60, 1),
        },
        "health": {
            "validator_block_rate": round(100 * held / max(1, len(outs))),
            "clarification_rate": round(100 * clar / n),
            "human_takeover_rate": round(100 * paused / n),
            "opt_out_rate": round(100 * optout / n),
            "golden_task_pass_rate": pass_rate,
        },
    }


@router.get("/grammar")
def voice_grammar():
    """The 20 universal voice commands — work identically in any industry (§6)."""
    return {
        "Status": ["What's pending?", "What happened today / overnight?",
                   "Where do we stand with [party]?", "Play my briefing"],
        "Action": ["Follow up with [party]", "Schedule [event] with [party] [time]",
                   "Draft a [document] for [party]", "Remind [party] about [money/event]",
                   "Send it / Hold it / Stop that message"],
        "Control": ["Approve / Reject", "I've got this one", "Hand it back",
                    "Pause everything for [party]"],
        "Knowledge": ["What did we tell [party] about [topic]?", "Who owes us money?",
                      "What's due this week?"],
        "Meta": ["What did you do for me this week?", "That was wrong", "What can I say?"],
    }


# ──────────────────────── voice / natural-language control ───────────────────
class ResolveIn(BaseModel):
    transcript: str


_DEPLOY_RE = re.compile(r"\b(deploy|install|enable|turn on|activate|switch on|add|start)\b", re.I)
_UNDEPLOY_RE = re.compile(r"\b(undeploy|uninstall|disable|turn off|remove|deactivate|switch off|stop)\b", re.I)
_ROSTER_RE = re.compile(r"\b(roster|all agents|all the agents|seven agents|universal agents|the team)\b", re.I)
_RESKIN_RE = re.compile(r"\b(re-?skin|switch to|change to|make it|turn it into|skin to|now it'?s)\b", re.I)
_OPEN_RE = re.compile(r"\b(open|show|view|see|details?|tell me about)\b", re.I)
_RSTOP = {"rule", "ops", "are", "the", "is", "in", "of", "a", "an"}
_IND_SYN = {"clinic": "Healthcare", "dental": "Healthcare", "dentist": "Healthcare", "hospital": "Healthcare",
            "law": "Legal Industry", "lawyer": "Legal Industry", "legal": "Legal Industry",
            "restaurant": "Hospitality / Restaurant", "hotel": "Hospitality / Restaurant",
            "hospitality": "Hospitality / Restaurant", "shop": "Retail Shops", "store": "Retail Shops",
            "retail": "Retail Shops", "school": "Schools & Colleges", "college": "Schools & Colleges",
            "factory": "Manufacturing", "manufacturing": "Manufacturing", "real estate": "Real Estate"}


def _match_engine(text):
    low = text.lower()
    best, score = None, 0
    for eid, name, *_ in ENGINES:
        sc = 3 if eid.lower() in low else 0
        for w in re.findall(r"[a-z]+", name.lower()):
            if len(w) > 3 and w in low:
                sc += 2
        if sc > score:
            best, score = (eid, name), sc
    return best if score >= 2 else None


def _match_industry(text):
    low = text.lower()
    for ind in tpl.SUPPORTED:
        head = ind.lower().split(" /")[0].split(" &")[0].strip()
        if head and head in low:
            return ind
    for k, v in _IND_SYN.items():
        if k in low:
            return v
    return None


def _match_rule(db, tenant_id, text):
    low = text.lower()
    m = re.search(r"\bu\s?(\d{1,2})\b", low)
    rmap = rules_map(db, tenant_id)
    if m:
        rid = f"U{int(m.group(1))}"
        if rid in rmap:
            return rid
    for r in sorted(rmap.values(), key=lambda x: int(x.rule_id[1:])):
        for w in re.findall(r"[a-z]+", r.title.lower()):
            if len(w) > 3 and w not in _RSTOP and w in low:
                return r.rule_id
    return None


@router.post("/resolve")
def resolve_voice(body: ResolveIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Turn a spoken/typed phrase into a concrete Universal Core action."""
    text = (body.transcript or "").strip()
    if not text:
        return {"action": "none", "message": "I didn't catch that."}
    is_un = bool(_UNDEPLOY_RE.search(text))
    is_dep = bool(_DEPLOY_RE.search(text)) and not is_un
    eng = _match_engine(text)
    roster = bool(_ROSTER_RE.search(text))

    # 1) re-skin to an industry
    if _RESKIN_RE.search(text):
        ind = _match_industry(text)
        if ind:
            return {"action": "reskin", "industry": ind, "message": f"Re-skinning to {ind}."}

    # 2) toggle a rule (needs a deploy/undeploy verb, and not an engine/roster phrase)
    if (is_un or is_dep) and not eng and not roster:
        rid = _match_rule(db, p.tenant_id, text)
        if rid:
            return {"action": "toggle_rule", "rule_id": rid, "enabled": bool(is_dep),
                    "message": f"Turning {rid} {'on' if is_dep else 'off'}."}

    # 3) the roster
    if roster:
        if is_un:
            return {"action": "undeploy_roster", "message": "Removing the universal roster."}
        return {"action": "deploy_roster", "message": "Deploying the universal roster."}

    # 4) a single engine
    if eng:
        eid, name = eng
        deployed = eid in _engine_deployed(db, p.tenant_id)
        if is_un:
            return {"action": "undeploy_engine", "eid": eid, "name": name, "deployed": deployed,
                    "message": f"Switching off {name}."}
        if _OPEN_RE.search(text) and not is_dep:
            return {"action": "open_engine", "eid": eid, "name": name, "message": f"Here's {name}."}
        return {"action": "deploy_engine", "eid": eid, "name": name, "deployed": deployed,
                "message": f"Deploying {name}."}

    return {"action": "none",
            "message": "Try \"deploy the appointment engine\", \"undeploy the roster\", "
                       "\"re-skin to healthcare\", or \"turn off rule U5\"."}

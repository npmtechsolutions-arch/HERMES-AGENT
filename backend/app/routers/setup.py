"""
Guided Setup — a requirement-driven onboarding assistant.

Educates a new user and DOES the work: pick an industry → staff the AI org →
switch on automations → build a first workflow. Each step's done-state is derived
from real data (resumable, accurate even if the user acts outside the wizard),
and "Do it for me" orchestrates the existing bulk endpoints.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import industry_templates as tpl
from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import Agent, Chatbot, Recipe, Tenant, Workflow, now
from ..security import ulid

# Reuse the real setup machinery so the guide creates the same objects the pages do.
from .company import ApplyIn, apply_suggestion, suggestions as company_suggestions
from .recipes import CATALOG as RECIPE_CATALOG
from .workflows import compile_workflow

router = APIRouter(tags=["setup"])

# Ordered steps. `why` educates; `route` is where the hands-on door is.
STEPS = [
    {"key": "company", "title": "Tell us about your business",
     "why": "Your industry skins the whole product — pipeline, agents and language all "
            "speak your business. This one choice personalizes everything that follows.",
     "cta": "Set my industry", "route": "/company", "required": True, "auto": True},
    {"key": "staff", "title": "Staff your AI team",
     "why": "Agents are your employees — a CEO Agent plus specialists for your industry. "
            "We'll hire a ready-made org (with departments and reporting lines) in one click.",
     "cta": "Hire my team", "route": "/org", "required": True, "auto": True},
    {"key": "automations", "title": "Switch on automations",
     "why": "Recipes are one-toggle automations (speed-to-lead, follow-ups, briefings). "
            "Turn a few on and your agents start working without you asking.",
     "cta": "Enable starter recipes", "route": "/recipes", "required": True, "auto": True},
    {"key": "workflow", "title": "Build your first workflow",
     "why": "Workflows chain steps into a repeatable process on a schedule. We'll compile "
            "a starter one from a sentence so you can see how it works.",
     "cta": "Create a starter workflow", "route": "/workflows", "required": True, "auto": True},
    {"key": "tune", "title": "Tune your Hermes agent",
     "why": "Set the tone, autonomy and grounding so every agent's output matches how you "
            "work. You can change these any time in Settings.",
     "cta": "Open agent settings", "route": "/settings", "required": False, "auto": False},
    {"key": "channel", "title": "Connect a customer channel",
     "why": "Add a chatbot or WhatsApp/Telegram channel so your agents can talk to customers, "
            "grounded in your company memory.",
     "cta": "Set up a chatbot", "route": "/chatbots", "required": False, "auto": False},
]
_STEP_KEYS = {s["key"] for s in STEPS}
_STARTER_RECIPES = ["speed_to_lead", "missed_call_wa", "quote_followup"]


def _counts(db, tenant_id):
    return {
        "agents": db.query(Agent).filter(Agent.tenant_id == tenant_id, Agent.is_ceo.is_(False),
                                          Agent.status != "archived").count(),
        "recipes": db.query(Recipe).filter_by(tenant_id=tenant_id, enabled=True).count(),
        "workflows": db.query(Workflow).filter(Workflow.tenant_id == tenant_id,
                                               Workflow.status != "archived").count(),
        "chatbots": db.query(Chatbot).filter_by(tenant_id=tenant_id).count(),
    }


def _done_map(t, c):
    return {
        "company": bool(t.industry),
        "staff": c["agents"] >= 2,
        "automations": c["recipes"] > 0,
        "workflow": c["workflows"] > 0,
        "tune": bool(t.agent_config),
        "channel": c["chatbots"] > 0,
    }


def _state(db, p):
    t = db.get(Tenant, p.tenant_id)
    setup = dict(t.setup or {})
    skipped = set(setup.get("skipped", []))
    c = _counts(db, p.tenant_id)
    done = _done_map(t, c)
    steps = []
    for s in STEPS:
        steps.append({**s, "done": done[s["key"]], "skipped": s["key"] in skipped})
    req = [s for s in steps if s["required"]]
    done_req = sum(1 for s in req if s["done"] or s["skipped"])
    nxt = next((s["key"] for s in steps if not s["done"] and not s["skipped"]), None)
    return {
        "steps": steps,
        "requirement": {"industry": t.industry, "company_name": t.company_name,
                        "goal": setup.get("goal")},
        "counts": c,
        "progress": {"done": done_req, "total": len(req),
                     "pct": round(100 * done_req / len(req)) if req else 100},
        "complete": done_req >= len(req),
        "dismissed": bool(setup.get("dismissed")),
        "next_key": nxt,
        "industries": tpl.SUPPORTED,
    }


@router.get("/setup/state")
def get_state(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    return _state(db, p)


class RequirementIn(BaseModel):
    industry: str | None = None
    company_name: str | None = None
    goal: str | None = None


@router.post("/setup/requirement")
def set_requirement(body: RequirementIn, p: Principal = Depends(current_user),
                    db: Session = Depends(get_db)):
    t = db.get(Tenant, p.tenant_id)
    changed = []
    if body.company_name and body.company_name.strip():
        t.company_name = body.company_name.strip()
        changed.append("name")
    if body.industry:
        if body.industry not in tpl.SUPPORTED:
            raise HTTPException(422, detail={"code": "BAD_INDUSTRY",
                "message": f"Unsupported industry. Pick one of {len(tpl.SUPPORTED)} supported."})
        t.industry = body.industry
        changed.append("industry")
        hub.emit(p.tenant_id, "vertical.changed", {"action": "deploy", "name": f"{body.industry} skin"})
    setup = dict(t.setup or {})
    if body.goal is not None:
        setup["goal"] = body.goal.strip()[:200]
    t.setup = setup
    audit(db, plane="local", actor=f"user:{p.user_id}", action="setup.requirement",
          tenant_id=p.tenant_id, meta={"industry": t.industry, "goal": setup.get("goal")})
    db.commit()
    hub.emit(p.tenant_id, "setup.changed", {"action": "requirement", "name": t.industry or "goal"})
    return {**_state(db, p),
            "message": f"Got it — setting you up for {t.industry}." if body.industry
                       else "Saved your goal."}


class DoIn(BaseModel):
    industry: str | None = None
    goal: str | None = None


def _ensure_industry(t, body, db, p):
    ind = (body.industry if body and body.industry in tpl.SUPPORTED else None) or t.industry
    if not ind:
        ind = "Small Business Owners"
    if t.industry != ind:
        t.industry = ind
        hub.emit(p.tenant_id, "vertical.changed", {"action": "deploy", "name": f"{ind} skin"})
    return ind


@router.post("/setup/do/{key}")
def do_step(key: str, body: DoIn, p: Principal = Depends(current_user),
            db: Session = Depends(get_db)):
    if key not in _STEP_KEYS:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Unknown step"})
    t = db.get(Tenant, p.tenant_id)
    result, msg = {}, ""

    if key == "company":
        ind = _ensure_industry(t, body, db, p)
        result = {"industry": ind}
        msg = (f"Your company now runs the {ind} template — the whole product just re-skinned "
               f"to your business. Next: staff your AI team.")

    elif key == "staff":
        if _counts(db, p.tenant_id)["agents"] >= 2:
            db.commit()
            return {**_state(db, p), "message": "Your team is already staffed.", "result": {}}
        ind = _ensure_industry(t, body, db, p)
        db.flush()
        sug = company_suggestions(industry=ind, product=None, ai=False, p=p, db=db)
        r = apply_suggestion(ApplyIn(suggestion=sug, adopt_agents=True, adopt_pipelines=True,
                                     adopt_tasks=False, product_name="your business"), p, db)
        result = r.get("created", {})
        msg = (f"Hired {result.get('agents', 0)} agents and built {result.get('pipelines', 0)} "
               f"pipelines for {ind}. Meet them on the Org Chart. Next: switch on automations.")

    elif key == "automations":
        from .recipes import toggle_recipe, ToggleIn
        enabled = []
        want = [r for r in _STARTER_RECIPES if any(c["id"] == r for c in RECIPE_CATALOG)]
        want = want or [c["id"] for c in RECIPE_CATALOG[:3]]
        for rid in want[:3]:
            try:
                toggle_recipe(rid, ToggleIn(enabled=True), p, db)
                enabled.append(rid)
            except Exception:
                pass
        result = {"recipes": enabled}
        names = ", ".join(next((c["name"] for c in RECIPE_CATALOG if c["id"] == r), r) for r in enabled)
        msg = (f"Switched on {len(enabled)} automations ({names}). They run hands-free now. "
               f"Next: build your first workflow.")

    elif key == "workflow":
        goal = (body.goal if body and body.goal else (t.setup or {}).get("goal")) or ""
        utterance = (f"Every Monday at 9 am, summarize {goal}".strip()
                     if goal else "Every Monday at 9 am, send me a summary of pending approvals and tasks")
        compiled = compile_workflow(utterance)
        w = Workflow(id=ulid("wkf"), tenant_id=p.tenant_id, name=utterance[:60],
                     graph=compiled["graph"], status="draft", source_utterance=utterance)
        db.add(w)
        result = {"workflow": w.name, "nodes": len(compiled["graph"]["nodes"])}
        msg = (f"Compiled a starter workflow “{w.name}” ({result['nodes']} steps) as a draft — "
               f"open Workflows to review and activate it. You're nearly there!")

    else:  # tune / channel — hands-on steps, just point the way
        step = next(s for s in STEPS if s["key"] == key)
        db.commit()
        return {**_state(db, p), "message": f"Opening {step['title']} — {step['cta']}.",
                "navigate": step["route"], "result": {}}

    audit(db, plane="local", actor=f"user:{p.user_id}", action=f"setup.step.{key}",
          tenant_id=p.tenant_id, meta=result)
    db.commit()
    hub.emit(p.tenant_id, "setup.changed", {"action": key, "name": key})
    st = _state(db, p)
    return {**st, "message": msg + (" 🎉 You're all set up!" if st["complete"] else ""),
            "result": result}


@router.post("/setup/skip/{key}")
def skip_step(key: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    if key not in _STEP_KEYS:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Unknown step"})
    t = db.get(Tenant, p.tenant_id)
    setup = dict(t.setup or {})
    setup["skipped"] = sorted(set(setup.get("skipped", []) + [key]))
    t.setup = setup
    db.commit()
    hub.emit(p.tenant_id, "setup.changed", {"action": "skip", "name": key})
    return {**_state(db, p), "message": f"Skipped “{key}”. You can do it later."}


@router.post("/setup/dismiss")
def dismiss(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(Tenant, p.tenant_id)
    setup = dict(t.setup or {})
    setup["dismissed"] = True
    t.setup = setup
    db.commit()
    return {**_state(db, p), "message": "Guided setup hidden — reopen it any time from the menu."}


@router.post("/setup/reset")
def reset(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(Tenant, p.tenant_id)
    t.setup = {}
    db.commit()
    return {**_state(db, p), "message": "Guided setup reset."}


class SetupVoiceIn(BaseModel):
    transcript: str


def _match_industry(text):
    low = text.lower()
    for ind in tpl.SUPPORTED:
        toks = [w for w in re.sub(r"[^a-z ]", " ", ind.lower()).split() if len(w) >= 4]
        if any(w in low for w in toks) or ind.lower() in low:
            return ind
    return None


@router.post("/setup/resolve")
def setup_resolve(body: SetupVoiceIn, p: Principal = Depends(current_user),
                  db: Session = Depends(get_db)):
    text = body.transcript or ""
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())

    if re.search(r"\b(dismiss|hide|close|done with setup)\b", low) or re.search(r"\bskip (the )?setup\b", low):
        return {"action": "dismiss", "message": "Hiding guided setup."}
    if re.search(r"\b(reset|start over|restart setup)\b", low):
        return {"action": "reset", "message": "Restarting setup."}

    # which step is being referenced?
    step_key = None
    if re.search(r"\b(staff|hire|team|org|employees?)\b", low):
        step_key = "staff"
    elif re.search(r"\b(automat\w*|recipe\w*)\b", low):
        step_key = "automations"
    elif re.search(r"\bworkflow\w*\b", low):
        step_key = "workflow"
    elif re.search(r"\b(tune|agent setting|configure)\b", low):
        step_key = "tune"
    elif re.search(r"\b(channel|chatbot|whatsapp)\b", low):
        step_key = "channel"
    elif re.search(r"\bcompany\b", low):
        step_key = "company"

    # skip a specific step
    if step_key and re.search(r"\b(skip|later|not now|do (this )?later)\b", low):
        return {"action": "skip", "key": step_key, "message": f"Skipping the {step_key} step."}

    # set industry / requirement
    ind = _match_industry(text)
    if ind and re.search(r"\b(set up|setup|company|industry|business|for|i (run|have|own))\b", low):
        return {"action": "requirement", "industry": ind,
                "message": f"Setting you up for {ind}."}
    # explicit step verbs
    if step_key:
        labels = {"staff": "Staffing your team.", "automations": "Switching on automations.",
                  "workflow": "Building a starter workflow.", "tune": "Opening agent settings.",
                  "channel": "Setting up a channel.", "company": "Setting your industry."}
        return {"action": "do", "key": step_key, "message": labels[step_key]}
    if ind:
        return {"action": "requirement", "industry": ind, "message": f"Setting you up for {ind}."}
    if re.search(r"\b(next|continue|keep going|what.?s next|proceed)\b", low):
        return {"action": "next", "message": "On to the next step."}
    if re.search(r"\b(start|begin|set up|setup|guide me|help me set)\b", low):
        return {"action": "next", "message": "Let's start your setup."}
    return {"action": "none",
            "message": 'Try "set up my company for healthcare", "staff my team", "turn on automations", or "what\'s next".'}

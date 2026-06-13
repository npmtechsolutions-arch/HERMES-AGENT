"""
Recipes (Doc 17 §9.2) — one-toggle automations: the layer below workflows. Each
recipe is a parameterized workflow underneath, obeying all universal rules (U1-U12)
by construction. Two doors: non-tech users toggle + tune 1-2 params; tech users
"Open as workflow" to fork into the full builder.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import Recipe, Workflow, now
from ..security import ulid

router = APIRouter(tags=["recipes"])


def R(rid, name, engine, desc, params, rules, category):
    return {"id": rid, "name": name, "engine": engine, "desc": desc,
            "params": params, "rules": rules, "category": category}


# Catalog: plain-language automations mapped to engines + the rules they honor.
# The first 13 ids are referenced by verticals/solutions/engines — keep them stable.
CATALOG = [
    # ───────────── Lead & Sales ─────────────
    R("speed_to_lead", "Answer new leads within 5 minutes", "E1",
      "When an inquiry arrives on any channel, qualify and reply fast.",
      {"minutes": 5}, ["U1", "U6", "U4"], "Lead & Sales"),
    R("missed_call_wa", "Reply to missed calls on WhatsApp", "E7",
      "Auto-text anyone whose call you missed.",
      {"message": "Sorry we missed your call! How can we help?"}, ["U6", "U8", "U10"], "Lead & Sales"),
    R("quote_followup", "Follow up on quotes until they decide", "E2",
      "Chase sent quotes on a schedule until won or a clear no.",
      {"days": 2}, ["U4", "U6", "U9", "U10"], "Lead & Sales"),
    R("stale_revival", "Re-engage 90-day-cold contacts", "E2",
      "Quarterly nudge to people who went quiet; stops on opt-out.",
      {"days": 90}, ["U7", "U9", "U10"], "Lead & Sales"),
    R("web_lead_capture", "Capture and qualify website leads", "E1",
      "Greet, qualify and route every form/website lead instantly.",
      {"seconds": 60}, ["U1", "U6"], "Lead & Sales"),
    R("lead_scoring", "Auto-score and prioritize new leads", "E1",
      "Score each lead hot/warm/cold so you work the best first.",
      {}, ["U3"], "Lead & Sales"),
    R("abandoned_cart", "Recover abandoned carts", "E2",
      "Nudge shoppers who left items behind; stop on purchase or opt-out.",
      {"delay_hours": 1}, ["U7", "U9"], "Lead & Sales"),
    R("win_back", "Win back lapsed customers", "E2",
      "Reach out to customers who stopped buying with a tailored offer.",
      {"days": 60}, ["U7", "U9"], "Lead & Sales"),
    R("sla_escalation", "Escalate unanswered inquiries to you", "E1",
      "If an inquiry isn't handled in time, escalate it to a human.",
      {"minutes": 30}, ["U1", "U9"], "Lead & Sales"),

    # ───────────── Appointments ─────────────
    R("confirm_appts", "Confirm tomorrow's appointments every evening", "E3",
      "Send a confirmation each evening for the next day's bookings.",
      {"time": "18:00"}, ["U8", "U10"], "Appointments"),
    R("noshow_prevent", "Prevent no-shows (confirm + remind + backfill)", "E3",
      "Confirm at T-24h, remind at T-2h; offer the slot to the waitlist if unconfirmed.",
      {"remind_hours": 2}, ["U8", "U10"], "Appointments"),
    R("appt_reminder", "Remind before every appointment", "E3",
      "A friendly reminder a set time before each booking.",
      {"hours": 24}, ["U8", "U10"], "Appointments"),
    R("waitlist_backfill", "Fill cancelled slots from the waitlist", "E3",
      "When a slot frees up, offer it to the next person on the waitlist.",
      {}, ["U8"], "Appointments"),
    R("reschedule_offer", "Offer easy reschedule on conflicts", "E3",
      "Proactively offer a new slot when a booking can't go ahead.",
      {}, ["U10"], "Appointments"),

    # ───────────── Reviews & Feedback ─────────────
    R("review_request", "Ask happy customers for a review", "E2",
      "After a good interaction, request a Google review — politely, once.",
      {"delay_hours": 3}, ["U7", "U8", "U9"], "Reviews & Feedback"),
    R("feedback_survey", "Send a feedback survey after service", "E2",
      "Collect feedback after each completed service; route unhappy ones to you.",
      {"delay_hours": 24}, ["U7", "U8"], "Reviews & Feedback"),
    R("nps_survey", "Quarterly NPS survey", "E2",
      "Measure loyalty with a short NPS survey every quarter.",
      {"days": 90}, ["U7", "U8"], "Reviews & Feedback"),
    R("referral_ask", "Ask happy customers for referrals", "E2",
      "Invite delighted customers to refer a friend.",
      {"delay_hours": 48}, ["U7", "U9"], "Reviews & Feedback"),

    # ───────────── Retention & Loyalty ─────────────
    R("retention", "Keep clients with timely check-ins", "E2",
      "Periodic value check-ins so clients never feel forgotten.",
      {"days": 30}, ["U7", "U8"], "Retention & Loyalty"),
    R("birthday", "Wish customers on their birthdays", "E2",
      "A warm message on the day — opt-out and quiet-hours respected.",
      {"time": "09:00"}, ["U7", "U8"], "Retention & Loyalty"),
    R("anniversary", "Wish customers on their anniversary", "E2",
      "Mark the customer's anniversary with a thoughtful message.",
      {"time": "09:00"}, ["U7", "U8"], "Retention & Loyalty"),
    R("thank_you", "Thank customers after a purchase", "E2",
      "A prompt thank-you after every purchase or visit.",
      {"delay_hours": 1}, ["U8"], "Retention & Loyalty"),
    R("loyalty_checkin", "Loyalty check-ins for regulars", "E2",
      "Keep your best customers warm with light, well-timed touches.",
      {"days": 45}, ["U7", "U8"], "Retention & Loyalty"),

    # ───────────── Payments & Finance ─────────────
    R("chase_invoices", "Chase invoices 7 days after due", "E5",
      "Politely remind on overdue dues; escalate to you when needed.",
      {"days": 7}, ["U4", "U5", "U9", "U10"], "Payments & Finance"),
    R("payment_reminder", "Remind before invoices are due", "E5",
      "A gentle reminder a few days before the due date.",
      {"days_before": 3}, ["U4", "U8", "U10"], "Payments & Finance"),
    R("subscription_renewal", "Subscription / membership renewal reminders", "E5",
      "Nudge customers to renew before their plan lapses.",
      {"days_before": 7}, ["U4", "U8"], "Payments & Finance"),

    # ───────────── Onboarding & Docs ─────────────
    R("onboarding", "Onboard new clients automatically", "E2",
      "Welcome, collect documents, and walk new clients through setup.",
      {"steps": 4}, ["U6", "U10"], "Onboarding & Docs"),
    R("document_chase", "Chase missing documents", "E4",
      "Request and remind clients for the documents you still need.",
      {"days": 3}, ["U6", "U10"], "Onboarding & Docs"),
    R("compliance_deadline", "Alert before compliance deadlines", "E6",
      "Track statutory dates and warn with escalating urgency.",
      {"days_before": 7}, ["U12"], "Onboarding & Docs"),

    # ───────────── Operations & Front Desk ─────────────
    R("inventory_alert", "Alert me before stock runs out", "E5",
      "Watch stock levels; warn you and draft a reorder before a stockout.",
      {"threshold": 10}, ["U5", "U11"], "Operations"),
    R("after_hours_capture", "After-hours auto-reply + capture", "E7",
      "When you're closed, reply, capture the lead, and promise a callback.",
      {}, ["U6", "U8"], "Operations"),
    R("faq_autoresponder", "Auto-answer common questions", "E7",
      "Instantly answer FAQs (hours, pricing, location) from your knowledge.",
      {}, ["U3"], "Operations"),

    # ───────────── Insights ─────────────
    R("daily_briefing", "Brief me every morning at 8am", "E8",
      "A 30-second voice/text summary of yesterday + today, anomalies flagged.",
      {"time": "08:00"}, ["U8", "U12"], "Insights"),
    R("weekly_digest", "Weekly performance digest", "E8",
      "A clear weekly scoreboard delivered every Monday.",
      {"day": "Monday"}, ["U8", "U12"], "Insights"),
    R("anomaly_alert", "Alert me on anomalies", "E8",
      "Warn the moment something's off — cash dip, no-show spike, stalled pipeline.",
      {}, ["U12"], "Insights"),
]
_BYID = {r["id"]: r for r in CATALOG}

CATEGORIES = []
for _r in CATALOG:
    if _r["category"] not in CATEGORIES:
        CATEGORIES.append(_r["category"])


def _state(db, tenant_id):
    return {r.recipe_id: r for r in db.query(Recipe).filter_by(tenant_id=tenant_id).all()}


@router.get("/recipes")
def list_recipes(grouped: bool = False, p: Principal = Depends(current_user),
                 db: Session = Depends(get_db)):
    state = _state(db, p.tenant_id)
    out = []
    for c in CATALOG:
        st = state.get(c["id"])
        out.append({**c, "enabled": bool(st and st.enabled),
                    "params": (st.params if st and st.params else c["params"])})
    if grouped:
        return {"categories": CATEGORIES, "count": len(out),
                "enabled_count": sum(1 for r in out if r["enabled"]), "recipes": out}
    return out


class ToggleIn(BaseModel):
    enabled: bool
    params: dict | None = None


@router.post("/recipes/{rid}/toggle")
def toggle_recipe(rid: str, body: ToggleIn, p: Principal = Depends(current_user),
                  db: Session = Depends(get_db)):
    if rid not in _BYID:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Unknown recipe"})
    st = db.query(Recipe).filter_by(tenant_id=p.tenant_id, recipe_id=rid).first()
    if not st:
        st = Recipe(id=ulid("rcp"), tenant_id=p.tenant_id, recipe_id=rid,
                    params=_BYID[rid]["params"])
        db.add(st)
    st.enabled = body.enabled
    if body.params is not None:
        st.params = {**(st.params or {}), **body.params}
    audit(db, plane="local", actor=f"user:{p.user_id}", action="recipe.toggle",
          target=rid, tenant_id=p.tenant_id, meta={"enabled": body.enabled, "params": body.params})
    db.commit()
    name = _BYID[rid]["name"]
    hub.emit(p.tenant_id, "recipe.changed",
             {"action": "enable" if body.enabled else "disable", "name": name})
    return {"recipe_id": rid, "enabled": st.enabled, "params": st.params,
            "message": (f"“{name}” is on." if body.enabled else f"“{name}” is off.")
            if body.params is None else f"“{name}” updated."}


@router.post("/recipes/{rid}/open-as-workflow")
def open_as_workflow(rid: str, p: Principal = Depends(current_user),
                     db: Session = Depends(get_db)):
    """Tech door: fork a recipe into the full visual workflow builder."""
    c = _BYID.get(rid)
    if not c:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Unknown recipe"})
    graph = {"nodes": [
        {"node_id": "n1", "type": "trigger", "label": f"Trigger · {c['engine']}"},
        {"node_id": "n2", "type": "condition", "label": "Universal rules gate (U1-U12)"},
        {"node_id": "n3", "type": "action", "label": c["name"]},
        {"node_id": "n4", "type": "approval", "label": "Human approval (money/new-contact)"},
        {"node_id": "n5", "type": "notification", "label": "Log + ROI ledger"},
    ], "edges": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"},
                 {"from": "n3", "to": "n4"}, {"from": "n4", "to": "n5"}]}
    w = Workflow(id=ulid("wfl"), tenant_id=p.tenant_id, name=c["name"], graph=graph,
                 status="draft", source_utterance=f"Forked from recipe '{c['id']}'")
    db.add(w)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="recipe.fork",
          target=w.id, tenant_id=p.tenant_id, meta={"recipe": rid})
    db.commit()
    return {"workflow_id": w.id, "name": w.name,
            "message": "Forked into the workflow builder — edit it freely; it still obeys U1-U12."}


# ──────────────────────── voice / natural-language control ───────────────────
class RecipeVoiceIn(BaseModel):
    transcript: str


_STOP = {"the", "and", "for", "with", "every", "new", "customers", "clients", "me", "my",
         "a", "an", "on", "to", "after", "before", "recipe", "automation"}


def _match_recipe(text):
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    toks = [t for t in low.split() if len(t) >= 4]
    best, score = None, 0
    for c in CATALOG:
        if c["id"] in low or c["id"].replace("_", " ") in low:
            return c
        s = 0
        words = re.findall(r"[a-z]+", c["name"].lower()) + c["id"].split("_")
        for w in words:
            if len(w) < 4 or w in _STOP:
                continue
            pre = w[:4]
            if any(t.startswith(pre) or w.startswith(t[:4]) for t in toks):   # stem/prefix match
                s += 2
        if s > score:
            best, score = c, s
    return best if score >= 2 else None


def _extract_param(c, text):
    """Pull a new value for the recipe's main param from the phrase."""
    low = text.lower()
    params = c["params"]
    # a clock time → time-type params
    mt = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", low) or re.search(r"\b(\d{1,2}):(\d{2})\b", low)
    if mt and any(k in params for k in ("time",)):
        if mt.lastindex and mt.group(mt.lastindex) in ("am", "pm"):
            h = int(mt.group(1)) % 12 + (12 if mt.group(3) == "pm" else 0)
            mins = int(mt.group(2) or 0)
        else:
            h, mins = int(mt.group(1)), int(mt.group(2))
        return ("time", f"{h:02d}:{mins:02d}")
    # a number + unit
    for unit, keys in (("minute", ("minutes",)), ("second", ("seconds",)),
                       ("hour", ("hours", "remind_hours", "delay_hours")),
                       ("day", ("days", "days_before"))):
        m = re.search(rf"\b(\d+)\s*{unit}s?\b", low)
        if m:
            for k in keys:
                if k in params:
                    return (k, int(m.group(1)))
    # a bare number → the recipe's first numeric param
    numkeys = [k for k, v in params.items() if isinstance(v, (int, float))]
    if numkeys:
        m = re.search(r"\b(\d+)\b", low)
        if m:
            return (numkeys[0], int(m.group(1)))
    return None


@router.post("/recipes/resolve")
def recipes_resolve(body: RecipeVoiceIn, p: Principal = Depends(current_user)):
    """Turn a spoken/typed phrase into a concrete Recipes action."""
    text = (body.transcript or "").strip()
    low = text.lower()
    if not text:
        return {"action": "none", "message": "I didn't catch that."}
    c = _match_recipe(text)
    if not c:
        return {"action": "none",
                "message": "Try \"turn on the daily briefing\", \"disable invoice chasing\", "
                           "\"answer leads within 3 minutes\", or \"open the no-show recipe as a workflow\"."}

    if re.search(r"\b(open|fork|edit|customize|customise)\b", low) and "workflow" in low:
        return {"action": "open_workflow", "rid": c["id"], "name": c["name"],
                "message": f"Opening “{c['name']}” as a workflow."}

    # a parameter change ("set the briefing to 9am", "chase invoices after 10 days")
    param = _extract_param(c, text)
    is_off = bool(re.search(r"\b(turn off|disable|stop|switch off|deactivate|pause)\b", low))
    is_on = bool(re.search(r"\b(turn on|enable|start|switch on|activate|set ?up|run)\b", low))
    if param and not is_off:
        return {"action": "set_param", "rid": c["id"], "name": c["name"],
                "key": param[0], "value": param[1], "enable": True,
                "message": f"Setting {c['name']} · {param[0]} to {param[1]}."}
    if is_off:
        return {"action": "disable", "rid": c["id"], "name": c["name"], "message": f"Turning off “{c['name']}”."}
    if is_on:
        return {"action": "enable", "rid": c["id"], "name": c["name"], "message": f"Turning on “{c['name']}”."}
    # bare recipe mention → enable
    return {"action": "enable", "rid": c["id"], "name": c["name"], "message": f"Turning on “{c['name']}”."}

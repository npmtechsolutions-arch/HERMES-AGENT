"""
Solutions — the productized agent store. Each is a focused, one-click-deployable
agent built on the universal engines + recipes (the "simpler, more focused than a
CRM" positioning). Deploy enables the mapped recipes + spins up a focused agent;
undeploy cleanly reverses it (a manifest records what was created). Actions are
also voice-drivable via `/solutions/resolve`. Plus the Daily Business Briefing
agent — a real 30-second morning summary.
"""
import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import (Agent, Approval, BackupJob, Department, EngineDeployment,
                      Lead, RoiEntry, Recipe, SiteVisit, SolutionDeployment,
                      Tenant, VerticalDeployment, now)
from ..routers.recipes import _BYID
from ..security import ulid

router = APIRouter(tags=["solutions"])


def S(sid, name, emoji, tagline, target, problem, flow, recipes, agent, *, category,
      price, pain="medium", competition="low", difficulty="easy", engines=("E2",),
      build_days="20-30", why="", rank=None):
    return {"id": sid, "name": name, "emoji": emoji, "tagline": tagline, "target": target,
            "problem": problem, "flow": list(flow), "recipes": list(recipes), "agent": agent,
            "category": category, "price": price, "pain": pain, "competition": competition,
            "difficulty": difficulty, "engines": list(engines), "build_days": build_days,
            "why": why or f"Built on the universal engines ({', '.join(engines)}) + recipes — no CRM needed.",
            "rank": rank}


SOLUTIONS = [
    # ───────────── Lead & Sales ─────────────
    S("missed_call", "Missed Call Text-Back", "📞", "Never lose a missed call again",
      "Service businesses (salons, clinics, trades) that miss calls all day",
      "Every missed call is a customer who calls the next business. You never even knew they tried.",
      ["Detect a missed call", "Text back within seconds", "Qualify by chat", "Book or route to you"],
      ["missed_call_wa"], "Missed-Call Responder", category="Lead & Sales", price="$19-39",
      pain="high", competition="low", difficulty="medium", engines=("E7", "E2"), build_days="30-45", rank=1,
      why="E7 Front Desk + E2 — auto-text and qualify, no CRM needed."),
    S("speed_to_lead", "Instant Lead Responder", "⚡", "Reply to every lead in under a minute",
      "Anyone whose leads arrive online and go cold fast",
      "The business that replies first wins — and most leads never get a reply at all.",
      ["Capture the lead", "Reply in under 60s", "Qualify by chat", "Hand hot ones to you"],
      ["speed_to_lead"], "Speed-to-Lead Agent", category="Lead & Sales", price="$29-59",
      pain="high", competition="medium", difficulty="medium", engines=("E1", "E2")),
    S("quote", "Quote Follow-Up", "📝", "Close the deals you already quoted",
      "Freelancers and B2B service providers who send quotes",
      "Most quotes die in silence — not from a 'no', just from no follow-up.",
      ["Send the quote", "Follow up on a schedule", "Stop on win or a clear no", "Flag hot ones to you"],
      ["quote_followup"], "Quote Follow-Up Agent", category="Lead & Sales", price="$19-39",
      pain="medium", competition="low", difficulty="easy", engines=("E2", "E4"), rank=2,
      why="E2 + E4 — validated follow-ups until they decide."),
    S("proposal", "Proposal Chaser", "📄", "Turn sent proposals into signed deals",
      "Agencies & consultants sending proposals",
      "A proposal with no follow-up is a coin flip. Most never get chased.",
      ["Send proposal", "Scheduled nudges", "Answer FAQs", "Escalate when they're warm"],
      ["quote_followup"], "Proposal Chaser", category="Lead & Sales", price="$29-49",
      pain="medium", competition="low", difficulty="easy", engines=("E2", "E4")),
    S("reengage", "Re-Engagement", "🔄", "Wake up your dead leads",
      "Any business sitting on a list of cold contacts",
      "Your CRM is a graveyard of leads who went quiet — worth money if revived.",
      ["Find 90-day-cold contacts", "Re-engage with something new", "Stop on opt-out"],
      ["stale_revival"], "Re-Engagement Agent", category="Lead & Sales", price="$29-59",
      pain="medium", competition="medium", difficulty="medium"),
    S("winback", "Win-Back Campaign", "💔", "Bring lapsed customers back",
      "Businesses with customers who used to buy and stopped",
      "Lapsed customers are cheaper to win back than new ones — if you reach out.",
      ["Spot lapsed customers", "Send a tailored win-back offer", "Stop on response or opt-out"],
      ["stale_revival"], "Win-Back Agent", category="Lead & Sales", price="$29-49",
      pain="medium", competition="low", difficulty="easy"),
    S("lead_nurture", "Lead Nurture", "🌱", "Stay top-of-mind until they're ready",
      "Long sales cycles where leads aren't ready today",
      "Leads that aren't ready now get forgotten — and bought by whoever stayed in touch.",
      ["Capture + qualify", "Value-led drip", "Re-engage the quiet ones", "Flag when they heat up"],
      ["speed_to_lead", "stale_revival"], "Lead Nurture Agent", category="Lead & Sales", price="$29-59",
      pain="high", competition="medium", difficulty="medium", engines=("E1", "E2")),
    S("cart_recovery", "Abandoned Cart Recovery", "🛒", "Recover the sales that almost happened",
      "E-commerce & online stores", "Most carts are abandoned — a nudge recovers a real share of them.",
      ["Detect an abandoned cart", "Remind with the items", "Offer help/incentive", "Stop on purchase"],
      ["stale_revival"], "Cart Recovery Agent", category="Lead & Sales", price="$29-59",
      pain="high", competition="medium", difficulty="medium"),
    S("whatsapp_lead", "WhatsApp Auto-Reply", "💬", "Instant answers on the channel they use",
      "Businesses that get enquiries on WhatsApp",
      "Customers message on WhatsApp and wait — and wander off if no one replies fast.",
      ["Receive a WhatsApp message", "Reply instantly", "Answer FAQs / qualify", "Hand off when needed"],
      ["missed_call_wa"], "WhatsApp Agent", category="Lead & Sales", price="$19-39",
      pain="high", competition="medium", difficulty="easy", engines=("E7", "E2")),

    # ───────────── Appointments & Booking ─────────────
    S("noshow", "No-Show Prevention", "📅", "Cut no-shows by a third",
      "Clinics, salons, consultants with appointment books",
      "No-shows are pure lost revenue — an empty chair you can't sell twice.",
      ["Confirm at T-24h", "Remind at T-2h", "Backfill the slot from the waitlist if unconfirmed"],
      ["confirm_appts", "noshow_prevent"], "Scheduler Agent", category="Appointments & Booking",
      price="$29-49", pain="high", competition="low", difficulty="medium", engines=("E3",), build_days="30-40",
      why="E3 Appointment Engine — reminders + recovery."),
    S("appt_confirm", "Appointment Confirmations", "✅", "Every booking, confirmed automatically",
      "Any appointment-based business", "Manual confirmation calls eat hours and still get missed.",
      ["Confirm on booking", "Reminder at T-24h / T-2h", "Capture reschedules", "Flag unconfirmed"],
      ["confirm_appts"], "Confirmations Agent", category="Appointments & Booking", price="$19-39",
      engines=("E3",)),
    S("reminder", "Reminder Bot", "⏰", "Gentle reminders that people actually read",
      "Service businesses with bookings", "Forgotten appointments and deadlines cost money and goodwill.",
      ["Schedule reminders", "Send on the right channel", "Handle replies", "Escalate if ignored"],
      ["confirm_appts"], "Reminder Agent", category="Appointments & Booking", price="$15-29",
      engines=("E3",)),
    S("waitlist", "Waitlist Backfill", "🪑", "Fill every cancelled slot",
      "Busy clinics, salons and studios", "A cancellation is lost revenue unless you fill the gap fast.",
      ["Maintain a waitlist", "Detect a cancellation", "Offer the slot to the next in line", "Confirm"],
      ["noshow_prevent"], "Waitlist Agent", category="Appointments & Booking", price="$29-49",
      pain="high", difficulty="medium", engines=("E3",)),
    S("rebooking", "Auto-Rebooking", "🔁", "Keep regulars on the calendar",
      "Recurring-visit businesses (salons, physio, dental)", "Regulars drift away when no one books their next visit.",
      ["Spot due-for-rebooking customers", "Invite them to book", "Confirm the slot", "Loop again"],
      ["retention"], "Rebooking Agent", category="Appointments & Booking", price="$19-39",
      engines=("E3", "E2")),

    # ───────────── Reviews & Reputation ─────────────
    S("reviews", "Review Generation", "⭐", "Turn happy customers into 5-star reviews",
      "Local businesses that live or die by their Google rating",
      "Happy customers rarely leave reviews unless asked — and you forget to ask.",
      ["Detect a good interaction", "Ask for a review (once, politely)", "Route negatives to you privately"],
      ["review_request"], "Reviews Agent", category="Reviews & Reputation", price="$15-29",
      pain="high", competition="medium", difficulty="easy"),
    S("reputation", "Reputation Guard", "🛡️", "Catch unhappy customers before they post",
      "Any business with public reviews", "One bad public review outweighs ten good ones — intercept it first.",
      ["Ask for feedback privately first", "Route happy → public review", "Route unhappy → you to fix"],
      ["review_request"], "Reputation Agent", category="Reviews & Reputation", price="$19-39",
      pain="high", competition="low", difficulty="easy"),

    # ───────────── Retention & Loyalty ─────────────
    S("retention", "Client Retention", "🤝", "Keep the clients you fought to win",
      "Recurring-revenue businesses (retainers, subscriptions, memberships)",
      "Clients churn quietly when they feel forgotten between invoices.",
      ["Timed value check-ins", "Catch at-risk signals", "Flag to you before they leave"],
      ["retention"], "Retention Agent", category="Retention & Loyalty", price="$29-49",
      pain="high", competition="low", difficulty="medium"),
    S("birthday", "Birthday & Anniversary", "🎂", "Thoughtful touches that drive repeat business",
      "Customer-facing businesses with repeat custom", "A birthday message is a cheap, warm reason to re-engage.",
      ["Track birthdays/anniversaries", "Send a warm message + offer", "Respect opt-outs"],
      ["birthday"], "Occasions Agent", category="Retention & Loyalty", price="$15-29"),
    S("loyalty", "Loyalty Check-ins", "💚", "Make every customer feel remembered",
      "Service businesses with regulars", "Loyalty fades without contact; small check-ins keep it alive.",
      ["Periodic friendly check-ins", "Surface relevant offers", "Flag VIPs to you"],
      ["retention"], "Loyalty Agent", category="Retention & Loyalty", price="$19-39"),
    S("membership", "Membership Renewals", "🎟️", "Stop silent membership lapses",
      "Gyms, clubs, subscriptions", "Memberships lapse silently — a timely nudge saves the renewal.",
      ["Spot upcoming expiries", "Nudge to renew", "Offer help / upgrade", "Flag at-risk to you"],
      ["retention"], "Renewals Agent", category="Retention & Loyalty", price="$29-49",
      pain="high", difficulty="medium"),

    # ───────────── Payments & Finance ─────────────
    S("invoice_chaser", "Invoice & Payment Reminders", "💸", "Get paid on time, without the awkward chase",
      "Anyone who invoices clients", "Late payments wreck cash flow; chasing them is awkward and easy to skip.",
      ["Send the invoice", "Polite reminders before & after due", "Stop on payment", "Escalate the stubborn ones"],
      ["chase_invoices"], "Payments Agent", category="Payments & Finance", price="$29-49",
      pain="high", competition="low", difficulty="medium", engines=("E5",)),
    S("fee_followup", "Fee Follow-Up", "🧾", "Recover outstanding fees, professionally",
      "Professional services (CA, legal, clinics)", "Outstanding fees pile up because no one wants to nag.",
      ["Track outstanding fees", "Scheduled polite follow-ups", "Offer payment options", "Escalate"],
      ["chase_invoices"], "Fee Recovery Agent", category="Payments & Finance", price="$29-49",
      engines=("E5",)),

    # ───────────── Operations & Stock ─────────────
    S("inventory", "Inventory Alerts", "📦", "Never run out of your best-seller",
      "Retail and manufacturing with stock to watch",
      "Stockouts cost sales and reorder panics cost margin — both avoidable.",
      ["Watch stock levels", "Warn before a stockout", "Draft a reorder to the right vendor"],
      ["inventory_alert"], "Inventory Agent", category="Operations & Stock", price="$19-39",
      pain="medium", competition="low", difficulty="hard", engines=("E5",), build_days="35-50"),

    # ───────────── Onboarding & Success ─────────────
    S("onboarding", "Client Onboarding", "👋", "Onboard every client the same, great way",
      "Agencies, accountants, SaaS — anyone with a setup process",
      "Onboarding is manual, inconsistent, and the first impression you can't redo.",
      ["Welcome", "Collect documents", "Walk through setup", "Hand to a human when needed"],
      ["onboarding"], "Onboarding Agent", category="Onboarding & Success", price="$29-49",
      competition="medium", difficulty="medium"),
    S("document_collector", "Document Collector", "📁", "Chase the paperwork so you don't have to",
      "CA / legal / lenders / clinics", "Half your delays are waiting on a document the client forgot.",
      ["Request the documents", "Remind until received", "Confirm what's missing", "Notify you when complete"],
      ["onboarding"], "Document Agent", category="Onboarding & Success", price="$29-49",
      difficulty="medium"),
    S("welcome", "Welcome Sequence", "🎉", "A warm, consistent first week",
      "Any business with new customers", "First impressions set churn; most onboarding is ad-hoc.",
      ["Send a warm welcome", "Set expectations", "Share getting-started tips", "Check in on day 7"],
      ["onboarding"], "Welcome Agent", category="Onboarding & Success", price="$19-39"),

    # ───────────── Insights & Reporting ─────────────
    S("briefing", "Daily Business Briefing", "📊", "Know how your business did — in 30 seconds, every morning",
      "Small business owners who never check their dashboards",
      "Your numbers are buried in tools you never open. You miss trends and cash problems.",
      ["Pull metrics at 8am", "Send a 30-second voice/text summary", "Flag anomalies"],
      ["daily_briefing"], "Briefing Agent", category="Insights & Reporting", price="$19-39",
      competition="low", difficulty="easy", engines=("E8",), build_days="25-35", rank=3,
      why="E8 + the core: aggregate data, deliver by voice/WhatsApp."),
    S("weekly_digest", "Weekly Performance Digest", "📈", "A clear weekly scoreboard, delivered",
      "Owners who want trends, not dashboards", "Weekly patterns are where the money is — and they're invisible day to day.",
      ["Aggregate the week", "Compare to last week", "Highlight wins & risks", "Deliver the digest"],
      ["daily_briefing"], "Digest Agent", category="Insights & Reporting", price="$19-39",
      engines=("E8",)),
    S("anomaly", "Anomaly Alerts", "🚨", "Get warned the moment something's off",
      "Owners who can't watch the numbers all day", "Cash dips, no-show spikes and stalled pipelines hurt most when caught late.",
      ["Watch key metrics", "Detect anomalies", "Alert you with context", "Suggest the next action"],
      ["daily_briefing"], "Anomaly Agent", category="Insights & Reporting", price="$29-49",
      pain="medium", difficulty="medium", engines=("E8",)),

    # ───────────── Industry flagship ─────────────
    S("re_nurture", "Real Estate Lead Nurture", "🏠", "Answer in 60 seconds, nurture forever",
      "Real-estate agents and brokerages (5-50 person offices)",
      "Leads arrive at all hours; the agent who replies first wins, and most never reply.",
      ["Capture from portal/website", "Reply in <60s", "Qualify by chat", "Schedule a showing",
       "Follow up after", "Nurture long-term with market updates"],
      ["speed_to_lead", "confirm_appts", "stale_revival"], "Lead Nurture Agent",
      category="Industry Flagship", price="$49-99", pain="high", competition="medium",
      difficulty="hard", engines=("E1", "E2", "E3"), build_days="40-55"),
]
_BY = {s["id"]: s for s in SOLUTIONS}

CATEGORIES = []
for _s in SOLUTIONS:
    if _s["category"] not in CATEGORIES:
        CATEGORIES.append(_s["category"])


def _deployed(db, tenant_id):
    """Authoritative deployed set = a SolutionDeployment record exists."""
    return {d.sid for d in db.query(SolutionDeployment).filter_by(tenant_id=tenant_id).all()}


def _pub(tenant_id, action, name):
    hub.emit(tenant_id, "solution.changed", {"action": action, "name": name})


def recipe_rows_in_use(db, tenant_id, *, skip_solution=None, skip_vertical=None, skip_engine=None):
    """Recipe row-ids still needed by other live deployments (so undeploy doesn't
    disable a recipe another vertical/solution/engine relies on)."""
    used = set()
    for d in db.query(VerticalDeployment).filter_by(tenant_id=tenant_id).all():
        if skip_vertical and d.id == skip_vertical:
            continue
        m = d.manifest or {}
        used |= set(m.get("recipes_created", [])) | set(m.get("recipes_enabled", []))
    for d in db.query(SolutionDeployment).filter_by(tenant_id=tenant_id).all():
        if skip_solution and d.id == skip_solution:
            continue
        m = d.manifest or {}
        used |= set(m.get("recipes_created", [])) | set(m.get("recipes_enabled", []))
    for d in db.query(EngineDeployment).filter_by(tenant_id=tenant_id).all():
        if skip_engine and d.id == skip_engine:
            continue
        m = d.manifest or {}
        used |= set(m.get("recipes_created", [])) | set(m.get("recipes_enabled", []))
    return used


@router.get("/solutions")
def list_solutions(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    from ..catalog_flags import disabled_set
    dep = _deployed(db, p.tenant_id)
    dis = disabled_set(db, "solutions")   # admin-hidden solutions
    items = [{**s, "deployed": s["id"] in dep} for s in SOLUTIONS if s["id"] not in dis]
    return {"categories": CATEGORIES, "count": len(items), "solutions": items}


@router.get("/solutions/{sid}")
def get_solution(sid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    s = _BY.get(sid)
    if not s:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Solution not found"})
    return {**s, "deployed": sid in _deployed(db, p.tenant_id),
            "recipe_detail": [_BYID.get(r) for r in s["recipes"] if r in _BYID]}


@router.post("/solutions/{sid}/deploy")
def deploy_solution(sid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """One-click: enable the mapped recipes + spin up the focused agent."""
    s = _BY.get(sid)
    if not s:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Solution not found"})
    if sid in _deployed(db, p.tenant_id):
        raise HTTPException(409, detail={"code": "ALREADY_DEPLOYED",
                            "message": f"{s['name']} is already deployed."})
    recipes_created, recipes_enabled = [], []
    for rid in s["recipes"]:
        r = db.query(Recipe).filter_by(tenant_id=p.tenant_id, recipe_id=rid).first()
        if not r:
            r = Recipe(id=ulid("rcp"), tenant_id=p.tenant_id, recipe_id=rid,
                       params=_BYID.get(rid, {}).get("params", {}))
            db.add(r); db.flush()
            recipes_created.append(r.id)
        else:
            recipes_enabled.append(r.id)
        r.enabled = True

    dept = db.query(Department).filter_by(tenant_id=p.tenant_id, name="Sales").first()
    agent = Agent(id=ulid("agt"), tenant_id=p.tenant_id, name=s["agent"], designation=s["agent"],
                  description=s["tagline"], objectives=[f"solution:{sid}"],
                  department_id=dept.id if dept else None, status="idle",
                  model_id="mdl_gemma9b", skills=s["engines"])
    db.add(agent); db.flush()

    db.add(SolutionDeployment(id=ulid("sdp"), tenant_id=p.tenant_id, sid=sid, name=s["name"],
                              manifest={"agent_id": agent.id, "recipes_created": recipes_created,
                                        "recipes_enabled": recipes_enabled}))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="solution.deploy",
          target=sid, tenant_id=p.tenant_id, meta={"recipes": s["recipes"], "agent": s["agent"]})
    db.commit()
    _pub(p.tenant_id, "deploy", s["name"])
    return {"status": "deployed", "name": s["name"], "agent": s["agent"],
            "recipes_enabled": s["recipes"],
            "message": f"{s['name']} is live — {s['agent']} created and its recipe(s) turned on."}


@router.post("/solutions/{sid}/undeploy")
def undeploy_solution(sid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Reverse a deploy — remove the focused agent and the recipes it switched on
    (recipes another live deployment still needs are kept)."""
    s = _BY.get(sid)
    dep = db.query(SolutionDeployment).filter_by(tenant_id=p.tenant_id, sid=sid).first()
    if not dep:
        raise HTTPException(409, detail={"code": "NOT_DEPLOYED",
                            "message": f"{(s or {}).get('name', sid)} is not deployed."})
    m = dep.manifest or {}
    removed = {"agent": False, "recipes_disabled": 0, "recipes_deleted": 0, "recipes_kept": 0}
    still_used = recipe_rows_in_use(db, p.tenant_id, skip_solution=dep.id)

    if m.get("agent_id"):
        removed["agent"] = bool(db.query(Agent).filter_by(id=m["agent_id"]).delete(synchronize_session=False))
    for rid in m.get("recipes_created", []):
        if rid in still_used:
            removed["recipes_kept"] += 1            # another deployment created/needs it
        else:
            removed["recipes_deleted"] += db.query(Recipe).filter_by(id=rid).delete(synchronize_session=False)
    for rid in m.get("recipes_enabled", []):
        if rid in still_used:
            removed["recipes_kept"] += 1
        else:
            db.query(Recipe).filter_by(id=rid).update({"enabled": False}, synchronize_session=False)
            removed["recipes_disabled"] += 1
    db.flush()
    db.query(SolutionDeployment).filter_by(id=dep.id).delete(synchronize_session=False)
    name = dep.name
    audit(db, plane="local", actor=f"user:{p.user_id}", action="solution.undeploy",
          target=sid, tenant_id=p.tenant_id, meta={"removed": removed})
    db.commit()
    _pub(p.tenant_id, "undeploy", name)
    return {"status": "undeployed", "name": name, "removed": removed,
            "message": f"{name} has been removed — its agent and automations are off."}


# ──────────────────────── voice / natural-language control ───────────────────
class ResolveIn(BaseModel):
    transcript: str


_DEPLOY_RE = re.compile(r"\b(deploy|install|set ?up|activate|enable|launch|add|create|start|turn on)\b", re.I)
_UNDEPLOY_RE = re.compile(r"\b(undeploy|uninstall|remove|delete|disable|deactivate|tear ?down|turn off|stop)\b", re.I)
_OPEN_RE = re.compile(r"\b(open|show|view|see|details?|what'?s included|tell me about|info)\b", re.I)
_CLOSE_RE = re.compile(r"\b(close|cancel|dismiss|go back|never ?mind)\b", re.I)
_STOP = {"agent", "the", "a", "an", "solution", "my", "for", "me", "please", "and", "to"}


def _match_solution(text):
    low = text.lower()
    best, score = None, 0
    for s in SOLUTIONS:
        sc = 0
        head = re.sub(r"\s*(agent|bot)$", "", s["name"].lower())
        for w in re.findall(r"[a-z]+", head):
            if len(w) > 3 and w not in _STOP and w in low:
                sc += 2
        if s["id"].replace("_", " ") in low or s["id"] in low:
            sc += 3
        for w in re.findall(r"[a-z]+", s["agent"].lower()):
            if len(w) > 3 and w not in _STOP and w in low:
                sc += 1
        if sc > score:
            best, score = s, sc
    return best if score >= 2 else None


@router.post("/solutions/resolve")
def resolve_voice(body: ResolveIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Turn a spoken/typed phrase into a concrete page action."""
    text = (body.transcript or "").strip()
    if not text:
        return {"action": "none", "message": "I didn't catch that."}
    s = _match_solution(text)
    if _CLOSE_RE.search(text) and not s:
        return {"action": "close", "message": "Closing."}
    if not s:
        return {"action": "none",
                "message": "Tell me which solution, e.g. \"deploy review generation\" or "
                           "\"uninstall the invoice reminders\"."}
    deployed = s["id"] in _deployed(db, p.tenant_id)
    if _UNDEPLOY_RE.search(text):
        return {"action": "undeploy", "sid": s["id"], "name": s["name"], "deployed": deployed,
                "message": f"Undeploying {s['name']}."}
    if _DEPLOY_RE.search(text):
        return {"action": "deploy", "sid": s["id"], "name": s["name"], "deployed": deployed,
                "message": f"Deploying {s['name']}."}
    return {"action": "open", "sid": s["id"], "name": s["name"], "deployed": deployed,
            "message": f"Here's {s['name']}."}


# ── #10 Daily Business Briefing agent (the real thing) ───────────────────────
@router.get("/briefing/daily")
def daily_briefing(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """The 30-second morning summary — yesterday + today, anomalies flagged."""
    since = now() - timedelta(days=1)
    leads = db.query(Lead).filter_by(tenant_id=p.tenant_id).all()
    new_leads = sum(1 for l in leads if l.created_at and l.created_at >= since)
    visits = db.query(SiteVisit).filter_by(tenant_id=p.tenant_id).all()
    done = sum(1 for v in visits if v.status == "done")
    no_show = sum(1 for v in visits if v.status == "no_show")
    today_appts = sum(1 for v in visits if v.slot and v.slot.date() == now().date())
    roi = db.query(RoiEntry).filter(RoiEntry.tenant_id == p.tenant_id, RoiEntry.at >= since).all()
    follow_ups = sum(1 for r in roi if r.kind == "followup")
    after_hours = sum(1 for r in roi if r.after_hours)
    hours = round(sum(float(r.value_minutes or 0) for r in roi) / 60, 1)
    pending = db.query(Approval).filter_by(tenant_id=p.tenant_id, state="pending").count()
    last_backup = (db.query(BackupJob).filter_by(tenant_id=p.tenant_id, status="completed")
                   .order_by(BackupJob.at.desc()).first())
    backup_ok = bool(last_backup) and (now() - last_backup.at) < timedelta(hours=48)

    anomalies = []
    if no_show:
        anomalies.append(f"{no_show} no-show(s) — above usual; worth a recovery call")
    if not backup_ok:
        anomalies.append("backup is stale (48h+) — your data is at risk")
    if pending:
        anomalies.append(f"{pending} approval(s) still waiting on you")

    metrics = {"new_leads": new_leads, "follow_ups": follow_ups, "visits_done": done,
               "no_shows": no_show, "after_hours": after_hours, "staff_hours_saved": hours,
               "today_appointments": today_appts, "pending_approvals": pending}
    summary = (f"Good morning. Yesterday: {new_leads} new inquiries answered, {follow_ups} follow-ups, "
               f"{done} appointment(s) completed{f' ({no_show} no-show)' if no_show else ''}, "
               f"about {hours} staff-hours saved" + (f", {after_hours} handled after-hours" if after_hours else "")
               + f". Today you have {today_appts} appointment(s) and {pending} approval(s) waiting."
               + ((" Heads up: " + "; ".join(anomalies) + ".") if anomalies else " Everything looks healthy."))
    return {"summary": summary, "metrics": metrics, "anomalies": anomalies,
            "delivery": ["voice", "whatsapp", "text"], "schedule": "08:00 daily"}

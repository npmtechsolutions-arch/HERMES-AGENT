"""
Real-Estate killer workflow (Doc 16): Lead → Follow-up → Site Visit, with the
launch-blocking gaps woven in:
  GAP-2  send-time output validators (figures match source, opt-out, templates)
  GAP-3  60-second undo window + mistake report
  GAP-4  ask-don't-guess clarifications + take-over + no-double-texting
  GAP-5  ROI ledger entries on every value-creating action
"""
import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import (Clarification, Correction, EvalCase, Lead, LeadInteraction,
                      Property, RoiEntry, SiteVisit, Tenant, now)
from ..security import ulid

router = APIRouter(tags=["real-estate"])

UNDO_SECONDS = 60
_MONEY = re.compile(r"(₹|rs\.?|inr)\s?[\d,]+", re.I)
_NUM = re.compile(r"[\d,]{4,}")


# ───────────────────────────── helpers ──────────────────────────────────────
def _after_hours():
    h = now().hour
    return h < 9 or h >= 21


def log_roi(db, tenant_id, kind, minutes, detail, lead_id=None):
    db.add(RoiEntry(id=ulid("roi"), tenant_id=tenant_id, kind=kind, value_minutes=minutes,
                    detail=detail, lead_id=lead_id, after_hours=_after_hours()))


def validate_outbound(db, tenant_id, body, lead, first_outbound):
    """GAP-2 — deterministic send-time checks. Returns violations + approval flag."""
    violations = []
    # opt-out honored (hard block)
    if lead and lead.opt_out:
        violations.append({"code": "opted_out", "msg": "Recipient opted out of this channel."})
    # template variables must be resolved
    if re.search(r"\{[a-z_]+\}", body or ""):
        violations.append({"code": "unresolved_template", "msg": "Unresolved template variable."})
    # every figure must match a source record (CC-03 in code)
    known = set()
    if lead and lead.budget:
        known.add(int(lead.budget))
    for pr in db.query(Property).filter_by(tenant_id=tenant_id).all():
        if pr.price:
            known.add(int(pr.price))
    for m in _MONEY.findall(body or ""):
        pass
    for num in _NUM.findall(body or ""):
        val = int(num.replace(",", ""))
        if val >= 1000 and val not in known:
            violations.append({"code": "unverified_figure",
                               "msg": f"₹{val:,} doesn't match any source record."})
    # approval gate: first message to a new contact OR anything mentioning money
    money = bool(_MONEY.search(body or ""))
    requires_approval = first_outbound or money
    return {"ok": len(violations) == 0, "violations": violations,
            "requires_approval": requires_approval, "money": money}


def _send_outbound(db, p, lead, body, channel="whatsapp", drafted_by="agent"):
    """Apply GAP-2 validators + GAP-3 undo window, then create the interaction."""
    first = db.query(LeadInteraction).filter_by(lead_id=lead.id, direction="out").count() == 0
    v = validate_outbound(db, p.tenant_id, body, lead, first)
    status, send_after, reviewed_by = "queued", now() + timedelta(seconds=UNDO_SECONDS), None
    if not v["ok"]:
        status, send_after = "held", None                       # validator hold
    elif v["requires_approval"] and drafted_by == "agent":
        status, send_after = "held", None                       # human approval gate
    if v["money"] and drafted_by == "human":
        reviewed_by = f"user:{p.user_id}"                       # GAP-3 liability stamp
    ix = LeadInteraction(id=ulid("lix"), tenant_id=p.tenant_id, lead_id=lead.id,
                         channel=channel, direction="out", body=body, drafted_by=drafted_by,
                         status=status, send_after=send_after, validator=v["violations"] or None,
                         reviewed_by=reviewed_by)
    db.add(ix)
    lead.last_contacted_at = now()
    return ix, v


def _settle(db, tenant_id):
    """GAP-3 — promote queued messages whose undo window elapsed to 'sent'."""
    due = (db.query(LeadInteraction).filter_by(tenant_id=tenant_id, status="queued")
           .filter(LeadInteraction.send_after <= now()).all())
    for ix in due:
        ix.status = "sent"
    if due:
        db.flush()


def lead_dto(db, l):
    last = (db.query(LeadInteraction).filter_by(lead_id=l.id)
            .order_by(LeadInteraction.at.desc()).first())
    return {"id": l.id, "name": l.name, "phone": l.phone, "requirement": l.requirement,
            "budget": float(l.budget) if l.budget else None, "location": l.location,
            "source": l.source, "stage": l.stage, "score": l.score, "confidence": l.confidence,
            "agent_paused": l.agent_paused, "opt_out": l.opt_out, "followup_step": l.followup_step,
            "last": last.body[:60] if last else None,
            "created_at": l.created_at.isoformat() if l.created_at else None}


# ───────────────────────────── Properties ───────────────────────────────────
@router.get("/properties")
def list_properties(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Property).filter_by(tenant_id=p.tenant_id).all()
    return [{"id": r.id, "name": r.name, "type": r.type, "price": float(r.price or 0),
             "location": r.location, "status": r.status} for r in rows]


class PropertyIn(BaseModel):
    name: str
    type: str = "3BHK"
    price: float
    location: str


@router.post("/properties")
def create_property(body: PropertyIn, p: Principal = Depends(current_user),
                    db: Session = Depends(get_db)):
    pr = Property(id=ulid("prop"), tenant_id=p.tenant_id, name=body.name, type=body.type,
                  price=body.price, location=body.location)
    db.add(pr)
    db.commit()
    return {"id": pr.id}


# ───────────────────────────── Leads (intake + dedupe) ──────────────────────
@router.get("/leads")
def list_leads(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    _settle(db, p.tenant_id)
    db.commit()
    rows = db.query(Lead).filter_by(tenant_id=p.tenant_id).order_by(Lead.created_at.desc()).all()
    return [lead_dto(db, l) for l in rows]


class LeadIn(BaseModel):
    name: str
    phone: str
    requirement: str | None = "3BHK"
    budget: float | None = None
    location: str | None = None
    source: str = "manual"
    confidence: float = 1.0


@router.post("/leads")
def create_lead(body: LeadIn, p: Principal = Depends(current_user),
                db: Session = Depends(get_db)):
    # dedupe by phone (UC-RE-07)
    dup = db.query(Lead).filter_by(tenant_id=p.tenant_id, phone=body.phone).first()
    if dup:
        return {"status": "duplicate", "lead_id": dup.id,
                "message": f"Merged with existing lead {dup.name} (same phone)."}
    score = "hot" if (body.budget or 0) >= 7500000 else "warm"
    lead = Lead(id=ulid("led"), tenant_id=p.tenant_id, name=body.name, phone=body.phone,
                requirement=body.requirement, budget=body.budget, location=body.location,
                source=body.source, stage="new", score=score, confidence=body.confidence)
    db.add(lead)
    db.flush()
    db.add(LeadInteraction(id=ulid("lix"), tenant_id=p.tenant_id, lead_id=lead.id,
                           channel=body.source if body.source in ("whatsapp", "email") else "note",
                           direction="in", body=f"New {body.requirement} enquiry, "
                           f"budget ₹{int(body.budget):,}" if body.budget else "New enquiry",
                           status="received"))
    log_roi(db, p.tenant_id, "lead_answered", 8, f"Captured lead {body.name}", lead.id)
    audit(db, plane="local", actor="agent:lead_qualifier", action="lead.capture",
          target=lead.id, tenant_id=p.tenant_id, meta={"source": body.source})
    db.commit()
    hub.emit(p.tenant_id, "lead.new", {"lead_id": lead.id, "name": lead.name, "score": score})
    # confidence surfacing (GAP-2): low-confidence → flag for clarification
    if body.confidence < 0.7:
        db.add(Clarification(id=ulid("clr"), tenant_id=p.tenant_id, lead_id=lead.id,
                             question=f"{body.name}'s budget/requirement was unclear — confirm before I reply?",
                             options=["Confirm details", "I'll call them"], status="open"))
        db.commit()
    return {"status": "captured", "lead": lead_dto(db, lead)}


@router.get("/leads/{lid}")
def get_lead(lid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    _settle(db, p.tenant_id)
    db.commit()
    l = db.get(Lead, lid)
    if not l or l.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Lead not found"})
    ix = db.query(LeadInteraction).filter_by(lead_id=lid).order_by(LeadInteraction.at).all()
    cl = db.query(Clarification).filter_by(lead_id=lid).order_by(Clarification.at.desc()).all()
    vs = db.query(SiteVisit).filter_by(lead_id=lid).order_by(SiteVisit.slot).all()
    return {
        **lead_dto(db, l),
        "interactions": [{"id": m.id, "channel": m.channel, "direction": m.direction,
                          "body": m.body, "drafted_by": m.drafted_by, "status": m.status,
                          "validator": m.validator, "reviewed_by": m.reviewed_by,
                          "undo_until": m.send_after.isoformat() if (m.status == "queued" and m.send_after) else None,
                          "at": m.at.isoformat() if m.at else None} for m in ix],
        "clarifications": [{"id": c.id, "question": c.question, "options": c.options,
                            "answer": c.answer, "status": c.status} for c in cl],
        "visits": [{"id": v.id, "slot": v.slot.isoformat() if v.slot else None,
                    "status": v.status, "outcome": v.outcome} for v in vs],
    }


# ───────────────────────────── Killer-workflow actions ──────────────────────
def _agent_guard(lead):
    if lead.agent_paused:
        raise HTTPException(409, detail={"code": "AGENT_PAUSED",
            "message": "You've taken over this thread — hand it back to let the agent act."})


@router.post("/leads/{lid}/qualify")
def qualify(lid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Speed-to-lead: send the qualification WhatsApp (validated, undo-windowed)."""
    l = db.get(Lead, lid)
    if not l or l.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Lead not found"})
    _agent_guard(l)
    company = db.get(Tenant, p.tenant_id).company_name
    body = (f"Hi {l.name}, thanks for your interest in a {l.requirement} in "
            f"{l.location or 'our project'}. To help you best — is your budget around "
            f"₹{int(l.budget):,}? And when would you like a site visit? — {company}"
            if l.budget else
            f"Hi {l.name}, thanks for your interest in a {l.requirement}. What's your budget "
            f"and when would you like a site visit? — {company}")
    ix, v = _send_outbound(db, p, l, body)
    if l.stage == "new":
        l.stage = "qualified"
    log_roi(db, p.tenant_id, "response_time_saved", 10, f"Qualified {l.name} in <5 min", l.id)
    audit(db, plane="local", actor="agent:lead_qualifier", action="lead.qualify",
          target=l.id, tenant_id=p.tenant_id, meta={"status": ix.status})
    db.commit()
    return {"status": ix.status, "validator": v, "interaction_id": ix.id}


FOLLOWUPS = {1: "Hi {name}, just following up on the {requirement} you enquired about — "
                "still looking? Happy to share options. — {company}",
             3: "Hi {name}, a couple of new {requirement} options came up in {location}. "
                "Want me to send details? — {company}",
             7: "Hi {name}, last check-in on your {requirement} search — shall I keep you "
                "posted on new launches? Reply STOP to opt out. — {company}"}


@router.post("/leads/{lid}/followup")
def followup(lid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    l = db.get(Lead, lid)
    if not l or l.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Lead not found"})
    _agent_guard(l)
    if l.opt_out:
        raise HTTPException(409, detail={"code": "OPTED_OUT", "message": "Lead opted out (CC-04)."})
    steps = [1, 3, 7]
    nxt = next((s for s in steps if s > l.followup_step), None)
    if not nxt:
        return {"status": "exhausted", "message": "Follow-up sequence complete."}
    company = db.get(Tenant, p.tenant_id).company_name
    body = FOLLOWUPS[nxt].format(name=l.name, requirement=l.requirement,
                                 location=l.location or "your area", company=company)
    ix, v = _send_outbound(db, p, l, body)
    l.followup_step = nxt
    l.stage = "follow_up" if l.stage in ("new", "qualified") else l.stage
    log_roi(db, p.tenant_id, "followup", 5, f"Day-{nxt} follow-up to {l.name}", l.id)
    db.commit()
    return {"status": ix.status, "step": nxt, "validator": v, "interaction_id": ix.id}


class ReplyIn(BaseModel):
    body: str


@router.post("/leads/{lid}/reply")
def human_reply(lid: str, body: ReplyIn, p: Principal = Depends(current_user),
                db: Session = Depends(get_db)):
    """GAP-4 — a human reply auto-pauses the agent on this thread (no double-texting)."""
    l = db.get(Lead, lid)
    if not l or l.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Lead not found"})
    ix, v = _send_outbound(db, p, l, body.body, drafted_by="human")
    ix.status = "sent"   # human messages send immediately
    ix.send_after = None
    l.agent_paused = True
    audit(db, plane="local", actor=f"user:{p.user_id}", action="lead.human_reply",
          target=l.id, tenant_id=p.tenant_id, meta={"auto_paused_agent": True})
    db.commit()
    return {"status": "sent", "agent_paused": True, "reviewed_by": ix.reviewed_by}


@router.post("/leads/{lid}/takeover")
def takeover(lid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    l = db.get(Lead, lid)
    if not l or l.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Lead not found"})
    l.agent_paused = True
    db.add(LeadInteraction(id=ulid("lix"), tenant_id=p.tenant_id, lead_id=lid, channel="note",
                           direction="in", body="— You took over this conversation. Agent silenced on this thread only. —",
                           status="received", drafted_by="human"))
    db.commit()
    return {"agent_paused": True}


@router.post("/leads/{lid}/handback")
def handback(lid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    l = db.get(Lead, lid)
    if not l or l.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Lead not found"})
    l.agent_paused = False
    db.commit()
    return {"agent_paused": False}


# ───────────────────────────── GAP-3 recall + mistake ───────────────────────
@router.post("/interactions/{iid}/recall")
def recall(iid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    ix = db.get(LeadInteraction, iid)
    if not ix or ix.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Message not found"})
    if ix.status != "queued":
        raise HTTPException(409, detail={"code": "CONFLICT", "message": "Already sent — use 'send correction'."})
    ix.status = "recalled"
    audit(db, plane="local", actor=f"user:{p.user_id}", action="message.recall",
          target=iid, tenant_id=p.tenant_id)
    db.commit()
    return {"status": "recalled"}


class MistakeIn(BaseModel):
    note: str = "Marked wrong by the owner."


@router.post("/interactions/{iid}/mistake")
def mistake(iid: str, body: MistakeIn, p: Principal = Depends(current_user),
            db: Session = Depends(get_db)):
    """GAP-3 — 'that was wrong': pause the sequence, file a correction, feed the eval suite."""
    ix = db.get(LeadInteraction, iid)
    if not ix or ix.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Message not found"})
    lead = db.get(Lead, ix.lead_id)
    if lead:
        lead.agent_paused = True
    case = EvalCase(id=ulid("evc"), tenant_id=p.tenant_id, workflow="from_mistake",
                    kind="from_mistake", input={"body": ix.body}, expected={"note": body.note})
    db.add(case)
    db.flush()
    db.add(Correction(id=ulid("cor"), tenant_id=p.tenant_id, interaction_id=iid,
                      lead_id=ix.lead_id, note=body.note, eval_case_id=case.id))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="mistake.report",
          target=iid, tenant_id=p.tenant_id, meta={"eval_case": case.id})
    db.commit()
    return {"status": "filed", "sequence_paused": True, "eval_case_id": case.id,
            "message": "Sequence paused, correction filed, and a new eval case was created."}


# ───────────────────────────── GAP-4 clarifications ─────────────────────────
class ClarifyIn(BaseModel):
    question: str
    options: list[str] = []


@router.post("/leads/{lid}/clarify")
def ask_clarify(lid: str, body: ClarifyIn, p: Principal = Depends(current_user),
                db: Session = Depends(get_db)):
    c = Clarification(id=ulid("clr"), tenant_id=p.tenant_id, lead_id=lid,
                      question=body.question, options=body.options, status="open")
    db.add(c)
    db.commit()
    return {"id": c.id, "status": "open"}


class AnswerIn(BaseModel):
    answer: str


@router.post("/clarifications/{cid}/answer")
def answer_clarify(cid: str, body: AnswerIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    c = db.get(Clarification, cid)
    if not c or c.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Not found"})
    c.answer = body.answer
    c.status = "answered"
    db.commit()
    return {"status": "answered"}


@router.get("/clarifications")
def open_clarifications(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Clarification).filter_by(tenant_id=p.tenant_id, status="open").all()
    return [{"id": c.id, "lead_id": c.lead_id, "question": c.question, "options": c.options}
            for c in rows]


# ───────────────────────────── Site visits ──────────────────────────────────
@router.post("/leads/{lid}/visit")
def offer_visit(lid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    l = db.get(Lead, lid)
    if not l or l.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Lead not found"})
    slot = now() + timedelta(days=2, hours=3)
    v = SiteVisit(id=ulid("svt"), tenant_id=p.tenant_id, lead_id=lid, slot=slot,
                  status="offered", reminders=[{"when": "T-24h", "sent": False},
                                               {"when": "T-2h", "sent": False}])
    db.add(v)
    l.stage = "site_visit"
    log_roi(db, p.tenant_id, "visit_booked", 15, f"Site visit offered to {l.name}", lid)
    db.commit()
    return {"id": v.id, "slot": slot.isoformat(), "status": "offered"}


@router.get("/visits")
def list_visits(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(SiteVisit).filter_by(tenant_id=p.tenant_id).order_by(SiteVisit.slot).all()
    out = []
    for v in rows:
        lead = db.get(Lead, v.lead_id)
        out.append({"id": v.id, "lead": lead.name if lead else "—", "lead_id": v.lead_id,
                    "slot": v.slot.isoformat() if v.slot else None, "status": v.status,
                    "outcome": v.outcome, "reminders": v.reminders})
    return out


class VisitActionIn(BaseModel):
    outcome: str | None = None


@router.post("/visits/{vid}/confirm")
def confirm_visit(vid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    v = db.get(SiteVisit, vid)
    if not v or v.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Visit not found"})
    v.status = "confirmed"
    db.commit()
    return {"status": "confirmed"}


@router.post("/visits/{vid}/outcome")
def visit_outcome(vid: str, body: VisitActionIn, p: Principal = Depends(current_user),
                  db: Session = Depends(get_db)):
    """Visit-outcome captured by voice in the car → CRM note + next step."""
    v = db.get(SiteVisit, vid)
    if not v or v.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Visit not found"})
    v.status = "done"
    v.outcome = body.outcome
    lead = db.get(Lead, v.lead_id)
    if lead:
        db.add(LeadInteraction(id=ulid("lix"), tenant_id=p.tenant_id, lead_id=lead.id,
                               channel="voice", direction="in", drafted_by="human",
                               body=f"Visit note: {body.outcome}", status="received"))
    db.commit()
    return {"status": "done"}

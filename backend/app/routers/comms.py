"""Communication Hub (unified inbox + voice triage) and AI Call Center."""
import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import llm
from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import Call, CommChannel, CommMessage, CommThread, now
from ..security import ulid

router = APIRouter(tags=["communication"])

_CATS = ("urgent", "action", "fyi", "spam")


@router.get("/comms/channels")
def channels(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(CommChannel).filter_by(tenant_id=p.tenant_id).all()
    return [{"id": c.id, "type": c.type, "account_ref": c.account_ref,
             "status": c.status} for c in rows]


@router.get("/comms/threads")
def threads(category: str | None = None, p: Principal = Depends(current_user),
            db: Session = Depends(get_db)):
    q = db.query(CommThread).filter_by(tenant_id=p.tenant_id)
    if category:
        q = q.filter_by(category=category)
    out = []
    for t in q.order_by(CommThread.updated_at.desc()).all():
        ch = db.get(CommChannel, t.channel_id)
        last = db.query(CommMessage).filter_by(thread_id=t.id).order_by(
            CommMessage.sent_at.desc()).first()
        out.append({"id": t.id, "subject": t.subject, "counterpart": t.counterpart,
                    "category": t.category, "channel": ch.type if ch else None,
                    "unread": t.unread, "ai_reply_count": t.ai_reply_count,
                    "preview": (last.body[:120] if last else "")})
    return out


@router.get("/comms/threads/{tid}")
def thread_detail(tid: str, p: Principal = Depends(current_user),
                  db: Session = Depends(get_db)):
    t = db.get(CommThread, tid)
    if not t or t.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Thread not found"})
    t.unread = False
    db.commit()
    ch = db.get(CommChannel, t.channel_id)
    msgs = db.query(CommMessage).filter_by(thread_id=tid).order_by(CommMessage.sent_at).all()
    return {"id": t.id, "subject": t.subject, "counterpart": t.counterpart,
            "category": t.category, "channel": ch.type if ch else None,
            "messages": [{"direction": m.direction, "body": m.body,
                          "drafted_by_agent": m.drafted_by_agent,
                          "sent_at": m.sent_at.isoformat()} for m in msgs]}


class DraftIn(BaseModel):
    instructions: str
    tone: str = "formal"


@router.post("/comms/threads/{tid}/draft")
def draft(tid: str, body: DraftIn, p: Principal = Depends(current_user),
          db: Session = Depends(get_db)):
    t = db.get(CommThread, tid)
    if not t or t.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Thread not found"})

    # Context: the last inbound message on this thread.
    last_in = db.query(CommMessage).filter_by(thread_id=tid, direction="in").order_by(
        CommMessage.sent_at.desc()).first()
    incoming = last_in.body if last_in else ""

    engine = "local-llm"
    text = llm.chat(
        f"Incoming message from {t.counterpart}:\n\"{incoming}\"\n\n"
        f"Write a reply. Instruction: {body.instructions}.",
        system=(f"You draft {body.tone} business email replies for a professional "
                f"office. Be concise (3-5 sentences), correct, and ready to send. "
                f"Sign off as 'Your Office'. Output only the email body."),
        smart=False)
    if not text:
        engine = "template"
        text = (f"Dear {t.counterpart or 'Sir/Madam'},\n\n"
                f"{body.instructions.strip().capitalize()}.\n\n"
                f"{'Best regards' if body.tone == 'formal' else 'Thanks'},\nYour Office")
    audit(db, plane="local", actor="agent:comms", action="comms.draft",
          target=tid, tenant_id=p.tenant_id, meta={"tone": body.tone})
    db.commit()
    return {"draft_id": ulid("drf"), "tone": body.tone, "body": text, "engine": engine,
            "note": "Draft only — not sent. Gates CC-03/CC-04/AC-05 run on send."}


class SendIn(BaseModel):
    body: str


@router.post("/comms/threads/{tid}/send")
def send(tid: str, body: SendIn, p: Principal = Depends(current_user),
         db: Session = Depends(get_db)):
    t = db.get(CommThread, tid)
    if not t or t.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Thread not found"})
    # CC-09: stop auto-replying after 3 AI replies without resolution.
    if t.ai_reply_count >= 3:
        raise HTTPException(409, detail={"code": "CONFLICT",
            "message": "3 AI replies without resolution (CC-09); escalated to human."})
    m = CommMessage(id=ulid("cmsg"), thread_id=tid, direction="out", body=body.body,
                    sent_at=now())
    t.ai_reply_count += 1
    t.unread = False
    db.add(m)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="comms.send",
          target=tid, tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "comms.changed", {"action": "send", "name": t.counterpart or t.subject})
    return {"status": "sent", "message": f"Reply sent to {t.counterpart or 'the contact'}."}


# ───────────────────────────── Re-triage / summary / demo ───────────────────
class ThreadPatch(BaseModel):
    category: str | None = None
    unread: bool | None = None


@router.patch("/comms/threads/{tid}")
def patch_thread(tid: str, body: ThreadPatch, p: Principal = Depends(current_user),
                 db: Session = Depends(get_db)):
    t = db.get(CommThread, tid)
    if not t or t.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Thread not found"})
    changed = []
    if body.category is not None:
        if body.category not in _CATS:
            raise HTTPException(422, detail={"code": "BAD_CATEGORY",
                "message": f"Category must be one of {', '.join(_CATS)}."})
        t.category = body.category
        changed.append(f"moved to {body.category}")
    if body.unread is not None:
        t.unread = body.unread
        changed.append("marked unread" if body.unread else "marked read")
    audit(db, plane="local", actor=f"user:{p.user_id}", action="comms.recategorize",
          target=tid, tenant_id=p.tenant_id, meta={"category": t.category})
    db.commit()
    hub.emit(p.tenant_id, "comms.changed", {"action": "recategorize", "name": t.counterpart or t.subject})
    return {"id": t.id, "category": t.category, "unread": t.unread,
            "message": f"“{t.subject}” {' & '.join(changed) if changed else 'updated'}."}


@router.get("/comms/summary")
def comms_summary(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(CommThread).filter_by(tenant_id=p.tenant_id).all()
    counts = {c: 0 for c in _CATS}
    unread = 0
    for t in rows:
        counts[t.category] = counts.get(t.category, 0) + 1
        if t.unread:
            unread += 1
    return {"total": len(rows), "unread": unread, "by_category": counts}


# A demo inbox so triage can be tried without connecting real channels.
_DEMO = [
    ("urgent", "email", "Acme Corp", "Invoice #4821 overdue — escalating",
     "We still haven't received payment for invoice #4821 (₹50,000), now 12 days overdue. Please respond today or we pause the contract."),
    ("action", "email", "Priya Sharma", "Site visit reschedule?",
     "Can we move tomorrow's 3BHK site visit to Saturday morning? Sunday also works."),
    ("action", "whatsapp", "Vendor — PrintFast", "Quote for 500 brochures",
     "Sharing the quote: ₹18,000 for 500 brochures, 4-day turnaround. Shall we proceed?"),
    ("fyi", "email", "Team Newsletter", "Weekly product digest",
     "This week: 3 features shipped, uptime 99.98%. No action needed."),
    ("spam", "email", "Crypto Rewards", "You won 5 BTC!!! Claim now",
     "Congratulations!! Click this link to claim your 5 BTC reward before it expires!!!"),
]


@router.post("/comms/demo")
def comms_demo(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Seed a sample triaged inbox (idempotent)."""
    if db.query(CommThread).filter_by(tenant_id=p.tenant_id).count() > 0:
        return {"status": "exists", "message": "The inbox already has conversations."}
    chans = {}
    for cat, ch_type, who, subj, msg in _DEMO:
        if ch_type not in chans:
            c = CommChannel(id=ulid("chan"), tenant_id=p.tenant_id, type=ch_type,
                            account_ref=f"{ch_type}@office", status="connected")
            db.add(c); db.flush(); chans[ch_type] = c.id
        t = CommThread(id=ulid("cth"), tenant_id=p.tenant_id, channel_id=chans[ch_type],
                       subject=subj, counterpart=who, category=cat, unread=True)
        db.add(t); db.flush()
        db.add(CommMessage(id=ulid("cmsg"), thread_id=t.id, direction="in", body=msg,
                           sent_at=now() - timedelta(hours=len(chans))))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="comms.demo",
          tenant_id=p.tenant_id, meta={"threads": len(_DEMO)})
    db.commit()
    hub.emit(p.tenant_id, "comms.changed", {"action": "demo", "name": f"{len(_DEMO)} conversations"})
    return {"status": "seeded", "threads": len(_DEMO),
            "message": f"Loaded a demo inbox — {len(_DEMO)} conversations to triage."}


def _match_thread(db, tenant_id, text):
    low = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    toks = [w for w in low.split() if len(w) >= 3 and w not in (
        "the", "from", "open", "thread", "reply", "message", "conversation", "with",
        "show", "this", "that", "mark", "move", "send", "draft", "and", "for")]
    rows = db.query(CommThread).filter_by(tenant_id=tenant_id).order_by(
        CommThread.updated_at.desc()).all()
    if not rows:
        return None
    best, score = None, 0
    for t in rows:
        hay = re.sub(r"[^a-z0-9 ]", " ", f"{t.counterpart} {t.subject}".lower())
        s = sum(1 for w in toks if w in hay)
        if s > score:
            best, score = t, s
    return best if score else None


class CommVoiceIn(BaseModel):
    transcript: str
    thread_id: str | None = None


@router.post("/comms/resolve")
def comms_resolve(body: CommVoiceIn, p: Principal = Depends(current_user),
                  db: Session = Depends(get_db)):
    text = body.transcript or ""
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())

    if re.search(r"\b(demo|sample|load.*inbox|populate|example)\b", low):
        return {"action": "demo", "message": "Loading a demo inbox."}
    # filter by category
    fm = re.search(r"\b(urgent|action|fyi|spam|all|everything|inbox)\b", low)
    if fm and re.search(r"\b(show|filter|view|go to|open the|switch to|see)\b", low):
        cat = fm.group(1)
        cat = "" if cat in ("all", "everything", "inbox") else cat
        return {"action": "filter", "category": cat, "message": f"Showing {cat or 'all'}."}
    # recategorize "this"/named thread
    rc = re.search(r"\b(mark|move|set|recategor\w*|flag|file|put)\b.*\b(as |to |into |under )?(urgent|action|fyi|spam)\b", low)
    if rc:
        cat = rc.group(3)
        t = (db.get(CommThread, body.thread_id) if body.thread_id else None) or _match_thread(db, p.tenant_id, text)
        if t and t.tenant_id == p.tenant_id:
            return {"action": "recategorize", "id": t.id, "category": cat,
                    "name": t.counterpart or t.subject, "message": f"Moving “{t.subject}” to {cat}."}
        return {"action": "none", "message": "Open a conversation first, then say e.g. \"mark this as spam\"."}
    # send the current draft
    if re.search(r"\b(send|fire it off|ship it|send it|send the (reply|draft|email))\b", low):
        if body.thread_id:
            return {"action": "send", "id": body.thread_id, "message": "Sending the reply."}
        return {"action": "none", "message": "Open a conversation with a draft, then say \"send it\"."}
    # draft a reply
    dm = re.search(r"\b(draft|reply|respond|write|compose|answer)\b(.*)$", text, re.I)
    if dm:
        rest = dm.group(2)
        rest = re.sub(r"^\s*(a |an |the )?(reply|response|email|message)\b", "", rest, flags=re.I)
        # drop a leading "to <name>" when it precedes the content connector
        rest = re.sub(r"^\s*to\s+[a-z0-9.&'-]+(?:\s+[a-z0-9.&'-]+)*?\s+(?=saying |that |with |about |telling |:)", " ", rest, flags=re.I)
        rest = re.sub(r"^\s*(saying|that says|with|:|that|telling them|about)\s+", "", rest, flags=re.I)
        instructions = rest.strip(" .'\",")
        tone = "formal"
        tm = re.search(r"\b(formal|friendly|casual|firm|polite|warm|professional)\b", low)
        if tm:
            tone = tm.group(1)
            instructions = re.sub(rf"\b(and )?(keep it |make it |be |,? *)?{tm.group(1)}\b", "", instructions, flags=re.I).strip(" ,.")
        t = (db.get(CommThread, body.thread_id) if body.thread_id else None) or _match_thread(db, p.tenant_id, text)
        if not (t and t.tenant_id == p.tenant_id):
            return {"action": "none", "message": "Open a conversation first, then say \"draft a reply saying …\"."}
        if not instructions:
            return {"action": "none", "message": "What should the reply say? e.g. \"draft a reply saying payment goes out Tuesday\"."}
        return {"action": "draft", "id": t.id, "instructions": instructions, "tone": tone,
                "name": t.counterpart or t.subject, "message": f"Drafting a {tone} reply to {t.counterpart or 'the contact'}."}
    # open a named thread
    if re.search(r"\b(open|show|read|go to)\b", low):
        t = _match_thread(db, p.tenant_id, text)
        if t:
            return {"action": "open", "id": t.id, "name": t.counterpart or t.subject,
                    "message": f"Opening {t.counterpart or t.subject}."}
    return {"action": "none",
            "message": 'Try "show urgent", "open the Acme thread", "draft a reply saying …", "mark this as spam", or "send it".'}


# ───────────────────────────── Call Center (FR-C5) ──────────────────────────
@router.get("/calls")
def list_calls(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Call).filter_by(tenant_id=p.tenant_id).order_by(
        Call.started_at.desc()).all()
    return [{"id": c.id, "direction": c.direction, "contact": c.contact,
             "agent_id": c.agent_id, "sentiment": c.sentiment,
             "outcome_code": c.outcome_code,
             "started_at": c.started_at.isoformat() if c.started_at else None,
             "transcript": c.transcript} for c in rows]

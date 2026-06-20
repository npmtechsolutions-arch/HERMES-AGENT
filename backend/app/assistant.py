"""
The assistant spine (ARCHITECTURE §10 integration step). This is what the guide
promises: you say a sentence, Aria figures out which teammate/tool handles it,
and the work happens. It turns a natural-language utterance into ONE call_tool()
invocation against the registered Tier-1/2/3 tools + domain packs.

Routing is deterministic (rule-based) so it works fully offline — no cloud, no
local LLM required — which is the whole point of a private, local-first assistant.
Unmatched utterances fall back to memory.search (recall) so "what's my landlord's
name?" just works.

`call_tool` still does all the heavy lifting: permission, approval gates (money /
new-contact / destructive stop and ask), validation, retry, operational memory,
Activity feed, voice. We only pick the tool and extract the arguments.
"""
import re
from datetime import datetime, timedelta

from .tools import Actor, ToolContext, TOOL_REGISTRY, call_tool, registry_dto

# ── ensure every tool + pack is registered (import-time side effects) ─────────
# Importing these populates TOOL_REGISTRY; load_packs imports each pack's tools.
from . import tier1_tools, tier2_tools, tier3_tools  # noqa: F401,E402
from .packs import load_packs  # noqa: E402

load_packs()


_WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
             "friday": 4, "saturday": 5, "sunday": 6}
_RE_AMOUNT = re.compile(r"(?:₹|rs\.?|inr|rupees?)\s*([\d,]+(?:\.\d+)?)", re.I)
_RE_TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)\b", re.I)


def _amount(text):
    m = _RE_AMOUNT.search(text)
    return float(m.group(1).replace(",", "")) if m else 0


def _time_of_day(text, default_h=9):
    """Return (hour, minute) parsed from the utterance, or a sensible default."""
    m = _RE_TIME.search(text)
    if m:
        h = int(m.group(1)) % 12
        if m.group(3).lower().startswith("p"):
            h += 12
        return h, int(m.group(2) or 0)
    t = text.lower()
    if "morning" in t:
        return 8, 0
    if "afternoon" in t:
        return 15, 0
    if "evening" in t:
        return 18, 0
    if "tonight" in t or "night" in t:
        return 20, 0
    # bare "at 8" / "at 11"
    m2 = re.search(r"\bat\s+(\d{1,2})\b", t)
    if m2:
        h = int(m2.group(1))
        return (h if h > 7 else h + 12), 0   # "at 8" reads as 8am, "at 4" as 4pm
    return default_h, 0


def parse_when(text, now):
    """Natural-language → (iso_due_string|None, repeat). Pure + offline."""
    t = text.lower()
    repeat = "none"
    if re.search(r"\bevery (morning|day|night)\b|\bdaily\b", t):
        repeat = "daily"
    elif re.search(r"\bevery week\b|\bweekly\b", t):
        repeat = "weekly"
    elif re.search(r"\bevery (month|six months|6 months)\b|\bmonthly\b", t):
        repeat = "monthly"

    h, mi = _time_of_day(text)
    base = now.replace(hour=h, minute=mi, second=0, microsecond=0)

    if "tomorrow" in t:
        base = base + timedelta(days=1)
    elif "today" in t or "tonight" in t:
        pass
    else:
        for name, wd in _WEEKDAYS.items():
            if name in t:
                delta = (wd - now.weekday()) % 7
                if delta == 0 and ("next" in t or base <= now):
                    delta = 7
                base = base + timedelta(days=delta)
                break
        else:
            # recurring with no explicit day → first run is today (or tomorrow if past)
            if repeat != "none" and base <= now:
                base = base + timedelta(days=1)
            elif repeat == "none" and base <= now:
                base = base + timedelta(days=1)   # default to the next occurrence
    return base.isoformat(), repeat


def _strip(text, *phrases):
    out = text
    for p in phrases:
        out = re.sub(p, "", out, flags=re.I)
    return out.strip(" ,.:;-")


# ── intent routing ────────────────────────────────────────────────────────────
def route_intent(text, now):
    """Return (tool_name, kwargs, note) or ('__help__', {}, None) or None.

    Ordered most-specific-first. Returns None only when nothing matches AND it
    isn't a recall question (the caller then defaults to memory.search)."""
    t = text.lower().strip()

    if t in {"help", "?"} or "what can you do" in t or "what can i ask" in t:
        return ("__help__", {}, None)
    if re.search(r"\b(stop|cancel|undo)\b.*\b(that|it|message|last)\b", t) or t in {"undo", "stop that"}:
        return ("__undo__", {}, None)

    # ── day / briefing ──
    if re.search(r"plan my day|what'?s on my plate|my agenda|brief me|good morning", t):
        return ("briefing.compose", {"scope": "daily"}, None)

    # ── money / bills / subscriptions ──
    if "subscription" in t and re.search(r"what|which|paying|list|show|how many", t):
        return ("finance.budget_status", {"period": "month"}, None)
    if re.search(r"where.*money|spending|how much.*spend|spend.*on", t):
        return ("finance.spending_insight", {"period": "month"}, None)
    if re.search(r"\btrack\b.*\b(bill|subscription|insurance|netflix|spotify|prime)\b", t) or \
       (re.search(r"\b(bill|subscription|renew|insurance|expire)\b", t) and re.search(r"every (month|week|year)|monthly|yearly|weekly", t)):
        cadence = ("weekly" if "week" in t else "yearly" if ("year" in t or "insurance" in t) else "monthly")
        name = _strip(t, r"track( my)?", r"remind me( when| about)?", r"every (month|week|year|six months)",
                      r"monthly|yearly|weekly", r"\bbill\b", r"is about to expire", r"about to expire") or "subscription"
        return ("finance.track_subscription",
                {"subscription": name.title(), "amount": _amount(text), "cadence": cadence}, None)

    # ── reminders ──
    if re.search(r"\bremind me\b|\bset a reminder\b|\bremember to\b", t):
        due, repeat = parse_when(text, now)
        body = _strip(text, r"remind me( to| about)?", r"set a reminder( to| about| for)?", r"remember to",
                      r"every (morning|day|night|week|month|six months)", r"\bdaily\b|\bweekly\b|\bmonthly\b",
                      r"tomorrow|today|tonight", r"\bon\b", r"|".join(_WEEKDAYS),
                      r"at \d{1,2}(:\d{2})?\s*[ap]\.?m\.?", r"at \d{1,2}\b", r"in the (morning|afternoon|evening)")
        return ("reminder.create", {"text": body or "reminder", "due_at": due, "repeat": repeat}, None)

    # ── memory: remember (write) vs recall (search) ──
    if re.search(r"\bremember (that |my |i |we )", t) or t.startswith("remember "):
        content = _strip(text, r"remember that", r"remember")
        return ("memory.write", {"content": content, "memory_class": "personal"}, None)
    if re.search(r"\bforget\b", t):
        return ("memory.forget", {"query": _strip(text, r"forget( that| my)?")}, None)

    # ── messages / email ──
    if re.search(r"\b(read|show|check).*(email|inbox|mail)\b|urgent emails?", t):
        q = "urgent" if "urgent" in t else _strip(text, r"read|show|check|my|emails?|inbox|mail|about") or "recent"
        return ("email.list", {"query": q}, "Needs Gmail connected.")
    if re.search(r"\b(reply|respond|email|write).*\bto\b", t) and "note" not in t:
        m = re.search(r"\bto\s+([A-Za-z][\w'.@ ]+?)(?:\s+(?:and|saying|say|that|tell)|[,.]|$)", text, re.I)
        to = (m.group(1).strip() if m else "")
        body = _strip(text, r".*\b(say|saying|tell\s+\w+|that)\b") if re.search(r"\bsay|saying|tell|that\b", t) else ""
        return ("email.draft", {"to": to, "subject": "(draft)", "body": body or text}, "Needs Gmail connected.")
    if re.search(r"did anyone (message|email|write|contact)|messages? about|heard back", t):
        about = _strip(text, r"did anyone (message|email|write|contact) me about", r"any messages? about", r"about")
        return ("email.list", {"query": about or "recent"}, "Needs Gmail connected.")

    # ── calendar ──
    if re.search(r"\bam i free\b|\bfree (on |this )?\w+|find (a )?slot|when am i free", t):
        return ("calendar.find_slots", {"duration_min": 30}, "Needs Calendar connected.")
    if re.search(r"book a meeting|schedule a meeting|set up a (call|meeting)|meeting with", t):
        m = re.search(r"with\s+([A-Za-z][\w' ]+?)(?:\s+(?:on|next|this|at|tomorrow)|[,.]|$)", text, re.I)
        who = m.group(1).strip() if m else "meeting"
        return ("calendar.create_event", {"title": f"Meeting with {who}", "attendees": [who]}, "Needs Calendar connected.")

    # ── research (before writing, so "research … and summarize" → web) ──
    if re.search(r"\bresearch\b|\bcompare\b|best .* under|look up|search (the web|online) for", t):
        q = _strip(text, r"research", r"and summari[sz]e( it)?", r"for me") or text
        return ("web.search", {"query": q, "n": 5}, None)

    # ── writing / documents ──
    if re.search(r"\binvoice\b", t):
        amt = _amount(text)
        m = re.search(r"\bfor\b\s+(.+)$", text, re.I)
        what = (m.group(1).strip() if m else "services")
        content = f"Invoice\n\nFor: {what}\nAmount: ₹{amt:,.0f}\n"
        return ("document.generate", {"title": "Invoice", "content": content, "source": content}, None)
    if re.search(r"write (a |an |me )?(thank|note|letter|email|message|reply|draft)", t):
        title = _strip(text, r"write (a |an |me )?") or "Note"
        return ("document.generate", {"title": title.title()[:60], "content": f"{title}\n\n(Drafted by Scribe.)"}, None)
    if re.search(r"summari[sz]e\b", t):
        src = _strip(text, r"summari[sz]e( this| the)?( pdf| document| text| email)?")
        return ("text.summarize", {"source": src or text}, None)
    if re.search(r"clean up|make (it|this) (polite|formal|better)|polish|rewrite", t):
        return ("text.polish", {"text": _strip(text, r"clean up( this)?( rough)?( text)?", r"and make (it|this) polite")}, None)

    # ── booking / external actions → one-tap handoff (never autonomous) ──
    if re.search(r"\bbook (a |an )?(table|cab|taxi|ride|appointment|reservation)\b|reserve a", t):
        return ("handoff.prepare",
                {"action_type": "booking", "payload": {"request": text, "when": parse_when(text, now)[0]}}, None)
    if re.search(r"\bpay\b|\bsend money|\btransfer\b", t):
        return ("handoff.prepare",
                {"action_type": "bill_payment", "payload": {"request": text}},
                "Money is never moved automatically — you confirm and pay.")

    return None


HELP_TEXT = (
    "I'm Aria, your chief of staff. Just tell me what you need — for example:\n"
    "• “Remind me to call the bank tomorrow at 11am.”\n"
    "• “Remember my landlord's name is Mr. Sharma.” / “What's my landlord's name?”\n"
    "• “Track my electricity bill every month.” / “What subscriptions am I paying for?”\n"
    "• “Write a thank-you note to my client.” / “Make me an invoice for ₹15,000 for consulting.”\n"
    "• “Research the best laptops under ₹60,000 and summarize.”\n"
    "• “Book a table for 4 at Spice Garden Friday 8pm.”\n"
    "Connect Gmail/Calendar/WhatsApp in Settings to also read mail and book real events."
)


# ── undo: pull back the most recent reversible action (guide Part 5) ──────────
def _undo_last(ctx):
    from .models import Reminder, WhatsAppOutbox
    # most recent queued message first (pull it back), else the last reminder set
    wa = (ctx.db.query(WhatsAppOutbox).filter_by(tenant_id=ctx.actor.tenant_id, status="queued")
          .order_by(WhatsAppOutbox.id.desc()).first())
    if wa:
        wa.status = "canceled"; ctx.db.flush()
        return {"ok": True, "summary": "Pulled that message back before it sent."}
    rem = (ctx.db.query(Reminder).filter_by(tenant_id=ctx.actor.tenant_id, status="active")
           .order_by(Reminder.id.desc()).first())
    if rem:
        rem.status = "canceled"; ctx.db.flush()
        return {"ok": True, "summary": f"Cancelled the last reminder (“{rem.text}”)."}
    return {"ok": False, "summary": "Nothing recent to undo."}


# ── the public entry point ────────────────────────────────────────────────────
def _result_dto(tool_name, r, note=None):
    needs = bool(r.data.get("needs_approval")) or r.error == "user_input_needed"
    return {
        "ok": r.ok, "tool": tool_name, "summary": r.summary, "data": r.data,
        "artifacts": [{k: v for k, v in a.items() if k != "content"} for a in (r.artifacts or [])],
        "error": r.error, "needs_approval": needs and not r.ok,
        "note": note,
    }


def run_assistant(db, *, tenant_id, user_id, text, approved=False, speak=None, clarify=None):
    """Route one utterance to a tool and run it. Returns a JSON-able dict."""
    actor = Actor(tenant_id=tenant_id, user_id=user_id, agent_id="Aria", grants={"*"})
    ctx = ToolContext(actor=actor, db=db, approved=approved, speak=speak,
                      request_clarification=clarify)
    routed = route_intent(text, ctx.now)

    if routed is None:
        # not a command — treat as a recall question against the Second Brain
        r = call_tool("memory.search", ctx, query=text)
        return _result_dto("memory.search", r)

    name, kwargs, note = routed
    if name == "__help__":
        return {"ok": True, "tool": "help", "summary": HELP_TEXT, "data": {}, "artifacts": [],
                "error": None, "needs_approval": False, "note": None}
    if name == "__undo__":
        out = _undo_last(ctx)
        return {"ok": out["ok"], "tool": "undo", "summary": out["summary"], "data": {}, "artifacts": [],
                "error": None, "needs_approval": False, "note": None}

    r = call_tool(name, ctx, **kwargs)
    return _result_dto(name, r, note)


def capabilities():
    """Grouped tool catalog for a discovery UI."""
    groups = {}
    for d in registry_dto():
        domain = d["name"].split(".")[0]
        groups.setdefault(domain, []).append(d)
    return {"help": HELP_TEXT, "domains": groups, "count": len(TOOL_REGISTRY)}

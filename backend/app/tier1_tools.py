"""
Tier-1 tools — Scheduler + Scribe (Doc 22 Prompt C). Local Python functions
registered with @tool; the call_tool wrapper handles permission/approval/retry/
memory/activity, so these bodies stay simple (ARCHITECTURE §3). Each returns a
one-sentence summary. Local only — no external network calls.
"""
import json
import re
from datetime import datetime, timedelta

from . import ceo_agent, llm
from .models import (Agent, KGEntity, MemoryItem, Reminder, RoiEntry, Schedule,
                     Task, now as _now)
from .security import ulid
from .tools import ToolResult, tool


def _parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _register_trigger(ctx, *, kind, expression, next_run_at):
    """Register a trigger with the existing scheduler (the `schedules` table)."""
    ctx.db.add(Schedule(id=ulid("sch"), tenant_id=ctx.actor.tenant_id, workflow_id=None,
                        kind=kind, expression=expression, next_run_at=next_run_at,
                        run_policy="run_on_wake"))


# ── source-citation guard (ARCHITECTURE §5 / rule U4) ────────────────────────
_RE_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")   # don't capture a trailing '.' (end-of-sentence)
# question/stop words dropped before keyword-matching the Second Brain
_STOPWORDS = {"the", "what", "whats", "when", "where", "who", "why", "how", "did",
              "does", "was", "are", "is", "my", "me", "you", "your", "for", "and",
              "that", "this", "his", "her", "their", "name", "about", "any", "have",
              "has", "with", "from", "was", "tell", "show", "find", "out", "get"}
_RE_DATE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b")


def validate_citations(content: str, source):
    """Every figure/date in outbound content MUST appear in the source. Returns the
    first unmatched token (→ the caller blocks, fail-closed) or None if all match."""
    src = source if isinstance(source, str) else json.dumps(source)
    src_norm = src.replace(",", "")
    for d in set(_RE_DATE.findall(content or "")):
        if d not in src:
            return d
    for tok in set(_RE_NUM.findall(content or "")):
        t = tok.replace(",", "")
        if t and t not in src_norm and tok not in src:
            return tok
    return None


# ════════════════════════════ SCHEDULER ═════════════════════════════════════
@tool("reminder.create", "Create a reminder at a time, optionally repeating.",
      {"text": {"type": "string", "required": True}, "due_at": {"type": "string", "required": True},
       "repeat": {"type": "string", "enum": ["none", "daily", "weekly", "monthly"], "default": "none"}},
      permission="reminders.write", writes_memory=True)
def reminder_create(ctx, text, due_at, repeat="none"):
    due = _parse_dt(due_at)
    # ask-don't-guess: a past time is usually a parse error (ARCHITECTURE §5)
    if due and due < ctx.now and ctx.request_clarification:
        ans = ctx.request_clarification(
            f"That time ({due:%d %b %I:%M %p}) is in the past — did you mean a future date?")
        due = _parse_dt(ans) or due
    r = Reminder(id=ulid("rem"), tenant_id=ctx.actor.tenant_id, user_id=ctx.actor.user_id,
                 text=text, due_at=due, repeat=repeat, kind="reminder", status="active")
    ctx.db.add(r); ctx.db.flush()
    _register_trigger(ctx, kind=("interval" if repeat != "none" else "event"),
                      expression=repeat, next_run_at=due)
    when = due.strftime("%a %d %b, %I:%M %p") if due else due_at
    return ToolResult(ok=True, data={"id": r.id, "due_at": due.isoformat() if due else due_at},
                      summary=f"Reminder set: “{text}” for {when}.")


@tool("reminder.list", "List reminders, optionally by status.",
      {"status": {"type": "string", "default": "active"}}, permission="reminders.read")
def reminder_list(ctx, status="active"):
    q = ctx.db.query(Reminder).filter_by(tenant_id=ctx.actor.tenant_id)
    if status:
        q = q.filter_by(status=status)
    rows = [{"id": r.id, "text": r.text, "due_at": r.due_at.isoformat() if r.due_at else None,
             "repeat": r.repeat, "kind": r.kind, "status": r.status}
            for r in q.order_by(Reminder.due_at).all()]
    return ToolResult(ok=True, data={"reminders": rows}, summary=f"You have {len(rows)} {status} reminder(s).")


@tool("reminder.update", "Update a reminder's text / time / repeat.",
      {"id": {"type": "string", "required": True}, "text": {"type": "string"},
       "due_at": {"type": "string"}, "repeat": {"type": "string", "enum": ["none", "daily", "weekly", "monthly"]}},
      permission="reminders.write", writes_memory=True)
def reminder_update(ctx, id, text=None, due_at=None, repeat=None):
    r = ctx.db.get(Reminder, id)
    if not r or r.tenant_id != ctx.actor.tenant_id:
        return ToolResult(ok=False, error="validation", summary="That reminder doesn't exist.")
    if text is not None:
        r.text = text
    if due_at is not None:
        r.due_at = _parse_dt(due_at)
    if repeat is not None:
        r.repeat = repeat
    return ToolResult(ok=True, data={"id": id}, summary=f"Updated the reminder “{r.text}”.")


@tool("reminder.cancel", "Cancel a reminder.", {"id": {"type": "string", "required": True}},
      permission="reminders.write", writes_memory=True)
def reminder_cancel(ctx, id):
    r = ctx.db.get(Reminder, id)
    if not r or r.tenant_id != ctx.actor.tenant_id:
        return ToolResult(ok=False, error="validation", summary="That reminder doesn't exist.")
    r.status = "canceled"
    return ToolResult(ok=True, data={"id": id}, summary=f"Canceled the reminder “{r.text}”.")


@tool("routine.create", "Create a recurring routine.",
      {"name": {"type": "string", "required": True}, "cadence": {"type": "string", "required": True}},
      permission="reminders.write", writes_memory=True)
def routine_create(ctx, name, cadence):
    c = cadence.lower()
    repeat = "daily" if "day" in c else "weekly" if "week" in c else "monthly"
    r = Reminder(id=ulid("rem"), tenant_id=ctx.actor.tenant_id, user_id=ctx.actor.user_id,
                 text=name, repeat=repeat, kind="routine", detail=cadence, status="active")
    ctx.db.add(r); ctx.db.flush()
    _register_trigger(ctx, kind="cron", expression=cadence, next_run_at=None)
    return ToolResult(ok=True, data={"id": r.id}, summary=f"Routine created: “{name}” ({cadence}).")


@tool("deadline.track", "Track a bill / renewal / license deadline.",
      {"label": {"type": "string", "required": True}, "due_at": {"type": "string", "required": True},
       "kind": {"type": "string", "enum": ["bill", "renewal", "license"], "default": "bill"}},
      permission="reminders.write", writes_memory=True)
def deadline_track(ctx, label, due_at, kind="bill"):
    due = _parse_dt(due_at)
    r = Reminder(id=ulid("rem"), tenant_id=ctx.actor.tenant_id, user_id=ctx.actor.user_id,
                 text=label, due_at=due, repeat="none", kind="deadline", detail=kind, status="active")
    ctx.db.add(r); ctx.db.flush()
    _register_trigger(ctx, kind="event", expression="once", next_run_at=due)
    when = due.strftime("%d %b %Y") if due else due_at
    return ToolResult(ok=True, data={"id": r.id}, summary=f"Tracking your {kind}: “{label}” due {when}.")


# ════════════════════════════ SCRIBE ════════════════════════════════════════
def _mem(ctx, title, body, source="note", mclass="personal"):
    m = MemoryItem(id=ulid("mem"), tenant_id=ctx.actor.tenant_id, memory_class=mclass,
                   title=title, source_type=source, body=body, tier="hot", confidence=1.0)
    ctx.db.add(m); ctx.db.flush()
    return m


@tool("note.create", "Save a note to the Second Brain.",
      {"text": {"type": "string", "required": True}, "tags": {"type": "array"}},
      permission="memory.write", writes_memory=True)
def note_create(ctx, text, tags=None):
    title = (text.strip().split("\n")[0])[:60] or "Note"
    _mem(ctx, title, text, "note")
    return ToolResult(ok=True, data={"title": title}, summary=f"Noted: “{title}”.")


@tool("note.search", "Search notes & memory.",
      {"query": {"type": "string", "required": True}, "top_k": {"type": "number", "default": 5}},
      permission="memory.read")
def note_search(ctx, query, top_k=5):
    rows = (ctx.db.query(MemoryItem).filter_by(tenant_id=ctx.actor.tenant_id)
            .filter(MemoryItem.tier != "deleted")
            .filter(MemoryItem.body.ilike(f"%{query}%") | MemoryItem.title.ilike(f"%{query}%"))
            .order_by(MemoryItem.created_at.desc()).limit(int(top_k)).all())
    hits = [{"id": m.id, "title": m.title, "class": m.memory_class} for m in rows]
    return ToolResult(ok=True, data={"results": hits}, summary=f"Found {len(hits)} item(s) for “{query}”.")


@tool("list.manage", "Add/remove/check an item on a named list.",
      {"list_name": {"type": "string", "required": True},
       "op": {"type": "string", "enum": ["add", "remove", "check"], "required": True},
       "item": {"type": "string", "required": True}},
      permission="memory.write", writes_memory=True)
def list_manage(ctx, list_name, op, item):
    m = (ctx.db.query(MemoryItem)
         .filter_by(tenant_id=ctx.actor.tenant_id, source_type="list", title=list_name).first())
    items = json.loads(m.body) if (m and m.body) else []
    if op == "add" and item not in items:
        items.append(item)
    elif op == "remove" and item in items:
        items.remove(item)
    has = item in items
    if not m:
        _mem(ctx, list_name, json.dumps(items), "list")
    else:
        m.body = json.dumps(items)
    verb = f"{'has' if has else 'no'} “{item}”" if op == "check" else f"{op}ed “{item}” on"
    return ToolResult(ok=True, data={"list": list_name, "items": items},
                      summary=f"Your “{list_name}” list: {verb} ({len(items)} item(s)).")


@tool("document.generate", "Generate a document; every figure/date must match the source, or it's blocked.",
      {"title": {"type": "string", "required": True}, "content": {"type": "string", "required": True},
       "source": {"type": "string"}, "format": {"type": "string", "enum": ["md", "txt"], "default": "md"}},
      permission="documents.write", writes_memory=True)
def document_generate(ctx, title, content, source=None, format="md"):
    if source:
        bad = validate_citations(content, source)
        if bad:
            return ToolResult(ok=False, error="validation",
                              summary=f"Blocked: “{bad}” isn't in the source — not generating (source-cited figures only).")
    doc = f"# {title}\n\n{content}\n" if format == "md" else f"{title}\n\n{content}\n"
    _mem(ctx, title, content, "document")
    return ToolResult(ok=True, data={"title": title},
                      artifacts=[{"kind": "document", "title": title, "ext": format, "content": doc}],
                      summary=f"Created “{title}” ({format.upper()}).")


@tool("text.summarize", "Summarize text or a memory item.",
      {"source": {"type": "string", "required": True}, "length": {"type": "string", "default": "short"}},
      permission="documents.read")
def text_summarize(ctx, source, length="short"):
    text = source
    if source.startswith("mem_"):
        m = ctx.db.get(MemoryItem, source)
        text = (m.body if m else "") or ""
    if llm.available() and text.strip():
        out = llm.chat(text[:6000], system="Summarize into a few clear sentences. Return ONLY the summary.")
        if out:
            return ToolResult(ok=True, data={"summary": out.strip()}, summary="Summarized it.", confidence=0.9)
    s = ". ".join([x.strip() for x in text.replace("\n", " ").split(".") if x.strip()][:3])
    return ToolResult(ok=True, data={"summary": s}, summary="Summarized it (on-device).", confidence=0.5)


@tool("text.polish", "Clean up / rewrite rough text.",
      {"text": {"type": "string", "required": True}, "tone": {"type": "string", "default": "clean"}},
      permission="documents.read")
def text_polish(ctx, text, tone="clean"):
    from .routers.dictate import _rule_clean
    base = _rule_clean(text)
    if llm.available():
        out = llm.chat(base, system="Clean up this text; fix grammar/filler; keep meaning. Return ONLY the text.")
        if out:
            return ToolResult(ok=True, data={"text": out.strip()}, summary="Polished the text.")
    return ToolResult(ok=True, data={"text": base}, summary="Polished the text (on-device rules).")


@tool("content.refine", "Refine an existing result with a plain-language instruction (content only).",
      {"prior_output": {"type": "string", "required": True},
       "instruction": {"type": "string", "required": True},
       "source": {"type": "string"}},
      permission="documents.write", writes_memory=True)
def content_refine(ctx, prior_output, instruction, source=None):
    """Doc 30 Phase 1. Improves an existing result per the user's instruction —
    fully on-device (local LLM). Guardrail §5/1.4: a refined version may not
    introduce a figure/date absent from the original (source) — it's blocked, not
    saved. Refinement changes content, never the approval rules of later actions."""
    out = None
    if llm.available():
        out = llm.chat(
            f"CONTENT:\n{prior_output}\n\nINSTRUCTION: {instruction}\n\nReturn ONLY the revised content, nothing else.",
            system=("You refine the user's existing content per their instruction. Preserve every fact, "
                    "number and date; change only what's asked. Never invent new numbers or dates."))
    if not out:
        out = prior_output    # no local model → return unchanged rather than fabricate
    bad = validate_citations(out, source) if source else None
    if bad:
        return ToolResult(ok=False, error="validation",
                          summary=f"Blocked — the refined version has “{bad}”, which isn't in the original. Not saved.")
    return ToolResult(ok=True, data={"output": out.strip()}, summary="Refined the result.")


@tool("form.fill", "Fill a {{placeholder}} form from data; figures validated against the data source.",
      {"template": {"type": "string", "required": True}, "data": {"type": "object", "required": True},
       "title": {"type": "string", "default": "Form"}},
      permission="documents.write", writes_memory=True)
def form_fill(ctx, template, data, title="Form"):
    filled = template
    for k, v in (data or {}).items():
        filled = filled.replace("{{" + str(k) + "}}", str(v))
    bad = validate_citations(filled, data)
    if bad:
        return ToolResult(ok=False, error="validation",
                          summary=f"Blocked: “{bad}” isn't in your data — not filling (no invented figures).")
    _mem(ctx, title, filled, "form")
    return ToolResult(ok=True, data={"title": title},
                      artifacts=[{"kind": "form", "title": title, "ext": "txt", "content": filled}],
                      summary=f"Filled “{title}” from your data.")


# ════════════════════════════ FINDER (Doc 22 Prompt D) ══════════════════════
@tool("memory.search", "Search the Second Brain.",
      {"query": {"type": "string", "required": True},
       "scopes": {"type": "array"}, "top_k": {"type": "number", "default": 5}},
      permission="memory.read")
def memory_search(ctx, query, scopes=None, top_k=5):
    # Keyword match (not whole-string): a natural question like "what's my
    # landlord's name?" must find "my landlord's name is Mr. Sharma". We drop
    # stop/question words, OR-match the rest, and rank by how many tokens hit.
    from sqlalchemy import or_
    tokens = [w for w in re.findall(r"[a-z]{3,}", query.lower()) if w not in _STOPWORDS]
    base = (ctx.db.query(MemoryItem).filter_by(tenant_id=ctx.actor.tenant_id)
            .filter(MemoryItem.tier != "deleted"))
    if scopes:
        base = base.filter(MemoryItem.memory_class.in_(scopes))
    if tokens:
        conds = []
        for w in tokens:
            conds += [MemoryItem.body.ilike(f"%{w}%"), MemoryItem.title.ilike(f"%{w}%")]
        base = base.filter(or_(*conds))
    else:
        base = base.filter(MemoryItem.body.ilike(f"%{query}%") | MemoryItem.title.ilike(f"%{query}%"))
    rows = base.order_by(MemoryItem.created_at.desc()).limit(50).all()

    def _score(m):
        hay = f"{m.title} {m.body}".lower()
        return sum(1 for w in tokens if w in hay)
    rows = sorted(rows, key=_score, reverse=True)[:int(top_k)]
    hits = [{"id": m.id, "title": m.title, "class": m.memory_class} for m in rows]
    return ToolResult(ok=True, data={"results": hits}, summary=f"Found {len(hits)} item(s) for “{query}”.")


@tool("memory.write", "Write a memory (memory_class: personal|business|knowledge).",
      {"content": {"type": "string", "required": True},
       "memory_class": {"type": "string", "default": "personal"}, "entity_links": {"type": "array"}},
      permission="memory.write", writes_memory=True)
def memory_write(ctx, content, memory_class="personal", entity_links=None):
    title = (content.strip().split("\n")[0])[:60] or "Memory"
    _mem(ctx, title, content, "note", memory_class)
    return ToolResult(ok=True, data={"title": title}, summary=f"Remembered: “{title}”.")


@tool("memory.forget", "Forget a memory (soft-delete, 30-day recovery).",
      {"id": {"type": "string", "required": True}},
      permission="memory.write", approval="required", writes_memory=True)
def memory_forget(ctx, id):
    m = ctx.db.get(MemoryItem, id)
    if not m or m.tenant_id != ctx.actor.tenant_id:
        return ToolResult(ok=False, error="validation", summary="That memory doesn't exist.")
    m.tier = "deleted"   # MC-04 soft delete; recoverable for 30 days
    return ToolResult(ok=True, data={"id": id}, summary=f"Forgotten “{m.title}” (recoverable for 30 days).")


@tool("contact.upsert", "Add or update a contact.",
      {"name": {"type": "string", "required": True}, "relationship": {"type": "string"},
       "fields": {"type": "object"}},
      permission="contacts.write", writes_memory=True)
def contact_upsert(ctx, name, relationship=None, fields=None):
    e = (ctx.db.query(KGEntity)
         .filter_by(tenant_id=ctx.actor.tenant_id, type="contact", name=name).first())
    attrs = dict(fields or {})
    if relationship:
        attrs["relationship"] = relationship
    if e:
        e.attrs = {**(e.attrs or {}), **attrs}
    else:
        e = KGEntity(id=ulid("ent"), tenant_id=ctx.actor.tenant_id, type="contact", name=name, attrs=attrs)
        ctx.db.add(e); ctx.db.flush()
    return ToolResult(ok=True, data={"id": e.id, "name": name}, summary=f"Saved contact: {name}.")


@tool("contact.lookup", "Find a contact by name or mention.",
      {"name_or_mention": {"type": "string", "required": True}}, permission="contacts.read")
def contact_lookup(ctx, name_or_mention):
    rows = (ctx.db.query(KGEntity).filter_by(tenant_id=ctx.actor.tenant_id, type="contact")
            .filter(KGEntity.name.ilike(f"%{name_or_mention}%")).limit(5).all())
    hits = [{"id": e.id, "name": e.name, "attrs": e.attrs} for e in rows]
    return ToolResult(ok=True, data={"contacts": hits}, summary=f"Found {len(hits)} contact(s).")


# ════════════════════════════ INBOX (drafting; send is Tier-2) ══════════════
@tool("message.draft", "Draft a message — produces a draft only, never sends.",
      {"to": {"type": "string", "required": True}, "intent": {"type": "string", "required": True},
       "tone": {"type": "string", "default": "friendly"}},
      permission="messages.draft", writes_memory=True)
def message_draft(ctx, to, intent, tone="friendly"):
    draft = None
    if llm.available():
        draft = llm.chat(f"Write a {tone} short message to {to}. Intent: {intent}.",
                         system="Return ONLY the message body, ready for the user to review.")
    if not draft:
        draft = f"Hi {to},\n\n{intent}\n\nThanks."
    _mem(ctx, f"Draft to {to}", draft, "draft")
    return ToolResult(ok=True, data={"to": to, "draft": draft},
                      summary=f"Drafted a message to {to} (review before sending).")


@tool("followup.schedule", "Schedule a follow-up reminder.",
      {"about": {"type": "string", "required": True}, "cadence": {"type": "string", "default": "in 3 days"}},
      permission="reminders.write", writes_memory=True)
def followup_schedule(ctx, about, cadence="in 3 days"):
    days = next((n for n in range(1, 31) if str(n) in cadence), 3)
    due = ctx.now + timedelta(days=days)
    r = Reminder(id=ulid("rem"), tenant_id=ctx.actor.tenant_id, user_id=ctx.actor.user_id,
                 text=f"Follow up: {about}", due_at=due, kind="followup", status="active")
    ctx.db.add(r); ctx.db.flush()
    _register_trigger(ctx, kind="event", expression="once", next_run_at=due)
    return ToolResult(ok=True, data={"id": r.id}, summary=f"Follow-up on “{about}” set for {due:%d %b}.")


# ════════════════════════════ ARIA (orchestration & reporting) ══════════════
@tool("task.plan", "Decompose a goal into a plan (the CEO-Agent assigns agents).",
      {"utterance": {"type": "string", "required": True}}, permission="orchestrate")
def task_plan(ctx, utterance):
    agents = [{"name": a.name, "designation": a.designation}
              for a in ctx.db.query(Agent).filter_by(tenant_id=ctx.actor.tenant_id).all()]
    plan = ceo_agent.plan_task(utterance, agents)
    steps = plan.get("steps", []) if isinstance(plan, dict) else (plan or [])
    return ToolResult(ok=True, data={"plan": plan}, summary=f"Planned “{utterance[:48]}” into {len(steps)} step(s).")


@tool("briefing.compose", "Compose a daily/weekly briefing.",
      {"scope": {"type": "string", "enum": ["daily", "weekly"], "default": "daily"}},
      permission="orchestrate")
def briefing_compose(ctx, scope="daily"):
    open_tasks = (ctx.db.query(Task).filter_by(tenant_id=ctx.actor.tenant_id)
                  .filter(Task.status.notin_(["done", "canceled"])).count())
    rems = ctx.db.query(Reminder).filter_by(tenant_id=ctx.actor.tenant_id, status="active").count()
    text = f"Your {scope} briefing: {open_tasks} task(s) in flight, {rems} active reminder(s)."
    return ToolResult(ok=True, data={"text": text, "open_tasks": open_tasks, "reminders": rems}, summary=text)


@tool("roi.summarize", "Summarize the value the assistant delivered.",
      {"period": {"type": "string", "default": "week"}}, permission="orchestrate")
def roi_summarize(ctx, period="week"):
    rows = ctx.db.query(RoiEntry).filter_by(tenant_id=ctx.actor.tenant_id).all()
    hours = round(sum(float(getattr(r, "value_minutes", 0) or 0) for r in rows) / 60, 1)
    return ToolResult(ok=True, data={"hours_saved": hours, "items": len(rows)},
                      summary=f"This {period}: {len(rows)} action(s), ~{hours} hours saved.")

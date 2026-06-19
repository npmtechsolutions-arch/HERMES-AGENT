"""
Golden tests for Prompt D tools (Finder + Inbox + Aria) + the voice round-trip
(Doc 22 / ARCHITECTURE §5, §8, §9). Self-contained (in-memory SQLite).

Run:  python -m pytest tests/test_tier1_finder_inbox_aria.py -q
Or:   python tests/test_tier1_finder_inbox_aria.py
"""
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import tier1_tools  # noqa: E402,F401  (registers the tools)
from app.tools import Actor, ToolContext, call_tool  # noqa: E402


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _ctx(db, **kw):
    return ToolContext(actor=Actor(tenant_id="tnt_d", user_id="usr_d", agent_id="Aria",
                                   grants={"*"}), db=db, **kw)


def _future():
    from app.models import now as _now
    return (_now() + timedelta(days=2)).isoformat()


# ── Finder ───────────────────────────────────────────────────────────────────
def test_memory_write_and_search():
    db = _mkdb()
    assert call_tool("memory.write", _ctx(db), content="The gym closes at 9pm").ok
    db.commit()
    res = call_tool("memory.search", _ctx(db), query="gym")
    assert res.ok and len(res.data["results"]) >= 1


def test_memory_forget_requires_approval_then_softdeletes():
    from app.models import MemoryItem
    db = _mkdb()
    call_tool("memory.write", _ctx(db), content="secret thing"); db.commit()
    mid = db.query(MemoryItem).filter_by(source_type="note").first().id
    r1 = call_tool("memory.forget", _ctx(db), id=mid)
    assert r1.ok is False and r1.error == "user_input_needed", "destructive op needs approval (§5)"
    assert db.get(MemoryItem, mid).tier != "deleted"
    r2 = call_tool("memory.forget", _ctx(db, approved=True), id=mid); db.commit()
    assert r2.ok and db.get(MemoryItem, mid).tier == "deleted", "soft-delete on approval"


def test_contact_upsert_dedup_and_lookup():
    from app.models import KGEntity
    db = _mkdb()
    call_tool("contact.upsert", _ctx(db), name="Dr Mehta", relationship="doctor"); db.commit()
    call_tool("contact.upsert", _ctx(db), name="Dr Mehta", fields={"phone": "x"}); db.commit()
    assert db.query(KGEntity).filter_by(type="contact").count() == 1, "same contact deduped"
    lk = call_tool("contact.lookup", _ctx(db), name_or_mention="mehta")
    assert lk.ok and len(lk.data["contacts"]) == 1


# ── Inbox ────────────────────────────────────────────────────────────────────
def test_message_draft_only_never_sends():
    from app.models import MemoryItem
    db = _mkdb()
    r = call_tool("message.draft", _ctx(db), to="Ravi", intent="confirm tomorrow's meeting")
    db.commit()
    assert r.ok and r.data["draft"] and "review before sending" in r.summary
    assert db.query(MemoryItem).filter_by(source_type="draft").count() == 1, "stored as a draft, not sent"


def test_followup_schedule():
    from app.models import Reminder, Schedule
    db = _mkdb()
    r = call_tool("followup.schedule", _ctx(db), about="the Mehta lead", cadence="in 5 days")
    db.commit()
    assert r.ok
    assert db.query(Reminder).filter_by(kind="followup").count() == 1
    assert db.query(Schedule).count() == 1


# ── Aria ─────────────────────────────────────────────────────────────────────
def test_task_plan_returns_steps():
    db = _mkdb()
    r = call_tool("task.plan", _ctx(db), utterance="follow up with the Mehta lead and book a visit")
    assert r.ok and "plan" in r.data and "Planned" in r.summary


def test_briefing_and_roi():
    db = _mkdb()
    assert call_tool("briefing.compose", _ctx(db), scope="daily").ok
    assert call_tool("roi.summarize", _ctx(db), period="week").ok


# ── the voice round-trip (Doc 22 Prompt D) ───────────────────────────────────
def test_voice_round_trip():
    """Spoken utterance → (STT) → task.plan → tool call → spoken summary;
    operational-memory AND activity (audit) records must exist."""
    from app.models import AuditLog, MemoryItem
    db = _mkdb()
    spoken = []
    ctx = ToolContext(actor=Actor("tnt_v", "usr_v", "Aria", {"*"}), db=db,
                      speak=lambda s: spoken.append(s))

    utterance = "remind me to pay the electricity bill"          # STT output (text)
    plan = call_tool("task.plan", ctx, utterance=utterance)
    assert plan.ok
    # the planned step gets executed as a tool call:
    done = call_tool("reminder.create", ctx, text="pay the electricity bill", due_at=_future())
    assert done.ok
    db.commit()

    # operational-memory records exist (reminder.create writes_memory=True)
    assert db.query(MemoryItem).filter_by(memory_class="operational").count() >= 1
    # activity records exist (both tool summaries audited into the feed)
    assert db.query(AuditLog).filter_by(action="assistant.action").count() >= 2
    # the summary was spoken back (TTS)
    assert len(spoken) >= 2 and any("Reminder set" in s for s in spoken)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}"); passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
        except Exception as e:
            import traceback; traceback.print_exc(); print(f"  ERROR {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)

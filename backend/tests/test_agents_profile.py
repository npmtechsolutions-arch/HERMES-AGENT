"""
Tests for Agent Profile + weekly summary (Doc 26 Prompt K) and simple agent
creation (Prompt L). Crucially verifies the guardrails: a simple-created agent
gets ONLY safe tools, is permission-gated on a sensitive action, and CANNOT be
instructed around a locked approval rule (ARCHITECTURE §5).

Run:  python -m pytest tests/test_agents_profile.py -q
Or:   python tests/test_agents_profile.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.routers import agents_profile as AP  # noqa: E402
from app.tools import Actor, ToolContext, call_tool  # noqa: E402


class _P:
    kind = "user"; user_id = "usr_k"; tenant_id = "tnt_k"; roles = []; email = "k@x.com"


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


# ── simple creation infers SAFE tools only ────────────────────────────────────
def test_infer_tools_safe_only():
    tools = AP.infer_tools("Watch deal sites and tell me about discounts on cameras")
    assert "web.search" in tools
    assert all(not t.startswith(AP.SENSITIVE_PREFIXES) for t in tools)
    # sensitive tools never appear from a description that mentions email/whatsapp
    tools2 = AP.infer_tools("email my accountant and whatsapp my landlord every day")
    assert not any(t.startswith(("email.", "whatsapp.")) for t in tools2)
    assert "reminder.create" in tools2   # "every day" → safe scheduler tool


def test_safe_tools_excludes_sensitive_and_approval_gated():
    safe = AP.safe_tools()
    assert "email.send" not in safe and "handoff.prepare" not in safe and "browser.perform" not in safe
    assert "reminder.create" in safe and "web.search" in safe


def test_create_simple_grants_only_safe_tools():
    db = _mkdb(); p = _P()
    out = AP.create_simple(AP.Propose(description="watch camera deals each morning", name="Deal Hunter", cadence="every morning"), p, db)
    assert out["name"] == "Deal Hunter" and out["tools"]
    assert "email.send" not in out["tools"] and "handoff.prepare" not in out["tools"]
    from app.models import Agent
    assert db.query(Agent).filter_by(name="Deal Hunter").count() == 1


# ── the guardrails (non-negotiable) ───────────────────────────────────────────
def test_simple_agent_is_permission_gated_on_sensitive_action():
    db = _mkdb(); p = _P()
    out = AP.create_simple(AP.Propose(description="watch camera deals", name="Deal Hunter"), p, db)
    # the agent's real grants (permission strings of its safe tools)
    actor = Actor(tenant_id="tnt_k", user_id="usr_k", agent_id="Deal Hunter", grants=set(out["grants"]))
    ctx = ToolContext(actor=actor, db=db)
    r = call_tool("email.send", ctx, to="x@y.com", subject="hi", body="hi")
    assert not r.ok and r.error == "permission", "a simple agent must NOT be able to send email"


def test_cannot_be_instructed_around_a_locked_rule():
    # even a god-mode actor (grants='*') is stopped by a locked approval gate:
    # a destructive op (memory.forget) requires approval no matter the grants.
    db = _mkdb()
    actor = Actor(tenant_id="tnt_k", user_id="usr_k", agent_id="rogue", grants={"*"})
    ctx = ToolContext(actor=actor, db=db)
    r = call_tool("memory.forget", ctx, id="mem_anything")
    assert not r.ok and r.error == "user_input_needed", "destructive op stays gated regardless of grants"


# ── profile + weekly summary read real operational data ───────────────────────
def test_weekly_summary_from_operational_memory():
    db = _mkdb(); p = _P()
    # log a couple of real Scheduler actions via the assistant
    from app.assistant import run_assistant
    run_assistant(db, tenant_id="tnt_k", user_id="usr_k", text="Remind me to call the bank tomorrow at 11am.")
    run_assistant(db, tenant_id="tnt_k", user_id="usr_k", text="Remind me to pay rent on friday.")
    db.commit()
    s = AP.weekly_summary(db, "tnt_k", "Scheduler")
    assert s["actions"] >= 2 and "reminder.create" in s["by_tool"]
    assert "Scheduler handled" in s["phrase"] and s["minutes_saved"] > 0


def test_profile_and_light_edit():
    from app.models import Agent
    from app.security import ulid
    db = _mkdb(); p = _P()
    db.add(Agent(id=ulid("agt"), tenant_id="tnt_k", name="Scheduler", designation="Scheduler", status="idle"))
    db.commit()
    aid = db.query(Agent).filter_by(name="Scheduler").one().id
    prof = AP.profile(aid, p, db)
    assert prof["name"] == "Scheduler" and "this_week" in prof
    out = AP.light_edit(aid, AP.LightEdit(name="Maya", tone="formal", hours="9–6"), p, db)
    assert out["name"] == "Maya" and out["tone"] == "formal" and out["hours"] == "9–6"


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

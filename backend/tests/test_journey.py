"""
Tests for the Doc 27 dashboard layer: capabilities discovery, Work Summary,
Agent Activity (success/failure), and My Activity (user's own actions). Each runs
real commands through the assistant and asserts the views reflect them.

Run:  python -m pytest tests/test_journey.py -q
Or:   python tests/test_journey.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import assistant as A  # noqa: E402
from app.routers import journey as J  # noqa: E402


class _P:
    kind = "user"; user_id = "usr_j"; tenant_id = "tnt_j"; roles = []; email = "j@x.com"


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _seed(db):
    for t in ["Remind me to call the bank tomorrow at 11am.",
              "Remind me to pay rent on friday.",
              "Remember my landlord's name is Mr. Sharma.",
              "Make me an invoice for ₹15,000 for consulting."]:
        A.run_assistant(db, tenant_id="tnt_j", user_id="usr_j", text=t)
    db.commit()


# ── capabilities discovery (Part 2.1) ─────────────────────────────────────────
def test_capabilities_groups_with_tappable_examples():
    caps = A.capabilities()
    assert caps["product_line"].startswith("HERMUS Personal")
    keys = {g["key"] for g in caps["groups"]}
    assert {"reminders", "money", "documents", "research"} <= keys
    reminders = next(g for g in caps["groups"] if g["key"] == "reminders")
    assert any("call the bank" in e for e in reminders["examples"])


# ── work summary (Part 8) ─────────────────────────────────────────────────────
def test_work_summary_counts_value_and_trends():
    db = _mkdb(); _seed(db)
    s = J.work_summary("week", _P(), db)
    assert s["total_actions"] >= 4
    assert s["by_agent"].get("Scheduler", 0) >= 2 and "Scribe" in s["by_agent"]
    assert s["value"]["hours_saved"] > 0 and s["value"]["money_value_inr"] > 0
    assert s["trends"]["most_active_agent"] and "handled" in s["headline"]


# ── agent activity success/failure (Part 4.4) ─────────────────────────────────
def test_agent_activity_marks_success():
    db = _mkdb(); _seed(db)
    out = J.agent_activity(None, None, 60, _P(), db)
    assert out["activity"] and all(a["marker"] in ("success", "failed") for a in out["activity"])
    assert any(a["agent"] == "Scheduler" for a in out["activity"])
    # filter by agent works
    only = J.agent_activity("Scribe", None, 60, _P(), db)
    assert all(a["agent"] == "Scribe" for a in only["activity"])


# ── agent action summary (Part 4) ─────────────────────────────────────────────
def test_agents_overview_full_picture():
    from app.models import Agent
    from app.security import ulid
    db = _mkdb()
    db.add(Agent(id=ulid("agt"), tenant_id="tnt_j", name="Scheduler", designation="Scheduler", status="idle"))
    db.add(Agent(id=ulid("agt"), tenant_id="tnt_j", name="Aria", designation="Chief of Staff", is_ceo=True, status="working"))
    db.commit()
    _seed(db)
    out = J.agents_overview(_P(), db)
    assert out["agents"][0]["is_ceo"] is True               # Aria first
    sched = next(a for a in out["agents"] if a["name"] == "Scheduler")
    assert sched["this_week"]["actions"] >= 2 and "phrase" in sched["this_week"]
    assert sched["scheduled_count"] >= 2                      # active reminders counted
    assert out["totals"]["agents"] == 2


# ── my activity (Part 6) ──────────────────────────────────────────────────────
def test_my_activity_captures_user_commands():
    db = _mkdb(); _seed(db)
    out = J.my_activity(80, _P(), db)
    asks = [a for a in out["activity"] if a["kind"] == "Asked"]
    assert len(asks) >= 4
    assert any("call the bank" in (a["detail"] or "") for a in asks)


# ── daily per-agent report (Part 3.5 / §5.1c) ─────────────────────────────────
def test_daily_report_per_agent_and_totals():
    db = _mkdb(); _seed(db)
    rep = J.daily_report(None, _P(), db)
    names = [a["agent"] for a in rep["agents"]]
    assert names == ["Aria", "Scheduler", "Scribe", "Finder", "Inbox"]   # fixed order
    sched = next(a for a in rep["agents"] if a["agent"] == "Scheduler")
    assert sched["actions"] >= 2 and sched["status"] in ("ok", "pending", "failed")
    assert rep["totals"]["actions"] >= 4 and rep["totals"]["hours_saved"] > 0
    assert "Report for" in rep["narrative"]


def test_daily_report_counts_pending_as_needs_you():
    from app.models import Approval, now as _n
    from app.security import ulid
    db = _mkdb(); _seed(db)
    db.add(Approval(id=ulid("apv"), tenant_id="tnt_j", action_summary="forget x",
                    payload={"feature_key": "memory.forget"}, rule_id="SCHED-GATE", state="pending"))
    db.commit()
    rep = J.daily_report(None, _P(), db)
    assert rep["totals"]["pending"] >= 1 and rep["totals"]["needed_you"] >= 1
    finder = next(a for a in rep["agents"] if a["agent"] == "Finder")   # memory.forget → Finder
    assert finder["pending"] >= 1 and finder["status"] in ("pending", "failed")


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

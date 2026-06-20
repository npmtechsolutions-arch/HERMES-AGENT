"""
Tests for the Pro advanced agent editor (Doc 26 Prompt M). Verifies the
non-negotiables: a locked-rule bypass is rejected, a bad edit is one-click
revertible, delegation depth is capped, and the whole panel is Pro-gated.

Run:  python -m pytest tests/test_agents_advanced.py -q
Or:   python tests/test_agents_advanced.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import HTTPException

from app.routers import agents_advanced as AA  # noqa: E402


class _P:
    kind = "user"; user_id = "usr_m"; tenant_id = "tnt_m"; roles = []; email = "m@x.com"


def _mkdb(tier="pro"):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base, Tenant, Agent
    from app.security import ulid
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()
    db.add(Tenant(id="tnt_m", company_name="X", plan_tier=tier))
    db.add(Agent(id="agt_m", tenant_id="tnt_m", name="Scribe", designation="Scribe",
                 description="writes things", tools=["note.create"], status="idle", voice_id="v1"))
    db.commit()
    return db


# ── Pro gating ────────────────────────────────────────────────────────────────
def test_advanced_is_pro_gated():
    db = _mkdb(tier="personal"); p = _P()
    try:
        AA.save_draft("agt_m", AA.DraftIn(name="X"), p, db)
        assert False, "non-Pro must be blocked"
    except HTTPException as e:
        assert e.status_code == 402 and e.detail["code"] == "PRO_REQUIRED"
    assert AA.eligibility(p, db)["pro"] is False


def test_pro_can_open_advanced():
    db = _mkdb(); p = _P()
    assert AA.eligibility(p, db)["pro"] is True


# ── locked-rule bypass is REJECTED ────────────────────────────────────────────
def test_locked_rule_bypass_rejected():
    db = _mkdb(); p = _P()
    for bad in ({"permissions": {"external_send": "auto"}},
                {"permissions": {"bypass_approvals": True}},
                {"permissions": {"auto_money": True}}):
        try:
            AA.save_draft("agt_m", AA.DraftIn(**bad), p, db)
            assert False, f"should reject {bad}"
        except HTTPException as e:
            assert e.status_code == 400 and e.detail["code"] == "LOCKED_RULE"
    # the validator pins external_send back to approval_required on a benign edit
    clean, err = AA.validate_advanced({"permissions": {"spend_limit": 100}})
    assert err is None and clean["permissions"]["external_send"] == "approval_required"


def test_tool_grant_beyond_ceiling_rejected():
    db = _mkdb(); p = _P()
    try:
        AA.save_draft("agt_m", AA.DraftIn(tools=["note.create", "system.delete_everything"]), p, db)
        assert False
    except HTTPException as e:
        assert e.status_code == 400 and "beyond your plan ceiling" in e.detail["message"]


# ── delegation depth capped at 3 ──────────────────────────────────────────────
def test_delegation_depth_capped():
    clean, err = AA.validate_advanced({"delegation": {"enabled": True, "depth": 5}})
    assert err is None and clean["delegation"]["depth"] == 3


# ── bad edit is one-click revertible ──────────────────────────────────────────
def test_publish_then_revert_restores_previous_version():
    from app.models import Agent
    db = _mkdb(); p = _P()
    d = AA.save_draft("agt_m", AA.DraftIn(name="Maya", instructions="be terse", tools=["note.create", "web.search"]), p, db)
    AA.rehearse(d["id"], p, db)
    AA.publish(d["id"], p, db)
    a = db.get(Agent, "agt_m")
    assert a.name == "Maya" and "web.search" in (a.tools or [])
    AA.revert("agt_m", p, db)
    a = db.get(Agent, "agt_m")
    assert a.name == "Scribe" and a.tools == ["note.create"], "revert restored the pre-publish snapshot"


def test_rehearse_required_before_confident_publish():
    db = _mkdb(); p = _P()
    d = AA.save_draft("agt_m", AA.DraftIn(name="Z"), p, db)
    r = AA.rehearse(d["id"], p, db)
    assert r["ok"] and "Locked approval gates intact" in r["checks"]


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

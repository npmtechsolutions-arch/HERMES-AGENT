"""
Tests for refine-with-chat (Doc 30 Phase 1): a content result gets v1, refining
makes v2 (logged + versioned), revert flips the current version, and the §1.4
guardrail blocks a refinement that introduces a figure absent from the original.
The local LLM is mocked so the test is deterministic and offline.

Run:  python -m pytest tests/test_refine.py -q
Or:   python tests/test_refine.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import refine as R  # noqa: E402
from app import tier1_tools  # noqa: E402  (registers content.refine + has llm)
from app.routers import feature_run as FR  # noqa: E402


class _P:
    kind = "user"; user_id = "usr_rf"; tenant_id = "tnt_rf"; roles = []; email = "rf@x.com"


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _patch_llm(fn):
    """Force content.refine through a deterministic 'model'."""
    from app import llm
    o_av, o_ch = llm.available, llm.chat
    llm.available = lambda: True
    llm.chat = fn
    return lambda: (setattr(llm, "available", o_av), setattr(llm, "chat", o_ch))


# ── v1 is created for a content result, but not for an action ─────────────────
def test_content_run_creates_v1_action_does_not():
    db = _mkdb()
    out = FR.run_feature("note.create", FR.RunIn(params={"text": "Dear client, thank you for your business."}), _P(), db)
    assert out["ok"] and out.get("result_id"), "a note is refinable → has a result_id"
    # a reminder is an action, not content → no result_id
    out2 = FR.run_feature("reminder.create", FR.RunIn(params={"text": "x", "due_at": "2026-07-01T09:00:00+00:00"}), _P(), db)
    assert "result_id" not in out2


# ── refine makes v2; revert flips current ─────────────────────────────────────
def test_refine_creates_version_and_revert():
    db = _mkdb()
    rid = FR.run_feature("note.create", FR.RunIn(params={"text": "Dear client, thank you so much for everything."}), _P(), db)["result_id"]
    undo = _patch_llm(lambda prompt, system=None, **k: "Thanks for your business.")   # the "shorter" version
    try:
        out = R.refine(db, tenant_id="tnt_rf", user_id="usr_rf", anchor_id=rid, instruction="make it shorter")
    finally:
        undo()
    assert out["ok"] and out["version"]["version"] == 2 and out["version"]["is_current"]
    assert out["version"]["output"] == "Thanks for your business."
    hist = R.history(db, rid, "tnt_rf")
    assert len(hist["versions"]) == 2 and hist["versions"][1]["instruction"] == "make it shorter"
    # revert to v1
    rv = R.revert(db, tenant_id="tnt_rf", anchor_id=rid, version=1)
    assert rv["ok"]
    cur = [v for v in R.history(db, rid, "tnt_rf")["versions"] if v["is_current"]]
    assert len(cur) == 1 and cur[0]["version"] == 1


# ── §1.4 guardrail: a refinement can't introduce a new figure ─────────────────
def test_refine_blocks_fabricated_figure():
    db = _mkdb()
    rid = FR.run_feature("document.generate",
                         FR.RunIn(params={"title": "Invoice", "content": "Invoice for consulting. Amount: 15000.", "source": "Invoice for consulting. Amount: 15000."}),
                         _P(), db)["result_id"]
    undo = _patch_llm(lambda prompt, system=None, **k: "Invoice for consulting. Amount: 99999.")   # wrong number
    try:
        out = R.refine(db, tenant_id="tnt_rf", user_id="usr_rf", anchor_id=rid, instruction="tidy it up")
    finally:
        undo()
    assert not out["ok"] and "99999" in out["summary"], "fabricated figure must be blocked, not saved"
    assert len(R.history(db, rid, "tnt_rf")["versions"]) == 1, "no v2 saved"


def test_refine_unknown_result():
    db = _mkdb()
    out = R.refine(db, tenant_id="tnt_rf", user_id="usr_rf", anchor_id="nope", instruction="x")
    assert not out["ok"] and out["error"] == "not_found"


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

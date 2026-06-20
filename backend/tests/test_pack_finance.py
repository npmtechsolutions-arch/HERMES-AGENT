"""
Tests for the domain-pack mechanism + the Finance pack (Doc 24 step 9). Verifies
a pack is discovered (persona + tools + KG entity types + locked rules), its tools
work on the shared engines, and money is NEVER moved autonomously.

Run:  python -m pytest tests/test_pack_finance.py -q
Or:   python tests/test_pack_finance.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.packs import PACK_REGISTRY, load_packs  # noqa: E402
from app.tools import TOOL_REGISTRY, Actor, ToolContext, call_tool  # noqa: E402

load_packs(force=True)   # discover packs (imports finance/tools.py)


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _ctx(db):
    return ToolContext(actor=Actor("tnt_fin", "usr_fin", "Fin", {"*"}), db=db)


# ── the mechanism ─────────────────────────────────────────────────────────────
def test_pack_discovered_with_persona_tools_entities_rules():
    assert "finance" in PACK_REGISTRY
    p = PACK_REGISTRY["finance"]
    assert p.persona["name"] == "Fin" and "never move money" in p.persona["instructions"].lower()
    assert "finance.track_subscription" in p.tool_names and "finance.report" in p.tool_names
    assert {e["type"] for e in p.entity_types} >= {"Account", "Bill", "Subscription", "Budget"}
    assert any(r["id"] == "FIN-R1" and r.get("locked") for r in p.rules), "locked money rule present"


def test_money_never_autonomous():
    # there is NO pay/transfer tool — payment routes to handoff (Tier-3)
    assert not any(t.startswith("finance.pay") or t == "finance.transfer" for t in TOOL_REGISTRY)
    p = PACK_REGISTRY["finance"]
    assert any("handoff" in r["do"].lower() for r in p.rules if r["id"] == "FIN-R1")


# ── the tools (on the shared engines) ────────────────────────────────────────
def test_track_subscription_creates_kg_and_renewal():
    from app.models import KGEntity, Reminder
    db = _mkdb()
    r = call_tool("finance.track_subscription", _ctx(db), subscription="Netflix", amount=649, cadence="monthly")
    db.commit()
    assert r.ok
    assert db.query(KGEntity).filter_by(type="Subscription", name="Netflix").count() == 1
    assert db.query(Reminder).filter_by(kind="routine", detail="subscription").count() == 1


def test_bill_reminder_creates_bill_and_deadline():
    from app.models import KGEntity, Reminder
    db = _mkdb()
    r = call_tool("finance.bill_reminder", _ctx(db), biller="Electricity", amount=1500, due_at="2026-07-05")
    db.commit()
    assert r.ok
    assert db.query(KGEntity).filter_by(type="Bill", name="Electricity").count() == 1
    assert db.query(Reminder).filter_by(kind="deadline", detail="bill").count() == 1


def test_categorize_and_budget_and_insight():
    db = _mkdb()
    assert call_tool("finance.categorize", _ctx(db), description="Swiggy dinner").data["category"] == "dining"
    call_tool("finance.import_transactions", _ctx(db),
              transactions=[{"description": "Swiggy", "amount": 500}, {"description": "DMart groceries", "amount": 2000}])
    call_tool("finance.track_subscription", _ctx(db), subscription="Spotify", amount=119)
    db.commit()
    bs = call_tool("finance.budget_status", _ctx(db))
    assert bs.data["spent"] == 2500 and bs.data["subscriptions"] == 119
    ins = call_tool("finance.spending_insight", _ctx(db))
    assert ins.data["by_category"]["groceries"] == 2000 and ins.data["by_category"]["dining"] == 500


def test_report_produces_local_artifact():
    from app.models import TaskArtifact
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HERMUS_DATA_ROOT"] = tmp
        try:
            db = _mkdb()
            call_tool("finance.track_subscription", _ctx(db), subscription="Prime", amount=1499, cadence="yearly")
            r = call_tool("finance.report", _ctx(db), period="month"); db.commit()
            assert r.ok and r.artifacts and os.path.exists(r.artifacts[0]["path"])
            assert db.query(TaskArtifact).count() == 1
            with open(r.artifacts[0]["path"]) as f:
                assert "Finance report" in f.read()
        finally:
            os.environ.pop("HERMUS_DATA_ROOT", None)


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

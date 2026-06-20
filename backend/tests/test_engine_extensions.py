"""
Tests for the Doc 25 engine extensions (step 8): Model Gateway middleware
(scrub / classify / offline / fallback), NOW.md + SOUL.md projections, and the
cost dashboard. Self-contained (in-memory SQLite); cloud + local are mocked.

Run:  python -m pytest tests/test_engine_extensions.py -q
Or:   python tests/test_engine_extensions.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import gateway as G  # noqa: E402
from app import projections as P  # noqa: E402
from app.security import ulid  # noqa: E402
from app.tools import Actor, ToolContext  # noqa: E402


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _ctx(db):
    return ToolContext(actor=Actor("tnt_x", "usr_x", "Aria", {"*"}), db=db)


def _patch(mod, name, fn):
    orig = getattr(mod, name)
    setattr(mod, name, fn)
    return lambda: setattr(mod, name, orig)


# ── gateway: scrub / reinject ────────────────────────────────────────────────
def test_scrub_and_reinject_roundtrip():
    scrubbed, mapping = G.scrub_pii("mail anil@gmail.com or call 9876543210")
    assert "anil@gmail.com" not in scrubbed and "9876543210" not in scrubbed
    assert G.reinject_pii(scrubbed, mapping) == "mail anil@gmail.com or call 9876543210"


# ── gateway: classified / offline never touch cloud ──────────────────────────
def test_classified_content_stays_local():
    def _boom(*a, **k):
        raise AssertionError("cloud must NOT be called for classified content")
    r0 = _patch(G, "_call_cloud", _boom)
    try:
        db = _mkdb()
        out = G.gateway_dispatch(_ctx(db), "[CLASSIFIED] my medical record", target_tier="managed")
        assert out["tier"] == "local" and out["decision"] == "classified_local"
    finally:
        r0()


def test_offline_killswitch_stays_local():
    def _boom(*a, **k):
        raise AssertionError("cloud must NOT be called when offline")
    r0 = _patch(G, "_call_cloud", _boom)
    try:
        db = _mkdb()
        G.set_offline(db, "tnt_x", True)
        out = G.gateway_dispatch(_ctx(db), "summarize this", target_tier="managed")
        assert out["tier"] == "local" and out["decision"] == "offline_local"
    finally:
        r0()


# ── gateway: cloud path scrubs before sending + reinjects after ──────────────
def test_cloud_path_scrubs_then_reinjects():
    seen = {}
    r0 = _patch(G, "_call_cloud", lambda tier, prompt, system=None: seen.setdefault("prompt", prompt) or f"RESP {prompt}")
    try:
        db = _mkdb()
        out = G.gateway_dispatch(_ctx(db), "email anil@gmail.com now", target_tier="managed")
        assert "anil@gmail.com" not in seen["prompt"], "PII must be scrubbed before the cloud call"
        assert "anil@gmail.com" in out["text"], "PII re-injected locally in the response"
        assert out["scrubbed"] is True and out["tier"] == "managed"
    finally:
        r0()


# ── gateway: fallback to local on cloud failure + recorded ───────────────────
def test_cloud_failure_falls_back_to_local():
    from app.models import AuditLog, GatewayCall
    r0 = _patch(G, "_call_cloud", lambda *a, **k: (_ for _ in ()).throw(G.CloudUnavailable("429")))
    r1 = _patch(G, "_run_local", lambda prompt, system=None: "[local answer]")
    try:
        db = _mkdb()
        out = G.gateway_dispatch(_ctx(db), "draft a note", target_tier="managed")
        assert out["fallback"] is True and out["tier"] == "local" and out["text"] == "[local answer]"
        db.commit()
        assert db.query(GatewayCall).count() >= 1, "decision recorded in the cost ledger"
        assert db.query(AuditLog).filter_by(action="gateway.fallback").count() == 1, "fallback surfaced in Activity"
    finally:
        r1(); r0()


# ── NOW.md + SOUL.md projections ─────────────────────────────────────────────
def test_now_md_written_and_read():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HERMUS_DATA_ROOT"] = tmp
        try:
            db = _mkdb()
            path = P.update_now(db, "tnt_x", "usr_x", focus="ship the demo")
            assert path and os.path.exists(path) and path.endswith("NOW.md")
            assert "ship the demo" in P.load_now()
        finally:
            os.environ.pop("HERMUS_DATA_ROOT", None)


def test_soul_md_regenerates_from_memory():
    from app.models import KGEntity, MemoryItem
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HERMUS_DATA_ROOT"] = tmp
        try:
            db = _mkdb()
            db.add(MemoryItem(id=ulid("mem"), tenant_id="tnt_x", memory_class="personal",
                              title="Prefers tea over coffee", source_type="note", body="x", tier="hot"))
            db.add(KGEntity(id=ulid("ent"), tenant_id="tnt_x", type="contact", name="Dr Mehta",
                            attrs={"relationship": "doctor"}))
            db.commit()
            P.regenerate_soul(db, "tnt_x", "usr_x")
            soul = P.load_soul()
            assert "## Preferences" in soul and "Prefers tea over coffee" in soul
            assert "Dr Mehta" in soul and "doctor" in soul
        finally:
            os.environ.pop("HERMUS_DATA_ROOT", None)


def test_soul_edits_parsed_back_into_memory():
    from app.models import MemoryItem
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HERMUS_DATA_ROOT"] = tmp
        try:
            db = _mkdb()
            md = "# SOUL\n\n## Preferences\n- likes early meetings\n- no calls after 6pm\n\n## Values\n- privacy\n"
            added = P.parse_soul_edits(db, "tnt_x", "usr_x", md); db.commit()
            assert added == 2
            rows = db.query(MemoryItem).filter_by(source_type="preference").all()
            assert {r.title for r in rows} == {"likes early meetings", "no calls after 6pm"}
            assert all(r.confidence == 0.7 for r in rows), "user-edited → confidence-flagged"
        finally:
            os.environ.pop("HERMUS_DATA_ROOT", None)


# ── cost dashboard ────────────────────────────────────────────────────────────
def test_cost_dashboard_and_recommendations():
    from types import SimpleNamespace

    from app.models import GatewayCall, now as _n
    from app.routers.billing import cost_dashboard
    db = _mkdb()
    db.add(GatewayCall(id=ulid("g"), tenant_id="tnt_x", model="local", tier="local",
                       task_profile="summary", prompt_tokens=100, output_tokens=50, cost=0, at=_n()))
    for i in range(6):                       # 6 cloud calls of a cheap profile → a recommendation
        db.add(GatewayCall(id=ulid("g"), tenant_id="tnt_x", model="managed-model", tier="managed",
                           task_profile="summary", prompt_tokens=100, output_tokens=50, cost=0.5, at=_n()))
    db.commit()
    p = SimpleNamespace(tenant_id="tnt_x", user_id="usr_x", kind="user", roles=[])
    out = cost_dashboard(p, db)
    assert out["calls"] == 7 and out["total"] == 3.0
    assert any(m["tier"] == "managed" for m in out["by_model"])
    assert out["by_day"] and out["projected_month"] > 0
    assert out["recommendations"] and "summary" in out["recommendations"][0]


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

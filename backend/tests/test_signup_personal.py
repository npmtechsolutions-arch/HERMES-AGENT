"""
THE_FIX_personal_ui — a brand-new signup must land on the clean Personal product
(simplified nav + capabilities-first Home), not the 35-item business UI. Verifies
the tenant gets the personal edition active and its skin.nav is served.

Run:  python -m pytest tests/test_signup_personal.py -q
Or:   python tests/test_signup_personal.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def test_new_signup_lands_on_personal_edition():
    from app import entitlements
    from app.models import Tenant, TenantMember
    from app.routers.auth import signup, SignupIn
    db = _mkdb()
    out = signup(SignupIn(email="new@user.com", password="pw123456", full_name="New User"), db)
    assert out["kind"] == "user"
    member = db.query(TenantMember).first()
    t = db.get(Tenant, member.tenant_id)
    # the personal edition is active + tier personal
    assert t.active_edition_id and t.plan_tier == "personal"
    eff = entitlements.effective(t, db)
    assert eff["edition"] == "personal"
    nav = (eff.get("skin") or {}).get("nav")
    assert nav, "personal skin must carry the simplified nav"
    labels = [i[2] for g in nav for i in g["items"]]
    assert "What I can do" in labels and "Agent Tree" in labels       # the clean shell
    # and it is NOT the giant business sidebar
    assert len(labels) < 24


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

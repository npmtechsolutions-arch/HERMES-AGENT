"""
Tests for the connection layer (Doc 23 Prompt E). Mocked provider — no network.
Covers: loopback OAuth flow (PKCE → callback → token in local Vault), silent
refresh, refresh-failure surfacing as a CredentialError, disconnect, and the
privacy invariant (the token is NEVER stored on the connections row).

Run:  python -m pytest tests/test_connections.py -q
Or:   python tests/test_connections.py
"""
import base64
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["HERMUS_OAUTH_GOOGLE_CALENDAR_CLIENT_ID"] = "test-client-id"

from app import connections as C  # noqa: E402
from app.tools import Actor, CredentialError, ToolContext  # noqa: E402

PROVIDER = "google_calendar"


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _ctx(db):
    return ToolContext(actor=Actor(tenant_id="tnt_e", user_id="usr_e", agent_id="Aria",
                                   grants={"*"}), db=db)


def _id_token(email):
    payload = base64.urlsafe_b64encode(json.dumps({"email": email}).encode()).rstrip(b"=").decode()
    return f"aaa.{payload}.bbb"


def _patch_token(fn):
    """Swap C._token_request for a mock; returns a restore() callable."""
    orig = C._token_request
    C._token_request = fn
    return lambda: setattr(C, "_token_request", orig)


def _mock_ok(url, data):
    if data.get("grant_type") == "authorization_code":
        return {"access_token": "acc1", "refresh_token": "ref1", "expires_in": 3600,
                "id_token": _id_token("anil@gmail.com")}
    if data.get("grant_type") == "refresh_token":
        return {"access_token": "acc2", "expires_in": 3600}
    return {}


# ── loopback flow ─────────────────────────────────────────────────────────────
def test_start_oauth_builds_pkce_consent_url():
    out = C.start_oauth(PROVIDER, "tnt_e", "usr_e")
    assert "code_challenge=" in out["auth_url"] and "code_challenge_method=S256" in out["auth_url"]
    assert "test-client-id" in out["auth_url"] and "127.0.0.1" in out["auth_url"]
    assert out["state"] in C._PENDING


def test_callback_stores_token_in_vault_not_on_connection():
    from app.models import Connection, VaultSecret
    restore = _patch_token(_mock_ok)
    try:
        db = _mkdb()
        out = C.start_oauth(PROVIDER, "tnt_e", "usr_e")
        con = C.handle_callback(db, "auth-code-123", out["state"]); db.commit()
        assert con.status == "connected" and con.account_label == "anil@gmail.com"
        # token lives in the Vault, referenced by key — NOT on the connection row
        assert con.vault_secret_key and db.query(VaultSecret).count() == 1
        assert C.vault_get(db, con.vault_secret_key)["access_token"] == "acc1"
        cols = {c.name for c in Connection.__table__.columns}
        assert "access_token" not in cols and "token" not in cols, "no token field on connections (privacy)"
    finally:
        restore()


def test_unknown_state_rejected():
    db = _mkdb()
    try:
        C.handle_callback(db, "code", "bogus-state")
        assert False, "should reject unknown state"
    except ValueError:
        pass


# ── silent refresh + failure surfacing ───────────────────────────────────────
def _connect(db):
    restore = _patch_token(_mock_ok)
    out = C.start_oauth(PROVIDER, "tnt_e", "usr_e")
    con = C.handle_callback(db, "code", out["state"]); db.commit()
    restore()
    return con


def test_silent_refresh_on_expiry():
    db = _mkdb()
    con = _connect(db)
    # force the token expired
    tok = C.vault_get(db, con.vault_secret_key); tok["expires_at"] = int(time.time()) - 10
    C.vault_update(db, con.vault_secret_key, tok); db.commit()
    restore = _patch_token(_mock_ok)
    try:
        client = C.get_provider_client(_ctx(db), PROVIDER)
        assert client.access_token == "acc2", "silently refreshed to the new token"
        assert C.vault_get(db, con.vault_secret_key)["refresh_token"] == "ref1", "refresh_token preserved"
        assert db.get(type(con), con.id).status == "connected"
    finally:
        restore()


def test_refresh_failure_raises_credential_error():
    db = _mkdb()
    con = _connect(db)
    tok = C.vault_get(db, con.vault_secret_key); tok["expires_at"] = int(time.time()) - 10
    C.vault_update(db, con.vault_secret_key, tok); db.commit()
    restore = _patch_token(lambda url, data: {})   # refresh returns no token
    try:
        try:
            C.get_provider_client(_ctx(db), PROVIDER)
            assert False, "should raise CredentialError"
        except CredentialError as e:
            assert "reconnect" in (e.user_message or "").lower()
        assert db.get(type(con), con.id).status == "expired", "marked expired, dependents pause"
    finally:
        restore()


def test_no_connection_raises_credential_error():
    db = _mkdb()
    try:
        C.get_provider_client(_ctx(db), PROVIDER)
        assert False
    except CredentialError as e:
        assert "Connect" in (e.user_message or "")


# ── disconnect ────────────────────────────────────────────────────────────────
def test_disconnect_removes_vault_secret():
    from app.models import VaultSecret
    db = _mkdb()
    con = _connect(db)
    assert db.query(VaultSecret).count() == 1
    restore = _patch_token(lambda u, d: {})   # revoke call is best-effort
    try:
        assert C.disconnect(db, "tnt_e", "usr_e", PROVIDER) is True
        db.commit()
        assert db.query(VaultSecret).count() == 0, "vault secret deleted"
        assert db.get(type(con), con.id).status == "revoked"
    finally:
        restore()


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

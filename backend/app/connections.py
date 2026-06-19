"""
HERMUS connection layer — Doc 23 Prompt E. Connects external providers (Google
Calendar, Gmail, Outlook…) for Tier-2 tools via the desktop-native OAuth2
Authorization-Code + PKCE flow on a loopback redirect.

ARCHITECTURE §2 (two-plane privacy): provider tokens live in the LOCAL Vault on
the user's machine and NEVER reach the cloud plane. `connections` stores only a
reference key to the token, never the token itself. Stdlib only (urllib) — no new
dependency.
"""
import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
import urllib.request

from .models import Connection, VaultSecret, now as _now
from .security import ulid
from .tools import CredentialError, TransientError

# Loopback redirect — the running local core IS the loopback target (127.0.0.1).
REDIRECT_URI = os.getenv("HERMUS_OAUTH_REDIRECT",
                         "http://127.0.0.1:7700/api/v1/connections/oauth/callback")

# Providers that use the OAuth2 Authorization-Code flow. client_id comes from env
# (public desktop client → PKCE, no client secret). WhatsApp uses a different flow
# (system-user token) and is handled in Prompt G, not here.
PROVIDERS = {
    "google_calendar": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "revoke_url": "https://oauth2.googleapis.com/revoke",
        "scopes": ["https://www.googleapis.com/auth/calendar", "openid", "email"],
        "extra_auth": {"access_type": "offline", "prompt": "consent"},
    },
    "gmail": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "revoke_url": "https://oauth2.googleapis.com/revoke",
        "scopes": ["https://www.googleapis.com/auth/gmail.modify", "openid", "email"],
        "extra_auth": {"access_type": "offline", "prompt": "consent"},
    },
    "outlook": {
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "revoke_url": None,
        "scopes": ["offline_access", "Calendars.ReadWrite", "Mail.ReadWrite", "User.Read"],
        "extra_auth": {},
    },
}


def _client_id(provider):
    return os.getenv(f"HERMUS_OAUTH_{provider.upper()}_CLIENT_ID", "")


# ── local Vault (tokens never leave the machine) ─────────────────────────────
def _enc(s: str) -> str:
    # Encryption-at-rest hook: when `cryptography` + a local key are present this
    # becomes Fernet. Until then it's identity — tokens sit in the LOCAL DB only.
    return s


def _dec(s: str) -> str:
    return s


def vault_put(db, tenant_id, value: dict) -> str:
    key = ulid("vlt")
    db.add(VaultSecret(id=key, tenant_id=tenant_id, value=_enc(json.dumps(value))))
    db.flush()
    return key


def vault_update(db, key, value: dict):
    s = db.get(VaultSecret, key)
    if s:
        s.value = _enc(json.dumps(value))
        db.flush()


def vault_get(db, key) -> dict | None:
    s = db.get(VaultSecret, key) if key else None
    return json.loads(_dec(s.value)) if s else None


def vault_delete(db, key):
    if key:
        db.query(VaultSecret).filter_by(id=key).delete(synchronize_session=False)


# ── PKCE ──────────────────────────────────────────────────────────────────────
def _pkce():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(40)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


# Pending authorizations keyed by state (single local-core process; in-memory is fine).
_PENDING: dict[str, dict] = {}


def _email_from_id_token(tok: dict) -> str | None:
    idt = tok.get("id_token")
    if not idt or idt.count(".") != 2:
        return None
    try:
        payload = idt.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("email")
    except Exception:
        return None


# ── token HTTP (stdlib; monkeypatched in tests) ──────────────────────────────
def _token_request(url: str, data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        if e.code >= 500:
            raise TransientError(f"provider {e.code}")
        return {}
    except Exception as e:
        raise TransientError(str(e))


def exchange_code(provider: str, code: str, verifier: str) -> dict:
    cfg = PROVIDERS[provider]
    return _token_request(cfg["token_url"], {
        "grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI,
        "client_id": _client_id(provider), "code_verifier": verifier})


def refresh_token(provider: str, refresh: str) -> dict:
    cfg = PROVIDERS[provider]
    return _token_request(cfg["token_url"], {
        "grant_type": "refresh_token", "refresh_token": refresh,
        "client_id": _client_id(provider)})


def _stamp_expiry(tok: dict) -> dict:
    tok["expires_at"] = int(time.time()) + int(tok.get("expires_in", 3600))
    return tok


# ── flow: start → callback ───────────────────────────────────────────────────
def start_oauth(provider: str, tenant_id: str, user_id: str) -> dict:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'.")
    if not _client_id(provider):
        raise ValueError(f"{provider} isn't configured (set HERMUS_OAUTH_{provider.upper()}_CLIENT_ID).")
    cfg = PROVIDERS[provider]
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(24)
    # The loopback callback is unauthenticated (a browser redirect), so the
    # tenant/user are carried in the (server-side, PKCE-bound) pending record.
    _PENDING[state] = {"provider": provider, "verifier": verifier,
                       "tenant_id": tenant_id, "user_id": user_id}
    params = {"client_id": _client_id(provider), "redirect_uri": REDIRECT_URI,
              "response_type": "code", "scope": " ".join(cfg["scopes"]), "state": state,
              "code_challenge": challenge, "code_challenge_method": "S256", **cfg.get("extra_auth", {})}
    return {"auth_url": cfg["auth_url"] + "?" + urllib.parse.urlencode(params), "state": state}


def handle_callback(db, code: str, state: str) -> Connection:
    pending = _PENDING.pop(state, None)
    if not pending:
        raise ValueError("Unknown or expired authorization (state mismatch).")
    provider, tenant_id, user_id = pending["provider"], pending["tenant_id"], pending["user_id"]
    tok = _stamp_expiry(exchange_code(provider, code, pending["verifier"]))
    if not tok.get("access_token"):
        raise ValueError("Token exchange failed.")
    label = _email_from_id_token(tok) or provider
    con = (db.query(Connection)
           .filter_by(tenant_id=tenant_id, user_id=user_id, provider=provider).first())
    key = (con.vault_secret_key if con else None)
    if key:
        vault_update(db, key, tok)
    else:
        key = vault_put(db, tenant_id, tok)
    if not con:
        con = Connection(id=ulid("con"), tenant_id=tenant_id, user_id=user_id, provider=provider)
        db.add(con)
    con.status = "connected"
    con.vault_secret_key = key
    con.scopes = PROVIDERS[provider]["scopes"]
    con.account_label = label
    con.connected_at = _now()
    con.last_ok_at = _now()
    con.last_error = None
    db.flush()
    return con


# ── client + self-healing (the operational reality of Tier-2) ────────────────
class ProviderClient:
    """Thin holder the Tier-2 tools build their provider calls on (Prompt F+)."""
    def __init__(self, provider, access_token, connection):
        self.provider = provider
        self.access_token = access_token
        self.connection = connection


def get_provider_client(ctx, provider: str) -> ProviderClient:
    con = (ctx.db.query(Connection)
           .filter_by(tenant_id=ctx.actor.tenant_id, user_id=ctx.actor.user_id, provider=provider)
           .filter(Connection.status != "revoked").first())
    if not con:
        raise CredentialError(user_message=f"Connect {provider} in Settings first.")
    tok = vault_get(ctx.db, con.vault_secret_key) or {}
    expired = con.status == "expired" or (tok.get("expires_at", 0) and tok["expires_at"] <= int(time.time()))
    if expired:
        new = refresh_token(provider, tok.get("refresh_token", "")) if tok.get("refresh_token") else {}
        if not new.get("access_token"):
            con.status = "expired"
            con.last_error = "token refresh failed"
            ctx.db.flush()
            raise CredentialError(user_message=f"Please reconnect {provider} in Settings.")
        new.setdefault("refresh_token", tok.get("refresh_token"))
        tok = _stamp_expiry(new)
        vault_update(ctx.db, con.vault_secret_key, tok)
        con.status = "connected"
        con.last_ok_at = _now()
        ctx.db.flush()
    return ProviderClient(provider, tok.get("access_token"), con)


# ── settings: list / disconnect ──────────────────────────────────────────────
def list_connections(db, tenant_id, user_id):
    rows = db.query(Connection).filter_by(tenant_id=tenant_id, user_id=user_id).all()
    return [{"provider": c.provider, "status": c.status, "account_label": c.account_label,
             "scopes": c.scopes or [], "connected_at": c.connected_at.isoformat() if c.connected_at else None,
             "last_ok_at": c.last_ok_at.isoformat() if c.last_ok_at else None, "last_error": c.last_error}
            for c in rows]


def disconnect(db, tenant_id, user_id, provider):
    con = (db.query(Connection)
           .filter_by(tenant_id=tenant_id, user_id=user_id, provider=provider).first())
    if not con:
        return False
    # best-effort provider-side revoke
    try:
        cfg = PROVIDERS.get(provider, {})
        tok = vault_get(db, con.vault_secret_key) or {}
        if cfg.get("revoke_url") and tok.get("access_token"):
            _token_request(cfg["revoke_url"], {"token": tok["access_token"]})
    except Exception:
        pass
    vault_delete(db, con.vault_secret_key)
    con.status = "revoked"
    con.vault_secret_key = None
    db.flush()
    return True

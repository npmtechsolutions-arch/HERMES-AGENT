"""
Settings → Connections (Doc 23 Prompt E). Start/list/disconnect external provider
connections via the desktop loopback OAuth flow. Provider tokens stay LOCAL
(ARCHITECTURE §2) — these endpoints only ever return status, never a token.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import connections as C
from ..database import get_db
from ..deps import Principal, audit, current_user

router = APIRouter(tags=["connections"])


@router.get("/connections")
def list_connections(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    return {"providers": list(C.PROVIDERS.keys()),
            "connections": C.list_connections(db, p.tenant_id, p.user_id)}


@router.post("/connections/{provider}/connect")
def connect(provider: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Begin OAuth — returns the consent URL for the desktop to open in the system browser."""
    try:
        out = C.start_oauth(provider, p.tenant_id, p.user_id)
    except ValueError as e:
        raise HTTPException(400, detail={"code": "BAD_PROVIDER", "message": str(e)})
    return {"auth_url": out["auth_url"], "state": out["state"],
            "message": f"Opening {provider} sign-in — approve it in your browser."}


@router.post("/connections/{provider}/reconnect")
def reconnect(provider: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    return connect(provider, p, db)


@router.post("/connections/{provider}/disconnect")
def disconnect(provider: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    ok = C.disconnect(db, p.tenant_id, p.user_id, provider)
    if ok:
        audit(db, plane="local", actor=f"user:{p.user_id}", action="connection.disconnect",
              target=provider, tenant_id=p.tenant_id)
    db.commit()
    return {"status": "revoked" if ok else "not_connected",
            "message": f"{provider} disconnected — its token was removed from your local Vault." if ok
                       else f"{provider} wasn't connected."}


@router.get("/connections/oauth/callback", response_class=HTMLResponse)
def oauth_callback(code: str = "", state: str = "", error: str = "",
                   db: Session = Depends(get_db)):
    """The loopback redirect target — unauthenticated (a browser hit). Identity is
    carried by the PKCE-bound state. Exchanges the code and stores the token locally."""
    if error:
        return _page("Connection cancelled", f"The provider returned: {error}. You can close this tab.")
    try:
        con = C.handle_callback(db, code, state)
        db.commit()
        return _page("Connected ✓", f"{con.provider} is connected as {con.account_label}. "
                                    "You can close this tab and return to HERMUS.")
    except Exception as e:
        return _page("Connection failed", f"{e}. Please try again from Settings.")


def _page(title, body):
    return f"""<!doctype html><meta charset=utf-8><title>HERMUS</title>
<body style="font-family:-apple-system,system-ui,sans-serif;display:grid;place-items:center;height:100vh;margin:0;background:#f5f6fb">
<div style="text-align:center;max-width:420px;padding:32px;background:#fff;border-radius:16px;box-shadow:0 8px 30px rgba(0,0,0,.08)">
<h2 style="margin:0 0 8px">{title}</h2><p style="color:#555">{body}</p></div></body>"""

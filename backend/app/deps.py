"""Shared FastAPI dependencies: auth context + audit helper."""
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import AdminUser, AuditLog, TenantMember, User
from .security import decode_token


class Principal:
    def __init__(self, kind, user_id=None, tenant_id=None, roles=None, email=None):
        self.kind = kind            # "user" | "admin"
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.roles = roles or []
        self.email = email


def _token_from_header(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, detail={"code": "UNAUTHENTICATED",
                                         "message": "Missing bearer token"})
    return authorization.split(" ", 1)[1]


def current_user(authorization: str | None = Header(None),
                 db: Session = Depends(get_db)) -> Principal:
    """End-user (account owner / team member) principal."""
    token = _token_from_header(authorization)
    try:
        claims = decode_token(token)
    except Exception:
        raise HTTPException(401, detail={"code": "UNAUTHENTICATED", "message": "Invalid token"})
    if claims.get("kind") != "user":
        raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "Not a user token"})
    user = db.get(User, claims["sub"])
    if not user or user.status != "active":
        raise HTTPException(401, detail={"code": "UNAUTHENTICATED", "message": "Unknown user"})
    member = db.query(TenantMember).filter_by(user_id=user.id).first()
    tenant_id = member.tenant_id if member else None
    return Principal("user", user_id=user.id, tenant_id=tenant_id,
                     roles=[member.role] if member else [], email=user.email)


def current_admin(authorization: str | None = Header(None),
                  db: Session = Depends(get_db)) -> Principal:
    """Product-admin principal with role scopes (super/support/finance/catalog)."""
    token = _token_from_header(authorization)
    try:
        claims = decode_token(token)
    except Exception:
        raise HTTPException(401, detail={"code": "UNAUTHENTICATED", "message": "Invalid token"})
    if claims.get("kind") != "admin":
        raise HTTPException(403, detail={"code": "FORBIDDEN", "message": "Not an admin token"})
    admin = db.get(AdminUser, claims["sub"])
    if not admin or admin.status != "active":
        raise HTTPException(401, detail={"code": "UNAUTHENTICATED", "message": "Unknown admin"})
    return Principal("admin", user_id=admin.id, roles=admin.roles or [], email=admin.email)


def require_role(principal: Principal, *roles: str):
    """PA-07: admin role lacks scope -> deny + audit."""
    if "super" in principal.roles:
        return
    if not any(r in principal.roles for r in roles):
        raise HTTPException(403, detail={"code": "FORBIDDEN",
                                         "message": f"Requires one of roles: {roles}"})


import hashlib
import json


def _identity_chain(actor, tenant_id, capability, substrate):
    """§3.1 — build the complete five-layer identity chain (sentinels for unknown)."""
    human, agent = "-", "-"
    if actor and actor.startswith(("user:", "admin:", "remote:")):
        human = actor
    elif actor and actor.startswith("agent:"):
        agent = actor
    return {
        "L1_tenant": tenant_id or "system",
        "L2_human": human,
        "L3_agent": agent,
        "L4_capability": capability or "-",
        "L5_substrate": substrate or "dev_local",
    }


def audit(db: Session, *, plane, actor, action, target=None, tenant_id=None, meta=None,
          capability=None, substrate=None):
    """Write a tamper-evident, identity-chained audit record (§3.1, §3.4)."""
    chain_key = tenant_id or "global"
    chain = _identity_chain(actor, tenant_id, capability, substrate)
    # previous head for this chain
    prev = (db.query(AuditLog).filter(AuditLog.chain_key == chain_key,
                                      AuditLog.this_hash.isnot(None))
            .order_by(AuditLog.id.desc()).first())
    prev_hash = prev.this_hash if prev else "GENESIS"
    record = {"plane": plane, "actor": actor, "action": action, "target": target,
              "tenant_id": tenant_id, "meta": meta or {}, "identity_chain": chain}
    this_hash = hashlib.sha256(
        (prev_hash + json.dumps(record, sort_keys=True, default=str)).encode()).hexdigest()
    db.add(AuditLog(plane=plane, actor=actor, action=action, target=target,
                    tenant_id=tenant_id, meta=meta or {}, identity_chain=chain,
                    chain_key=chain_key, prev_hash=prev_hash, this_hash=this_hash))
    db.flush()  # so chained calls within one txn see the new head (autoflush is off)

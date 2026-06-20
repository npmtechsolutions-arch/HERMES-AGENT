"""Auth: user + admin login, signup, device flow, current identity."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, audit, current_admin, current_user
from ..models import AdminUser, Plan, Subscription, Tenant, TenantMember, User
from ..security import create_token, hash_password, ulid, verify_password
from ..models import now

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class SignupIn(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    company_name: str | None = None
    industry: str | None = None


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.password_hash or ""):
        raise HTTPException(401, detail={"code": "UNAUTHENTICATED",
                                         "message": "Invalid email or password"})
    user.last_login_at = now()
    member = db.query(TenantMember).filter_by(user_id=user.id).first()
    token = create_token(user.id, "user",
                         {"tenant_id": member.tenant_id if member else None})
    audit(db, plane="cloud", actor=f"user:{user.id}", action="auth.login",
          tenant_id=member.tenant_id if member else None)
    db.commit()
    return {"token": token, "kind": "user", "user": _user_dto(db, user)}


@router.post("/admin/login")
def admin_login(body: LoginIn, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter(AdminUser.email == body.email.lower()).first()
    if not admin or not verify_password(body.password, admin.password_hash or ""):
        raise HTTPException(401, detail={"code": "UNAUTHENTICATED",
                                         "message": "Invalid admin credentials"})
    admin.last_login_at = now()
    token = create_token(admin.id, "admin", {"roles": admin.roles})
    audit(db, plane="cloud", actor=f"admin:{admin.id}", action="admin.login")
    db.commit()
    return {"token": token, "kind": "admin",
            "admin": {"id": admin.id, "email": admin.email,
                      "full_name": admin.full_name, "roles": admin.roles}}


@router.post("/signup")
def signup(body: SignupIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email.lower()).first():
        raise HTTPException(409, detail={"code": "CONFLICT", "message": "Email already registered"})
    user = User(id=ulid("usr"), email=body.email.lower(),
                password_hash=hash_password(body.password), full_name=body.full_name)
    tenant = Tenant(id=ulid("tnt"), owner_user_id=user.id,
                    company_name=body.company_name or f"{body.full_name}'s Company",
                    industry=body.industry, region="IN", status="active")
    member = TenantMember(id=ulid("mem"), tenant_id=tenant.id, user_id=user.id, role="owner")
    # Insert each level separately so referenced rows exist before the rows that
    # reference them (the unit-of-work doesn't order these FKs reliably, so we
    # force it): user → tenant → member/subscription.
    db.add(user); db.flush()
    # Land every new user on the clean Personal product (the simplified shell +
    # capabilities-first Home) instead of the 35-item business UI. They can switch
    # to a Professional/vertical product later from Products. (THE_FIX_personal_ui)
    try:
        from .editions import _seed_editions
        from ..models import Edition
        _seed_editions(db)
        personal = (db.query(Edition).filter_by(slug="personal", status="published").first()
                    or db.query(Edition).filter_by(is_default=True, status="published").first())
        if personal:
            tenant.active_edition_id = personal.id
            tenant.plan_tier = "personal"
    except Exception:
        pass   # never block signup on edition seeding; the default-edition fallback still applies
    db.add(tenant); db.flush()
    db.add(member)
    # default everyone onto the trial plan (only if it exists)
    if db.get(Plan, "pln_trial"):
        db.add(Subscription(id=ulid("sub"), tenant_id=tenant.id, plan_id="pln_trial",
                            status="trialing", trial_ends_at=now()))
    audit(db, plane="cloud", actor=f"user:{user.id}", action="auth.signup", tenant_id=tenant.id)
    db.commit()
    token = create_token(user.id, "user", {"tenant_id": tenant.id})
    return {"token": token, "kind": "user", "user": _user_dto(db, user)}


@router.get("/me")
def me(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    user = db.get(User, p.user_id)
    return _user_dto(db, user)


def _user_dto(db: Session, user: User):
    member = db.query(TenantMember).filter_by(user_id=user.id).first()
    tenant = db.get(Tenant, member.tenant_id) if member else None
    return {
        "id": user.id, "email": user.email, "full_name": user.full_name,
        "role": member.role if member else None,
        "tenant": {"id": tenant.id, "company_name": tenant.company_name,
                   "industry": tenant.industry, "status": tenant.status} if tenant else None,
    }

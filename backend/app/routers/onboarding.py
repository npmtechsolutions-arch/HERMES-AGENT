"""
First-run Guided Setup wizard (Doc 26 Part 1). Takes a brand-new user from
"just installed" to "just completed my first real task" in a few minutes. State
is persisted (setup_state) so an interrupted wizard resumes where it left off,
and it's re-runnable from Settings.

The magic-moment step (Step 4) calls the REAL assistant spine — not a fake demo —
so the user watches genuine execution (a reminder actually gets created).
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..assistant import run_assistant
from ..database import get_db
from ..deps import Principal, current_user
from ..models import MemoryItem, SetupState, now
from ..security import ulid

router = APIRouter(tags=["onboarding"])

# Step keys the frontend renders. `required` steps can't be skipped (Step 4 has
# an auto-run example so no one gets stuck). Order == wizard order.
STEPS = [
    {"key": "welcome", "title": "Welcome", "required": False},
    {"key": "about", "title": "About you", "required": False},
    {"key": "team", "title": "Meet your team", "required": False},
    {"key": "first_task", "title": "Your first task", "required": True},
    {"key": "powerups", "title": "Power-ups", "required": False},
    {"key": "done", "title": "All set", "required": False},
]
EXAMPLE_TASK = "Remind me to call the bank tomorrow at 11am."


def _state(db, p) -> SetupState:
    s = db.get(SetupState, p.user_id)
    if not s:
        s = SetupState(user_id=p.user_id, tenant_id=p.tenant_id, step=1, data={}, skipped=[])
        db.add(s); db.flush()
    return s


def _dto(s: SetupState):
    return {"step": s.step, "total": len(STEPS), "steps": STEPS,
            "data": s.data or {}, "skipped": s.skipped or [],
            "completed": s.completed_at is not None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "example_task": EXAMPLE_TASK}


@router.get("/onboarding")
def get_state(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    s = _state(db, p); db.commit()
    return _dto(s)


class About(BaseModel):
    name: str | None = None
    language: str | None = None
    role: str | None = None


@router.post("/onboarding/about")
def about(body: About, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Step 2 — seed preferences + SOUL.md so the assistant feels personal from message one."""
    s = _state(db, p)
    s.data = {**(s.data or {}),
              **{k: v for k, v in body.model_dump().items() if v}}
    prefs = []
    if body.name:
        prefs.append(f"My name is {body.name}.")
    if body.language:
        prefs.append(f"I prefer to communicate in {body.language}.")
    if body.role:
        prefs.append(f"What I do: {body.role}.")
    for text in prefs:
        db.add(MemoryItem(id=ulid("mem"), tenant_id=p.tenant_id, memory_class="personal",
                          title=text[:60], source_type="preference", body=text, tier="hot", confidence=1.0))
    db.flush()
    try:
        from .. import projections
        projections.regenerate_soul(db, p.tenant_id, p.user_id)
    except Exception:
        pass   # SOUL is a projection; never block onboarding on it
    s.step = max(s.step, 3)
    db.commit()
    return {"ok": True, "saved": s.data, "message": f"Nice to meet you{', ' + body.name if body.name else ''}."}


class FirstTask(BaseModel):
    text: str | None = None


@router.post("/onboarding/first-task")
def first_task(body: FirstTask, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Step 4 — run a REAL command through the assistant so the user sees it work."""
    text = (body.text or "").strip() or EXAMPLE_TASK
    out = run_assistant(db, tenant_id=p.tenant_id, user_id=p.user_id, text=text)
    s = _state(db, p)
    s.step = max(s.step, 5)
    db.commit()
    return {"ok": out["ok"], "result": out, "ran": text}


class Nav(BaseModel):
    step: int
    skip_key: str | None = None


@router.post("/onboarding/nav")
def nav(body: Nav, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    s = _state(db, p)
    s.step = max(1, min(body.step, len(STEPS)))
    if body.skip_key:
        req = next((x["required"] for x in STEPS if x["key"] == body.skip_key), False)
        if not req and body.skip_key not in (s.skipped or []):
            s.skipped = [*(s.skipped or []), body.skip_key]
    db.commit()
    return _dto(s)


@router.post("/onboarding/complete")
def complete(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    s = _state(db, p)
    s.step = len(STEPS)
    s.completed_at = now()
    db.commit()
    return {"ok": True, "message": "You're all set. Tap the mic or just type any time."}


@router.post("/onboarding/reset")
def reset(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """“Run setup again” from Settings."""
    s = _state(db, p)
    s.step = 1
    s.completed_at = None
    db.commit()
    return _dto(s)

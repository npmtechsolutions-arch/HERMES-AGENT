"""
Skills — Auto-Skill Capture (G3), sandbox levels (G8), and skill import (G10).

G3: when a novel multi-step task or pipeline succeeds, the executing agent drafts
a parameterized skill from the execution trace and proposes it (status='proposed').
The user reviews and saves it — "self-improving, but supervised". Repeated runs
refine the skill (runs counter / confidence). The CEO planner can reuse saved
skills when planning similar work.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import Skill
from ..security import ulid

router = APIRouter(tags=["skills"])

_PARAM = re.compile(r"(₹[\d,]+|\b\d{4,}\b|\bSharma Traders\b|\bApex Supplies\b)", re.I)


def _pub(tenant_id, action, name):
    hub.emit(tenant_id, "skill.changed", {"action": action, "name": name})


def _parameterize(text: str) -> str:
    """Generalize a concrete instruction into a reusable, parameterized one."""
    return _PARAM.sub("{value}", text or "")


def capture_skill(db: Session, tenant_id: str, title: str, steps: list, task_id: str,
                  agent_name: str = "an agent"):
    """Draft (or refine) a parameterized skill from a completed multi-step trace."""
    if not steps or len(steps) < 2:
        return None  # only novel *multi-step* work is worth a skill
    name = re.sub(r"\s+for\s+.*$", "", title, flags=re.I).strip()[:80] or title[:80]
    existing = db.query(Skill).filter(
        Skill.tenant_id == tenant_id, func.lower(Skill.name) == name.lower()).first()
    if existing:  # refinement loop — count the run, bump confidence
        existing.runs = (existing.runs or 0) + 1
        existing.confidence = min(0.99, (existing.confidence or 0.7) + 0.05)
        db.flush()
        return existing
    definition = {"steps": [{"order": i + 1,
                             "do": _parameterize(s.get("instruction") or s.get("description", "")),
                             "by": s.get("agent_name")} for i, s in enumerate(steps)]}
    sk = Skill(id=ulid("skl"), tenant_id=tenant_id, name=name,
               description=f"Auto-captured from a completed task by {agent_name}.",
               source="auto_captured", status="proposed", definition=definition,
               learned_from_task_id=task_id, confidence=0.78, runs=1)
    db.add(sk)
    db.flush()
    hub.emit(tenant_id, "skill.proposed", {"skill_id": sk.id, "name": sk.name})
    return sk


def skill_dto(s: Skill):
    return {"id": s.id, "name": s.name, "description": s.description, "source": s.source,
            "status": s.status, "confidence": s.confidence, "runs": s.runs,
            "sandbox_level": s.sandbox_level, "definition": s.definition,
            "learned_from_task_id": s.learned_from_task_id, "version": s.version,
            "created_at": s.created_at.isoformat() if s.created_at else None}


@router.get("/skills")
def list_skills(status: str | None = None, p: Principal = Depends(current_user),
                db: Session = Depends(get_db)):
    q = db.query(Skill).filter_by(tenant_id=p.tenant_id).filter(Skill.status != "archived")
    if status:
        q = q.filter_by(status=status)
    return [skill_dto(s) for s in q.order_by(Skill.created_at.desc()).all()]


class SkillIn(BaseModel):
    name: str
    description: str | None = None
    steps: list[str] = []
    status: str = "active"            # active | proposed
    sandbox_level: str = "process"


@router.post("/skills")
def create_skill(body: SkillIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Author a skill by hand (name + ordered steps)."""
    steps = [{"order": i + 1, "do": s} for i, s in enumerate([x.strip() for x in body.steps if x.strip()])]
    sk = Skill(id=ulid("skl"), tenant_id=p.tenant_id, name=body.name,
               description=body.description or "Authored by hand.", source="manual",
               status=body.status if body.status in ("active", "proposed") else "active",
               definition={"steps": steps}, sandbox_level=body.sandbox_level,
               confidence=0.9, runs=0)
    db.add(sk)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="skill.create",
          target=sk.id, tenant_id=p.tenant_id, meta={"name": body.name})
    db.commit()
    _pub(p.tenant_id, "create", sk.name)
    return {**skill_dto(sk), "message": f"Skill “{sk.name}” created."}


@router.post("/skills/{sid}/save")
def save_skill(sid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Approve a proposed (auto-captured) skill → active, versioned, reusable."""
    s = db.get(Skill, sid)
    if not s or s.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Skill not found"})
    s.status = "active"
    audit(db, plane="local", actor=f"user:{p.user_id}", action="skill.save",
          target=sid, tenant_id=p.tenant_id, meta={"name": s.name, "source": s.source})
    db.commit()
    _pub(p.tenant_id, "save", s.name)
    return {**skill_dto(s), "message": f"Saved skill “{s.name}”."}


class SkillPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    steps: list[str] | None = None
    sandbox_level: str | None = None


@router.patch("/skills/{sid}")
def update_skill(sid: str, body: SkillPatch, p: Principal = Depends(current_user),
                 db: Session = Depends(get_db)):
    s = db.get(Skill, sid)
    if not s or s.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Skill not found"})
    if body.name is not None:
        s.name = body.name
    if body.description is not None:
        s.description = body.description
    if body.steps is not None:
        s.definition = {"steps": [{"order": i + 1, "do": x} for i, x in enumerate([y.strip() for y in body.steps if y.strip()])]}
    if body.sandbox_level in ("process", "docker"):
        s.sandbox_level = body.sandbox_level
    audit(db, plane="local", actor=f"user:{p.user_id}", action="skill.update",
          target=sid, tenant_id=p.tenant_id)
    db.commit()
    _pub(p.tenant_id, "update", s.name)
    return {**skill_dto(s), "message": f"Skill “{s.name}” updated."}


@router.delete("/skills/{sid}")
def delete_skill(sid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    s = db.get(Skill, sid)
    if not s or s.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Skill not found"})
    s.status = "archived"
    name = s.name
    was_proposed = False  # noqa
    audit(db, plane="local", actor=f"user:{p.user_id}", action="skill.archive",
          target=sid, tenant_id=p.tenant_id)
    db.commit()
    _pub(p.tenant_id, "archive", name)
    return {"status": "archived", "message": f"Skill “{name}” removed."}


# ───────────────────────────── G10 — Skill import (Hermes / OpenClaw) ────────
class ImportIn(BaseModel):
    format: str = "hermes"            # hermes | openclaw | generic
    name: str | None = None
    document: str                     # raw skill doc (markdown/json text)


@router.post("/skills/import")
def import_skill(body: ImportIn, p: Principal = Depends(current_user),
                 db: Session = Depends(get_db)):
    """Bring a Hermes skill document (structured steps) into our skill format."""
    text = body.document.strip()
    name = body.name
    steps = []
    import json as _json
    try:  # JSON skill doc
        data = _json.loads(text)
        name = name or data.get("name")
        raw = data.get("steps") or data.get("actions") or []
        steps = [{"order": i + 1, "do": (s if isinstance(s, str) else s.get("do") or s.get("instruction", ""))}
                 for i, s in enumerate(raw)]
    except Exception:  # markdown / numbered list
        if not name:
            first = text.splitlines()[0].lstrip("# ").strip() if text else ""
            # don't use a step line ("1. …") as the title
            name = "Imported skill" if (not first or re.match(r"\s*(\d+\.|-|\*)\s+", first)) else first[:80]
        for i, line in enumerate([l for l in text.splitlines() if re.match(r"\s*(\d+\.|-|\*)\s+", l)]):
            steps.append({"order": i + 1, "do": re.sub(r"^\s*(\d+\.|-|\*)\s+", "", line).strip()})
    if not steps:
        steps = [{"order": 1, "do": text[:300]}]
    sk = Skill(id=ulid("skl"), tenant_id=p.tenant_id, name=name or "Imported skill",
               description=f"Imported from {body.format} format.", source="imported",
               status="active", definition={"steps": steps}, confidence=0.9, runs=0)
    db.add(sk)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="skill.import",
          target=sk.id, tenant_id=p.tenant_id, meta={"format": body.format})
    db.commit()
    _pub(p.tenant_id, "import", sk.name)
    return {"status": "imported", "skill": skill_dto(sk),
            "message": f"Imported “{sk.name}” ({len(steps)} steps)."}


# ──────────────────────── voice / natural-language control ───────────────────
class SkillVoiceIn(BaseModel):
    transcript: str


def _match_skill(db, tenant_id, text):
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    toks = [t for t in low.split() if len(t) >= 3]
    best, score = None, 0
    for s in (db.query(Skill).filter_by(tenant_id=tenant_id)
              .filter(Skill.status != "archived").all()):
        nm = (s.name or "").lower()
        if nm and nm in low:
            return s
        for w in re.findall(r"[a-z]+", nm):
            if len(w) > 3 and w not in ("skill", "the", "and", "for") and w in toks and len(w) > score:
                best, score = s, len(w)
    return best


@router.post("/skills/resolve")
def skills_resolve(body: SkillVoiceIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    """Turn a spoken/typed phrase into a concrete Skills action."""
    text = (body.transcript or "").strip()
    low = text.lower()
    if not text:
        return {"action": "none", "message": "I didn't catch that."}

    if re.search(r"\b(save|approve|accept)\b", low) and re.search(r"\ball\b", low):
        return {"action": "save_all", "message": "Saving all proposed skills."}
    if re.search(r"\b(import)\b", low):
        return {"action": "import", "message": "Opening the import dialog."}
    if re.search(r"\b(create|add|new|author|make)\b", low) and re.search(r"\bskill\b", low) \
            and not _match_skill(db, p.tenant_id, text):
        return {"action": "create", "message": "Opening the new-skill form."}

    s = _match_skill(db, p.tenant_id, text)
    if s:
        if re.search(r"\b(docker|container)\b", low):
            return {"action": "sandbox", "id": s.id, "name": s.name, "level": "docker",
                    "message": f"Putting “{s.name}” in a Docker sandbox."}
        if re.search(r"\b(process|jail|light)\b", low) and "sandbox" in low:
            return {"action": "sandbox", "id": s.id, "name": s.name, "level": "process",
                    "message": f"Setting “{s.name}” to process jail."}
        if re.search(r"\b(save|approve|accept|keep)\b", low):
            return {"action": "save", "id": s.id, "name": s.name, "message": f"Saving “{s.name}”."}
        if re.search(r"\b(discard|archive|delete|remove|reject|drop)\b", low):
            return {"action": "discard", "id": s.id, "name": s.name, "message": f"Removing “{s.name}”."}
        if re.search(r"\b(edit|change|modify|update|rename)\b", low):
            return {"action": "edit", "id": s.id, "name": s.name, "message": f"Editing “{s.name}”."}
        if re.search(r"\b(open|show|view|see|details?)\b", low):
            return {"action": "edit", "id": s.id, "name": s.name, "message": f"Opening “{s.name}”."}

    if re.search(r"\b(create|add|new|author)\b", low):
        return {"action": "create", "message": "Opening the new-skill form."}
    return {"action": "none",
            "message": "Try \"create a skill\", \"save the lead-nurture skill\", \"import a skill\", "
                       "or \"discard the X skill\"."}

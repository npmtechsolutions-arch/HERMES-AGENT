"""
Refine-with-chat endpoints (Doc 30 Phase 1). Anchored to a result_id (the result
a tool produced), not a free-floating bot. Reuses call_tool + the content.refine
tool — no new engine.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import refine as R
from ..database import get_db
from ..deps import Principal, current_user
from ..models import ResultVersion

router = APIRouter(tags=["refine"])


class RefineIn(BaseModel):
    result_id: str
    instruction: str


@router.post("/assistant/refine")
def do_refine(body: RefineIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    out = R.refine(db, tenant_id=p.tenant_id, user_id=p.user_id,
                   anchor_id=body.result_id, instruction=body.instruction)
    db.commit()
    return out


def _owned(db, rid, p):
    if db.query(ResultVersion).filter_by(anchor_id=rid, tenant_id=p.tenant_id).count() == 0:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Result not found"})


@router.get("/results/{rid}/versions")
def versions(rid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    _owned(db, rid, p)
    return R.history(db, rid, p.tenant_id)


class RevertIn(BaseModel):
    version: int


@router.post("/results/{rid}/revert")
def revert(rid: str, body: RevertIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    _owned(db, rid, p)
    out = R.revert(db, tenant_id=p.tenant_id, anchor_id=rid, version=body.version)
    db.commit()
    return out

"""
Direct feature run (Doc 29 §5.1, live mode — Option B). A "Do it now" click runs
EXACTLY that tool via call_tool — the same execution path the scheduler uses, only
the trigger differs (one reliable path for cards). Approval-aware: a gated tool
(money / new-contact / destructive) returns needs_approval instead of executing,
so the UI can route it through the approval gate. Free-text/voice still go through
/assistant; this is for the structured feature cards where the tool must be exact.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..assistant import _result_dto
from ..database import get_db
from ..deps import Principal, current_user
from ..tools import TOOL_REGISTRY, Actor, ToolContext, call_tool
from .agents_profile import agent_of_tool

router = APIRouter(tags=["feature-run"])


class RunIn(BaseModel):
    params: dict = {}
    approved: bool = False


@router.post("/features/{key}/run")
def run_feature(key: str, body: RunIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    if key not in TOOL_REGISTRY:
        raise HTTPException(404, detail={"code": "UNKNOWN_FEATURE",
                                         "message": f"'{key}' is not a known feature."})
    ctx = ToolContext(actor=Actor(tenant_id=p.tenant_id, user_id=p.user_id,
                                  agent_id=agent_of_tool(key), grants={"*"}),
                      db=db, approved=body.approved)
    r = call_tool(key, ctx, **(body.params or {}))   # the SAME tool the scheduler runs
    db.commit()
    out = _result_dto(key, r)
    out["agent"] = agent_of_tool(key)
    return out

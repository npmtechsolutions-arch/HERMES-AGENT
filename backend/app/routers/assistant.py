"""
The assistant endpoint — the spine of HERMUS Personal. The voice/text command
bar POSTs an utterance here; Aria routes it to the right tool and runs it
(permission/approval/memory/Activity all handled by call_tool). Also exposes the
tool + pack catalog and the "go fully offline" privacy switch (guide Part 8).
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..assistant import capabilities, run_assistant
from ..database import get_db
from ..deps import Principal, current_user
from .. import gateway as G
from ..packs import pack_dto, load_packs

router = APIRouter(tags=["assistant"])


class Utterance(BaseModel):
    text: str
    approved: bool = False


@router.post("/assistant")
def assistant(body: Utterance, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Say anything in plain language; the right assistant handles it."""
    out = run_assistant(db, tenant_id=p.tenant_id, user_id=p.user_id,
                        text=body.text, approved=body.approved)
    db.commit()
    return out


@router.get("/assistant/capabilities")
def assistant_capabilities(p: Principal = Depends(current_user)):
    """“What can you do?” — the grouped tool catalog."""
    return capabilities()


@router.get("/tools")
def list_tools(p: Principal = Depends(current_user)):
    from ..tools import registry_dto
    return {"tools": registry_dto()}


@router.get("/packs")
def list_packs(p: Principal = Depends(current_user)):
    load_packs()
    return {"packs": pack_dto()}


@router.get("/assistant/offline")
def get_offline(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    return {"offline": G.is_offline(db, p.tenant_id)}


class Offline(BaseModel):
    on: bool


@router.post("/assistant/offline")
def set_offline(body: Offline, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    G.set_offline(db, p.tenant_id, body.on)
    db.commit()
    return {"offline": body.on,
            "summary": "Fully offline — nothing leaves this computer." if body.on
            else "Back online — cloud models may be used for non-private work."}

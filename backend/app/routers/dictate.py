"""
Dictation (M36) — voice-to-text "Voice Type". Speak, get polished text. The
daily-habit hook (claude_chat.txt): in-app first, system-wide overlay later.

Local-first: transcription happens on-device (browser STT / local model); the
*polish* step runs on the local LLM with the tenant's profession vocabulary when
available, and falls back to deterministic cleanup (so it also works against the
hosted backend, which has no Ollama).
"""
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import llm
from ..database import get_db
from ..deps import Principal, current_user
from ..models import Tenant

router = APIRouter(prefix="/dictate", tags=["dictate"])

# Spoken punctuation/format commands → characters (always applied; the only
# "polish" available when no LLM is reachable).
_SPOKEN = [
    (r"\bnew paragraph\b", "\n\n"), (r"\bnext line\b", "\n"), (r"\bnew line\b", "\n"),
    (r"\bfull stop\b", "."), (r"\bperiod\b", "."), (r"\bcomma\b", ","),
    (r"\bquestion mark\b", "?"), (r"\bexclamation (mark|point)\b", "!"),
    (r"\bcolon\b", ":"), (r"\bsemicolon\b", ";"), (r"\bdash\b", " — "),
    (r"\bopen quote\b", ' "'), (r"\bclose quote\b", '" '),
]
_FILLERS = re.compile(r"\b(um+|uh+|er+|ah+|hmm+|you know|i mean|sort of|kind of)\b", re.I)


def _rule_clean(raw: str) -> str:
    t = " " + raw.strip() + " "
    for pat, rep in _SPOKEN:
        t = re.sub(pat, rep, t, flags=re.I)
    t = _FILLERS.sub("", t)
    t = re.sub(r"\s+([.,!?;:])", r"\1", t)        # no space before punctuation
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r" *\n *", "\n", t).strip()
    # Capitalize sentence starts.
    t = re.sub(r"(^|[.!?]\s+|\n)([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)
    return t


_MODE_SYS = {
    "clean": "Clean up this dictation into clear, well-punctuated text. Fix filler words and obvious "
             "speech-to-text errors. Keep the meaning and the speaker's voice. Do NOT add new "
             "information or commentary. Return ONLY the cleaned text.",
    "formal": "Rewrite this dictation as polished, professional prose suitable for an email or document. "
              "Keep the meaning; do not invent facts. Return ONLY the text.",
    "notes": "Turn this dictation into concise bullet-point notes. Return ONLY the bullet list.",
}


class PolishIn(BaseModel):
    raw: str
    mode: str = "clean"   # clean | formal | notes | raw


@router.get("/status")
def status(p: Principal = Depends(current_user)):
    return {"llm": llm.available(), "model": llm.MODEL_FAST, "local": True,
            "modes": ["clean", "formal", "notes", "raw"]}


@router.post("/polish")
def polish(body: PolishIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    raw = (body.raw or "").strip()
    if not raw:
        return {"text": "", "polished": False, "engine": "none"}
    if body.mode == "raw":
        return {"text": _rule_clean(raw), "polished": True, "engine": "rule-based"}

    base = _rule_clean(raw)
    sys = _MODE_SYS.get(body.mode, _MODE_SYS["clean"])
    if llm.available():
        t = db.get(Tenant, p.tenant_id)
        vocab = f" The user's domain is {t.industry}; respect its terminology." if t and t.industry else ""
        out = llm.chat(base, system=sys + vocab)
        if out and out.strip():
            return {"text": out.strip(), "polished": True, "engine": f"local-llm ({llm.MODEL_FAST})"}
    return {"text": base, "polished": True, "engine": "rule-based"}

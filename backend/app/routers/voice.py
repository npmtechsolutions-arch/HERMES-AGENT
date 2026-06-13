"""Voice pipeline: intent parsing (text path for command palette / testing)
and the per-tenant Hermes Agent configuration."""
import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import llm
from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import Tenant

router = APIRouter(prefix="/voice", tags=["voice"])

system_router = APIRouter(tags=["compute"])


@system_router.get("/models")
def models(p: Principal = Depends(current_user)):
    """Local LLM runtime status + installed models (FR-L1/L2)."""
    return {
        "runtime": "ollama",
        "online": llm.available(),
        "routing": {"fast": llm.MODEL_FAST, "smart": llm.MODEL_SMART,
                    "embed": llm.MODEL_EMBED},
        "models": llm.list_models(),
    }

# Global navigation + action grammar (Screen Navigation §1, Design Flow §2.3).
_INTENTS = [
    ("navigate", r"\b(go to|open|show me|show)\b\s+(?P<target>.+)", None),
    ("hire_agent", r"\bhire\b.*\bemployee\b|\bhire a\b", None),
    ("create_task", r"\b(prepare|create|make|draft|send|do)\b", None),
    ("create_workflow", r"\b(create|build)\b.*\bworkflow\b|\bevery (monday|day|week|morning)\b", None),
    ("briefing", r"\bbrief(ing)?\b|\bwhat's pending\b|\bwhat is pending\b", None),
    ("search_memory", r"\bsearch\b.*\b(brain|memory)\b|\bwhat did we\b", None),
    ("approvals", r"\bapprov(e|al)\b|\bpending approvals\b", None),
]

# Map navigation targets to screen routes.
_SCREEN_MAP = {
    "home": "/", "dashboard": "/", "org": "/org", "org chart": "/org",
    "company": "/org", "tasks": "/tasks", "task board": "/tasks",
    "workflows": "/workflows", "inbox": "/inbox", "messages": "/inbox",
    "brain": "/brain", "memory": "/brain", "knowledge graph": "/graph",
    "approvals": "/approvals", "analytics": "/analytics",
    "marketplace": "/marketplace", "settings": "/settings",
    "billing": "/billing", "subscription": "/billing", "devices": "/devices",
}


class ParseIn(BaseModel):
    text: str


@router.post("/intents/parse")
def parse_intent(body: ParseIn, p: Principal = Depends(current_user)):
    text = body.text.strip()
    low = text.lower()
    for name, pattern, _ in _INTENTS:
        m = re.search(pattern, low)
        if m:
            slots = {}
            confidence = 0.9
            if name == "navigate":
                target = (m.groupdict().get("target") or "").strip(" .?!")
                route = None
                for key, r in _SCREEN_MAP.items():
                    if key in target:
                        route = r
                        break
                slots = {"target": target, "route": route}
                if not route:
                    confidence = 0.55
            return {"intent": name, "slots": slots, "confidence": confidence,
                    "utterance": text}
    return {"intent": "unknown", "slots": {}, "confidence": 0.4, "utterance": text,
            "suggestion": "Try 'hire an employee', 'create a task to…', "
                          "'show my tasks', or 'give me my briefing'."}


# ───────────────────────────── Hermes Agent configuration ───────────────────
# The full set of knobs that shape every agent's output. Persisted per-tenant
# (Tenant.agent_config) and merged over these defaults.
DEFAULT_AGENT_CONFIG = {
    # Reasoning & models (LC-03/04 routing)
    "reasoning_model": llm.MODEL_SMART,
    "fast_model": llm.MODEL_FAST,
    "embed_model": llm.MODEL_EMBED,
    # Generation parameters
    "temperature": 0.3,            # 0=deterministic … 1=creative
    "max_tokens": 600,             # response length cap (num_predict)
    "context_window": 8192,        # num_ctx
    # Behaviour / output quality
    "autonomy": "ask_approval",    # suggest_only|ask_approval|act_within_limits|full_auto
    "tone": "professional",        # professional|friendly|concise|detailed
    "verbosity": "normal",         # brief|normal|detailed
    "grounding": "cite_sources",   # free|cite_sources|strict
    "language": "en-IN",
    "retry_count": 1,
    "failover_managed": False,     # on local failure escalate to managed gateway
    "approval_threshold_inr": 10000,
    # Voice I/O
    "wake_word": "Hey Office",
    "push_to_talk": "Ctrl+Space",
    "tts_voice": "piper-female-1",
    "dnd_window": "21:00-08:00",
    # Privacy
    "telemetry": False,
}

_OPTIONS = {
    "autonomy": [
        {"value": "suggest_only", "label": "Suggest only", "desc": "Agents draft; you do everything."},
        {"value": "ask_approval", "label": "Ask approval", "desc": "Agents act after you approve (recommended)."},
        {"value": "act_within_limits", "label": "Act within limits", "desc": "Auto up to budget/risk ceilings; escalate the rest."},
        {"value": "full_auto", "label": "Full auto", "desc": "Agents act autonomously (high trust)."},
    ],
    "tone": [
        {"value": "professional", "label": "Professional"}, {"value": "friendly", "label": "Friendly"},
        {"value": "concise", "label": "Concise"}, {"value": "detailed", "label": "Detailed"},
    ],
    "verbosity": [{"value": "brief", "label": "Brief"}, {"value": "normal", "label": "Normal"},
                  {"value": "detailed", "label": "Detailed"}],
    "grounding": [
        {"value": "free", "label": "Free", "desc": "May use general knowledge."},
        {"value": "cite_sources", "label": "Cite sources", "desc": "Prefer your data + citations."},
        {"value": "strict", "label": "Strict", "desc": "Only your data; refuse if unknown (lowest hallucination)."},
    ],
    "language": ["en-IN", "hi-IN", "en-US", "ta-IN", "te-IN", "mr-IN", "bn-IN"],
    "voices": ["piper-female-1", "piper-male-1", "piper-female-2", "piper-male-2"],
}

_FIELD_TYPES = {
    "temperature": (float, 0.0, 1.0), "max_tokens": (int, 64, 4096),
    "context_window": (int, 1024, 32768), "retry_count": (int, 0, 5),
    "approval_threshold_inr": (int, 0, 10_000_000),
}
_ENUMS = {"autonomy": {o["value"] for o in _OPTIONS["autonomy"]},
          "tone": {o["value"] for o in _OPTIONS["tone"]},
          "verbosity": {o["value"] for o in _OPTIONS["verbosity"]},
          "grounding": {o["value"] for o in _OPTIONS["grounding"]},
          "language": set(_OPTIONS["language"]), "tts_voice": set(_OPTIONS["voices"])}


def platform_agent_defaults(db) -> dict:
    """Fleet-wide Hermes defaults set by a product admin (ConfigItem). Tenants inherit
    these and may override per-tenant. Empty when the admin hasn't customized anything."""
    from ..models import ConfigItem
    row = db.query(ConfigItem).filter_by(domain="hermes_defaults", key="agent_config",
                                         active=True).first()
    return dict(row.value) if row and isinstance(row.value, dict) else {}


def effective_config(t: Tenant, db=None) -> dict:
    """Layered: code defaults → platform (admin) defaults → tenant override."""
    cfg = dict(DEFAULT_AGENT_CONFIG)
    if db is not None:
        cfg.update(platform_agent_defaults(db))
    cfg.update(t.agent_config or {})
    return cfg


def _coerce(field, value):
    """Validate/coerce a single field; raises ValueError on bad input."""
    if field in _FIELD_TYPES:
        typ, lo, hi = _FIELD_TYPES[field]
        v = typ(value)
        if not (lo <= v <= hi):
            raise ValueError(f"{field} must be between {lo} and {hi}")
        return v
    if field in _ENUMS:
        if str(value) not in _ENUMS[field]:
            raise ValueError(f"{field} must be one of {sorted(_ENUMS[field])}")
        return str(value)
    if field in ("failover_managed", "telemetry"):
        return bool(value)
    if field in ("reasoning_model", "fast_model", "embed_model", "wake_word",
                 "push_to_talk", "dnd_window"):
        return str(value)[:80]
    raise ValueError(f"Unknown setting: {field}")


@system_router.get("/agent/config")
def get_agent_config(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(Tenant, p.tenant_id)
    return {
        "config": effective_config(t, db),
        "defaults": DEFAULT_AGENT_CONFIG,
        "options": _OPTIONS,
        "installed_models": llm.list_models(),
        "runtime": "ollama", "runtime_online": llm.available(),
    }


class AgentConfigPatch(BaseModel):
    config: dict


@system_router.patch("/agent/config")
def patch_agent_config(body: AgentConfigPatch, p: Principal = Depends(current_user),
                       db: Session = Depends(get_db)):
    t = db.get(Tenant, p.tenant_id)
    cfg = dict(t.agent_config or {})
    changed = []
    for k, v in (body.config or {}).items():
        if k not in DEFAULT_AGENT_CONFIG:
            continue
        try:
            cfg[k] = _coerce(k, v)
            changed.append(k)
        except (ValueError, TypeError) as e:
            from fastapi import HTTPException
            raise HTTPException(422, detail={"code": "BAD_VALUE", "message": str(e)})
    t.agent_config = cfg
    audit(db, plane="local", actor=f"user:{p.user_id}", action="agent.config_update",
          target=t.id, tenant_id=p.tenant_id, meta={"fields": changed})
    db.commit()
    hub.emit(p.tenant_id, "settings.changed", {"action": "update", "name": ", ".join(changed) or "config"})
    return {"config": effective_config(t, db),
            "message": f"Saved {len(changed)} setting(s)." if changed else "No changes."}


@system_router.post("/agent/config/reset")
def reset_agent_config(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(Tenant, p.tenant_id)
    t.agent_config = {}
    audit(db, plane="local", actor=f"user:{p.user_id}", action="agent.config_reset",
          tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "settings.changed", {"action": "reset", "name": "defaults"})
    return {"config": DEFAULT_AGENT_CONFIG, "message": "Hermes agent settings reset to defaults."}


_TONE_SYS = {"professional": "a professional business assistant", "friendly": "a warm, friendly assistant",
             "concise": "a terse assistant who answers in one line", "detailed": "a thorough assistant who explains fully"}
_GROUND_SYS = {"free": "", "cite_sources": " Cite sources where possible.",
               "strict": " Use only provided facts; if unknown, say you don't know."}


class TestIn(BaseModel):
    prompt: str = "Write a one-sentence greeting to a new customer named Sharma."


@system_router.post("/agent/config/test")
def test_agent_config(body: TestIn, p: Principal = Depends(current_user),
                      db: Session = Depends(get_db)):
    """Run a sample generation with the CURRENT config so the user sees the effect."""
    cfg = effective_config(db.get(Tenant, p.tenant_id), db)
    system = (f"You are {_TONE_SYS.get(cfg['tone'], 'an assistant')}. "
              f"Verbosity: {cfg['verbosity']}.{_GROUND_SYS.get(cfg['grounding'], '')}")
    out = llm.chat(body.prompt, system=system, model=cfg["reasoning_model"],
                   temperature=cfg["temperature"], num_predict=min(cfg["max_tokens"], 200),
                   num_ctx=cfg["context_window"], timeout=30)
    online = llm.available()
    if not out:
        out = (f"[{_TONE_SYS.get(cfg['tone'], 'assistant').split(' ')[-1]} · temp {cfg['temperature']}] "
               f"Hello Sharma, welcome aboard — delighted to have you with us.")
    return {"online": online, "model": cfg["reasoning_model"], "temperature": cfg["temperature"],
            "tone": cfg["tone"], "output": out,
            "message": "Sample generated with your current settings." if online
                       else "Runtime offline — showing a templated sample (your settings still saved)."}


# Field aliases the voice resolver understands → canonical config key.
_VOICE_FIELDS = {
    "temperature": ["temperature", "creativity"], "max_tokens": ["max tokens", "response length", "max length", "output length"],
    "context_window": ["context window", "context size", "context"],
    "autonomy": ["autonomy", "automation level"], "tone": ["tone"], "verbosity": ["verbosity", "detail level"],
    "grounding": ["grounding", "hallucination", "citation"], "language": ["language", "locale"],
    "retry_count": ["retries", "retry", "retry count"], "approval_threshold_inr": ["approval threshold", "approval limit", "threshold"],
    "wake_word": ["wake word", "wake phrase"], "tts_voice": ["voice", "tts voice"],
    "failover_managed": ["failover", "fallback to managed", "managed fallback"], "telemetry": ["telemetry", "analytics sharing", "usage data"],
    "reasoning_model": ["reasoning model", "smart model", "thinking model"], "fast_model": ["fast model", "quick model"],
}


class SettingsVoiceIn(BaseModel):
    transcript: str


@router.post("/settings/resolve")
def settings_resolve(body: SettingsVoiceIn, p: Principal = Depends(current_user),
                     db: Session = Depends(get_db)):
    text = body.transcript or ""
    low = re.sub(r"[^a-z0-9 .]", " ", text.lower())

    if re.search(r"\b(test|try|preview|sample)\b", low):
        return {"action": "test", "message": "Running a sample with your settings."}
    if re.search(r"\b(reset|defaults|restore default)\b", low):
        return {"action": "reset", "message": "Resetting to defaults."}
    if re.search(r"\b(advanced mode|simple mode|large type|big text|accessibility)\b", low):
        return {"action": "display",
                "mode": "advanced" if "advanced" in low else ("simple" if "simple" in low else None),
                "big": True if re.search(r"\b(large|big)\b", low) else None,
                "message": "Updating the display."}

    # on/off toggles
    on = bool(re.search(r"\b(turn on|enable|allow|activate)\b", low))
    off = bool(re.search(r"\b(turn off|disable|stop|deny)\b", low))
    for field in ("telemetry", "failover_managed"):
        if any(a in low for a in _VOICE_FIELDS[field]) and (on or off):
            return {"action": "set", "field": field, "value": on,
                    "message": f"{'Enabling' if on else 'Disabling'} {field.replace('_', ' ')}."}

    # enum sets — match a known value word for the field
    for field in ("autonomy", "tone", "verbosity", "grounding"):
        if any(a in low for a in _VOICE_FIELDS[field]) or field in low:
            for val in _ENUMS[field]:
                if val.replace("_", " ") in low or val in low:
                    return {"action": "set", "field": field, "value": val,
                            "message": f"Setting {field} to {val.replace('_', ' ')}."}
    # tone shorthand without the word "tone" (e.g. "be more friendly")
    for val in _ENUMS["tone"]:
        if re.search(rf"\b{val}\b", low):
            return {"action": "set", "field": "tone", "value": val, "message": f"Tone: {val}."}

    # numeric fields — "set <field> to <number>"
    for field in ("temperature", "max_tokens", "context_window", "retry_count", "approval_threshold_inr"):
        if any(a in low for a in _VOICE_FIELDS[field]):
            nm = re.search(r"(?:to|=|at|of)\s*([\d.,]+)", low) or re.search(r"\b([\d.,]+)\b", low)
            if nm:
                raw = nm.group(1).replace(",", "")
                try:
                    val = _coerce(field, float(raw) if field == "temperature" else int(float(raw)))
                    return {"action": "set", "field": field, "value": val,
                            "message": f"Setting {field.replace('_', ' ')} to {val}."}
                except ValueError as e:
                    return {"action": "none", "message": str(e)}
    # wake word / voice / language / model (string)
    wm = re.search(r"\b(?:wake word|wake phrase)\b.*?\bto\s+(.+)$", text, re.I)
    if wm:
        return {"action": "set", "field": "wake_word", "value": wm.group(1).strip(" .'\"")[:40],
                "message": f"Wake word set to {wm.group(1).strip()}."}
    for val in _ENUMS["language"]:
        if val.lower() in low:
            return {"action": "set", "field": "language", "value": val, "message": f"Language: {val}."}
    for val in _ENUMS["tts_voice"]:
        if val.lower() in low:
            return {"action": "set", "field": "tts_voice", "value": val, "message": f"Voice: {val}."}

    return {"action": "none",
            "message": 'Try "set temperature to 0.5", "use a friendly tone", "set autonomy to full auto", "turn on telemetry", or "test the agent".'}


@router.get("/config")
def voice_config(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    cfg = effective_config(db.get(Tenant, p.tenant_id), db)
    return {"wake_word": cfg["wake_word"], "push_to_talk": cfg["push_to_talk"],
            "locales": _OPTIONS["language"], "verbosity": cfg["verbosity"],
            "dnd_window": cfg["dnd_window"], "voices": _OPTIONS["voices"],
            "tts_voice": cfg["tts_voice"], "language": cfg["language"]}

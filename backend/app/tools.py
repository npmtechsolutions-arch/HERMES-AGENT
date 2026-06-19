"""
HERMUS internal tool framework — Doc 22 Prompt A (the foundation; everything in
Tier-1 depends on it). ARCHITECTURE.md §3: every capability is a function
registered with @tool; tools NEVER implement permission / approval / retry /
memory writes themselves — the single `call_tool` wrapper does all of it. Tool
bodies stay simple and return a uniform ToolResult with a one-line summary.

Stack note (deliberate, approved deviation — see commit summary): ARCHITECTURE
§1 specifies async SQLAlchemy, but the shipped backend is 100% synchronous, and
§9 forbids inventing a parallel session layer. So this framework is **sync**, to
match the running repo. The only async-shaped concept — "await approval" — is
adapted to sync by returning a *pending* ToolResult that the caller re-invokes
once the human approves (a sync request handler cannot block on a person).

This module is the FRAMEWORK ONLY. The actual tools (reminder.*, note.*, …) are
Prompt C/D; the richer Operational-Memory + artifact plumbing is Prompt B.
"""
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pydantic import ValidationError as PydanticValidationError, create_model

# ── error kinds (ARCHITECTURE §7 / Prompt A) ─────────────────────────────────
# transient | validation | permission | user_input_needed | credential
class ToolError(Exception):
    kind = "error"

    def __init__(self, *args, user_message: Optional[str] = None):
        super().__init__(*args)
        self.user_message = user_message


class TransientError(ToolError):
    """A retryable failure (timeout / network / 5xx). The wrapper retries these."""
    kind = "transient"


class CredentialError(ToolError):
    """A provider token expired and silent refresh failed (Tier-2). The wrapper
    surfaces ONE 'reconnect X' message and pauses dependents (ARCHITECTURE §7)."""
    kind = "credential"


class ToolValidationError(ToolError):
    kind = "validation"


class PermissionDenied(ToolError):
    kind = "permission"


class UserInputNeeded(ToolError):
    """Raised/returned when a human decision is required (approval / clarification)."""
    kind = "user_input_needed"


# ── uniform result (ARCHITECTURE §3) ─────────────────────────────────────────
@dataclass
class ToolResult:
    ok: bool
    summary: str = ""                       # ALWAYS one plain-language sentence
    data: dict = field(default_factory=dict)
    artifacts: list = field(default_factory=list)   # [{kind, title, ext, content/path}]
    error: Optional[str] = None             # one of the error kinds above
    confidence: Optional[float] = None


# ── identity / context (Doc 22 §1.2; actor models the identity chain) ────────
@dataclass
class Actor:
    """The identity chain for a tool call (tenant→user→agent). `grants` is the set
    of permission strings the calling agent holds; "*" grants everything."""
    tenant_id: str
    user_id: str
    agent_id: Optional[str] = None
    grants: set = field(default_factory=set)

    def allows(self, permission: str) -> bool:
        return "*" in self.grants or permission in self.grants


@dataclass
class ToolContext:
    actor: Actor
    db: Any = None                          # local SQLAlchemy Session (sync)
    user_id: Optional[str] = None
    now: Any = None                         # tz-aware now
    speak: Optional[Callable] = None        # optional TTS progress callback
    request_clarification: Optional[Callable] = None   # ask-don't-guess (returns user's answer)
    approved: bool = False                  # set true on the re-invocation after a human approval

    def __post_init__(self):
        if self.user_id is None:
            self.user_id = self.actor.user_id
        if self.now is None:
            from .models import now as _now
            self.now = _now()


# ── registry + decorator (ARCHITECTURE §3) ───────────────────────────────────
@dataclass
class ToolSpec:
    name: str
    description: str
    params: dict                # {pname: {type, required, enum, default, format}}
    permission: str
    approval: str               # "none" | "required" | "conditional"
    writes_memory: bool
    fn: Callable
    needs_approval: Optional[Callable] = None   # predicate(ctx, kwargs)->bool for "conditional"


TOOL_REGISTRY: dict[str, ToolSpec] = {}


def tool(name, description, params, permission, approval="none", writes_memory=False, needs_approval=None):
    """Register a capability. Tool bodies must NOT do permission/approval/retry/
    memory work — `call_tool` handles all of it (ARCHITECTURE §3). For
    approval="conditional", pass `needs_approval(ctx, kwargs)->bool`; when it
    returns True the call is gated like approval="required"."""
    def wrap(fn):
        TOOL_REGISTRY[name] = ToolSpec(name, description, params or {}, permission,
                                       approval, writes_memory, fn, needs_approval)
        return fn
    return wrap


# ── validation (Pydantic v2, built from the param schema) ────────────────────
_PYTYPES = {"string": str, "number": float, "integer": int, "boolean": bool,
            "bool": bool, "object": dict, "array": list}


def _model_for(spec: ToolSpec):
    fields = {}
    for pname, ps in spec.params.items():
        pytype = _PYTYPES.get(ps.get("type", "string"), Any)
        if ps.get("required"):
            fields[pname] = (pytype, ...)
        else:
            fields[pname] = (Optional[pytype], ps.get("default", None))
    return create_model(f"Params_{spec.name.replace('.', '_')}", **fields)


def _validate(spec: ToolSpec, kwargs: dict) -> dict:
    model = _model_for(spec)
    try:
        validated = model(**kwargs)
    except PydanticValidationError as e:
        raise ToolValidationError(str(e.errors()[0].get("msg", e)) if e.errors() else str(e))
    # enum checks (Pydantic create_model doesn't carry our enum constraint)
    for pname, ps in spec.params.items():
        val = kwargs.get(pname)
        if val is not None and ps.get("enum") and val not in ps["enum"]:
            raise ToolValidationError(f"'{pname}' must be one of {ps['enum']}")
    return validated.model_dump()


# ── enforcement / retry ──────────────────────────────────────────────────────
def enforce_permission(actor: Actor, permission: str):
    if not actor.allows(permission):
        raise PermissionDenied(f"Agent lacks the '{permission}' grant.")


def run_with_retry(fn, ctx, kwargs, *, max_attempts=3, base_delay=0.05) -> ToolResult:
    """Bounded retry on TRANSIENT errors only; exponential backoff (ARCHITECTURE §7)."""
    last = None
    for attempt in range(max_attempts):
        try:
            return fn(ctx, **kwargs)
        except TransientError as e:
            last = e
            if attempt < max_attempts - 1:
                time.sleep(base_delay * (2 ** attempt))
    raise last if last else TransientError("retries exhausted")


# ── memory / artifact plumbing (Doc 22 Prompt B / ARCHITECTURE §8) ───────────
def _data_root() -> str:
    """The user's LOCAL data root (~/HERMUS by default; overridable for tests/desktop)."""
    return os.environ.get("HERMUS_DATA_ROOT") or os.path.join(os.path.expanduser("~"), "HERMUS")


_RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_RE_PHONE = re.compile(r"\+?\d[\d \-()]{6,}\d")
_RE_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_RE_LONGNUM = re.compile(r"\b\d{6,}\b")          # account / Aadhaar / id numbers


def redact_pii(value):
    """Strip emails / phones / id-numbers from a string or (recursively) a dict/list.
    Used on the stored Operational-Memory input body — names stay, identifiers go."""
    if isinstance(value, str):
        v = _RE_EMAIL.sub("[redacted-email]", value)
        v = _RE_PAN.sub("[redacted-id]", v)
        v = _RE_PHONE.sub("[redacted-phone]", v)
        v = _RE_LONGNUM.sub("[redacted-id]", v)
        return v
    if isinstance(value, dict):
        return {k: redact_pii(x) for k, x in value.items()}
    if isinstance(value, list):
        return [redact_pii(x) for x in value]
    return value


def _extract_entities(spec: ToolSpec, kwargs: dict, result: ToolResult):
    """Heuristically pull the entities an action touched — contacts, bills/renewals,
    documents (Doc 22 Part 5). Returns deduped [(type, name)]."""
    ents = []
    for el in (kwargs.get("entity_links") or []):
        if isinstance(el, dict) and el.get("name"):
            ents.append((el.get("type", "custom"), el["name"]))
        elif isinstance(el, str) and el.strip():
            ents.append(("custom", el.strip()))
    for k in ("name", "to", "payee", "contact"):
        v = kwargs.get(k)
        if isinstance(v, str) and v.strip() and "@" not in v:
            ents.append(("contact", v.strip()))
    kind, label = kwargs.get("kind"), (kwargs.get("label") or kwargs.get("text"))
    if kind in ("bill", "renewal", "license") and isinstance(label, str) and label.strip():
        ents.append((kind, label.strip()))
    for art in (result.artifacts or []):
        if isinstance(art, dict) and art.get("title"):
            ents.append(("document", art["title"]))
    seen, out = set(), []
    for t, n in ents:
        key = (t, n.lower())
        if key not in seen:
            seen.add(key); out.append((t, n))
    return out


def _upsert_entity(db, tenant_id, etype, name):
    from .models import KGEntity
    from .security import ulid
    e = db.query(KGEntity).filter_by(tenant_id=tenant_id, type=etype, name=name).first()
    if not e:
        e = KGEntity(id=ulid("ent"), tenant_id=tenant_id, type=etype, name=name)
        db.add(e); db.flush()
    return e


def write_operational_memory(ctx: ToolContext, spec: ToolSpec, kwargs: dict, result: ToolResult):
    """On a successful tool, append exactly ONE Operational-Memory row (PII-redacted
    input) and upsert+link the entities it touched in the Knowledge Graph (§8)."""
    if ctx.db is None:
        return
    from .models import KGRelation, MemoryItem
    from .security import ulid
    clean_input = redact_pii({k: v for k, v in kwargs.items() if not str(k).startswith("_")})
    ent_ids = [_upsert_entity(ctx.db, ctx.actor.tenant_id, t, n).id
               for t, n in _extract_entities(spec, kwargs, result)]
    # KG relations are entity→entity: link the first touched entity to the rest.
    for eid in ent_ids[1:]:
        ctx.db.add(KGRelation(id=ulid("rel"), tenant_id=ctx.actor.tenant_id,
                              from_id=ent_ids[0], to_id=eid, relation=spec.name))
    body = {"tool": spec.name, "input": clean_input, "output": result.data,
            "agent": ctx.actor.agent_id, "at": ctx.now.isoformat(), "entities": ent_ids}
    ctx.db.add(MemoryItem(id=ulid("mem"), tenant_id=ctx.actor.tenant_id,
                          memory_class="operational", title=result.summary,
                          source_type="agent_action", body=json.dumps(body),
                          tier="hot", confidence=1.0))
    ctx.db.flush()


def save_artifacts(ctx: ToolContext, result: ToolResult):
    """Write each artifact LOCALLY to ~/HERMUS/files/{user_id}/{yyyy}/{mm}/ and record
    a task_artifacts row with the path. Content is NEVER transmitted (§2, §8)."""
    if not result.artifacts:
        return
    from .models import TaskArtifact
    from .security import ulid
    base = os.path.join(_data_root(), "files", ctx.actor.user_id,
                        ctx.now.strftime("%Y"), ctx.now.strftime("%m"))
    saved = []
    for art in result.artifacts:
        path = art.get("path")
        if art.get("content") is not None:
            try:
                os.makedirs(base, exist_ok=True)
                path = os.path.join(base, f"{ulid('art')}.{art.get('ext', 'md')}")
                with open(path, "w") as f:
                    f.write(art["content"])
            except Exception:
                path = "(local write failed)"
        if path and ctx.db is not None:
            ctx.db.add(TaskArtifact(id=ulid("art"), tenant_id=ctx.actor.tenant_id,
                                    user_id=ctx.actor.user_id, kind=art.get("kind", "document"),
                                    title=art.get("title"), path=path))
        rec = {k: v for k, v in art.items() if k != "content"}
        rec["path"] = path
        saved.append(rec)
    if ctx.db is not None:
        ctx.db.flush()
    result.artifacts = saved


def emit_activity(ctx: ToolContext, result: ToolResult, spec: ToolSpec):
    """Wire the one-line summary into the Activity feed: persist an audit record
    (what the feed reads + powers "Why?") and push it live over WebSocket."""
    if ctx.db is not None:
        try:
            from .deps import audit
            audit(ctx.db, plane="local", actor=f"agent:{ctx.actor.agent_id or 'aria'}",
                  action="assistant.action", target=result.summary,
                  tenant_id=ctx.actor.tenant_id, meta={"tool": spec.name, "ok": result.ok})
        except Exception:
            pass
    try:
        from .events import hub
        hub.emit(ctx.actor.tenant_id, "activity",
                 {"summary": result.summary, "tool": spec.name, "ok": result.ok})
    except Exception:
        pass


# ── the single execution path (Doc 22 §1.5 / ARCHITECTURE §3, §5, §7, §8) ────
def call_tool(name: str, ctx: ToolContext, /, **kwargs) -> ToolResult:
    # `name` + `ctx` are positional-only so a tool param literally called "name"
    # (e.g. routine.create) doesn't collide with the wrapper's own argument.
    spec = TOOL_REGISTRY.get(name)
    if not spec:
        return ToolResult(ok=False, error="validation", summary=f"Unknown tool '{name}'.")

    # 1) permission
    try:
        enforce_permission(ctx.actor, spec.permission)
    except PermissionDenied as e:
        return ToolResult(ok=False, error="permission", summary=str(e))

    # 2) validate params (Pydantic v2) — before the conditional predicate sees them
    try:
        clean = _validate(spec, kwargs)
    except ToolValidationError as e:
        return ToolResult(ok=False, error="validation", summary=str(e))

    # 3) approval gate — money / new-contact / destructive (ARCHITECTURE §5).
    #    "required" always gates; "conditional" gates iff the tool's predicate says
    #    so. Sync adaptation: return a pending result; the caller re-invokes with
    #    approval granted (ctx.approved=True) after the human decides.
    gate = spec.approval == "required"
    if spec.approval == "conditional" and spec.needs_approval:
        try:
            gate = bool(spec.needs_approval(ctx, clean))
        except Exception:
            gate = True   # fail-safe: if we can't evaluate, require approval
    if gate and not (ctx.approved or kwargs.get("_approved")):
        return ToolResult(ok=False, error="user_input_needed",
                          summary=f"“{spec.name}” needs your approval before it runs.",
                          data={"needs_approval": True})

    # 4) run with bounded transient retry
    try:
        result = run_with_retry(spec.fn, ctx, clean)
    except CredentialError as e:
        return ToolResult(ok=False, error="credential",
                          summary=e.user_message or "A connection needs reconnecting.")
    except UserInputNeeded as e:
        return ToolResult(ok=False, error="user_input_needed", summary=str(e) or "Need one detail from you.")
    except TransientError as e:
        return ToolResult(ok=False, error="transient", summary=f"{spec.name} kept failing: {e}")
    except Exception as e:
        return ToolResult(ok=False, error="validation", summary=f"{spec.name} failed: {e}")

    # 5) persist memory + artifacts on success, 6) emit activity summary
    if result.ok:
        if result.artifacts:
            save_artifacts(ctx, result)
        if spec.writes_memory:
            write_operational_memory(ctx, spec, clean, result)
        emit_activity(ctx, result, spec)
        if ctx.speak:                       # voice session → speak the one-line summary
            try:
                ctx.speak(result.summary)
            except Exception:
                pass
    return result


def registry_dto():
    """The MCP-style tool list (for later discovery endpoints)."""
    return [{"name": s.name, "description": s.description, "params": s.params,
             "permission": s.permission, "approval": s.approval,
             "writes_memory": s.writes_memory} for s in TOOL_REGISTRY.values()]

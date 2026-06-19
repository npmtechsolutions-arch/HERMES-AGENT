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
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pydantic import ValidationError as PydanticValidationError, create_model

# ── error kinds (ARCHITECTURE §7 / Prompt A) ─────────────────────────────────
# transient | validation | permission | user_input_needed
class ToolError(Exception):
    kind = "error"


class TransientError(ToolError):
    """A retryable failure (timeout / network / 5xx). The wrapper retries these."""
    kind = "transient"


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
    approval: str               # "none" | "required"
    writes_memory: bool
    fn: Callable


TOOL_REGISTRY: dict[str, ToolSpec] = {}


def tool(name, description, params, permission, approval="none", writes_memory=False):
    """Register a capability. Tool bodies must NOT do permission/approval/retry/
    memory work — `call_tool` handles all of it (ARCHITECTURE §3)."""
    def wrap(fn):
        TOOL_REGISTRY[name] = ToolSpec(name, description, params or {}, permission,
                                       approval, writes_memory, fn)
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


# ── memory / artifact / activity hooks ───────────────────────────────────────
# NOTE: Prompt B replaces write_operational_memory + save_artifacts with the full
# plumbing (redact_pii, KG entity linking, ~/HERMUS/files paths, task_artifacts).
# These minimal versions keep the wrapper functional and testable for Prompt A.
def write_operational_memory(ctx: ToolContext, spec: ToolSpec, kwargs: dict, result: ToolResult):
    if ctx.db is None:
        return
    import json
    from .models import MemoryItem
    from .security import ulid
    body = {"tool": spec.name, "input": {k: v for k, v in kwargs.items() if not k.startswith("_")},
            "output": result.data, "agent": ctx.actor.agent_id, "at": ctx.now.isoformat()}
    ctx.db.add(MemoryItem(id=ulid("mem"), tenant_id=ctx.actor.tenant_id,
                          memory_class="operational", title=result.summary,
                          source_type="agent_action", body=json.dumps(body),
                          tier="hot", confidence=1.0))


def save_artifacts(ctx: ToolContext, result: ToolResult):
    if not result.artifacts:
        return
    import os
    from .security import ulid
    base = os.path.join(os.path.expanduser("~"), "HERMUS", "files", ctx.actor.tenant_id)
    saved = []
    for art in result.artifacts:
        if art.get("content") is not None:
            try:
                os.makedirs(base, exist_ok=True)
                path = os.path.join(base, f"{ulid('art')}.{art.get('ext', 'md')}")
                with open(path, "w") as f:
                    f.write(art["content"])
                art["path"] = path
            except Exception:
                art["path"] = "(local write failed)"
        saved.append({k: v for k, v in art.items() if k != "content"})
    result.artifacts = saved


def emit_activity(ctx: ToolContext, result: ToolResult, spec: ToolSpec):
    """Stream the one-line summary to the Activity WebSocket topic (Prompt A)."""
    try:
        from .events import hub
        hub.emit(ctx.actor.tenant_id, "activity",
                 {"summary": result.summary, "tool": spec.name, "ok": result.ok})
    except Exception:
        pass


# ── the single execution path (Doc 22 §1.5 / ARCHITECTURE §3, §5, §7, §8) ────
def call_tool(name: str, ctx: ToolContext, **kwargs) -> ToolResult:
    spec = TOOL_REGISTRY.get(name)
    if not spec:
        return ToolResult(ok=False, error="validation", summary=f"Unknown tool '{name}'.")

    # 1) permission
    try:
        enforce_permission(ctx.actor, spec.permission)
    except PermissionDenied as e:
        return ToolResult(ok=False, error="permission", summary=str(e))

    # 2) approval gate — money / new-contact / destructive (ARCHITECTURE §5).
    #    Sync adaptation: return a pending result; caller re-invokes with the
    #    approval granted (ctx.approved=True) after the human decides.
    if spec.approval == "required" and not (ctx.approved or kwargs.get("_approved")):
        return ToolResult(ok=False, error="user_input_needed",
                          summary=f"“{spec.name}” needs your approval before it runs.",
                          data={"needs_approval": True})

    # 3) validate params (Pydantic v2)
    try:
        clean = _validate(spec, kwargs)
    except ToolValidationError as e:
        return ToolResult(ok=False, error="validation", summary=str(e))

    # 4) run with bounded transient retry
    try:
        result = run_with_retry(spec.fn, ctx, clean)
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
    return result


def registry_dto():
    """The MCP-style tool list (for later discovery endpoints)."""
    return [{"name": s.name, "description": s.description, "params": s.params,
             "permission": s.permission, "approval": s.approval,
             "writes_memory": s.writes_memory} for s in TOOL_REGISTRY.values()]

"""
Refine-with-chat (Doc 30 Phase 1). A fourth door into the SAME engine, specialised
for improving an existing result. A content-producing tool run persists v1; each
refinement runs the generic content.refine tool on the prior output and saves a
new version. History is revertible and every version is in Activity (§1.3).
Guardrails are unchanged: refinement edits content, never the approval rules of
later actions (§1.4).
"""
from .models import ResultVersion
from .routers.agents_profile import agent_of_tool
from .security import ulid
from .tools import Actor, ToolContext, call_tool

# result.data keys (in priority order) that hold refinable content
_OUTPUT_KEYS = ("output", "text", "draft", "summary", "content", "body", "answer")

# Only content-producing tools are refinable. Actions (reminders, contacts,
# memory ops, list edits) are not — there's nothing to "make shorter / more formal".
REFINABLE_TOOLS = {"note.create", "document.generate", "text.summarize", "text.polish",
                   "message.draft", "form.fill", "briefing.compose", "roi.summarize", "task.plan"}


def extract_output(result, params=None):
    """The refinable text a result holds, or None (e.g. a reminder has none).
    Prefers the tool's OUTPUT (polished/summarized text); falls back to the input
    content it was given (note text, doc content) — which survives even after an
    artifact's body has been written to a file."""
    d = result.data or {}
    for k in _OUTPUT_KEYS:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v
    for a in (result.artifacts or []):
        if isinstance(a.get("content"), str) and a["content"].strip():
            return a["content"]
    for k in ("content", "text", "body", "message", "intent", "draft", "output"):
        v = (params or {}).get(k)
        if isinstance(v, str) and v.strip():
            return v
    return None


def create_v1(db, *, tenant_id, user_id, tool, params, result):
    """Persist the original result as v1 if it has refinable content. Returns the
    anchor_id (the result the UI can ✨ Refine) or None."""
    if tool not in REFINABLE_TOOLS:
        return None
    output = extract_output(result, params)
    if not output:
        return None
    anchor = ulid("res")
    db.add(ResultVersion(id=ulid("rv"), anchor_id=anchor, tenant_id=tenant_id, user_id=user_id,
                         version=1, tool=tool, params=params or {}, instruction=None,
                         output=output, summary=result.summary, is_current=True))
    db.flush()
    return anchor


def _versions(db, anchor_id, tenant_id):
    return (db.query(ResultVersion)
            .filter_by(anchor_id=anchor_id, tenant_id=tenant_id)
            .order_by(ResultVersion.version).all())


def _dto(rv, *, full=False):
    d = {"id": rv.id, "version": rv.version, "instruction": rv.instruction,
         "summary": rv.summary, "is_current": rv.is_current, "tool": rv.tool,
         "created_at": rv.created_at.isoformat() if rv.created_at else None}
    d["output"] = rv.output if full else (rv.output or "")[:280]
    return d


def history(db, anchor_id, tenant_id):
    rows = _versions(db, anchor_id, tenant_id)
    return {"anchor_id": anchor_id, "versions": [_dto(r, full=True) for r in rows]}


def refine(db, *, tenant_id, user_id, anchor_id, instruction):
    """Run content.refine on the current version → save + activate a new version."""
    rows = _versions(db, anchor_id, tenant_id)
    if not rows:
        return {"ok": False, "error": "not_found", "summary": "That result no longer exists."}
    cur = next((r for r in rows if r.is_current), rows[-1])

    ctx = ToolContext(actor=Actor(tenant_id=tenant_id, user_id=user_id,
                                  agent_id=agent_of_tool(cur.tool or "") or "Scribe", grants={"*"}), db=db)
    # source = the prior content → the refine may not introduce a figure absent
    # from it (§1.4 — a refined invoice with a wrong number is blocked, not saved).
    r = call_tool("content.refine", ctx, prior_output=cur.output,
                  instruction=instruction, source=cur.output)
    if not r.ok:
        return {"ok": False, "error": r.error, "summary": r.summary, "anchor_id": anchor_id}

    new_out = r.data.get("output", cur.output)
    n = max(x.version for x in rows) + 1
    for x in rows:
        x.is_current = False
    nv = ResultVersion(id=ulid("rv"), anchor_id=anchor_id, tenant_id=tenant_id, user_id=user_id,
                       version=n, tool=cur.tool, params=cur.params or {}, instruction=instruction,
                       output=new_out, summary=f"v{n}: {instruction}"[:120], is_current=True)
    db.add(nv); db.flush()
    return {"ok": True, "anchor_id": anchor_id, "version": _dto(nv, full=True),
            "summary": f"Here's v{n}.", "total_versions": n}


def revert(db, *, tenant_id, anchor_id, version):
    rows = _versions(db, anchor_id, tenant_id)
    target = next((r for r in rows if r.version == version), None)
    if not target:
        return {"ok": False, "error": "not_found", "summary": "No such version."}
    for x in rows:
        x.is_current = (x.version == version)
    db.flush()
    return {"ok": True, "anchor_id": anchor_id, "version": _dto(target, full=True),
            "summary": f"Reverted to v{version}."}

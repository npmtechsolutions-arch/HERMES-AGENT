# HERMUS PERSONAL — TIER-1 INTERNAL TOOL SET
## Build-Ready Implementation Specification
**Version 1.0 | Pure local tools, zero external dependencies — your team can start today**
**Stack: Python FastAPI (local core) · PostgreSQL (local) · MCP tool convention · Ollama**

This is the implementation spec for the ~20 internal tools that give HERMUS Personal most of its daily value with no OAuth, no third-party APIs, no network. Every tool is a local Python function exposed as an MCP tool, callable by agents, gated by approval rules where needed, and writing its result to the Second Brain.

---

# PART 1 — THE TOOL CONTRACT (how every tool is built)

## 1.1 Anatomy of a tool
Every Tier-1 tool is a Python function with a declarative manifest:

```python
@tool(
    name="reminder.create",
    description="Create a reminder for the user at a specific time.",
    params={
        "text": {"type": "string", "required": True},
        "due_at": {"type": "string", "format": "iso8601", "required": True},
        "repeat": {"type": "string", "enum": ["none","daily","weekly","monthly"], "default": "none"},
    },
    permission="reminders.write",   # checked against the calling agent's grants
    approval="none",                # none | required (money/new-contact/destructive)
    writes_memory=True,             # auto-logs to Operational Memory on success
)
async def reminder_create(ctx: ToolContext, text: str, due_at: str, repeat="none"):
    ...
    return ToolResult(ok=True, data={...}, summary="Reminder set for ...")
```

## 1.2 The ToolContext (what every tool receives)
```python
class ToolContext:
    actor: IdentityChain      # tenant→user→agent→tool→device (Doc 15 §3.1)
    db: AsyncSession          # local PostgreSQL session
    user_id: str
    now: datetime             # user's timezone-aware now
    speak: Callable           # optional TTS callback for progress
    request_clarification: Callable  # ask-don't-guess (returns user's answer)
```

## 1.3 The ToolResult (uniform return)
```python
class ToolResult:
    ok: bool
    data: dict                # structured result
    summary: str              # ONE plain-language line (shown in Activity, spoken)
    artifacts: list[Artifact] # files produced (saved locally, Part 4)
    error: ToolError | None   # class: transient|validation|permission|user_input_needed
    confidence: float | None  # if extraction/parse involved
```

## 1.4 The six rules every tool obeys
1. **Local only** — no network calls in Tier-1 (enforced: these tools run in a no-egress context).
2. **Permission-checked** — `ctx.actor` agent must hold the tool's `permission` grant (∩ tenant ceiling).
3. **Approval-gated where declared** — `approval="required"` routes through the approval engine before execution (money, new contact, destructive).
4. **Ask-don't-guess** — ambiguous/low-confidence input calls `ctx.request_clarification()` instead of guessing (rule U3).
5. **Writes memory** — on success, if `writes_memory`, append an Operational Memory entry + link KG entities (Part 5).
6. **Returns a plain summary** — one human sentence, always (powers Activity feed + voice).

## 1.5 Execution wrapper (the engine runs every tool through this — build once)
```
resolve identity chain → check permission → (if approval) enqueue & wait decision
  → validate params (Pydantic) → run with bounded retry (transient×3)
  → on user_input_needed: ask once, resume → write memory + artifacts
  → emit ToolResult → stream summary to Activity (WebSocket) → speak if voice session
```
Retry/clarification/approval are handled HERE, not in each tool — tools stay simple.

---

# PART 2 — THE TIER-1 TOOL CATALOG (the ~20 to build)

Grouped by the agent that typically calls them. All are local. "Approval" column: ✋ = human gate.

## 2.1 Scheduler agent — time & reminders
| Tool | Params | Approval | Memory |
|---|---|---|---|
| `reminder.create` | text, due_at, repeat | none | ✅ |
| `reminder.list` | filter(due_before, status) | none | — |
| `reminder.update` | id, fields | none | ✅ |
| `reminder.cancel` | id | none | ✅ |
| `routine.create` | name, cadence(cron), action_ref | none | ✅ |
| `deadline.track` | label, due_at, kind(bill/renewal/license) | none | ✅ |

## 2.2 Scribe agent — notes, documents, summaries
| Tool | Params | Approval | Memory |
|---|---|---|---|
| `note.create` | text, tags[] | none | ✅ |
| `note.search` | query, top_k | none | — |
| `list.manage` | list_name, op(add/remove/check), item | none | ✅ |
| `document.generate` | template_id, data, format(pdf/docx) | none | ✅ (artifact) |
| `text.summarize` | source(text|doc_id), length | none | ✅ |
| `text.polish` | text, tone | none | — |
| `form.fill` | form_template_id, autofill_from_memory:bool | none | ✅ (artifact) |

## 2.3 Finder agent — memory & knowledge
| Tool | Params | Approval | Memory |
|---|---|---|---|
| `memory.search` | query, scopes[], top_k | none | — |
| `memory.write` | content, class, entity_links[] | none | ✅ |
| `memory.forget` | id | ✋ (destructive) | ✅ |
| `contact.upsert` | name, fields, relationship | none | ✅ (KG) |
| `contact.lookup` | name_or_mention | none | — |

## 2.4 Inbox agent — drafting (local part; sending is Tier-2)
| Tool | Params | Approval | Memory |
|---|---|---|---|
| `message.draft` | to_entity, intent, tone, channel | none (draft only) | ✅ |
| `followup.schedule` | thread_or_entity, cadence | none | ✅ |

## 2.5 Aria (CEO-Agent) — orchestration & reporting
| Tool | Params | Approval | Memory |
|---|---|---|---|
| `task.plan` | utterance | none | — |
| `briefing.compose` | scope(daily/weekly) | none | — |
| `roi.summarize` | period | none | — |

**Total: ~24 tools.** Every one is local Python + a DB write. No external auth. This is the buildable core.

---

# PART 3 — REFERENCE IMPLEMENTATIONS (copy-paste starting points)

## 3.1 `reminder.create`
```python
@tool(name="reminder.create", permission="reminders.write", approval="none", writes_memory=True,
      description="Create a reminder at a specific time, optionally repeating.",
      params={"text":{"type":"string","required":True},
              "due_at":{"type":"string","format":"iso8601","required":True},
              "repeat":{"type":"string","enum":["none","daily","weekly","monthly"],"default":"none"}})
async def reminder_create(ctx, text, due_at, repeat="none"):
    due = parse_iso(due_at, tz=ctx.user_tz)
    if due < ctx.now:
        # ask-don't-guess: past time likely a parse error
        ans = await ctx.request_clarification(
            f"That time ({due:%d %b %I:%M %p}) is in the past — did you mean a future date?")
        due = parse_iso(ans, tz=ctx.user_tz)
    rid = ulid()
    await ctx.db.execute(insert(Reminders).values(
        id=rid, user_id=ctx.user_id, text=text, due_at=due, repeat=repeat, status="active"))
    await schedule_trigger(rid, due, repeat)          # hooks your existing scheduler
    return ToolResult(ok=True, data={"id":rid,"due_at":due.isoformat()},
                      summary=f"Reminder set: “{text}” for {due:%a %d %b, %I:%M %p}.")
```

## 3.2 `document.generate` (uses Document Factory + saves artifact locally)
```python
@tool(name="document.generate", permission="documents.write", approval="none", writes_memory=True,
      description="Generate a document from a template and data; saves a file locally.",
      params={"template_id":{"type":"string","required":True},
              "data":{"type":"object","required":True},
              "format":{"type":"string","enum":["pdf","docx"],"default":"pdf"}})
async def document_generate(ctx, template_id, data, format="pdf"):
    tmpl = await load_template(ctx.db, ctx.user_id, template_id)
    # validate every figure/date against source (rule U4) — fail closed if mismatch
    validate_fields(tmpl, data)
    path = render_document(tmpl, data, format,
                           out_dir=user_files_dir(ctx.user_id))   # LOCAL folder (Part 4)
    art = Artifact(kind=format, path=path, title=tmpl.title)
    return ToolResult(ok=True, data={"path":path}, artifacts=[art],
                      summary=f"Created {tmpl.title} ({format.upper()}).")
```

## 3.3 `memory.forget` (destructive → approval-gated, soft-delete)
```python
@tool(name="memory.forget", permission="memory.write", approval="required", writes_memory=True,
      description="Forget a memory item. Soft-deletes with a 30-day recovery window.",
      params={"id":{"type":"string","required":True}})
async def memory_forget(ctx, id):
    # approval handled by the wrapper BEFORE we run — here we just execute
    await ctx.db.execute(update(MemoryItems).where(MemoryItems.id==id)
        .values(deleted_at=ctx.now, purge_after=ctx.now + timedelta(days=30)))
    return ToolResult(ok=True, data={"id":id},
                      summary="Forgotten (recoverable for 30 days).")
```

## 3.4 The `@tool` decorator + registry (build this once)
```python
TOOL_REGISTRY: dict[str, ToolSpec] = {}

def tool(name, description, params, permission, approval="none", writes_memory=False):
    def wrap(fn):
        spec = ToolSpec(name, description, params, permission, approval, writes_memory, fn)
        TOOL_REGISTRY[name] = spec           # agents discover tools from here (MCP list)
        return fn
    return wrap

async def call_tool(name, ctx, **kwargs):    # the wrapper from Part 1.5
    spec = TOOL_REGISTRY[name]
    enforce_permission(ctx.actor, spec.permission)
    if spec.approval == "required":
        await await_approval(ctx, spec, kwargs)        # blocks until decided
    validate_params(spec.params, kwargs)
    result = await run_with_retry(spec.fn, ctx, **kwargs)   # transient×3
    if result.ok and spec.writes_memory:
        await write_operational_memory(ctx, spec, kwargs, result)   # Part 5
        await save_artifacts(ctx, result.artifacts)                 # Part 4
    await emit_activity(ctx, result.summary)            # WebSocket → Activity feed
    return result
```

---

# PART 4 — WHERE OUTPUT IS STORED (on the user's machine)

```
~/HERMUS/                              (user's local data root)
  ├── hermus.db        ← local PostgreSQL (tasks, memory, reminders, KG, audit)
  ├── files/           ← generated docs, summaries, exports
  │     └── {user_id}/{yyyy}/{mm}/{artifact}.pdf
  ├── ingest/          ← dropped files awaiting/after ingestion
  └── backups/         ← encrypted backups (user key) — or user's chosen destination
```
- `user_files_dir()` returns `~/HERMUS/files/{user_id}/...`; every artifact path is recorded in `task_artifacts` (Doc 12).
- **Nothing here is sent to the cloud** — the cloud plane has no endpoint accepting file content (privacy invariant, Doc 15 DB-01).
- The user opens/exports/shares from the Tasks or Memory screen; backup is local-key, user-destination.

---

# PART 5 — HOW ACTIONS WRITE TO THE SECOND BRAIN

Every successful tool with `writes_memory=True` appends an **Operational Memory** record and links entities:

```python
async def write_operational_memory(ctx, spec, kwargs, result):
    await ctx.db.execute(insert(MemoryItems).values(
        id=ulid(), user_id=ctx.user_id, memory_class="operational",
        title=result.summary,
        body={"tool":spec.name, "input":redact_pii(kwargs), "output":result.data,
              "agent":ctx.actor.agent_id, "at":ctx.now.isoformat()},
        source_type="agent_action"))
    for ent in extract_entities(kwargs, result):     # contacts, bills, docs...
        await upsert_kg_entity_and_link(ctx.db, ctx.user_id, ent, action=spec.name)
```
This is what makes the assistant *learn*: "you set this reminder last month — repeat it?" comes from querying Operational Memory; the Knowledge Graph links the reminder to the bill to the payee so "remind me about the gas bill" resolves correctly next time. All local, all user-editable/forgettable.

---

# PART 6 — HOW AGENTS USE THESE TOOLS (the loop, end to end)

```
User: "Every month remind me to pay the electricity bill and note it as paid when I confirm."
 → STT → Aria.task.plan(utterance)
 → plan: [Scheduler.routine.create(monthly), Scheduler.reminder.create,
          on-confirm: Finder.memory.write("electricity paid {month}")]
 → no approval needed (no money moved, known context) → execute
 → call_tool runs each, writes Operational Memory, emits Activity summaries
 → Aria speaks: "Done — I'll remind you on the 1st each month and log it when you confirm."
```
The agent's job is only to **choose tools and arguments**; the wrapper handles permission, approval, retry, memory, and reporting. Adding a new capability later = add one tool to the registry; the loop is unchanged.

---

# PART 7 — BUILD PLAN (what to do, in order)

| Step | Deliverable | Days (rough) |
|---|---|---|
| 1 | `@tool` decorator + registry + `call_tool` wrapper (Part 1.5, 3.4) | 3–4 |
| 2 | Permission check + approval-await + retry + clarification plumbing | 4–5 |
| 3 | Operational-memory writer + KG linker + artifact saver (Parts 4–5) | 3 |
| 4 | Scheduler tools (reminders, routines, deadlines) | 3 |
| 5 | Scribe tools (notes, lists, summarize, polish, document.generate, form.fill) | 5 |
| 6 | Finder tools (memory search/write/forget, contacts) | 3 |
| 7 | Inbox draft + followup tools (draft only; send is Tier-2) | 2 |
| 8 | Aria tools (plan, briefing, roi) — wire to existing planner | 3 |
| 9 | Activity feed wiring (WebSocket) + "Why?" surfacing from audit | 3 |
| 10 | Golden-task evals for each tool (no wrong output) + voice round-trip test | 4 |

~6 weeks for one engineer; ~3 weeks for two. Output: a genuinely useful local PA before any external integration exists.

---

# PART 8 — IMPLEMENTATION PROMPTS (paste into Claude Code / your IDE agent)

These are ready-to-use build prompts. Run them in order; each assumes the previous is merged.

## Prompt A — Tool framework
```
Build the HERMUS internal tool framework in the local FastAPI core (Python 3.12, SQLAlchemy 2 async, Pydantic v2).
Create:
1. A `@tool(name, description, params, permission, approval="none", writes_memory=False)` decorator that registers ToolSpec objects in a TOOL_REGISTRY dict.
2. ToolContext (actor: IdentityChain, db session, user_id, now (tz-aware), speak callback, request_clarification async callback) and ToolResult (ok, data, summary, artifacts, error, confidence) dataclasses.
3. A `call_tool(name, ctx, **kwargs)` async wrapper that: enforces permission against ctx.actor's grants, awaits approval if approval=="required", validates kwargs against the param schema with Pydantic, runs the tool with bounded retry (3x exponential backoff on transient errors only), and on success (if writes_memory) calls write_operational_memory and save_artifacts, then emits the summary to an Activity WebSocket topic.
4. Error classes: transient | validation | permission | user_input_needed.
Write unit tests for permission denial, approval gating, retry, and param validation.
Do not make any external network calls in this layer.
```

## Prompt B — Memory + artifacts plumbing
```
Implement write_operational_memory(ctx, spec, kwargs, result) and save_artifacts(ctx, artifacts) for HERMUS.
- write_operational_memory inserts a MemoryItems row (memory_class='operational', title=result.summary, body=JSON of {tool, redacted input, output, agent, timestamp}, source_type='agent_action'), then extracts entities (contacts, bills, documents, dates) and upserts/links them in kg_entities/kg_relations.
- redact_pii() must strip emails/phones/IDs from the stored input body.
- save_artifacts writes each artifact to ~/HERMUS/files/{user_id}/{yyyy}/{mm}/ and records a task_artifacts row with the path. Never transmit file content anywhere.
Add tests: a tool run produces exactly one operational memory row, correct KG links, and a locally-saved file with a recorded path.
```

## Prompt C — Scheduler + Scribe tools
```
Using the @tool framework, implement these local tools with Pydantic-validated params, each returning a one-sentence plain-language summary and writing operational memory where noted:
reminder.create/list/update/cancel, routine.create, deadline.track (Scheduler);
note.create/search, list.manage, document.generate (use the Document Factory; save PDF/DOCX locally; validate every figure/date against provided source and fail closed on mismatch), text.summarize, text.polish, form.fill (Scribe).
reminder.create and routine.create must register triggers with the existing scheduler. document.generate and form.fill must produce a local artifact. Add golden-task tests covering a correct case and an adversarial case (e.g., a wrong figure that must be blocked) per tool.
```

## Prompt D — Finder + Inbox + Aria tools
```
Implement: memory.search/write/forget (forget = approval=required, soft-delete with 30-day purge_after), contact.upsert/lookup (write to kg_entities) — Finder;
message.draft (produces a draft only, never sends), followup.schedule — Inbox;
task.plan (wrap the existing CEO-Agent planner), briefing.compose (daily/weekly), roi.summarize — Aria.
Wire all summaries into the Activity feed. Add a voice round-trip test: a spoken utterance → STT → task.plan → tool calls → spoken summary, asserting the operational-memory and activity records exist.
```

---

# PART 9 — DEFINITION OF DONE

A user can, fully offline, by voice or click: set/repeat/cancel reminders and routines; track bills & renewals; take and search notes & lists; generate and summarize documents; fill forms from memory; search and edit their Second Brain; manage contacts; draft messages and schedule follow-ups; get a daily briefing and weekly ROI note — with every action permission-checked, approval-gated where sensitive, retried on transient failure, asking rather than guessing when unsure, stored locally, written to Operational Memory, visible in the Activity feed with a "Why?", and never sent to the cloud. That is HERMUS Personal's Tier-1 — most of the daily value, zero external dependencies.
```

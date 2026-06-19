# HERMUS PERSONAL — CONSOLIDATED FEATURE ANALYSIS & GAP-FILL IMPLEMENTATION
**Version 1.0 | Reconciling the "Personal Agentic AI" consolidated list against HERMUS Docs 21–24**
**What's already covered · what's genuinely new · what to defer · how to build the new items**

---

# PART 1 — VERDICT ON THE LIST

It's a strong, well-structured vision and it **validates your architecture** — ~85% of it already maps onto HERMUS Docs 21–24 (multi-model gateway, memory types, proactive engine, Tier-1/2/3 tools, desktop/browser control, local-first privacy, approval gates, audit). The value is in **~8 genuinely new items** worth adopting, **2 traps** to neutralize, and **1 correction** to prevent a wrong dependency.

## 1.1 Coverage map (every section of the list → where it already lives)
| List section | HERMUS status |
|---|---|
| 1 Hybrid Model Architecture | ✅ Doc 24 §3.3 Model Gateway (+ new items below: scrub&send, offline toggle, fallback) |
| 2 Autonomous Task Execution | ✅ Doc 21 §6 (CEO-Agent, approval, monitoring) |
| 3 Advanced Persistent Memory | ✅ Doc 24 §3.1 five memory types (+ NEW: SOUL.md, NOW.md) |
| 4 Adaptive Onboarding | 🔨 partial — auto-profile is NEW (below) |
| 5 Proactive Engine | ✅ Doc 24 §3.4 |
| 6 Scheduled/Recurring/Conditional | ✅ scheduler; conditional triggers 🔨 minor extension |
| 7 System-Level Actions | ✅ Doc 23 Tier-3 (desktop/shell/screen — sandboxed) |
| 8 Digital Life Actions | ✅ Doc 23 Tier-2 connectors |
| 9 Custom Tool Generation | ✅ Skill Builder/auto-capture (Doc 24) — *safe version only* |
| 10 Multi-Platform | 🔨 mobile/messaging are roadmap (Doc 14 G2) |
| 11 Cross-Device Orchestration | ✅ Remote Command (Doc 14 G2) + NEW: user-encrypted sync |
| 12 Privacy-First | ✅ + NEW: scrub&send, classification tags, offline toggle |
| 13 Security & Safety | ✅ Doc 15 (sandbox, RBAC, audit, permissions) |
| 14 Deployment (BYOC) | 🔨 BYOC adopt; Hybrid Burst Mode DEFER |
| 15 Cost Dashboard | 🆕 NEW — adopt (strong for BYOK) |
| 16 Observability/Self-Improvement | ✅ eval layer; self-modification = *safe version only* |
| 17 Natural Interaction | ✅ |
| 18 Accessibility | ✅ Doc 17 §9.6 |

## 1.2 The correction (prevent a wrong dependency)
The list says vector DB = "ChromaDB/LanceDB." **HERMUS uses PostgreSQL + pgvector** — keep it. One database, transactional with tasks/memory/KG, already in your build. **Do not add a second vector store.** (Note this in the engineering brief so nobody introduces Chroma.)

---

# PART 2 — THE GENUINELY NEW ITEMS TO ADOPT (8)

## 2.1 SOUL.md — Portable Identity File ★ (best new idea)
**What:** the user's core personality + key preferences + identity, stored as a **human-readable Markdown file the user owns**, movable between machines, backupable, editable.
**Why it fits:** makes "you own your data" tangible; a perfect local-first artifact; a marketing asset ("your AI's soul is a file you control").
**Implementation:**
- `SOUL.md` generated at `~/HERMUS/SOUL.md`, regenerated from the semantic+preference memory layers (Doc 24 §3.1) on change.
- Sections: Identity, Communication style, Preferences, Key relationships, Active goals, Values/boundaries.
- It is a **projection of memory**, not a separate store — memory remains the source of truth in pgvector; SOUL.md is the readable, portable export the agent also reads at session start to set tone.
- User can hand-edit it; edits are parsed back into memory (with confidence flags). Moving SOUL.md to a new machine seeds a fresh install's personality instantly.
- Ties to Digital Twin later (Doc 24 §6 deferred) — SOUL.md is the twin's seed.

## 2.2 NOW.md — Active Context / Scratchpad ★
**What:** a short-term "current focus" layer — active projects, today's thread, what we're mid-task on — so the assistant doesn't lose the plot across a session.
**Why it fits:** you have long-term memory (pgvector) and conversation memory (Redis/TTL); NOW.md is the *working-set* layer between them. Genuine gap.
**Implementation:** a small, always-in-context structured doc (`~/HERMUS/NOW.md`) holding current goals, open tasks, and recent decisions; updated as tasks start/finish; injected into every agent prompt as "current context." Cheap, high-impact for coherence.

## 2.3 Scrub & Send — PII stripping for cloud calls ★
**What:** when a task *does* use a cloud model (BYOK/managed), strip PII from the prompt, send anonymized, re-inject locally on return.
**Why it fits:** operationalizes your "PII never leaves local" rule for the cloud-allowed cases; strong privacy proof point.
**Implementation:** a pre-dispatch middleware in the Model Gateway: detect PII (names, emails, phones, IDs, classified-tagged content) → replace with placeholders → call cloud → map placeholders back in the response. **Classified-tagged content (2.4) is never scrubbed-and-sent — it's blocked from cloud entirely.** Log every scrub decision to audit.

## 2.4 Data Classification Tags ([PRIVATE]/[CLASSIFIED]) ★
**What:** user tags folders/documents/memory as private/classified; the agent is hard-blocked from sending tagged content to any cloud model.
**Implementation:** a `classification` field on memory_items/documents (none|private|classified); the Model Gateway routing rule: classified → local-only, no exceptions (extends the per-data-class rule, Doc 24 §3.3). Surfaced in the UI as a tag on folders/files; spoken on relevant actions ("this is marked private — I'll keep it on your machine").

## 2.5 Offline Priority Toggle / Kill-Switch ★
**What:** one global switch → instant 100% local, all cloud disconnected (airplane mode, sensitive meeting).
**Implementation:** a gateway flag that forces local routing and disables connector egress; visible state in the top bar; voice command "go fully offline." Pairs with the existing offline-grace entitlement cache.

## 2.6 Cost & Performance Dashboard ★ (strong for BYOK)
**What:** live tokens/cost per model, latency benchmarks, and **routing recommendations** ("200 simple tasks went to GPT-4 — route them local to save $X").
**Implementation:** the budget-gate ledger (Doc 15 §3.2) already records estimated/actual cost per call; surface it as a dashboard + a weekly recommendation job that spots cheap-task-on-expensive-model patterns. Tenant-facing; a genuine BYOK selling feature.

## 2.7 Fallback & Redundancy (cloud → local) ★
**What:** cloud API fails/rate-limits → seamlessly fall back to a local model to keep working.
**Implementation:** already implied by per-task failover chains (Doc 18 FR-2.5); make the *terminal* link of every chain a local model so the assistant never fully stops. Surface the fallback in Activity ("used local model — cloud was rate-limited").

## 2.8 Auto-Profile Onboarding ★
**What:** the agent builds the user's personality/preference profile by *observing early conversations*, rather than a rigid setup form.
**Implementation:** during first sessions, the implicit-memory extractor (Doc 24 §3.1) runs more eagerly, proposing profile entries the user can confirm; SOUL.md is populated progressively. Pairs with Rehearsal Mode for a warm first-run.

---

# PART 3 — THE TWO TRAPS (adopt the SAFE version only)

## 3.1 "Self-Improvement Loop — agent fixes its own code/instructions" ⚠️
**Risk:** an agent rewriting its own code on a user's machine is a security + reliability hazard; auto-editing its own instructions causes silent, undebuggable drift.
**Safe version (build this instead):**
- The agent may **propose** improvements: new skills (auto-capture, Doc 14 G3), instruction refinements, workflow guards from failure patterns (Self-Healing SH-05).
- Every proposal is **versioned, evaluated against golden tasks, and human-approved** before taking effect (Doc 16 GAP-2 + draft/publish lifecycle, Doc 18 §4).
- **Never** self-modifies core code; never silently changes instructions. "Self-improving, but supervised" — the same governance edge that beats Hermes (Doc 14 G3).

## 3.2 "Hybrid Burst Mode — spin up cloud spot instances with user credentials" ⚠️
**Risk:** cloud-cost surprises, credential handling complexity, blast radius. Premature.
**Decision:** **Defer.** BYOK + Managed Gateway already cover heavy workloads. Revisit only with enterprise demand and proper spend caps. Adopt **BYOC** (point at the user's existing private cloud/vLLM/Bedrock/Azure) now — that's safe and valuable; burst-provisioning is the risky part to skip.

---

# PART 4 — WHERE EVERYTHING LANDS (engine vs pack vs cross-cutting)

Consistent with Doc 24's model — the new items are mostly **engine extensions** (they're horizontal, every pack benefits):

| New/changed item | Type | Touches |
|---|---|---|
| SOUL.md, NOW.md | ENGINE (Memory) | M5 — projection + working-set layers |
| Scrub & send, classification tags, offline toggle, fallback | ENGINE (Model Gateway) | M10/M32 — routing middleware |
| Cost dashboard | ENGINE (Analytics) | M19 + budget ledger |
| Auto-profile onboarding | ENGINE (Memory) + onboarding | M5 + first-run |
| Safe self-improvement | ENGINE (Eval/Skills) | eval layer + auto-skill + approval |
| BYOC | ENGINE (Gateway/Deploy) | connection layer |
| Conditional triggers | ENGINE (Scheduler) | M12 minor extension |

None of these are new *engines* — they extend the ~8 horizontal engines. Domain packs (Finance, Travel…) inherit them automatically. This keeps the maintainability guarantee from Doc 24.

---

# PART 5 — IMPLEMENTATION SPECS FOR THE NEW ITEMS

## 5.1 SOUL.md + NOW.md (Memory projection layer)
```python
# soul.py — projection of semantic+preference memory to a portable file
async def regenerate_soul(user_id):
    facts   = await memory.query(user_id, classes=["semantic","explicit"], top="identity")
    prefs   = await memory.query(user_id, classes=["explicit","implicit"], top="preferences")
    rels    = await kg.top_relationships(user_id)
    goals   = await goals.active(user_id)
    md = render_soul_md(identity=facts, prefs=prefs, relationships=rels,
                        goals=goals, values=facts.values)
    write_file(f"~/HERMUS/SOUL.md", md)        # user-owned, portable

async def load_soul_into_context(user_id):     # at session start
    return read_file("~/HERMUS/SOUL.md")        # sets tone/persona

# now.py — working-set context, injected into every agent prompt
async def update_now(user_id, *, active_tasks, recent_decisions, focus):
    write_file("~/HERMUS/NOW.md",
        render_now(focus=focus, tasks=active_tasks, decisions=recent_decisions))
```
- On edit of SOUL.md by the user → parse back into memory (confidence-flagged).
- NOW.md updated by the orchestrator on task start/finish; small enough to always include.

## 5.2 Model Gateway middleware (scrub, classify, offline, fallback)
```python
async def gateway_dispatch(ctx, prompt, task_profile):
    if OFFLINE_TOGGLE or classification_of(prompt) == "classified":
        return await run_local(prompt, task_profile)          # never cloud
    target = route(task_profile)                              # local/byok/managed
    if target.is_cloud:
        prompt, mapping = scrub_pii(prompt)                   # strip → placeholders
        try:
            resp = await call_cloud(target, prompt)
        except (RateLimit, ProviderError):
            resp = await run_local(prompt, task_profile)      # FALLBACK
            log_activity("used local model — cloud unavailable")
        return reinject_pii(resp, mapping)
    return await run_local(prompt, task_profile)
```
- `scrub_pii` redacts names/emails/phones/IDs + any classified spans; `reinject_pii` restores in the response. Every decision audited.

## 5.3 Cost dashboard + recommendations
```python
# uses budget_ledger rows (estimated/actual cost per call, model, task_profile)
GET /analytics/cost?period=  → {by_model[], by_day[], projected_month}
# weekly job:
def cost_recommendations(user_id):
    for pattern in find_cheap_tasks_on_expensive_models(user_id):
        yield f"{pattern.count} {pattern.task_type} tasks used {pattern.model}; " \
              f"routing to {pattern.local_alt} would save ~{pattern.savings}."
```

## 5.4 Safe self-improvement
```
on novel task success → draft skill (auto-capture)
on repeated failure signature → draft a guard/instruction refinement
   → run against golden tasks (eval) → if pass, present to user for approval
   → on approve: version & publish (draft/publish lifecycle) → audit
NEVER: modify core code; NEVER: silent instruction change.
```

---

# PART 6 — UPDATED BUILD SEQUENCE (folding new items into Doc 24 waves)

| Wave | Add these new items |
|---|---|
| **Wave 0 (Foundation)** | Model Gateway middleware (scrub/classify/offline/fallback), NOW.md, BYOC, cost ledger wiring. *These harden the core every pack uses.* |
| **Wave 1 (Daily packs)** | SOUL.md generation + auto-profile onboarding, cost dashboard + recommendations, conditional triggers |
| **Wave 2 (Proactive)** | (proactive engine already here) + classification-aware proactivity |
| **Wave 3+ (Depth/Moat)** | Safe self-improvement loop (after eval layer is mature), Digital Twin seeded from SOUL.md |
| **Deferred** | Hybrid Burst Mode (revisit with enterprise demand + spend caps), voice cloning, autonomous self-code-modification |

---

# PART 7 — DIRECT ANSWERS

- **How is the output?** Strong and validating — your architecture already anticipated most of it. The list's real value is ~8 new items (SOUL.md, NOW.md, scrub&send, classification tags, offline toggle, cost dashboard, fallback, auto-profile) plus sharper privacy framing.
- **Did we miss anything before?** Yes, four worth adding: **SOUL.md** (portable identity), **NOW.md** (working-set context), **scrub & send** (PII-safe cloud), and the **cost/observability dashboard**. All now specced (Part 5).
- **Two cautions:** make "self-improvement" **supervised** (propose→eval→approve, never self-modify code/instructions silently); **defer** Hybrid Burst Mode; **keep pgvector** (don't add Chroma/LanceDB).
- **Where do they go?** All are **engine extensions** (Memory, Model Gateway, Analytics, Scheduler) — not new engines — so every domain pack inherits them, preserving the maintainability model of Doc 24.

**One-line verdict:** *Adopt the eight new items as engine extensions, take only the supervised version of self-improvement, defer burst mode, keep pgvector — and this list becomes a clean enhancement layer on the architecture you already have, not a redesign.*

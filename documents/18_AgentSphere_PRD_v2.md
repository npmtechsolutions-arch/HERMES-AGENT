# PRODUCT REQUIREMENTS DOCUMENT
## AgentSphere — Multi-Agent Customer Conversation Platform (SaaS)
**Version 2.0 (full rewrite of v1.0 draft) | Status: Ready for estimation**
**Stack: React · Python FastAPI · PostgreSQL (+pgvector) · Redis**

---

# 1. PRODUCT DEFINITION & POSITIONING

## 1.1 What it is
AgentSphere is a multi-tenant cloud SaaS where businesses build a **team of specialized AI agents that talk to their customers** across web chat, WhatsApp, and Telegram — and talk to **each other** to resolve what no single bot can. A manager agent routes; specialists (billing, reservations, support, sales) collaborate; humans take over seamlessly when confidence drops.

## 1.2 What it is NOT (scope fences)
Not an internal back-office automation tool (that is the desktop AI Office Assistant product line — complementary, §1.4). Not a developer agent framework (LangChain/CrewAI). Not a voice/telephony product in v1.

## 1.3 Differentiation (the honest answer to "why not Intercom Fin / Chatbase / Botpress?")
The single-bot support market is saturated. AgentSphere wins only on the **multi-agent thesis**, so v1 must make these four things visibly true:
1. **Specialist teams outperform one mega-prompt** — measurably higher resolution rate because each agent has narrow instructions, scoped knowledge, and scoped tools.
2. **Agent collaboration is a product feature, not plumbing** — the customer sees "Reservation Agent consulted Billing Agent" in the transcript; the tenant sees the internal dialogue in debugging view.
3. **Trust is built in** — confidence-based human handoff, guardrails, and an evaluation suite are core, not enterprise add-ons.
4. **Time-to-first-agent ≤ 10 minutes** — template → knowledge upload → test in sandbox → embed snippet.

## 1.4 Relationship to the AI Office Assistant product line
Shared company assets: the universal engines concept, budget-gate design, five-layer identity chain, tamper-evident audit, eval/golden-task methodology, and (long-term) one admin plane. Distinct planes: AgentSphere agents run **in our cloud** and face **end-customers**; Office Assistant agents run **on tenant hardware** and face **the business itself**. Cross-sell path: an AgentSphere "Front Desk" hands qualified leads into the customer's Office Assistant pipeline via webhook.

---

# 2. TARGET CUSTOMERS & JOBS-TO-BE-DONE

| Segment | JTBD | First agents installed |
|---|---|---|
| SMB services (hotels, clinics-front-desk, salons) | "Answer every customer instantly on WhatsApp, 24x7, without hiring" | Front Desk, Reservations, FAQ |
| E-commerce/D2C | "Deflect order-status & returns volume; recover carts" | Support, Returns, Recommendations |
| SaaS companies | "Onboard users and answer product/billing questions from our docs" | Onboarding, Technical FAQ, Billing |
| Agencies (multiplier segment) | "Deploy and manage bots for 20 clients from one login" | All templates, white-label (v1.5) |

Primary design persona: **the operations manager, not a developer** — no-code creation is P0; the API is for the agency/dev minority.

---

# 3. PRODUCT PRINCIPLES (decision tiebreakers)

1. **Resolution rate is the product.** Every feature is judged by its effect on resolved-without-human %.
2. **Never invent facts to a customer.** Grounded answers with citations or graceful handoff — no confident hallucination, ever.
3. **The human is one tap away.** Escalation is a first-class flow, not a failure state.
4. **Tenant cost is bounded by design.** No tenant can wake up to a surprise bill (pre-dispatch budget gates).
5. **Public-facing means adversarial.** Every end-user message is treated as potentially hostile input (prompt injection, abuse, data extraction).

---

# 4. CORE CONCEPTS & DOMAIN MODEL

| Concept | Definition | Key fields |
|---|---|---|
| **Profile (tenant)** | Top-level container | id, name, tier, region, settings, budget |
| **User** | Staff with login | role: Owner / Admin / Manager / Human-Agent / Viewer |
| **Agent** | AI persona with instructions, model, tools, knowledge scope | draft/published versions, can_delegate, confidence_threshold |
| **End-User** | The customer's customer | cross-channel identity (phone/email), consent state, memory |
| **Channel** | Web widget, WhatsApp number, Telegram bot | credentials, routing rules, session rules |
| **Conversation** | Thread between end-user ↔ agents ↔ humans | status: active/escalated/closed; CSAT |
| **Internal Thread** | Agent↔agent dialogue attached to a conversation | visible in debug view & optionally in transcript |
| **Workflow** | Declarative graph: triggers, agents, conditions, approvals | versioned |
| **Knowledge Source** | Docs/sites/API feeding RAG | scope: global or per-agent; sync schedule |

**Agent lifecycle (new vs draft v1.0):** `draft → sandbox-tested → published vN → (rollback to vN-1)`. Editing never mutates the live agent; publishing is explicit. This single change prevents the most common production incident in this category (someone "just tweaking the prompt" on a live bot).

---

# 5. FUNCTIONAL REQUIREMENTS

Priorities: P0 = launch-blocking · P1 = fast-follow (≤3 months post-launch) · P2 = roadmap.

## FR-1 Tenancy & Access (P0)
- FR-1.1 Profile creation (email/password + Google OAuth); region selection at creation (EU/US/IN data residency cell — cheap now, impossible later).
- FR-1.2 Roles: Owner, Admin, Manager (agents/workflows), **Human-Agent (inbox only)**, Viewer. (Draft v1.0 omitted the Human-Agent seat — it is the most numerous role in support teams and a pricing axis, §11.)
- FR-1.3 Hard isolation: `profile_id` row-level security in PostgreSQL + JWT-claim validation at gateway; **namespace-filtered vector search enforced in a mandatory retrieval middleware** (agent code cannot query the vector store directly).
- FR-1.4 SAML SSO — P2 (Enterprise pull only; do not build speculatively).

## FR-2 Agent Builder (P0)
- FR-2.1 No-code creation: name, avatar, instructions, tone preset, model, temperature, tools, knowledge scope, confidence threshold, language(s).
- FR-2.2 **Draft/publish versioning with one-click rollback** (P0, promoted from P2 — see §4 rationale).
- FR-2.3 **Sandbox test chat on every draft** — simulated conversation panel incl. a library of adversarial test personas (angry customer, prompt-injector, off-topic rambler) before publish. (Rehearsal-mode pattern; this is also the seed of FR-12 evals.)
- FR-2.4 Clone from template/marketplace; enable/disable without deletion.
- FR-2.5 Model abstraction: tenant selects capability tier (Fast/Smart/Reasoning), platform maps to concrete models with failover chains — tenants never hard-bind to a model name (vendor churn-proofing). BYO-key: P1 (Enterprise demand exists; answers draft Open Question 4 — yes, support it, priced as a platform-fee plan since we lose token margin).

## FR-3 Knowledge Base / RAG (P0 core)
- FR-3.1 Upload PDF/DOCX/TXT/MD/CSV (P0); website crawl with depth/include-exclude (P1); REST ingestion (P1); scheduled re-sync (P1).
- FR-3.2 Scopes: global / per-agent (P0).
- FR-3.3 Chunking (512/50 default, configurable), pgvector hybrid search (BM25 + cosine) (P0 — hybrid is P0, not P1: keyword-heavy queries like order numbers fail pure-semantic search).
- FR-3.4 **Grounding contract (P0):** answers from KB carry source citations visible to the tenant (optionally to end-users); a groundedness check gates responses — if retrieval confidence is low, the agent says it doesn't know / hands off rather than improvising (Principle 2 enforced in code).
- FR-3.5 KB analytics: unanswered-question mining ("what customers asked that the KB couldn't answer") — P1, but specced now because it is the retention feature: it tells tenants exactly what content to add.

## FR-4 Multi-Agent Collaboration (P0 — the differentiator)
- FR-4.1 **Hybrid model for v1:** Manager (router) agent classifies intent → routes to specialist; specialists may call peers via a `consult_agent` tool. Broadcast P1; swarm P2.
- FR-4.2 Internal messaging: synchronous in-process call chain (NOT gRPC microservice mesh in v1 — see §8; the draft's <100ms gRPC registry is architecture astronautics at launch scale). Async task-queue consults with callback: P1.
- FR-4.3 Loop & cost containment (P0): max delegation depth 3 (draft's 10 is a cost bomb), cycle detection on the call graph, per-conversation hop budget, per-conversation token budget — all enforced **before** each model call (§FR-11).
- FR-4.4 Capability registry: agents tagged with capabilities; router resolves by tag; admin sees a routing matrix ("which intents go where") with test utterances.
- FR-4.5 **Collaboration transparency:** internal thread attached to the conversation; tenant debug view shows full agent-to-agent dialogue with tokens/cost per hop; optional end-user-visible status line ("Checking with our reservations specialist…").
- FR-4.6 Misroute recovery: specialist can return `wrong_route` → router re-classifies once → else handoff. (Routers are wrong ~10–20% early; the product must degrade gracefully, not dead-end.)

## FR-5 Channels (P0: Web + WhatsApp + Telegram)
- FR-5.1 **Web widget:** JS snippet, theming, pre-chat form, mobile-responsive, GDPR consent hook, end-user identity capture (email/phone optional), file/image upload.
- FR-5.2 **WhatsApp Business (the operationally hardest channel — specced honestly):** integrate via Cloud API as a Tech Provider or via BSP partner (decision in §15-Q1); **24-hour customer-service-window rule enforced by the platform** (outside the window only approved template messages may be sent — the platform must manage template submission/approval status, variables, and rejection feedback in-product); interactive buttons/lists; media; per-number quality-rating monitoring with proactive alerts (a banned number is an existential tenant event); message queue with retry + dead-letter.
- FR-5.3 **Telegram:** Bot API, groups, commands, media; voice notes transcribed (Whisper) — P0 cheap win.
- FR-5.4 Channel-normalized formatting layer (Markdown ↔ WhatsApp markdown ↔ HTML) (P0).
- FR-5.5 Omnichannel identity stitching by phone/email with explicit merge rules (P1).
- FR-5.6 Slack/Teams as channels: P2 (they serve internal use cases — wrong segment for v1 focus).
- FR-5.7 Ingestion architecture: all inbound → Redis Streams → async workers; ordered per conversation; idempotent on provider retries (P0).

## FR-6 Human Handoff (P0 — first-class, not add-on)
- FR-6.1 Triggers: confidence < threshold, end-user asks for human, sentiment threshold, guardrail trip, agent `handoff` tool call, N misroutes. Reason always recorded.
- FR-6.2 **Human inbox:** real-time queue (WebSocket), conversation context + AI-drafted summary + suggested reply, claim/assign (round-robin P1), internal notes, canned responses, return-to-AI with instructions ("I resolved billing; resume upsell flow").
- FR-6.3 While-waiting behavior: configurable auto-acknowledgment with expectation setting; SLA timers with escalation alerts (P0 — the draft had SLA at P1; an unanswered escalated customer is the worst failure mode the product has).
- FR-6.4 Handoff analytics: volume, reasons, wait time, resolution time per human (P1).
- FR-6.5 **No-human-online policy** (P0, missing from draft): after-hours escalations get a promised-response template + ticket creation + optional email capture — never silence.

## FR-7 Workflow Engine (P0 minimal → P1 full)
- FR-7.1 P0 ships **linear + conditional flows with a Human Approval node and execution logs** — triggers: incoming message intent, agent completion. Visual canvas: P0-simple (vertical step editor), full drag-and-drop graph: P1. (The draft's full builder in P0 is the single biggest schedule risk; a step editor delivers 80% of v1 value.)
- FR-7.2 Cron triggers + scheduled autonomous agents (daily report, KB re-sync, broadcast): P1, with execution history, failure alerts, pause/resume.
- FR-7.3 Webhook trigger + webhook action (P0 — cheap, unlocks agency integrations day one).
- FR-7.4 Versioning + rollback (P1); max depth/recursion shared with FR-4.3 limits.

## FR-8 Tools Framework (P0 core set)
- P0: HTTP request (signed, allow-listed domains per tenant), web search, calculator, datetime, `consult_agent`, `handoff_to_human`, `create_ticket`, `capture_lead` (writes structured lead + fires webhook).
- P1: send email, Slack webhook post, Google Calendar, CRM lookups (HubSpot first), read-only SQL connector.
- P1: **Custom tools via OpenAPI spec import** with per-tool auth (API key/OAuth) stored in secrets manager; every custom tool call is budget-gated and logged.
- P2: serverless function tools.
- Tool permissioning: tools are granted per-agent; tenant-level ceilings (e.g., "no agent may call HTTP to non-allow-listed domains") — agent grant ∩ tenant ceiling.

## FR-9 Safety & Guardrails (P0 — entirely missing from draft; non-negotiable for public-facing agents)
- FR-9.1 **Prompt-injection defense:** end-user content is data, never instructions — structural prompt isolation, instruction-detection classifier on inputs, and tool-call argument validation (an end-user must not be able to make an agent call `http_request` against internal endpoints or exfiltrate KB content wholesale).
- FR-9.2 Output guardrails: toxicity/PII-leak/competitor-mention/off-brand filters with tenant-configurable policies; blocked output → safe fallback + log.
- FR-9.3 Topic fences: per-agent allowed/denied topic lists ("never discuss refunds > $500 — hand off"), enforced post-generation.
- FR-9.4 Abuse handling: harassment/spam from end-users → rate-limit, cooldown scripts, block-list per channel identity.
- FR-9.5 Data minimization: PII redaction in logs/analytics (P0); end-user data deletion API for GDPR Art-17 pass-through (P0 — tenants will be asked by *their* customers).
- FR-9.6 Every guardrail event is auditable (what tripped, what was blocked, what was sent instead).

## FR-10 Memory (P0 simple → P1 rich)
- Conversation memory (Redis, 24h TTL) P0; end-user memory (preferences, history summary, cross-conversation) P0-simple; profile memory (shared facts) P1; agent self-memory P1.
- Tenant dashboard to view/edit/delete any memory entry (P1) — with end-user deletion cascading (FR-9.5).
- Agents write memory via explicit tool call only (no silent learning) — auditability.

## FR-11 Cost Control & Budget Gates (P0 — promoted from "risk mitigation" to product feature)
- Pre-dispatch reserve-then-settle ledger per tenant per month; hierarchy: tenant cap → per-agent allowance → per-conversation ceiling.
- 80% alert, 100% soft (queue + notify), hard cap → graceful degradation script ("high demand — a human will follow up") not silent failure.
- Per-conversation token/hop budgets (FR-4.3) catch loops independent of money.
- **Tenant-facing cost analytics:** per agent, per channel, per conversation drill-down; projected month-end spend. Transparency is a sales feature in this category.

## FR-12 Evaluation & Quality (P0-light → P1 — missing from draft)
- Golden-conversation suite per template (≥30 cases incl. adversarial); runs on every agent publish and platform model change; publish blocked on regression (tenant-overridable with warning).
- Production sampling: thumbs up/down (end-user) + automated groundedness scoring on sampled responses; weekly quality digest to tenant.
- The sandbox personas (FR-2.3), golden suites, and production sampling are one system with three entry points.

## FR-13 Analytics & Dashboards (P0 basic, P1 full)
- P0: conversations, resolution rate, handoff rate + reasons, response times, tokens/cost per agent, CSAT.
- P1: funnel views (lead capture), KB hit-rate & unanswered-question mining (FR-3.5), agent-collaboration stats, human-team performance, cost analyzer, conversation explorer with search.
- All analytics tenant-scoped at the query layer (no cross-tenant aggregation visible to tenants).

## FR-14 Marketplace & Templates (P1)
- Curated first-party template packs at launch *inside* the product (Hotel, E-commerce, SaaS-support, Clinic-front-desk) — P0 as static templates, marketplace mechanics (publishing, review, ratings, revenue share 20/80) P2. Templates are the 10-minute-time-to-value mechanism, not a revenue line in year one (answers draft Open Question 2).

---

# 6. NON-FUNCTIONAL REQUIREMENTS (corrected math)

| NFR | Target | Note |
|---|---|---|
| End-user response latency | **First token ≤ 3s P95 (streaming), single-agent turn complete ≤ 8s P95; multi-hop turns ≤ 15s P95 with progress indication** | The draft's "<2s P95" is unachievable with RAG + tool calls + delegation; honest targets + streaming UX beat fake ones |
| Internal agent consult | ≤ 150ms overhead per hop (excl. model time) | In-process v1, not gRPC mesh |
| KB search | < 300ms P95 | pgvector HNSW |
| Availability | 99.9% (Business), 99.5% (lower tiers) | Status page public |
| Throughput | 50 msg/s/tenant sustained, burst 200; platform 2k msg/s at launch capacity | Draft's 500/s/tenant is ~43M msgs/day/tenant — not a v1 number |
| Isolation | Zero cross-tenant leakage; RLS + middleware-enforced vector filtering; pen-test pre-launch | |
| Data residency | Region cell selected at signup (US/EU; IN fast-follow) | |
| Audit retention | 30d/90d/1y by tier; tamper-evident (hash-chained) for Business+ | |
| Backups | Daily, 30-day retention, quarterly restore drill | |
| Webhook/event delivery | At-least-once, signed (HMAC), retries + DLQ | |

---

# 7. SECURITY & COMPLIANCE

Auth: bcrypt/Argon2id, Google OAuth, JWT 1h + refresh 7d rotation, 2FA (TOTP) for Owner/Admin P0. AuthZ: RBAC at gateway, profile_id from JWT only (never from request body). Encryption: TLS 1.3, AES-256 at rest, secrets in cloud secrets manager, per-tenant encryption keys for KB content (Business+). Compliance sequencing (answers draft Q5): **SOC 2 Type I by GA + GDPR features at P0 (deletion, export, consent, DPA template); HIPAA explicitly out of scope for v1** (healthcare *front-desk scheduling* without PHI in KB is permitted with contractual carve-outs). API security: per-key rate limits, CORS allow-list, webhook signature verification both directions. Audit: immutable, hash-chained log of agent publishes, config changes, logins, guardrail events, human takeovers.

---

# 8. ARCHITECTURE SUMMARY (v1-honest)

Modular monolith (FastAPI) + workers — not microservices: `gateway/auth` · `channel adapters (web/WA/TG)` → Redis Streams → `conversation orchestrator` (router agent, delegation call-graph, budget gate, guardrails) → `model gateway` (tier mapping, failover, BYO-key later) → `RAG service` (pgvector, retrieval middleware) → `human-inbox service` (WebSocket) → `workflow runner` → `analytics pipeline` (events → warehouse). PostgreSQL (RLS, pgvector) + Redis (streams, cache, session memory) + object storage (KB files, media). The draft's gRPC agent-registry mesh becomes an internal interface that *could* be extracted at scale — designed for, not built.

---

# 9. DATA MODEL (corrected core — full DDL in companion table doc)

Draft schema gaps fixed: add `channels`, `kb_sources` + `kb_chunks` (chunks ≠ documents; embeddings live on chunks), `agent_versions` (draft/publish), `end_users` (identity stitching, consent), `escalations` (queue, claim, SLA), `internal_messages` (agent↔agent thread), `tool_invocations` (audit + cost), `budget_ledgers`/`budget_reservations`, `guardrail_events`, `eval_cases`/`eval_runs`, `subscriptions`/`usage_meters`/`invoices`, `webhook_endpoints`/`deliveries`. All tenant tables: `profile_id` + RLS policy + composite indexes on (profile_id, created_at). `VECTOR(1536)` replaced by dimension-configurable embedding column + model-version tag (embedding model WILL change; plan re-embedding jobs now).

---

# 10. PRICING (with the unit economics the draft omitted)

**Cost reality:** a resolved conversation ≈ 3–8 model turns ≈ $0.01–0.06 at current mid-tier pricing (+ WhatsApp conversation fees passed through at cost +10% handling). Tiers priced for ≥70% blended gross margin at expected usage; per-conversation overage beyond bundle (answers draft Q1: **bundled + metered overage**, overage priced ~3× marginal cost).

| | Starter $49 | Growth $199 | Business $799 | Enterprise custom |
|---|---|---|---|---|
| Agents | 3 | 15 | 50 | Custom |
| Bundled conversations/mo | 500 | 4,000 | 25,000 | Custom |
| Team seats (incl. human-agents) | 2 | 8 | 25 | Custom |
| Channels | Web + 1 | Web + WA + TG | All + API | All + BYO-key |
| Workflows | 3 simple | 20 | Unlimited | Unlimited |
| Human handoff | ✅ (basic inbox) | ✅ | ✅ + SLA tools | ✅ |
| Evals & guardrail policies | Defaults | Configurable | Custom + audit export | Custom |
| KB | 200 pages | 2,000 | 20,000 | Custom |

(Handoff moved into Starter vs draft — shipping a public-facing bot with *no* human fallback at any tier violates Principle 3 and invites brand-damage stories we can't afford.)

---

# 11. MVP RECUT (the draft's 10-P0 list is a 9-month plan labeled 6)

**Phase A — Weeks 1–10 (private alpha):** tenancy+RBAC, agent builder with draft/publish + sandbox chat, KB upload + hybrid RAG with grounding contract, **web widget only**, router→specialist delegation (depth 3) with transparency view, budget gates, guardrails v1, human inbox v1, basic analytics. *One channel. Prove resolution rate ≥ 70% on 5 design partners.*
**Phase B — Weeks 11–18 (beta):** WhatsApp (with template/window machinery) + Telegram, step-editor workflows + approval node + webhooks, escalation SLAs, cost analytics, eval suites on templates, CSAT.
**Phase C — Weeks 19–26 (GA):** template packs polished, onboarding flow (10-min target instrumented), billing/metering/overage, SOC2 Type I groundwork, status page, agency multi-profile switching.
P1 after GA: scheduled agents, async consults, OpenAPI custom tools, marketplace mechanics, omnichannel identity, BYO-key. P2: Slack/Teams, swarm, voice, mobile SDK, white-label.

# 12. SUCCESS METRICS (GA + 3 months)

Resolution-without-human ≥ **75%** (the headline; draft's 85% is unrealistic early) · handoff answered ≤ 5 min P90 · time-to-first-published-agent ≤ 10 min median · weekly active tenants 200 (500 by +6 mo) · agents/tenant ≥ 4 · agent-consult usage in ≥ 25% of multi-intent conversations (proves the thesis) · KB hit rate ≥ 60% · CSAT ≥ 4.2 · gross margin ≥ 70% · GDR ≥ 93%.

# 13. RISKS (re-ranked)

| Risk | P×I | Mitigation |
|---|---|---|
| **Prompt injection / jailbreak on public bots** | High×Critical | FR-9 stack, pen-test, bounty at GA |
| **Hallucination to end-customers** | High×High | Grounding contract, evals, handoff bias |
| **WhatsApp policy/quality bans** | Med×High | Quality monitoring, template hygiene, BSP relationship, multi-number strategy |
| Cost explosion | High×High | FR-11 gates (pre-dispatch, not post) |
| Agent loops | Med×Med | Depth 3, cycle detection, conversation budgets |
| Undifferentiated vs incumbents | Med×Critical | §1.3 thesis instrumented as metrics (consult-usage, resolution delta vs single-agent A/B) |
| Cross-tenant leakage | Low×Critical | RLS + retrieval middleware + pen-test |
| Schedule (workflow builder, WA integration) | High×High | §11 recut; step-editor first; WA in Phase B not A |

# 14. DECIDED QUESTIONS (was "Open Questions")

1. **Pricing:** bundled conversations + metered overage (§10). 2. **Marketplace revenue share:** defer to P2; templates are first-party adoption tools in year one. 3. **Self-hosting:** no — that demand routes to the Office Assistant product line (§1.4). 4. **BYO-key:** yes, P1, platform-fee priced. 5. **Compliance:** SOC2 Type I + GDPR first; HIPAA out of v1 scope explicitly.

# 15. REMAINING OPEN QUESTIONS (genuinely open)

Q1: WhatsApp via direct Cloud API Tech-Provider vs BSP partner (speed vs margin — needs a spike, 2 weeks). Q2: end-user-visible agent collaboration line — delight or noise? (A/B in alpha.) Q3: EU cell at GA or fast-follow (depends on design-partner mix). Q4: model-tier default for Starter (cost floor vs quality floor — eval-suite data will decide).

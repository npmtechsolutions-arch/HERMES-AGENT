# AI OFFICE ASSISTANT — ARCHITECTURE INFORMATION DOCUMENT
**Version 2.0 | Hybrid SaaS Architecture**
**React · Python FastAPI · PostgreSQL**

---

## 1. ARCHITECTURE OVERVIEW

A **hybrid two-plane architecture**:

- **Cloud Platform Plane** — multi-tenant SaaS control plane: identity, subscriptions, payments, entitlements, common configurations, marketplace, releases, aggregate analytics.
- **Local Execution Plane** — single-tenant runtime on the customer's machines: voice, agents, memory, workflows, tools, LLMs. All business data lives here.

```
┌──────────────────────────── CLOUD PLATFORM PLANE ────────────────────────────┐
│                                                                              │
│  React User Portal        React Admin Dashboard                              │
│        │                          │                                          │
│        ▼                          ▼                                          │
│  ┌─────────────────────── API Gateway / LB ───────────────────────┐          │
│  │                    FastAPI Service Cluster                     │          │
│  │  auth-svc  billing-svc  entitlement-svc  config-svc            │          │
│  │  tenant-svc  marketplace-svc  release-svc  analytics-svc       │          │
│  │  admin-svc  support-svc  notification-svc(email/SMS)           │          │
│  └───────┬───────────────┬───────────────┬───────────────┬────────┘          │
│          │               │               │               │                   │
│   PostgreSQL (HA)     Redis (cache,   Object Store    Celery/Arq             │
│   + read replicas     rate-limit,     (installers,    workers                │
│   + PgBouncer         sessions)       config bundles, (webhooks, dunning,    │
│                                       packages → CDN)  emails, reports)      │
│          ▲                                                                    │
│   Stripe/Razorpay webhooks ── signature verify ── idempotent processors      │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                │  HTTPS only: auth, entitlements, signed
                                │  config bundles, marketplace, releases,
                                │  heartbeats, opt-in aggregate telemetry
                                │  ✕ NEVER business data (schema-enforced)
┌───────────────────────────────▼───────────────── LOCAL EXECUTION PLANE ─────┐
│                        Customer Machine(s)                                   │
│                                                                              │
│  Electron Shell (React UI: Org Chart, Builders, Inbox, Voice Orb)            │
│        │  REST + WebSocket (loopback 127.0.0.1)                              │
│        ▼                                                                     │
│  ┌──────────────── Local Core Service (Python FastAPI) ──────────────┐       │
│  │                                                                   │       │
│  │  Voice Pipeline ── Intent Layer ── Agent Orchestration (CEO)      │       │
│  │   (wake word,       (NLU, slot     ── Agent Runtime Pool          │       │
│  │    STT, TTS,         filling,      ── Messaging Bus (pub/sub)     │       │
│  │    speaker-ID)       graph ref     ── Approval Chain Engine       │       │
│  │                      resolution)                                  │       │
│  │  Workflow Engine ── Scheduler ── Self-Healing Monitor             │       │
│  │  Second Brain (memory svc + Knowledge Graph + pgvector)           │       │
│  │  Tool Execution Framework ── Local MCP Servers ── Plugin Sandbox  │       │
│  │   (computer ctl, browser, email, docs, integrations)              │       │
│  │  GPU Resource Manager ── LLM Router                               │       │
│  │  Entitlement Agent (license cache, heartbeat, config apply)       │       │
│  │  Vault (secrets) ── Audit Logger ── RBAC                          │       │
│  └────────────┬───────────────────────┬──────────────────────────────┘       │
│               │                       │                                      │
│     Local PostgreSQL            LLM Runtimes                                 │
│     (+pgvector, encrypted)      (Ollama / llama.cpp / vLLM / LM Studio)      │
│                                                                              │
│   ◄── mTLS LAN mesh ──► other paired nodes (Multi-Computer Agent Network)    │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. CLOUD PLANE — COMPONENT DETAIL

| Service (FastAPI) | Responsibility | Key Stores |
|---|---|---|
| **auth-svc** | Signup, login, SSO, 2FA, JWT issue/refresh, device flow | `users`, `sessions`, Redis |
| **tenant-svc** | Tenants, members/seats, devices, onboarding states, suspension | `tenants`, `members`, `devices` |
| **billing-svc** | Plans, subscriptions, checkout sessions, invoices, coupons, dunning state machine, webhook processors (idempotency table) | `plans`, `subscriptions`, `invoices`, `payments`, `webhook_events` |
| **entitlement-svc** | Signs entitlement snapshots, validates heartbeats, offline licenses | `entitlements`, `licenses` (private signing keys in KMS) |
| **config-svc** | Common configuration domains, versioning, canary/publish/rollback, adoption tracking | `config_items`, `config_bundles`, `config_adoption` |
| **marketplace-svc** | Catalog, purchases, package signing pipeline, publisher management | `mp_items`, `mp_versions`, `mp_purchases` |
| **release-svc** | Installer metadata, staged rollout, crash gates, force floor | `releases`, `rollouts` |
| **admin-svc** | Admin RBAC, approval queues, four-eyes engine, impersonation consent, admin audit | `admin_users`, `admin_approvals`, `audit_admin` |
| **analytics-svc** | Aggregates (MRR, churn, activation), opt-in telemetry ingestion (content-free) | `metrics_*` (aggregated) |
| **notification-svc** | Transactional email/SMS via admin-configured providers | `notifications` |

**Cross-cutting:** API Gateway (rate limiting, JWT validation), Redis (cache/sessions/locks), Celery or Arq workers (webhooks, dunning schedules, report generation), CDN (installers, signed config bundles, marketplace packages), OpenTelemetry observability, KMS for signing keys.

**Multi-tenancy model:** single PostgreSQL cluster, shared schema with `tenant_id` on every tenant-scoped row + row-level security policies; heavy isolation (enterprise) optionally via dedicated schemas.

---

## 3. LOCAL PLANE — COMPONENT DETAIL

### 3.1 Voice Pipeline
openWakeWord (always-on, tiny) → VAD → Faster-Whisper streaming STT → Intent Layer (small local LLM + grammar; Knowledge-Graph reference resolution for "my CA", "the Mehta project") → dialog manager (slot filling, confirmation tiers VC-01..06) → TTS (Piper default; per-agent voices) with barge-in. Voice models hold a **reserved VRAM block** the GPU manager never evicts.

### 3.2 Agent Orchestration
- **CEO Agent**: plan compiler (goal → DAG), assignment solver (skills × availability × KPI), monitor/re-planner, escalation.
- **Agent Runtime Pool**: each agent = persistent profile + scoped memory handles + tool grants + assigned model; executed as async workers with checkpointable state.
- **Messaging Bus**: local pub/sub (Postgres LISTEN/NOTIFY + in-proc broker); threads keyed to tasks; everything audited and observable in UI.
- **Approval Chain Engine**: rule evaluation (AC-01..12) → tiered routing → voice prompt integration → decision trail.

### 3.3 Second Brain
Ingestion workers (OCR via Tesseract/PaddleOCR, AV transcription via Whisper, parsers per format) → chunking → embeddings (local model) → **local PostgreSQL + pgvector** → hybrid retrieval (BM25 + vector + graph expansion). **Knowledge Graph** stored relationally (`kg_entities`, `kg_relations`) with conflict markers and reference-resolution index.

### 3.4 Tooling
Every capability is a **local MCP server**: computer control, browser automation (Playwright), email, documents, each external integration. Plugin SDK runs plugins in sandboxed subprocesses (resource + permission limits); Skill Builder compiles recordings/descriptions into parameterized MCP tool definitions.

### 3.5 Compute Management
GPU Resource Manager: VRAM ledger, model registry (family/size/quant/runtime), load/unload scheduler (LRU + pins + voice reservation), router (task complexity → model tier, LC-03/04), multi-node placement when network mode active. Runtimes abstracted behind a uniform inference interface.

### 3.6 Entitlement Agent (the only cloud client)
Holds device token; performs heartbeats; caches signed entitlements (grace window); fetches/verifies config bundles and marketplace packages; enforces plan limits locally (SB-02/03); exposes none of its channel to other components for data upload (privacy invariant is also process-level: no other module gets cloud credentials).

### 3.7 Multi-Computer Agent Network
Pairing via short-lived code → mutual TLS certificates (local CA on primary node) → capability gossip (GPU, tools, peripherals) → task router places agent work and model hosting per node → checkpoint/migrate on node loss (EC-05). LAN-only; works in Offline Enterprise Mode.

---

## 4. KEY ARCHITECTURAL DECISIONS

| # | Decision | Rationale |
|---|---|---|
| AD-1 | Hybrid control-plane/execution-plane split | SaaS monetization + admin control without sacrificing the privacy pillar |
| AD-2 | FastAPI on both planes | One language/skillset; Pydantic schemas shared as contract library; the privacy invariant is testable at schema level |
| AD-3 | PostgreSQL everywhere (cloud HA cluster; embedded local + pgvector) | One mental model; pgvector removes a separate vector DB; local SQLite fallback only for very constrained machines |
| AD-4 | Signed artifacts (entitlements, configs, packages, releases) | Desktop trusts nothing unsigned; enables offline verification |
| AD-5 | Entitlements cached with grace, enforcement local | Desktop never depends on cloud availability |
| AD-6 | All tools as MCP servers | Uniform discovery for agents, plugin ecosystem, future external MCP reuse |
| AD-7 | Industry logic = data (templates), never code | Single product for all industries; admin-curated template library |
| AD-8 | Event-driven UI (WebSocket both planes) | Live org chart, approvals, rollout monitors |
| AD-9 | Append-only audit on both planes; privileged actions fail closed | Trust requirement of professional/enterprise personas |

---

## 5. DATA FLOWS (CANONICAL)

**5.1 Activation:** Desktop → `POST /auth/device/start` → user approves on web → device JWT → `GET /entitlements` (signed) → `GET /configs/current` (signed bundle) → local apply → voice onboarding proceeds offline.

**5.2 Voice task:** Mic → wake → STT stream → intent {action, slots} → graph reference resolution → CEO plan → (voice confirm) → bus dispatch → agents call MCP tools → approval gates as rules fire → artifacts to local store → TTS summary → operational memory write. *(Zero cloud involvement.)*

**5.3 Payment lifecycle:** Checkout session → gateway → webhook → signature check → idempotency check → subscription state machine → entitlement re-issue → desktop picks up at next heartbeat.

**5.4 Config push:** Admin edit → bundle vN signed → canary tenants flagged → adoption telemetry (version numbers only) → publish all → desktops verify signature → apply at safe window → "managed by provider" labels on locked items.

**5.5 Self-healing incident:** Tool failure → classify → retry/re-auth/remediation-proposal/escalate → incident stored locally → recurring signature pre-empted on future runs. *(Local only; opt-in telemetry sends error class counts, never content.)*

---

## 6. SECURITY ARCHITECTURE

- **Cloud:** TLS 1.2+, Argon2id, JWT (short access/rotating refresh), per-route rate limits, RLS in PostgreSQL, KMS-held signing keys, WAF, PCI SAQ-A (gateway-hosted card fields), admin SSO+2FA mandatory, four-eyes workflow engine, append-only `audit_admin`.
- **Local:** disk encryption of local Postgres (AES-256, key wrapped in OS keychain), Vault for integration credentials (secrets injected as references into tools), per-agent tool permission grants, speaker-ID gating, plugin sandboxing (no ambient authority), mTLS LAN mesh, hard WAN-egress kill switch in Offline Enterprise Mode (SC-08).
- **Boundary:** cloud API surface has **no schema accepting business content**; CI contract tests + egress allow-list in the desktop (only `api.aioffice.app` + gateway/CDN hosts) enforce the invariant in both directions.

---

## 7. SCALABILITY & DEPLOYMENT

| Concern | Approach |
|---|---|
| Cloud scale | Stateless FastAPI pods (K8s HPA), PgBouncer, read replicas for catalogs/analytics, Redis cache, CDN offload for all large artifacts |
| Hot paths | Entitlement reads cached (Redis, 5 min); config bundles immutable + CDN; webhook bursts absorbed by queue workers |
| Local scale | Multi-node network distributes models/agents; GPU manager prevents thrash; per-machine concurrency tuned to hardware tier |
| Environments | dev → staging → prod; canary tenants for config & release rollouts; feature flags per plan and per tenant |
| Observability | Cloud: OpenTelemetry traces/metrics/logs + alerting on webhook lag, dunning queue, rollout crash gates. Local: structured logs + local diagnostics screen; opt-in crash signatures only |
| DR | PostgreSQL WAL archiving (RPO ≤ 5 min), cross-zone replicas, monthly restore drills; signed-artifact store replicated |

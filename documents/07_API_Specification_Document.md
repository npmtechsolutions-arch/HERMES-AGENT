# AI OFFICE ASSISTANT — API SPECIFICATION DOCUMENT
**Version 1.0 | Internal Local API (Core Service ↔ UI / Plugins / Nodes)**

---

## 1. SCOPE & ARCHITECTURE OF THE API

AI Office Assistant runs a **local Core Service** (background daemon) exposing APIs consumed by:

1. The Electron UI (renderer)
2. The Voice Pipeline
3. Plugins (via Plugin SDK, permission-scoped)
4. Peer nodes (Multi-Computer Agent Network)
5. Local MCP servers (tool layer)

**Transport:**
- REST over `http://127.0.0.1:7700/api/v1` (loopback only; LAN binding only in network mode with mTLS)
- WebSocket `ws://127.0.0.1:7700/ws/v1` for events/streams (voice, agent status, bus messages)
- MCP (stdio / SSE) for tool servers

**Conventions:**
- JSON request/response; `snake_case` fields
- IDs: ULIDs (`agt_…`, `tsk_…`, `wfl_…`, `apv_…`, `mem_…`, `msg_…`, `cal_…`, `nod_…`, `skl_…`)
- Timestamps: ISO-8601 with zone
- Pagination: `?limit=&cursor=` → `{ "data": [...], "next_cursor": "..." }`
- Errors:
```json
{ "error": { "code": "AGENT_BUSY", "message": "Agent is mid-task", "details": {...}, "retryable": true } }
```

**Authentication:**
- UI/local: session token from unlock (`POST /auth/unlock`), sent as `Authorization: Bearer <token>`
- Plugins: scoped plugin tokens (permission claims embedded)
- Nodes: mutual TLS client certificates
- Voice-print assertion attached as `X-Speaker-Id` claim when speaker identified

**Common headers:** `X-Request-Id`, `X-Actor` (`user:<id>` | `agent:<id>` | `plugin:<id>` | `node:<id>`) — every mutating call requires an actor for audit.

---

## 2. RESOURCE GROUPS (ENDPOINT INDEX)

| Group | Base Path | Purpose |
|---|---|---|
| Auth & Session | `/auth` | unlock, lock, speaker enrollment |
| Organization | `/departments`, `/agents` | org model CRUD |
| Tasks | `/tasks` | task lifecycle |
| Workflows | `/workflows` | definitions, runs, compile-from-voice |
| Schedules | `/schedules` | CRON/event registrations |
| Approvals | `/approvals` | chains, decisions, delegations |
| Memory (Second Brain) | `/memory` | items, search, ingestion |
| Knowledge Graph | `/graph` | entities, relations, queries |
| Messaging Bus | `/bus` | agent threads & messages |
| Communication Hub | `/comms` | channels, threads, send |
| Call Center | `/calls` | inbound/outbound, transcripts |
| Voice | `/voice` (+WS) | STT/TTS sessions, intents |
| Models & Compute | `/models`, `/gpu` | LLM lifecycle, allocation |
| Skills & Plugins | `/skills`, `/plugins` | Skill Builder, SDK |
| Marketplace | `/marketplace` | browse, install |
| Network | `/nodes` | multi-computer management |
| Integrations | `/integrations`, `/mcp` | connectors, MCP servers |
| Security | `/vault`, `/audit`, `/rbac` | secrets, logs, roles |
| Analytics | `/analytics` | metrics, performance |
| Documents | `/documents` | generation jobs |

---

## 3. KEY ENDPOINT SPECIFICATIONS

### 3.1 Auth

| Method & Path | Description |
|---|---|
| `POST /auth/unlock` | Body: `{method: "passphrase"|"os_auth"|"voiceprint", credential}` → `{token, expires_at, user}` |
| `POST /auth/lock` | Invalidate session |
| `POST /auth/voiceprint/enroll` | Multipart audio samples → `{speaker_id, quality_score}` |

### 3.2 Agents

| Method & Path | Description |
|---|---|
| `GET /agents?department_id=&status=` | List agents |
| `POST /agents` | Create agent (see schema below) |
| `GET /agents/{id}` | Full profile |
| `PATCH /agents/{id}` | Partial update (any profile field) |
| `DELETE /agents/{id}` | Soft-delete (requires approval if agent has active tasks) |
| `POST /agents/{id}/pause` / `/resume` | State control |
| `GET /agents/{id}/performance?period=` | KPI metrics |
| `POST /agents/{id}/train` | Body: `{memory_item_ids[], quiz: bool}` → training job |
| `GET /agents/{id}/tasks` | Agent's task queue |

**Agent create schema:**
```json
{
  "name": "Maya",
  "designation": "Social Media Manager",
  "department_id": "dep_01H...",
  "description": "...",
  "objectives": ["..."],
  "skill_ids": ["skl_..."],
  "tool_grants": ["browser.automation", "comms.whatsapp.send"],
  "memory_scopes": ["business", "knowledge:marketing"],
  "model_id": "mdl_qwen14b_q4",
  "permissions": {"spend_limit": 5000, "external_send": "approval_required"},
  "kpis": [{"metric": "tasks_completed", "target": 40, "period": "month"}],
  "schedule": {"active_hours": "09:00-21:00", "timezone": "Asia/Kolkata"},
  "reporting_manager_id": "agt_..."
}
```

### 3.3 Tasks

| Method & Path | Description |
|---|---|
| `POST /tasks` | `{title, description, source: "voice"|"manual"|"workflow"|"trigger", priority, deadline, assignee_agent_id?, parent_task_id?, dependencies[]}` |
| `POST /tasks/plan` | `{utterance | description}` → CEO Agent plan: `{subtasks[], assignments[], estimate_minutes, requires_approval}` (does not execute) |
| `POST /tasks/{id}/execute` | Start approved plan |
| `GET /tasks/{id}` | Detail incl. state, artifacts, bus thread ref, approval refs |
| `PATCH /tasks/{id}` | Update priority/deadline/assignee |
| `POST /tasks/{id}/cancel` | Graceful cancel (TC-11 semantics) |
| `GET /tasks?status=&agent_id=&due_before=` | Board queries |
| `WS event: task.status_changed` | `{task_id, old, new, agent_id, ts}` |

### 3.4 Workflows & Schedules

| Method & Path | Description |
|---|---|
| `POST /workflows/compile` | **Voice-to-Workflow:** `{utterance}` → `{graph, warnings[], unmapped_steps[]}` |
| `POST /workflows` | Save graph `{name, graph, status: "draft"}` |
| `POST /workflows/{id}/dry_run` | Sandbox execution → step-by-step results |
| `POST /workflows/{id}/activate` / `/deactivate` | Lifecycle |
| `GET /workflows/{id}/runs?status=` | Run history |
| `POST /schedules` | `{workflow_id, type: "cron"|"interval"|"event", expression, run_policy: "run_on_wake"|"skip"}` |

**Workflow graph node types:** `trigger`, `condition`, `action`, `agent_task`, `approval`, `notification` — each `{node_id, type, config, next[], on_fail?}`.

### 3.5 Approvals

| Method & Path | Description |
|---|---|
| `GET /approvals?state=pending&tier=human` | Inbox |
| `GET /approvals/{id}` | Full chain: request, rationale, tier history |
| `POST /approvals/{id}/decide` | `{decision: "approve"|"reject", reason?, actor}` — enforces AC-09 segregation |
| `POST /approvals/delegations` | Temp delegation (AC-10): `{from_actor, to_actor, scope, expires_at}` |
| `WS event: approval.requested` | Pushed to eligible approvers (drives voice prompt) |

### 3.6 Memory & Knowledge Graph

| Method & Path | Description |
|---|---|
| `POST /memory/ingest` | Multipart files or `{url}` / `{source: "email", ref}` → ingestion job `{job_id}` |
| `GET /memory/ingest/{job_id}` | Status: ocr/transcribe/chunk/embed/graph-link stages |
| `POST /memory/search` | `{query, scopes[], top_k, hybrid: true}` → chunks + source refs + graph context |
| `GET /memory/items/{id}` / `PATCH` / `DELETE` | CRUD; delete = soft (MC-04) |
| `POST /graph/query` | `{entity?, relation?, depth, cypher_like?}` → subgraph |
| `POST /graph/entities` / `/relations` | Manual curation |
| `GET /graph/conflicts` | MC-02 conflict list |
| `POST /graph/resolve_reference` | `{mention: "my CA", context}` → ranked entity candidates (used by intent layer) |

### 3.7 Messaging Bus

| Method & Path | Description |
|---|---|
| `POST /bus/threads` | `{task_id?, participants[], topic}` |
| `POST /bus/threads/{id}/messages` | `{from_agent_id, content, kind: "query"|"handoff"|"result"|"status"}` |
| `GET /bus/threads?task_id=` | Observability ("what are agents discussing") |
| `WS topic: bus.message` | Live stream, RBAC-filtered |

### 3.8 Communication Hub & Call Center

| Method & Path | Description |
|---|---|
| `GET /comms/channels` | Connected channels + health |
| `GET /comms/threads?category=urgent` | Triaged inbox |
| `POST /comms/threads/{id}/draft` | `{intent: "reply", instructions, tone}` → draft (not sent) |
| `POST /comms/threads/{id}/send` | `{draft_id}` — runs CC-03/CC-04/AC-05 gates |
| `POST /comms/rules` | Auto-handling rule sets |
| `POST /calls/outbound` | `{campaign_id? , contact_id, script_id, window_policy}` — enforces CC-07/08 |
| `GET /calls/{id}` | Transcript, sentiment timeline, outcome code |
| `POST /calls/{id}/transfer` | Warm transfer to human `{summary_tts: true}` |
| `WS topic: call.live` | Real-time transcript stream |

### 3.9 Voice Pipeline (WebSocket-centric)

| Channel / Endpoint | Description |
|---|---|
| `WS /ws/v1/voice/session` | Bidirectional: client sends PCM frames; server streams `{partial_transcript}`, `{final_transcript, confidence}`, `{intent, slots, confidence}`, `{tts_audio_chunk}` |
| `POST /voice/intents/parse` | Text → intent (for testing/palette) |
| `POST /voice/tts` | `{text, voice_id, speed}` → audio (non-streaming utility) |
| `GET /voice/config` / `PATCH` | Wake word, locales, DND windows, verbosity |
| Events | `voice.state_changed` (sleeping/listening/thinking/speaking/acting/confirming/error) |

### 3.10 Models & GPU

| Method & Path | Description |
|---|---|
| `GET /models` | Installed models: family, size, quant, runtime, status |
| `POST /models/pull` | `{family, size, quant, runtime}` → download job (LC-07 resumable) |
| `POST /models/{id}/load` / `/unload` | Explicit lifecycle |
| `POST /models/route` | `{task_profile}` → chosen model (LC-03/04 logic) |
| `GET /gpu/status` | Per-GPU/per-node VRAM, loaded models, reservations |
| `POST /gpu/policy` | Pin/evict rules; voice reservation size |

### 3.11 Skills, Plugins, Marketplace

| Method & Path | Description |
|---|---|
| `POST /skills/record/start` / `/stop` | Demonstration capture session |
| `POST /skills/generate` | `{recording_id | description}` → draft skill (steps + params) |
| `POST /skills/{id}/test` | Sandbox run with sample inputs |
| `POST /skills/{id}/publish` | `{agent_ids[]}` |
| `POST /plugins/install` | Signed package; permission manifest returned for consent (SC-03/04) |
| `GET /marketplace/search?type=agent|skill|workflow|integration|template` | Catalog |
| `POST /marketplace/install/{item_id}` | Install with permission review |
| `POST /templates/{id}/apply` | Industry template → org bootstrap plan → confirm → create |

### 3.12 Network (Multi-Computer)

| Method & Path | Description |
|---|---|
| `POST /nodes/pairing/start` | → `{pairing_code, expires_in}` (admin only, SC-10) |
| `POST /nodes/pairing/complete` | From joining node: `{code, node_info}` → mTLS cert exchange |
| `GET /nodes` | Fleet: capabilities, health, hosted agents/models |
| `POST /nodes/{id}/evacuate` | Move agents/models off node |
| Internal node RPC | Task dispatch, inference proxy, memory sync — mTLS, same schemas |

### 3.13 Security & Audit

| Method & Path | Description |
|---|---|
| `POST /vault/secrets` / `GET /vault/secrets/{key}/meta` | Values never returned in full after write; tools receive injected refs |
| `GET /audit?actor=&action=&from=&to=` | Query log (append-only store) |
| `GET /rbac/roles` / `POST /rbac/assignments` | Enterprise role management |

### 3.14 Analytics & Documents

| Method & Path | Description |
|---|---|
| `GET /analytics/summary?period=` | Tasks automated, hours saved, response times, KPIs |
| `POST /analytics/query` | `{question}` → structured answer + chart spec (powers voice analytics) |
| `POST /documents/generate` | `{type: "report"|"contract"|"proposal"|"invoice"|"audit", format: "pdf"|"docx"|"xlsx"|"pptx", template_id?, data|instructions}` → job |
| `GET /documents/{id}` | Metadata + file path |

---

## 4. WEBSOCKET EVENT CATALOG

| Topic | Payload (abridged) | Consumers |
|---|---|---|
| `agent.status` | `{agent_id, status, task_id?}` | Org chart, ticker |
| `task.status_changed` | `{task_id, old, new}` | Task board |
| `approval.requested` / `.decided` | chain snapshot | Approvals, voice prompt |
| `bus.message` | thread message | Bus viewer |
| `voice.state_changed` | state enum | Voice orb |
| `comms.message_received` | `{channel, category, thread_id}` | Inbox, voice alert |
| `call.live` | transcript deltas | Call console |
| `workflow.run_update` | `{run_id, node_id, status}` | Builder/run history |
| `healing.incident` | `{class, action_taken, needs_approval?}` | Notifications |
| `gpu.pressure` | `{node, vram_pct}` | GPU manager |
| `node.health` | heartbeat | Network console |

---

## 5. ERROR CODES (CANONICAL)

| Code | HTTP | Meaning |
|---|---|---|
| `UNAUTHENTICATED` / `FORBIDDEN` | 401/403 | Session/RBAC/permission failure |
| `SPEAKER_UNVERIFIED` | 403 | Privileged voice command without voice-print (SC-02) |
| `AGENT_BUSY` | 409 | TC-05 interrupt-or-queue required |
| `APPROVAL_REQUIRED` | 409 | Action gated; response includes `approval_id` |
| `MODEL_UNAVAILABLE` | 503 | Load failed / VRAM (includes suggested alternative) |
| `INTEGRATION_DISCONNECTED` | 424 | Connector needs re-auth (SH-02 path) |
| `VALIDATION_ERROR` | 422 | Schema issues, field-level details |
| `CONFLICT` | 409 | Versioning / duplicate |
| `RATE_LIMITED` | 429 | Channel/tool throttle (CC-10) |
| `OFFLINE_QUEUED` | 202 | Accepted, queued for connectivity |

---

## 6. VERSIONING & COMPATIBILITY

- Path-versioned (`/api/v1`); additive changes only within a version.
- Plugins declare `min_api_version`; Core refuses incompatible plugins at load.
- Node protocol version negotiated at pairing; mismatched nodes prompted to update (EC handling).

---

# PART B — CLOUD SAAS API (Python FastAPI + PostgreSQL)

The platform adds a **Cloud API** (`https://api.aioffice.app/v1`), built with **FastAPI**, backed by **PostgreSQL**. The local API (Part A) remains the desktop's internal plane. The two planes communicate only through the endpoints in §B6 (license/config/marketplace) — never business data (rule DB-01).

**Conventions:** OAuth2/JWT (access+refresh), Pydantic-validated schemas, idempotency keys on all billing mutations, RFC7807 error bodies, OpenAPI auto-docs at `/docs`.

## B1. Auth & Accounts
| Endpoint | Description |
|---|---|
| `POST /auth/signup` | email, password → verification mail |
| `POST /auth/login` / `POST /auth/refresh` / `POST /auth/logout` | JWT session |
| `POST /auth/sso/google` | OAuth code exchange |
| `POST /auth/2fa/enroll` / `/verify` | TOTP |
| `POST /auth/device/start` | Desktop device flow → `{device_code, user_code, verification_uri}` |
| `POST /auth/device/token` | Poll → device JWT on approval |
| `GET/PATCH /accounts/me` | Profile, preferences |
| `POST /accounts/me/delete` | GDPR-style deletion (30-day purge, DB-03) |

## B2. Tenants, Teams, Devices
| Endpoint | Description |
|---|---|
| `GET /tenants/me` | Tenant profile, status (active/suspended/grace/locked) |
| `POST /tenants/me/members/invite` | `{email, role, seat}` |
| `GET /tenants/me/members` / `PATCH /members/{id}` / `DELETE` | Seat management (SB-07) |
| `GET /devices` | Activated devices (name, os, fingerprint, last_seen) |
| `DELETE /devices/{id}` | Deactivate (frees device slot, SB-06) |

## B3. Plans, Subscriptions, Billing
| Endpoint | Description |
|---|---|
| `GET /plans` | Public plan catalog (features, limits, prices) |
| `POST /subscriptions/checkout` | `{plan_id, coupon?}` → gateway checkout session (Stripe/Razorpay) |
| `GET /subscriptions/me` | Status, period, plan, proration preview |
| `POST /subscriptions/me/change` | Upgrade/downgrade (SB-03/04) |
| `POST /subscriptions/me/cancel` | End-of-period cancel |
| `GET /invoices` / `GET /invoices/{id}/pdf` | Billing history |
| `POST /webhooks/stripe` `POST /webhooks/razorpay` | Signature-verified (PB-06), idempotent (PB-07); drives dunning state machine |

## B4. Entitlements & Licensing (Desktop ↔ Cloud)
| Endpoint | Description |
|---|---|
| `GET /entitlements` | Signed snapshot: `{plan, limits:{agents,workflows,seats,devices,channels,call_minutes}, feature_flags{}, config_version, expires_at}` — desktop caches with grace |
| `POST /entitlements/heartbeat` | Device check-in: `{device_id, app_version, config_version}` → deltas |
| `POST /licenses/offline` | Enterprise: generate signed offline license file (admin-approved, UC-S17) |

## B5. Common Configurations & Releases
| Endpoint | Description |
|---|---|
| `GET /configs/current?since_version=` | Signed config bundle: model catalog, connector catalog, template library, locale packs, compliance presets, default thresholds; items flagged `locked|overridable|suggestion` |
| `GET /releases/latest?platform=win|mac|linux&channel=` | Installer metadata, signatures, force-update floor |
| `GET /marketplace/catalog` / `POST /marketplace/purchase/{item}` / `GET /marketplace/download/{item}` | Signed packages to desktop |
| `POST /support/tickets` / `GET /support/tickets` | Support |

## B6. Product Admin API (`/admin/*` — admin JWT + role scopes; four-eyes on destructive)
| Endpoint | Description |
|---|---|
| `GET /admin/tenants?status=&search=` / `GET /admin/tenants/{id}` | Tenant ops |
| `POST /admin/tenants/{id}/approve|reject|suspend|reactivate` | Onboarding & lifecycle (UC-S09/S15) |
| `POST /admin/tenants/{id}/impersonate` | Consent-token required (PA-02) |
| `POST /admin/plans` / `PATCH /admin/plans/{id}` | Plans & feature flags (UC-S10) |
| `POST /admin/coupons` | Promotions |
| `GET/PUT /admin/gateways/{provider}` | Keys, webhook endpoints, test mode |
| `POST /admin/refunds` → `POST /admin/refunds/{id}/approve` | Four-eyes refunds (PB-03) |
| `PUT /admin/configs/{domain}` | Edit config item (models/connectors/templates/locales/compliance/thresholds) |
| `POST /admin/configs/publish` | `{scope: canary|all, version}`; `POST /admin/configs/rollback` |
| `GET /admin/configs/adoption` | Fleet version spread (A12) |
| `POST /admin/marketplace/review/{pkg}` | Approve/sign/reject (PA-06) |
| `POST /admin/releases` / `PATCH /admin/releases/{id}/rollout` | Staged rollout, crash gate (PA-05) |
| `GET /admin/analytics/{mrr|churn|activation|adoption}` | Aggregates only |
| `GET /admin/audit?actor=&action=` | Admin audit log |

## B7. Error & Status Additions
| Code | HTTP | Meaning |
|---|---|---|
| `PLAN_LIMIT_EXCEEDED` | 402 | Includes `limit`, `current`, `upgrade_url` (SB-02) |
| `SUBSCRIPTION_INACTIVE` | 402 | Grace/soft-lock states distinguished in body |
| `DEVICE_LIMIT` | 409 | Device list returned |
| `CONSENT_REQUIRED` | 403 | Impersonation without consent token |
| `FOUR_EYES_REQUIRED` | 409 | Second admin approval pending |
| `CONFIG_SIGNATURE_INVALID` | 409 | Desktop rejects tampered bundle |

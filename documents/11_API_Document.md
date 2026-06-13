# AI OFFICE ASSISTANT — API DOCUMENT (DEVELOPER REFERENCE)
**Version 2.0 | FastAPI · OpenAPI 3.1 · PostgreSQL**

This is the working developer reference with request/response examples. The companion **API Specification Document** defines the full endpoint inventory; this document shows how to call the most important APIs correctly.

---

## 1. ENVIRONMENTS & BASE URLS

| Plane | Base URL | Auth |
|---|---|---|
| Cloud API (prod) | `https://api.aioffice.app/v1` | OAuth2 Bearer JWT |
| Cloud API (sandbox) | `https://sandbox.api.aioffice.app/v1` | Test-mode keys/webhooks |
| Local Core API | `http://127.0.0.1:7700/api/v1` | Local session Bearer |
| Local Events | `ws://127.0.0.1:7700/ws/v1` | Same token |
| Admin API | `https://api.aioffice.app/v1/admin` | Admin JWT (SSO+2FA) + role scopes |

Interactive docs: `/docs` (Swagger UI) and `/redoc` on every FastAPI service.

**Standard headers**
```
Authorization: Bearer <jwt>
Content-Type: application/json
X-Request-Id: <uuid>            # echoed back; use for support
Idempotency-Key: <uuid>         # REQUIRED on POST billing mutations
X-Actor: user:usr_01H...        # local API: who/what is acting (audit)
```

**Error format (RFC 7807)**
```json
{
  "type": "https://docs.aioffice.app/errors/PLAN_LIMIT_EXCEEDED",
  "title": "Plan limit exceeded",
  "status": 402,
  "code": "PLAN_LIMIT_EXCEEDED",
  "detail": "Starter allows 5 agents; you have 5.",
  "meta": { "limit": 5, "current": 5, "upgrade_url": "https://app.aioffice.app/billing?plan=pro" }
}
```

---

## 2. AUTH — CLOUD

### 2.1 Signup & Login
```http
POST /v1/auth/signup
{ "email": "mehul@caoffice.in", "password": "S3cure!pass", "full_name": "Mehul Shah" }
→ 201 { "user_id": "usr_01HZX...", "verification": "email_sent" }

POST /v1/auth/login
{ "email": "mehul@caoffice.in", "password": "S3cure!pass", "otp": "482913" }
→ 200 { "access_token": "eyJ...", "refresh_token": "eyJ...", "expires_in": 900,
        "tenant": { "id": "tnt_01HZX...", "status": "active", "plan": "pro" } }
```

### 2.2 Desktop Device Flow (activation)
```http
POST /v1/auth/device/start        # called by desktop app
{ "device_name": "Mehul-Workstation", "os": "windows", "fingerprint": "fp_9f2c..." }
→ 200 { "device_code": "dvc_...", "user_code": "HKQT-PWNV",
        "verification_uri": "https://app.aioffice.app/activate", "interval": 5 }

POST /v1/auth/device/token        # desktop polls
{ "device_code": "dvc_..." }
→ 428 { "code": "AUTHORIZATION_PENDING" }      # until user approves on web
→ 200 { "device_token": "eyJ...", "device_id": "dev_01HZX..." }
→ 409 { "code": "DEVICE_LIMIT", "meta": { "devices": [ ... ] } }
```

---

## 3. ENTITLEMENTS & CONFIG — CLOUD↔DESKTOP

### 3.1 Fetch entitlements (signed)
```http
GET /v1/entitlements
Authorization: Bearer <device_token>
→ 200
{
  "snapshot": {
    "tenant_id": "tnt_01HZX...", "plan": "pro",
    "limits": { "agents": 25, "workflows": 100, "seats": 5, "devices": 3,
                "channels": ["email","whatsapp","slack","telegram","teams","sms"],
                "call_minutes_month": 0 },
    "feature_flags": { "call_center": false, "multi_node": false, "offline_mode": false },
    "config_version": 119,
    "issued_at": "2026-06-04T07:00:00+05:30",
    "grace_until": "2026-06-11T07:00:00+05:30"
  },
  "signature": "MEUCIQ...",         // Ed25519; desktop verifies with pinned public key
  "key_id": "ent-key-2026a"
}
```

### 3.2 Heartbeat
```http
POST /v1/entitlements/heartbeat
{ "device_id": "dev_01HZX...", "app_version": "2.4.1", "config_version": 118 }
→ 200 { "entitlements_changed": false, "config_update_available": true,
        "latest_config_version": 119, "force_update_floor": "2.3.0" }
```

### 3.3 Config bundle
```http
GET /v1/configs/current?since_version=118
→ 200 { "version": 119, "bundle_url": "https://cdn.aioffice.app/configs/119.tar.zst",
        "sha256": "ab39...", "signature": "MEQCIA...",
        "changed_domains": ["model_catalog","connector_catalog"] }
```
Desktop: download → verify sha+signature → apply per-item scope (`locked|overridable|suggestion`).

---

## 4. BILLING — CLOUD

### 4.1 Checkout
```http
POST /v1/subscriptions/checkout
Idempotency-Key: 0d9f...
{ "plan_id": "pln_pro_monthly_inr", "coupon": "LAUNCH20", "gateway": "razorpay" }
→ 200 { "checkout_url": "https://rzp.io/i/abc123", "session_id": "cs_..." }
```

### 4.2 Webhook (gateway → platform)
```http
POST /v1/webhooks/razorpay
X-Razorpay-Signature: <hmac>
{ "event": "payment.failed", "payload": { "subscription_id": "sub_R7...", ... } }
```
Processing rules: verify signature → check `webhook_events` idempotency table → apply to subscription state machine → enqueue dunning job → 200. Replays return 200 with `{"duplicate": true}` and no side effects.

### 4.3 Plan change with proration preview
```http
POST /v1/subscriptions/me/change
{ "plan_id": "pln_pro_monthly_inr", "preview": true }
→ 200 { "prorated_charge": 1240.00, "currency": "INR", "effective": "immediate",
        "downgrade_effects": null }
```
`preview:false` executes (Idempotency-Key required). Downgrades return `downgrade_effects` listing resources to archive — desktop prompts the user to choose which.

---

## 5. ADMIN API — CLOUD

All admin routes require role scopes (`admin:tenants`, `admin:billing`, `admin:configs`, `admin:releases`, `admin:super`). Destructive operations return `FOUR_EYES_REQUIRED` until co-approved.

### 5.1 Approve a tenant
```http
POST /v1/admin/tenants/tnt_01HZX.../approve
{ "note": "KYC verified", "welcome_email": true }
→ 200 { "status": "active" }
```

### 5.2 Edit a plan (no deploy)
```http
PATCH /v1/admin/plans/pln_pro_monthly_inr
{ "limits": { "agents": 30 }, "apply": "next_renewal" }
→ 200 { "affected_subscriptions": 1204, "version": 7 }
```

### 5.3 Publish a config bundle (canary → all)
```http
POST /v1/admin/configs/publish
{ "version": 119, "scope": "canary", "canary_percent": 2 }
→ 202 { "rollout_id": "rlt_...", "monitor_url": ".../admin/configs/adoption" }

POST /v1/admin/configs/publish   { "version": 119, "scope": "all" }
POST /v1/admin/configs/rollback  { "to_version": 118 }   # one click, instant
```

### 5.4 Refund with four-eyes
```http
POST /v1/admin/refunds
{ "invoice_id": "inv_...", "amount": 2999.00, "reason": "duplicate charge" }
→ 202 { "refund_id": "rfd_...", "state": "pending_second_approval" }

POST /v1/admin/refunds/rfd_.../approve      # different admin
→ 200 { "state": "executed", "gateway_ref": "rfnd_R8..." }
```

### 5.5 Release rollout
```http
POST /v1/admin/releases
{ "version": "2.5.0", "platforms": {...installer URLs+sha...}, "notes_md": "..." }
PATCH /v1/admin/releases/rel_.../rollout
{ "percent": 25, "crash_gate_pct": 1.0, "force_floor": "2.3.0" }
```

---

## 6. LOCAL CORE API — KEY CALLS (DESKTOP PLANE)

### 6.1 Plan a task from a voice utterance
```http
POST /api/v1/tasks/plan
X-Actor: user:usr_01HZX
{ "utterance": "Prepare the monthly GST report and email it to my CA by Friday" }
→ 200
{
  "plan_id": "pln_lcl_01...",
  "resolved_entities": { "my CA": { "entity_id": "ent_ca_sharma", "confidence": 0.93 } },
  "subtasks": [
    { "title": "Compile transactions", "agent_id": "agt_accountant", "tools": ["mcp.tally"] },
    { "title": "Prepare GSTR summary", "agent_id": "agt_gst" },
    { "title": "Verification pass", "agent_id": "agt_auditor", "gate": "variance_check" },
    { "title": "Email to CA Sharma", "tool": "mcp.email", "approval_rule": "AC-05?:no (whitelisted)" }
  ],
  "estimate_minutes": 20, "deadline": "2026-06-06T18:00:00+05:30",
  "requires_confirmation": true
}

POST /api/v1/tasks/pln_lcl_01.../execute   → 202 { "task_id": "tsk_..." }
```

### 6.2 Subscribe to live events
```js
const ws = new WebSocket("ws://127.0.0.1:7700/ws/v1?token=...");
ws.send(JSON.stringify({ subscribe: ["task.status_changed","approval.requested","voice.state_changed"] }));
// ← {"topic":"approval.requested","data":{"approval_id":"apv_...","summary":"Auditor found ₹12,400 mismatch","tier":"human"}}
```

### 6.3 Decide an approval (voice layer calls this on "approve")
```http
POST /api/v1/approvals/apv_.../decide
X-Actor: user:usr_01HZX   X-Speaker-Id: spk_mehul
{ "decision": "approve", "reason": "verified manually" }
→ 200 { "state": "approved", "chain": ["agt_auditor","agt_ceo","usr_01HZX"] }
```

### 6.4 Search the Second Brain
```http
POST /api/v1/memory/search
{ "query": "what did we quote Mehta last year", "scopes": ["business"], "top_k": 5 }
→ 200 { "results": [ { "chunk": "...quotation Q-2025-114 ₹4.2L...", "source": {"doc_id":"mem_...","page":2},
        "graph_context": ["Mehta & Sons → Project Riverside → Quotation Q-2025-114"] } ] }
```

### 6.5 Voice session (WebSocket)
```
WS /ws/v1/voice/session
→ client streams 16kHz PCM frames
← {"type":"partial","text":"prepare the monthly gst"}
← {"type":"final","text":"prepare the monthly gst report...","confidence":0.91}
← {"type":"intent","name":"task.create","slots":{...},"confidence":0.88}
← {"type":"tts_chunk","audio_b64":"...","seq":1}        # plan readback
→ {"type":"barge_in"}                                    # client detected user speech
```

---

## 7. RATE LIMITS, PAGINATION, IDEMPOTENCY

| Surface | Limit |
|---|---|
| Cloud authenticated | 120 req/min/user (burst 240); webhooks unmetered |
| Admin API | 300 req/min/admin |
| Local API | unmetered (loopback); tool-level throttles apply (CC-10) |

- Pagination: `?limit=50&cursor=` → `next_cursor`; max limit 200.
- Idempotency: required on `POST /subscriptions/*`, `/admin/refunds`, `/marketplace/purchase`; keys stored 48h.
- Retry guidance: respect `Retry-After`; webhook consumers must be idempotent.

## 8. VERSIONING & DEPRECATION

`/v1` is stable; additive changes only. Deprecations announced ≥90 days via `Sunset` header + changelog. Desktop ↔ cloud compatibility guaranteed across one major desktop version (force-update floor governs the rest). Pydantic schema package `aioffice-contracts` published for plugin/internal reuse — the privacy invariant lives here: cloud schemas contain no business-content fields, enforced by contract tests in CI.

## 9. SANDBOX & TESTING

- Sandbox cloud env with gateway test modes (Stripe test cards, Razorpay test keys) and webhook replay tool.
- Local API ships with `--demo` seed (sample org, tasks, memory) for UI/plugin development.
- `POST /v1/admin/configs/publish {scope:"canary"}` against sandbox fleet simulator for config testing.

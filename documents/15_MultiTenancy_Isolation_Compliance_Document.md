# AI OFFICE ASSISTANT — MULTI-TENANCY, ISOLATION & COMPLIANCE ARCHITECTURE
**Version 1.0 | Elaboration of the Multi-Tenant Agent Platform Gap Analysis**
**Companion to: Architecture (09), SRS (08), Table Design (12), Gap Analysis (14)**

---

## 0. EXECUTIVE SUMMARY

The industry's hardest multi-tenant agent problems — cross-tenant data bleed, runaway costs, identity misattribution, compliance theater, shadow agents — are mostly consequences of **executing every tenant's agents on shared cloud infrastructure**. Our hybrid architecture sidesteps the worst of this *by construction*: each tenant's agents execute on the tenant's own hardware. That is our headline ("isolation by architecture, not by promise").

But four zones of our platform still face real multi-tenancy, and the moment we ship the **Managed Model Gateway** (Gap Analysis G5) and any future **Hosted Agent Runtime**, we inherit every problem on the list. This document (a) maps each problem to where it actually lives in our system, (b) elaborates each opportunity-gap feature into a concrete design on our stack (FastAPI/PostgreSQL/local plane), and (c) specifies the flagship build: the **Tenant-Aware Execution Sandbox with Instant Recycling**.

---

## 1. WHERE MULTI-TENANCY LIVES IN OUR ARCHITECTURE

| Zone | Tenancy Reality | Risk Class |
|---|---|---|
| **Z1 — Local Execution Plane** (customer machines) | Single-tenant by physics. Agents, memory, RAG, transcripts on tenant hardware | Cross-tenant bleed: structurally impossible. Residual risk: intra-tenant (departments, users) |
| **Z2 — Cloud Control Plane** (accounts, billing, configs) | Multi-tenant PostgreSQL (RLS) | Metadata-only, but still needs identity, tamper-evident audit, offboarding, tenant-scoped observability |
| **Z3 — Managed Model Gateway** (planned: metered cloud inference) | **True multi-tenant inference** — prompts/completions transit shared infra | The danger zone: data-in-use, budget, noisy neighbor, routing, residency |
| **Z4 — Hosted Agent Runtime** (future: "Always-On Cloud Node" running a tenant's agents when their machines are off) | Full multi-tenant agent execution | Inherits 100% of the industry problem list → requires the flagship sandbox |
| **Z5 — Intra-tenant multi-tenancy** (enterprise: departments, users, nodes; agencies: per-client walls) | "Tenants within a tenant" on local plane | Same patterns at smaller scale: namespace RAG, identity, shadow agents |

**Design law:** every feature below is specified once and applied per-zone. Anything mandatory in Z3/Z4 becomes a software-enforced version in Z5.

---

## 2. PROBLEM-BY-PROBLEM ANALYSIS

### P1 — Per-Tenant Models, Prompts, Tools, Behaviors at Scale
**Industry failure mode:** one global config (inflexible) or manual per-tenant setup (doesn't scale).
**Our answer — the Configuration Inheritance Engine (CIE):** five-layer cascade, every layer pure data:

```
Platform defaults (admin Common Config)
  → Plan layer (feature flags & limits — entitlements)
    → Industry Template layer (rosters, rules, prompts, phrase packs)
      → Tenant overrides (where scope = overridable)
        → Department / Agent layer (per-agent model, tools, prompt persona)
```

- **Per-tenant model routing:** `routing_policies` per tenant: ordered model preference per task-profile, e.g. Tenant A `{drafting: [claude-x → qwen72b-local], extraction: [phi-local]}`. Resolved at dispatch by the LLM Router; admin can ship recommended policies per plan/template; tenants override within their entitlement.
- **Per-tenant failover chains:** each routing entry is a chain with health-aware failover (timeout/5xx/quality-validator failure → next link), circuit breakers per provider per tenant, and a terminal local-model fallback so the workforce never fully stops.
- **Per-tenant tool permissions:** already modeled (`tool_grants` per agent); add tenant-level **tool policy ceilings** ("no agent in this tenant may ever get `payments.execute`") that agent-level grants cannot exceed — evaluated as: effective_permission = agent_grant ∩ department_policy ∩ tenant_ceiling ∩ plan_flag.
- **Per-tenant prompt customization:** prompt assembly is layered, not monolithic: `system_core (locked) + template_persona + tenant_voice (brand tone, terminology) + agent_persona + task_context`. Tenants edit only their layers; locked core carries safety/compliance language (ties to `locked_rules`, Doc 13 §4.3). Versioned, diffable, canary-testable per tenant.
- **Scale mechanism:** all five layers are rows, not deployments. The admin changes the platform layer once; 10,000 tenants inherit at next config pull. This is the same machinery as Common Config (UC-S12) — extended downward.

### P2 — Compliance Theater vs Real Compliance
**Industry failure:** claimed SOC2/HIPAA/GDPR with incomplete, mutable logs; unclear residency; encryption at rest but not in use.
**Our answers:**
- **Tamper-evident audit (§3.4):** hash-chained, per-tenant verifiable — not just "append-only by GRANT."
- **Residency by architecture:** Z1 business data resides wherever the tenant's machines are — residency is the tenant's choice by default, provable. Z2 metadata: region-pinned deployments (EU cell, IN cell) with tenant→cell assignment recorded. Z3/Z4: region-pinned gateway endpoints; routing policies carry an allowed-regions constraint.
- **Encryption in use:** for Z3/Z4 regulated tenants, a **Confidential Computing tier** (§3.11) following the Omega direction — CVM (AMD SEV-SNP) + confidential GPU (H100 CC) execution with remote attestation evidence surfaced to the tenant. We don't claim this for v1; we roadmap it honestly and design the gateway so the tier slots in.
- **Compliance-as-Code (§3.10):** controls are executable policies, not PDF claims; every control maps to a policy ID, every policy decision to an audit record — auditors get evidence queries, not screenshots.

### P3 — Shadow Agent Proliferation
**Industry failure:** business units deploy unauthorized agents; no inventory, no governance.
**Our answer (§3.9):** we have a structural advantage — agents only run inside our runtime, so the **Org Chart is the inventory**. The residual risks: unregistered nodes, sideloaded plugins/skills, and other agent tools (a Hermes install in the sales department). We add detection + policy for all three.

### P4–P7 — Data bleed, budget runaway, noisy neighbor, identity confusion
Solved per-zone in §3 and §4. Key stance: in Z1 these are non-problems across tenants (physics) but real within tenants (Z5); in Z3/Z4 they are existential and get the full treatment.

---

## 3. ELABORATED FEATURE DESIGNS

### 3.1 🥇 Five-Layer Identity Model (every zone)

Every action in the system is attributed to a **complete identity chain**, not a single principal:

| Layer | Identity | Carried As |
|---|---|---|
| L1 Tenant | `tnt_…` | RLS context (Z2), entitlement snapshot (Z1), sandbox label (Z3/Z4) |
| L2 Human | `usr_…` + `spk_…` (voice-print) + session | JWT claims / `X-Actor` + `X-Speaker-Id` |
| L3 Agent | `agt_…` + agent version | dispatch envelope |
| L4 Capability | `skl_…` / `plg_…` / tool name + version + signature | tool-call wrapper |
| L5 Substrate | `dev_…` / `nod_…` / sandbox instance id | runtime context |

- **Attribution rule:** an audit record is invalid unless all five layers are present (system actions use `system` sentinels). The audit writer rejects partial chains → fail closed (extends SC-07).
- **Authorization rule:** permission checks evaluate the *chain*, not the leaf — an allowed agent (L3) using a revoked plugin (L4) on an unpaired node (L5) is denied.
- **Why it matters:** prevents the classic misattribution ("the agent did it" — *which* tenant's agent, on *whose* command, via *which* tool, *where*?). Schema: `audit_local` / `audit_cloud` gain `identity_chain jsonb NOT NULL` with a CHECK on the five keys.

### 3.2 🥇 Pre-Dispatch Budget Gates (Z3/Z4 mandatory; Z1 optional for BYO keys)

**Industry failure:** cost checked *after* the LLM call.
**Design — gate before every call:**
1. **Estimate:** dispatcher computes `est_cost = f(prompt_tokens, max_output_tokens, model_rate)` before contacting the provider.
2. **Reserve:** atomic reservation against the tenant's budget ledger (`SELECT … FOR UPDATE` on `budget_ledgers`): `available = limit − spent − reserved`. Insufficient → call never happens; structured `BUDGET_EXCEEDED` with options.
3. **Settle:** on completion, reservation replaced by actual cost; on failure, released.
4. **Budget hierarchy:** tenant monthly cap → per-department envelope → per-agent allowance → per-task ceiling (CEO Agent sets a task budget at planning time and the plan readback *speaks it*: "Estimated cost ₹14 on the gateway. Proceed?").
5. **Graduated behavior:** 80% → voice/visual warning; 100% soft → queue non-urgent, ask for human approval per call (AC chain reused as *budget approvals*); hard cap → local-model fallback chain only.
6. **Runaway-loop breaker:** per-task call-count and token-velocity limits independent of money (catches infinite agent loops even within budget).
Schema: `budget_ledgers(tenant_id, scope, period, limit, spent, reserved)`, `budget_reservations(id, ledger, est_cost, task_id, state)`.

### 3.3 🥈 Per-Tenant Model Routing & Failover (Z3 + Z1 hybrid)
Covered in P1; additional mechanics: provider health scored per-tenant-per-model (latency p95, error rate, validator-rejection rate); failover decisions logged with reason; **quality failover** (output fails schema/validator → escalate chain, LC-05 generalized); router decisions visible in the Glass-Box Console ("Maya's draft used Qwen-local; Claude was skipped: budget rule B-3").

### 3.4 🥈 Tamper-Evident Audit Logs (Z1 + Z2)

Upgrade from "append-only by permission" to **cryptographically verifiable**:
- Each record: `hash_n = SHA-256(hash_{n−1} ‖ canonical(record_n))` — per-tenant chain in Z2, per-installation chain in Z1.
- **Anchoring:** every N records / T minutes, the head hash is (Z1) signed by the device key and optionally heartbeated to the cloud as a 32-byte anchor — content-free, so the privacy invariant holds (DB-01 compatible: an anchor reveals nothing); (Z2) co-signed across two services and written to WORM object storage.
- **Verification:** `GET /audit/verify?from=&to=` replays the chain → `{intact: true|false, first_break}`; enterprise admins can export chain + anchors for external auditors.
- **Detection guarantee:** deletion or mutation anywhere breaks every subsequent hash; the cloud anchor catches even a locally-root-privileged attacker rewriting history (they can't rewrite the anchors we already sent).
Schema: add `prev_hash, this_hash` to `audit_local`/`audit_cloud`; new `audit_anchors(head_hash, signed_at, signature, range)`.

### 3.5 🥇 One-Click Tenant Offboarding (Z2/Z3, with Z1 dignity)

A single admin/tenant-initiated action executing a **deletion saga** with a certificate:
1. Snapshot offered to tenant (export: invoices, account data) — 7-day window unless immediate requested.
2. Revoke: device tokens, mTLS certs, marketplace licenses, gateway keys — propagated within one heartbeat; desktops drop to local-only mode but **local business data is untouched and remains fully usable for export** (their machine, their data — our differentiator: offboarding doesn't hold work hostage).
3. Purge cloud rows across all services via the saga (ordered, idempotent, resumable): identity → billing (retain legally-required financial records, flagged & minimized) → configs → marketplace → support → telemetry.
4. Z3/Z4: budget ledgers closed; any sandbox snapshots/volumes for the tenant cryptographically shredded (keys destroyed).
5. Emit **Deletion Certificate**: per-system completion proof, hash-chained into the admin audit; sent to the tenant (GDPR/DPDP Art. 17 evidence).
6. Verification job re-scans all stores for the tenant_id after 24h; non-empty → incident.
SLA: logical deletion ≤ 24 h; backup expiry ≤ 35 days (documented in the certificate).

### 3.6 🥇 Per-Tenant Observability (Z2/Z3/Z4)

- **Tenant-scoped tracing:** every request/trace carries `tenant_id` as a baggage attribute; trace storage is partitioned by tenant; support engineers query through a proxy that *requires* a tenant context and an open support ticket (or consented impersonation, PA-02) — cross-tenant queries are technically impossible from the support role.
- **Content-free spans:** spans record sizes, timings, model ids, policy decisions — never prompt/response bodies (Z3 bodies are not logged at all in standard tier; in confidential tier they never leave the enclave).
- **Tenant-facing slice:** users see their own gateway/eventing telemetry in the web dashboard ("your gateway calls, latencies, spend") — observability as a feature, not just an internal tool.
- Z1 corollary: the Glass-Box Console (Gap doc G6) is per-department-scoped in enterprise mode (Z5).

### 3.7 🥈 Namespace-Isolated RAG (Z1/Z5; Z3/Z4 by prohibition)

- **Z1:** vector store is per-installation — physical isolation across tenants. Done by architecture.
- **Z5 (the real work):** department/client walls inside one installation. Three stacked guarantees: (1) PostgreSQL **RLS on `memory_chunks` and `kg_entities`** keyed to the session's department/clearance context; (2) a **mandatory retrieval middleware** that injects namespace filters — agent code cannot call pgvector directly (the raw connection role lacks SELECT; only the middleware role has it); (3) post-retrieval citation check: every chunk's namespace re-validated before entering the prompt. Agencies get per-client namespaces (Persona Priya, rule AG-R1) on the same machinery.
- **Z3/Z4 rule:** the gateway performs **no retrieval** — context is assembled locally and sent per-call; the Hosted Agent Runtime (Z4) mounts only the tenant's own encrypted volume. No shared vector DB exists to contaminate.

### 3.8 🥈 Tenant-Aware Rate Limiting (Z2/Z3)
Token-bucket per tenant per resource (API class, gateway tokens/min, channel sends) with **burst credits** earned by under-use (solves "noisy neighbor vs killing bursts"); per-plan QoS classes (Enterprise gets reserved gateway capacity); fairness scheduler on shared queues = weighted fair queuing by tenant, so one tenant's 10k-task storm delays itself, not neighbors; per-tenant backpressure signaled to the desktop (`RATE_LIMITED` + retry-after) so the local scheduler reshapes load instead of hammering.

### 3.9 🥉 Agent Inventory & Shadow Detection (Z5, enterprise)

- **Inventory is native:** agents exist only as `agents` rows executed by our runtime → the Org Chart is a complete, live inventory with owner, tools, model, node, last activity — exportable to IT.
- **Shadow vectors & countermeasures:**
  1. *Unregistered nodes:* network console flags LAN hosts running our core that aren't paired (mDNS beacon + cert check); admin policy "no unpaired instances" → unpaired installs in managed networks run in restricted mode.
  2. *Sideloaded skills/plugins:* signature-mandatory already (SC-03/04); enterprise policy adds allow-list mode (only admin-approved package IDs load) + weekly attestation report of every loaded capability per node.
  3. *Third-party agent tools* (an employee's personal Hermes/OpenClaw install): out of our runtime, but our enterprise agent on each managed machine can detect known agent-tool process signatures and report to the IT console — positioned as the "AI usage visibility" feature CISOs are asking for (opt-in, disclosed, policy-driven).
- **Governance loop:** unknown capability detected → quarantine state → approval chain to legitimize or block → audited either way.

### 3.10 🥉 Compliance-as-Code (all zones)

We already have a rule engine (Conditional doc) and `locked_rules` (Doc 13). Formalize:
- **Policy packs:** declarative documents `{policy_id, scope, condition, effect (allow/deny/require_approval/redact), evidence}` evaluated by a policy decision point in the dispatcher *before* tool calls and *before* gateway calls — same evaluation point the Omega paper argues for (policy interpreted outside the agent's execution context). Engine: CEL or OPA/Rego embedded in the local core; packs are data.
- **Admin-shipped packs:** "GDPR pack", "HIPAA-adjacent clinic pack", "RERA pack", "EU AI Act logging pack" — versioned, pushed via Common Config, lockable (PA-03). Regulation changes become a config push, not a customer project → recurring SaaS value.
- **Evidence by construction:** every policy decision writes `{policy_id, decision, identity_chain, hash}` to the tamper-evident log; an auditor's question ("show me every cross-border send blocked in Q2") is a query.
- Tenant-authored policies allowed *under* locked packs (can tighten, never loosen).

### 3.11 🥉 Hardware-Level Isolation Option (Z3/Z4 roadmap, regulated tenants)

Following the Omega architecture (arXiv 2512.05951): confidential VMs (AMD SEV-SNP) as the CPU trust anchor composed with NVIDIA H100 confidential-computing GPUs so prompts, model state, and outputs are protected *in use* from the cloud provider and from us; nested isolation (VMPL-style) to keep per-tenant density economical; **remote attestation** evidence exposed to the tenant ("verify the enclave before your data enters it") and policy enforcement evaluated at the trusted layer, not inside the agent.
- Productization: **"Confidential Gateway" add-on** for Enterprise — attested region-pinned inference; later, the same substrate hosts Z4.
- Honest sequencing: standard gateway first (encrypted transit, no logging, region pinning); confidential tier when volume justifies H100-CC capacity. We market the *roadmap commitment* now and attestation when real — never theater.

### 3.12 🥉 Per-Tenant Canary Deployments
Already built for configs/releases (UC-S12/S14); extend the same rollout engine to **agent prompt versions and auto-captured skills**: a tenant can canary a new prompt/skill on one department before org-wide adoption; the platform can canary template updates on volunteer tenants. One engine, three artifact types.

---

## 4. THE FLAGSHIP BUILD — TENANT-AWARE EXECUTION SANDBOX WITH INSTANT RECYCLING

**Where it applies:** Z4 Hosted Agent Runtime (the strategic unlock: "your AI office keeps working when your laptop is closed" — the one structural advantage cloud-agent rivals have over us today) and Z3 code-execution tools; the same design at smaller scale hardens Z1 skill/plugin sandboxes (Gap doc G8).

### 4.1 Requirements (the four properties, made testable)
1. **Instant sanitization:** tenant-switch turnaround ≤ 250 ms with zero residual state (memory, disk, network, GPU).
2. **Pre-dispatch budget gates:** no LLM/tool call without a settled reservation (§3.2).
3. **Resource isolation:** per-tenant CPU/mem/IO/GPU quotas; no noisy neighbor beyond QoS class.
4. **Tenant-scoped tamper-evident logging:** every action inside the sandbox emits chain-hashed, identity-chain-complete records (§3.1, §3.4).

### 4.2 Design — "Golden Snapshot, Ephemeral Overlay"

```
                    ┌────────────── Warm Pool Manager ──────────────┐
                    │  N pre-booted microVMs (Firecracker/Cloud     │
                    │  Hypervisor) restored from a GOLDEN SNAPSHOT  │
                    │  (runtime + tools baked, ZERO tenant state)   │
                    └──────┬─────────────────────────────┬──────────┘
            lease(tenant)  │                             │ recycle()
                           ▼                             ▼
┌─ Sandbox instance (one tenant, one task batch) ─────────────────────────┐
│ • Ephemeral overlay volume (emptyDir-pattern): tenant workspace,        │
│   tmpfs-backed, per-lease encryption key                                │
│ • Tenant secrets injected as scoped, single-lease references (Vault)    │
│ • Egress through a per-tenant network namespace + policy proxy          │
│   (allow-list from tool grants; all calls pass the Policy Decision      │
│   Point and the Budget Gate BEFORE leaving)                             │
│ • cgroup/microVM quotas per QoS class; GPU via MIG slice or             │
│   time-sliced lease with VRAM scrub on release                          │
│ • Log shipper: chain-hashed records tagged with full identity chain     │
└──────────────────────────────────────────────────────────────────────────┘
                           │ task batch ends / tenant switch
                           ▼
   RECYCLE = (1) destroy overlay + shred its key  (2) revoke secret leases
             (3) reset network namespace          (4) GPU VRAM scrub
             (5) restore microVM memory from golden snapshot  → back to pool
```

**Why this solves the cold-start vs bleed dilemma:** destroy+recreate is slow because it reboots a kernel and re-initializes a runtime; manual wipe is risky because it trusts cleanup code to find every byte. Snapshot-restore does neither: the microVM's *entire memory* is replaced by the golden image (restore is memory-mapped, tens of milliseconds for a slim guest), and tenant data only ever existed on the overlay volume and in secret leases — both cryptographically destroyed (shred the key = the data is gone, regardless of blocks). Sanitization becomes **subtractive and provable**, not procedural and hopeful.

**Warm pool economics:** pool size auto-scales on tenant demand curves; QoS classes map to pool priority (Enterprise reserved instances); a cold path (boot from image) backstops pool exhaustion with honest queue-position feedback to the desktop.

**Attestation hook:** the golden snapshot is measured; in the confidential tier (§3.11) the snapshot hash is part of the attestation report — tenants can verify *which* runtime their task entered.

### 4.3 Dispatcher sequence (per task batch)
`resolve identity chain (§3.1) → evaluate policy packs (§3.10) → budget reserve (§3.2) → lease sandbox (tenant-labeled) → inject scoped secrets → execute with streaming logs → settle budget → recycle → anchor logs (§3.4)`
Any step failing = no execution, structured error, audited.

### 4.4 What ships where
| Increment | Scope |
|---|---|
| S1 (with Gateway, Z3) | Budget gates + per-tenant routing/failover + rate limiting + tenant-scoped observability (no sandbox needed for pure inference) |
| S2 (code-execution tool, Z3) | Full sandbox v1 for generated-code runs |
| S3 (Z1 hardening) | Same overlay+policy-proxy pattern, process-jail/microVM-lite, for marketplace skills & plugins |
| S4 (Z4 launch) | Hosted Agent Runtime on the sandbox substrate — "Always-On Cloud Node" as a per-agent opt-in with loud data-locality labeling |
| S5 (regulated tier) | Confidential computing variant + attestation UX |

---

## 5. SCHEMA & API DELTAS (consolidated)

- `budget_ledgers`, `budget_reservations` (Z2/Z3) — §3.2
- `routing_policies(tenant_id, task_profile, chain jsonb, regions text[])` — §3.3
- `audit_*`: `prev_hash`, `this_hash`, `identity_chain jsonb NOT NULL`; `audit_anchors` — §3.1/§3.4
- `deletion_sagas(tenant_id, steps jsonb, state, certificate_hash)` — §3.5
- `policy_packs(id, version, scope, rules jsonb, locked bool)` + decisions into audit — §3.10
- `sandbox_leases(id, tenant_id, qos, golden_hash, leased_at, recycled_at, scrub_proof)` — §4
- `tenant_ceilings(tenant_id, tool_pattern, effect)` — §P1
- API: `GET /audit/verify`, `POST /admin/tenants/{id}/offboard`, `GET /gateway/usage`, `POST /policies/evaluate` (dry-run), sandbox lease internal RPC.

## 6. POSITIONING & SEQUENCING

**Message:** *"Isolation by architecture. Governance by design. Compliance you can verify."* — local execution removes the cross-tenant problem class entirely; everything that must be shared (control plane, gateway, hosted runtime) gets budget-gated, policy-checked, identity-chained, hash-anchored, and — for regulated tenants — hardware-attested execution.

**Priority order:** (1) Identity chain + tamper-evident audit + offboarding saga — cheap, immediately credible, hardens what exists today; (2) Budget gates + routing/failover + tenant observability — ship *with* the Gateway, never after; (3) Compliance-as-code packs — converts our rule engine into a sales asset; (4) Sandbox S2→S4 — the strategic build that unlocks Always-On agents safely; (5) Confidential tier — when regulated-tenant demand and GPU economics align.

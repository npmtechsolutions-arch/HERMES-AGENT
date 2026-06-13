# AI OFFICE ASSISTANT — SOFTWARE REQUIREMENTS SPECIFICATION (SRS)
**Version 2.0 | SaaS Hybrid: Cloud Platform + Local Execution**
**Stack: React (frontend) · Python FastAPI (APIs) · PostgreSQL (database)**

---

## 1. INTRODUCTION

### 1.1 Purpose
Defines the complete software requirements for AI Office Assistant: a voice-first AI Workforce SaaS where users subscribe via a cloud web portal, download a desktop app, and operate AI employees locally; a Product Admin operates the platform centrally.

### 1.2 System Scope — Two Planes
| Plane | Components | Data Held |
|---|---|---|
| **Cloud Platform** | User Web Portal (React), Admin Dashboard (React), Platform API (FastAPI), PostgreSQL, payment gateways, CDN | Identity, tenants, plans, subscriptions, payments, entitlements, common configs, marketplace catalog, releases, aggregate analytics |
| **Local Execution** | Desktop app (Electron + React), Local Core Service (Python FastAPI), local PostgreSQL, voice pipeline, LLM runtimes, agents | All business data: memory, tasks, transcripts, documents, credentials |

**Invariant SRS-INV-1:** No business data (memory, transcripts, documents, messages, voice audio) is ever transmitted to the cloud plane.

### 1.3 Definitions
Agent (AI employee), Tenant (customer account), Entitlement (signed plan-limit snapshot), Common Configuration (admin-managed config pushed to desktops), Node (paired machine in agent network), MCP (Model Context Protocol tool server).

---

## 2. OVERALL DESCRIPTION

- **Users:** Account Owner, Team Member, Enterprise IT Admin (tenant side); Super/Support/Finance/Catalog Admin (platform side). Industry-agnostic — verticalization only via templates.
- **Operating environment:** Desktop — Windows 10+, macOS 13+, Ubuntu 22.04+; Web — evergreen browsers; Cloud — containerized FastAPI services + managed PostgreSQL 15+.
- **Constraints:** Voice-first parity (every function operable by voice and by UI); offline-first desktop; payment compliance (PCI via gateway tokenization — card data never touches our servers); local data sovereignty.

---

## 3. FUNCTIONAL REQUIREMENTS

(Identifiers cross-reference the PRD; this section states them as testable requirements.)

### 3.1 Cloud — Identity & Subscription
- SRS-F-001: The system shall provide signup with email verification, login, Google SSO, TOTP 2FA, and session refresh via JWT (FastAPI OAuth2).
- SRS-F-002: The system shall offer plan checkout through Stripe and Razorpay with tax computation (GST/VAT), coupons, and PDF invoices.
- SRS-F-003: The system shall process gateway webhooks idempotently with signature verification and shall drive the subscription state machine: `trialing → active → past_due → grace → soft_locked → canceled`.
- SRS-F-004: The system shall issue signed entitlement snapshots (plan limits, feature flags, config version) consumable offline by the desktop for a configurable grace period (default 7 days); Enterprise offline license files shall bypass heartbeats.
- SRS-F-005: The user dashboard shall display real-time usage vs limits (agents, workflows, seats, devices, channels) and support upgrade/downgrade/cancel with proration; downgrades shall archive (never delete) excess resources.
- SRS-F-006: The system shall support device activation via OAuth device flow, listing and remote deactivation of devices, with per-plan device limits.
- SRS-F-007: The system shall support team seats with role assignment and seat revocation propagating to desktops at next heartbeat.

### 3.2 Cloud — Product Administration
- SRS-F-010: The admin dashboard shall provide tenant onboarding/approval queues, suspend/reactivate, and consent-based time-boxed impersonation, all audited.
- SRS-F-011: Admins shall create/edit plans, per-plan feature flags and numeric limits, and coupons without code deployment.
- SRS-F-012: Admins shall configure payment gateway credentials and monitor webhook health; refunds shall require four-eyes approval.
- SRS-F-013: Admins shall manage **Common Configurations** — approved model catalog, integration/MCP connector catalog, industry template library, voice locale packs, compliance presets, default thresholds — as signed, versioned bundles with canary publish, fleet adoption monitoring, and one-click rollback; each item flagged locked/overridable/suggestion.
- SRS-F-014: Admins shall manage desktop releases with staged rollout percentages, automatic pause on crash-rate threshold breach, and a force-update version floor.
- SRS-F-015: Admins shall review, sign, version, and take down marketplace packages; unsigned packages shall be uninstallable on desktops.
- SRS-F-016: The platform shall present aggregate analytics (MRR, ARR, churn, activation funnel, plan mix, crash rates, opt-in feature adoption) with no access to tenant business data.
- SRS-F-017: Destructive admin actions (tenant deletion, mass refunds, force update) shall require second-admin approval.

### 3.3 Desktop — Voice Platform
- SRS-F-020: Wake word (customizable), push-to-talk, and continuous listening modes; barge-in shall halt TTS ≤ 200 ms.
- SRS-F-021: Local STT (Whisper/Faster-Whisper) with streaming partials and ≥12 languages; local TTS (Piper/Kokoro/OpenVoice) with per-agent voices.
- SRS-F-022: 100% of platform functions shall be operable by voice, with confidence-tiered confirmation (auto ≥0.85; confirm 0.60–0.84; re-ask <0.60) and mandatory explicit confirmation for sensitive actions.
- SRS-F-023: Speaker identification (voice-print) shall gate privileged commands in multi-user mode.
- SRS-F-024: Proactive voice notifications shall respect Do-Not-Disturb schedules with urgent-class override (user-configurable).

### 3.4 Desktop — AI Organization & Orchestration
- SRS-F-030: CRUD for departments and agents with full profile (name, designation, department, objectives, skills, tools, memory scopes, LLM, permissions, KPIs, schedule, reporting manager), subject to plan limits.
- SRS-F-031: CEO Agent shall decompose tasks into DAGs, assign by skill/availability/KPI, monitor, re-plan, and escalate.
- SRS-F-032: Agent-to-Agent Messaging Bus: threaded, task-linked, fully logged, user-observable, RBAC-filtered in enterprise mode.
- SRS-F-033: Agent states (Idle/Working/Waiting/Reviewing/Escalated/Completed/Error/Paused/Archived) shall stream live to the Org Chart UI.
- SRS-F-034: Approval chains (Specialist→Manager→CEO Agent→Human) with delegated limits, timeouts/escalation, segregation of duties, temporary delegations, and full decision trails.

### 3.5 Desktop — Second Brain & Knowledge Graph
- SRS-F-040: Ingestion of PDF, DOCX, XLSX, PPTX, images (OCR), audio/video (transcription), websites, emails, and databases into typed memory (Personal/Business/Knowledge/Operational).
- SRS-F-041: Hybrid semantic + keyword search across scoped memory, voice-queryable, returning source-cited chunks.
- SRS-F-042: Knowledge Graph of entities (customer, vendor, project, task, document, agent, policy, contact) and typed relations; graph-augmented retrieval; conflict detection and resolution workflow; reference resolution for voice mentions ("my CA").
- SRS-F-043: Memory lifecycle: per-agent scoping, cold-tiering, soft-delete with 30-day recovery, full export.

### 3.6 Desktop — Automation
- SRS-F-050: Visual workflow builder with trigger/condition/action/agent/approval/notification nodes; voice-to-workflow compilation; dry-run sandbox; versioning.
- SRS-F-051: Scheduling: daily/weekly/monthly/yearly/CRON/event triggers; run-on-wake or skip policies; DST-safe local-time storage.
- SRS-F-052: Self-healing: failure classification (transient/credential/config/logic), bounded retries with backoff, remediation proposals gated by approval, incident memory, auto-pause after 2 consecutive scheduled failures.
- SRS-F-053: Task management with priority, deadline, dependencies, escalation, approvals, artifacts, and full lifecycle tracking.

### 3.7 Desktop — Communication & Execution
- SRS-F-060: Unified inbox across Email (Gmail/Outlook/Exchange), WhatsApp, Telegram, Slack, Teams, Discord, SMS with categorization, drafting, rule-based auto-response, escalation, and voice triage.
- SRS-F-061: AI Call Center: inbound answering and outbound campaigns over SIP/VoIP with real-time STT/TTS, CRM context, sentiment-based human transfer, transcripts, outcome coding, compliance windows, and opt-out enforcement.
- SRS-F-062: Computer control (apps, keyboard, mouse, windows) and browser automation (Playwright/Puppeteer) under per-agent permission grants.
- SRS-F-063: Document generation (reports, contracts, proposals, invoices, audit docs) to PDF/DOCX/XLSX/PPTX from templates and voice dictation.
- SRS-F-064: All tools exposed via local MCP servers; external MCP servers attachable; Plugin SDK (Python/JS/Java) with sandboxing and install-time permission consent; Skill Builder Studio (record/describe → parameterize → sandbox test → publish).

### 3.8 Desktop — Models & Compute
- SRS-F-070: Support Qwen, DeepSeek, Gemma, Llama, Mistral, Phi across Ollama, llama.cpp, vLLM, LM Studio; model catalog restricted to admin-approved entries (Common Configuration) unless tenant override permitted.
- SRS-F-071: GPU Resource Manager: VRAM accounting, LRU eviction, quantization selection, multi-GPU and multi-node placement, guaranteed voice-pipeline reservation, complexity-based routing.
- SRS-F-072: Resumable, checksum-verified model downloads; CPU-only degraded mode.
- SRS-F-073: Multi-Computer Agent Network: admin-initiated pairing with mutual TLS, capability advertisement, cross-node task routing, checkpointed task migration on node loss.

### 3.9 Marketplace & Templates
- SRS-F-080: Browse/purchase from web or desktop; signed-package verification at install; permission review screen; updates channel.
- SRS-F-081: Industry templates shall bootstrap a complete org (departments, agents, skills, workflows, document templates) from data files with zero industry logic in core code.

---

## 4. NON-FUNCTIONAL REQUIREMENTS

### 4.1 Performance
| ID | Requirement |
|---|---|
| SRS-N-001 | Wake-word to listening ≤ 300 ms; STT partials ≤ 500 ms; command→TTS start ≤ 1.5 s (local 7B class, recommended hardware) |
| SRS-N-002 | Cloud API p95 ≤ 300 ms (reads), ≤ 800 ms (billing mutations); web dashboards LCP ≤ 2.5 s |
| SRS-N-003 | Desktop usable on 16 GB RAM / 8 GB VRAM; functional (degraded) on CPU-only 16 GB |
| SRS-N-004 | Local semantic search over 100k chunks ≤ 1.5 s p95 |
| SRS-N-005 | Cloud scales to 100k tenants / 1M devices (stateless FastAPI behind LB; PostgreSQL with read replicas + PgBouncer) |

### 4.2 Reliability & Availability
| ID | Requirement |
|---|---|
| SRS-N-010 | Cloud availability ≥ 99.9% monthly; desktop must remain fully functional during any cloud outage (entitlement grace) |
| SRS-N-011 | Scheduled task success ≥ 97%; self-healing auto-recovers ≥ 60% of transient failures |
| SRS-N-012 | Local core service runs 24x7 as OS service; auto-restart; crash-safe write-ahead logging on local DB |
| SRS-N-013 | Cloud RPO ≤ 5 min (WAL archiving), RTO ≤ 1 h; daily encrypted backups, restore-tested monthly |

### 4.3 Security & Privacy
| ID | Requirement |
|---|---|
| SRS-N-020 | Local data: AES-256 at rest; OS keychain-wrapped keys; vault for credentials; tools receive secret references, never raw values |
| SRS-N-021 | Cloud: TLS 1.2+, Argon2id password hashing, JWT rotation, rate limiting, OWASP ASVS L2 |
| SRS-N-022 | Card data handled exclusively by gateway elements (PCI-DSS SAQ-A scope) |
| SRS-N-023 | Privacy invariant (SRS-INV-1) enforced by schema: cloud API has no endpoints accepting business-data payloads; CI contract tests verify |
| SRS-N-024 | Append-only audit logs both planes; privileged action fails closed if audit write fails |
| SRS-N-025 | RBAC: tenant-side roles + department isolation; platform-side admin roles; four-eyes on destructive admin actions |
| SRS-N-026 | Config bundles, marketplace packages, releases: signed; desktops verify signatures before applying |
| SRS-N-027 | GDPR/DPDP: account deletion purges cloud PII ≤ 30 days; data export self-serve |

### 4.4 Usability & Accessibility
SRS-N-030: Voice/keyboard/mouse parity (no modality dead ends). SRS-N-031: WCAG 2.1 AA for web apps. SRS-N-032: ≥12 UI/voice locales. SRS-N-033: First-value time ≤ 15 minutes from signup (template path).

### 4.5 Maintainability & Compatibility
SRS-N-040: OpenAPI-documented FastAPI services; ≥80% coverage on billing/entitlement logic. SRS-N-041: Additive-only changes within API v1; plugin/node version negotiation. SRS-N-042: Desktop auto-update honoring staged rollout and force floor.

---

## 5. TECHNOLOGY STACK REQUIREMENTS

| Layer | Mandated Choice | Notes |
|---|---|---|
| Web frontend | **React 18+** (TypeScript), Vite, React Query, component library + Tailwind | User Portal & Admin Dashboard separate apps, shared design system |
| Desktop UI | Electron + **React** (same design system) | Voice Orb, Org Chart, builders |
| Cloud API | **Python 3.12 + FastAPI**, Pydantic v2, SQLAlchemy 2 + Alembic, Celery/Arq for jobs | OAuth2/JWT, OpenAPI |
| Local Core | **Python 3.12 + FastAPI** (loopback), WebSocket events | Same skill set as cloud team |
| Database (cloud) | **PostgreSQL 15+** (managed), PgBouncer, read replicas | Schemas in Table Design doc |
| Database (local) | **PostgreSQL (embedded)** with pgvector for embeddings; SQLite fallback on constrained machines | Local-only |
| Vector search | pgvector (both planes where needed) | |
| Voice | Whisper/Faster-Whisper, Piper/Kokoro/OpenVoice, openWakeWord | Local |
| LLM runtimes | Ollama, llama.cpp, vLLM, LM Studio | Local |
| Automation | Playwright (primary), Puppeteer (compat) | |
| Payments | Stripe + Razorpay | Webhooks → FastAPI |
| Infra | Docker/K8s, CDN for installers/config bundles, S3-compatible object store | |

---

## 6. EXTERNAL INTERFACE REQUIREMENTS

1. **Payment gateways:** checkout sessions, webhooks (signature-verified, idempotent).
2. **Email/SMS providers:** transactional mail (verification, dunning, invoices) — admin-configurable.
3. **Business integrations (desktop, via MCP):** CRM (Salesforce, HubSpot, Zoho), ERP (SAP, Oracle, Odoo, ERPNext), Accounting (Tally, QuickBooks, Zoho Books), Storage (Drive, OneDrive, Dropbox), Comms (WhatsApp, Telegram, Slack, Teams, Discord, SMS), Calendars, PM tools (Jira, Trello, Asana, ClickUp), Dev (GitHub, GitLab, Bitbucket), Databases (MySQL, PostgreSQL, MongoDB, SQL Server).
4. **Telephony:** SIP/VoIP provider for Call Center module.

---

## 7. ACCEPTANCE CRITERIA (RELEASE GATES)

1. New user: signup → pay → download → activate → voice-create first agent → complete first voice task, in ≤ 15 minutes, on reference hardware.
2. Cloud unreachable for 72 h: desktop fully functional; reconciles on reconnect.
3. Plan downgrade leaves zero data loss; archived resources restorable on upgrade.
4. Admin publishes config to canary → fleet; rollback restores previous version on 100% of canary devices.
5. Privacy contract tests prove no business-data fields accepted by any cloud endpoint.
6. Webhook replay/duplicate storm causes zero double-charges or state corruption.
7. All P0 use cases (Use Case doc) pass by voice-only and by UI-only execution.

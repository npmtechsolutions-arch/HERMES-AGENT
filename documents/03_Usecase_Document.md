# AI OFFICE ASSISTANT — USE CASE DOCUMENT
**Version 1.0 | Voice-First AI Workforce Platform**

---

## 1. ACTORS

| Actor | Description |
|---|---|
| **Owner/User (Human)** | Primary human operator; full permissions; speaks commands |
| **Team Member (Human)** | Secondary human in multi-user/enterprise mode; scoped permissions |
| **Administrator (Human)** | Manages enterprise deployment, nodes, users, policies |
| **CEO Agent (AI)** | Orchestrator: decomposes, assigns, tracks, escalates |
| **Manager Agent (AI)** | Department-level supervisor; mid-tier approvals |
| **Specialist Agent (AI)** | Executes domain tasks (e.g., GST Specialist, Recruiter) |
| **Self-Healing Agent (AI)** | Monitors failures and remediates |
| **External Party** | Customer/vendor reached via email, WhatsApp, or voice call |
| **External System** | CRM, ERP, accounting, calendar, database, etc. (via MCP) |
| **Scheduler** | System actor firing time/event triggers |

---

## 2. USE CASE INDEX

| ID | Use Case | Primary Actor | Priority |
|---|---|---|---|
| UC-01 | Voice onboarding & org bootstrap | Owner | P0 |
| UC-02 | Hire (create) an AI employee by voice | Owner | P0 |
| UC-03 | Assign a task by voice | Owner | P0 |
| UC-04 | CEO Agent decomposes & delegates a task | CEO Agent | P0 |
| UC-05 | Query the Second Brain by voice | Owner | P0 |
| UC-06 | Ingest documents into knowledge | Owner | P0 |
| UC-07 | Voice triage of unified inbox | Owner | P0 |
| UC-08 | Build a workflow by voice | Owner | P0 |
| UC-09 | Scheduled workflow executes autonomously | Scheduler | P0 |
| UC-10 | Multi-tier approval chain | Manager/CEO Agent, Owner | P0 |
| UC-11 | Agent-to-agent collaboration via Messaging Bus | Specialist Agents | P0 |
| UC-12 | Self-healing of a failed workflow | Self-Healing Agent | P1 |
| UC-13 | Train an agent (Training Center) | Owner | P1 |
| UC-14 | Build a skill without code (Skill Builder) | Owner | P1 |
| UC-15 | Install from Marketplace / apply Industry Template | Owner | P1 |
| UC-16 | AI handles an inbound phone call | Specialist Agent | P1 |
| UC-17 | AI makes outbound follow-up calls | Specialist Agent | P1 |
| UC-18 | Browser automation data entry | Specialist Agent | P0 |
| UC-19 | Generate business documents by voice | Owner | P0 |
| UC-20 | Daily proactive voice briefing | CEO Agent | P1 |
| UC-21 | Pair a second computer (Agent Network) | Administrator | P2 |
| UC-22 | Enterprise multi-user with department isolation | Administrator | P2 |
| UC-23 | Voice analytics query | Owner | P1 |
| UC-24 | Review agent performance & retrain | Owner | P1 |
| UC-25 | Knowledge Graph exploration | Owner | P1 |

---

## 3. DETAILED USE CASES

### UC-02 — Hire an AI Employee by Voice

- **Actors:** Owner, CEO Agent
- **Preconditions:** Onboarding complete; ≥1 LLM available.
- **Trigger:** "Hey Office, hire a [role]."
- **Main Flow:**
  1. System asks clarifying questions (role, department) if missing.
  2. System drafts agent profile (name, designation, objectives, default skills/tools, LLM via GPU Resource Manager).
  3. TTS reads back the profile.
  4. Owner says "Confirm" (or edits fields by voice).
  5. Agent instantiated; reporting manager linked; appears on Org Chart as Idle.
- **Alternate Flows:**
  - A1: Owner edits any field by voice before confirming.
  - A2: Insufficient VRAM for requested model → GPU Manager proposes smaller/quantized model.
  - A3: Marketplace pack matches role → system offers pre-built agent instead.
- **Postconditions:** Agent persisted; audit log entry; optional training prompt.
- **Exceptions:** Duplicate name → system proposes alternative.

### UC-03 — Assign a Task by Voice

- **Actors:** Owner, CEO Agent, Specialist Agents
- **Trigger:** Natural utterance, e.g., "Prepare the monthly GST report and email it to my CA by Friday."
- **Main Flow:**
  1. STT → Intent Layer extracts task, entities (resolved via Knowledge Graph: "my CA" → contact), deadline, post-actions.
  2. CEO Agent builds an execution plan (subtasks, agents, tools, estimated time).
  3. Plan read back by voice; Owner approves.
  4. Tasks dispatched over Messaging Bus; statuses stream to Task Board.
  5. On completion: voice summary; artifacts linked; Operational Memory updated.
- **Alternate Flows:**
  - A1: Ambiguity ("Which CA — Sharma or Patel?") → voice disambiguation.
  - A2: Plan rejected → Owner edits steps by voice.
  - A3: Mid-execution approval gate fires → UC-10.
- **Exceptions:** Required integration not connected → system offers connection flow; task queued.

### UC-04 — CEO Agent Decomposes & Delegates

- **Trigger:** Any approved multi-step task.
- **Main Flow:** parse goal → consult Knowledge Graph + Operational Memory (similar past tasks) → generate DAG of subtasks → match subtasks to agents by skills/availability/KPIs → dispatch → monitor → re-plan on delays → aggregate result → report.
- **Alternates:** no capable agent → propose hiring (UC-02) or marketplace pack (UC-15); deadline risk → voice alert with options.

### UC-07 — Voice Triage of Unified Inbox

- **Trigger:** "What's in my inbox?" or proactive urgent alert.
- **Main Flow:**
  1. Comms agents pre-categorize messages (Urgent/Action/FYI/Spam).
  2. TTS summarizes counts and highlights.
  3. Owner: "Read the one from Mehta." → full read.
  4. Owner dictates reply intent; agent drafts; readback; "Send."
  5. Sent message logged; contact record updated in Business Memory.
- **Alternates:** "Auto-handle FYI under rule two" → bulk workflow; angry-customer detection → escalation task created.

### UC-08 — Build a Workflow by Voice

- **Trigger:** "Create a workflow: every Monday at 9…"
- **Main Flow:** utterance → workflow graph compiled → visual canvas shown → voice edits ("add a condition…") → dry-run test → spoken test results → "Activate" → registered with Scheduler.
- **Postconditions:** Workflow active; appears in workflow list; audit entry.
- **Exceptions:** Unmappable step → system asks for clarification or suggests a Skill Builder session (UC-14).

### UC-10 — Multi-Tier Approval Chain

- **Actors:** Specialist Agent (requester), Manager Agent, CEO Agent, Owner
- **Trigger:** Action matches an approval rule (amount thresholds, new external contact, destructive operations, policy flags).
- **Main Flow:**
  1. Request enters chain at the lowest tier with authority.
  2. Each AI tier auto-approves within delegated limits or escalates with rationale.
  3. Human tier: voice notification with context; "Approve / Reject / Show me / Ask CFO agent first."
  4. Decision propagates; requesting agent resumes or aborts.
  5. Full decision trail written to Audit Log.
- **Alternates:** timeout → escalate up; Owner unavailable → action parked, reminder scheduled.

### UC-11 — Agent-to-Agent Collaboration (Messaging Bus)

- **Example:** Sales Manager needs invoice status from Accountant.
- **Main Flow:** Sales Manager publishes query on bus (thread tied to task ID) → Accountant subscribes/responds with data → thread visible to Owner ("What are the agents discussing?") → outcome merged into task.
- **Rules:** all bus traffic logged; cross-department messages respect department isolation in enterprise mode.

### UC-12 — Self-Healing of a Failed Workflow

- **Trigger:** Tool error, timeout, schema change, expired credential.
- **Main Flow:** detect → classify (transient/config/credential/logic) → transient: backoff retry ×3 → config: propose remap ("Zoho renamed the field; approve fix?") → credential: voice prompt to re-authenticate via Vault → logic: escalate to CEO Agent → human.
- **Postconditions:** incident record stored; recurrence pattern learned; workflow resumes or is paused with notice.

### UC-13 — Train an Agent

- **Trigger:** "Train the HR Manager on our leave policy" / drag-drop onto agent card.
- **Main Flow:** ingest files (OCR/transcribe) → chunk/embed → link in Knowledge Graph → scope to agent memory → optional voice quiz to verify comprehension → training log saved.

### UC-14 — Build a Skill Without Code

- **Main Flow (record mode):** Owner says "Learn a new skill" → demonstrates steps (clicks/typing captured) → system generalizes into parameterized skill → names it by voice ("Call this 'file a Trello card'") → sandbox test → publish to agent(s).
- **Main Flow (describe mode):** Owner verbally describes steps → system drafts skill definition → readback → test → publish.

### UC-16 — AI Handles an Inbound Phone Call

- **Preconditions:** Call Center module configured (SIP/VoIP), agent assigned, scripts/knowledge loaded.
- **Main Flow:** call answered with agent voice → real-time STT → intent + Knowledge Graph lookup (caller recognized via CRM) → conversational handling (booking, status query, FAQ) → outcome coded → transcript + summary to CRM and Business Memory → follow-up tasks auto-created.
- **Alternates:** caller requests human / sentiment turns negative → warm transfer with spoken context summary; outside business hours → voicemail + transcription + task.
- **Compliance:** recording disclosure per jurisdiction; opt-out list enforced.

### UC-21 — Pair a Second Computer

- **Main Flow:** admin issues "Add the reception PC" → pairing code/QR → second node enters code → mutual TLS over LAN → node advertises GPU/tools → GPU Resource Manager redistributes models → agents schedule across nodes; org chart shows node badges.
- **Exceptions:** version mismatch → guided update; node offline → tasks re-routed to remaining nodes.

### UC-20 — Daily Proactive Voice Briefing

- **Trigger:** Scheduled time or "Give me my briefing."
- **Main Flow:** CEO Agent compiles overnight results, pending approvals, urgent messages, today's calendar, KPI deltas, anomalies → 60–120 s spoken brief → interruptible drill-downs → unresolved items become tasks.

---

## 4. CROSS-CUTTING USE CASE RULES

1. Every use case must be fully completable by voice, and fully completable without voice.
2. Any action touching money, external parties, or data deletion passes through the approval rule engine (UC-10).
3. Every agent action emits an audit event.
4. All use cases function offline except those inherently requiring external systems; those queue for connectivity.
5. In enterprise mode, every use case is evaluated against RBAC + department isolation before execution.

---

# PART B — SAAS USE CASES (Cloud Plane)

## Additional Actors
| Actor | Description |
|---|---|
| **Visitor** | Pre-signup website visitor |
| **Account Owner** | Paying user; manages subscription, devices, team seats |
| **Team Member (SaaS)** | Invited seat-holder |
| **Product Admin (Super/Support/Finance/Catalog)** | Operates the platform |
| **Payment Gateway** | Stripe/Razorpay (webhooks) |
| **Marketplace Publisher** | Third party submitting packs/templates |

## Use Case Index (SaaS)
| ID | Use Case | Actor | Priority |
|---|---|---|---|
| UC-S01 | Sign up, verify email, choose plan, pay | Visitor | P0 |
| UC-S02 | Download & activate desktop app (device flow) | Account Owner | P0 |
| UC-S03 | Manage subscription (upgrade/downgrade/cancel) | Account Owner | P0 |
| UC-S04 | Manage devices (view/deactivate) | Account Owner | P0 |
| UC-S05 | Invite team members, assign seats/roles | Account Owner | P1 |
| UC-S06 | Entitlement sync & plan-limit enforcement | Desktop app | P0 |
| UC-S07 | Payment failure → dunning → recovery | Payment Gateway / System | P0 |
| UC-S08 | Raise & track support ticket | Account Owner | P1 |
| UC-S09 | Admin approves/onboards a tenant | Product Admin | P0 |
| UC-S10 | Admin creates/edits a plan & feature flags | Finance/Super Admin | P0 |
| UC-S11 | Admin configures payment gateway & handles refunds | Finance Admin | P0 |
| UC-S12 | Admin publishes Common Configuration to all desktops | Catalog Admin | P0 |
| UC-S13 | Admin reviews/signs marketplace package | Catalog Admin | P1 |
| UC-S14 | Admin manages desktop release rollout | Super Admin | P0 |
| UC-S15 | Admin suspends/reactivates a tenant | Support Admin | P0 |
| UC-S16 | Consent-based support impersonation | Support Admin | P1 |
| UC-S17 | Enterprise offline license issuance | Super Admin | P2 |
| UC-S18 | Aggregate analytics review | Product Admin | P1 |

## Selected Details

### UC-S02 — Activate Desktop App
1. User logs into desktop app → device flow code shown → confirmed on web (or in-app browser).
2. Cloud issues device token + entitlement snapshot (plan limits, feature flags, config version).
3. Desktop validates signature, caches entitlements (offline grace N days), registers device (name, OS, fingerprint).
4. Common Configurations downloaded (templates, model catalog, connectors).
**Exceptions:** device limit reached → list devices, offer deactivation; suspended account → block with support link.

### UC-S06 — Entitlement Enforcement
1. Daily/launch heartbeat fetches entitlements.
2. Action exceeding a limit (6th agent on Starter) → voice/visual upsell with options (upgrade deep-link / archive an agent).
3. Downgrade: excess agents/workflows become Archived (read-only), never deleted.

### UC-S07 — Dunning
Webhook `payment_failed` → retry schedule (1/3/7 days) + emails → grace period (7d full function) → soft-lock (agents paused, data intact, export always allowed) → payment → instant reactivation. All transitions audited.

### UC-S09 — Tenant Onboarding Approval (Admin)
Queue shows new signups requiring review (enterprise, flagged regions, manual KYC). Admin views details → approve / reject (reason) / request info. Approval triggers welcome email + activation enablement. SLA timer + audit.

### UC-S12 — Common Configuration Push (Admin)
1. Catalog Admin edits item (e.g., adds Qwen-2.5 14B to approved model catalog; updates Tally connector v1.4).
2. Marks scope: locked / overridable / suggestion. Stages to "canary" tenants → monitors → publishes to all.
3. Config bundle versioned + signed → desktops poll/pull → apply on safe window → adoption % visible to admin.
**Exceptions:** faulty config → one-click rollback to previous version.

### UC-S14 — Release Rollout
Upload installers (Win/Mac/Linux) → staged rollout (5% → 25% → 100%) → crash-rate gate auto-pauses rollout → force-update floor for security releases.

## Cross-Cutting SaaS Rules
1. Cloud plane never receives tenant business data (memory, transcripts, documents) — enforced at API design level; desktop has no endpoints to send it.
2. Every admin action is audited and attributable; destructive admin actions require second-admin approval (four-eyes).
3. All limits enforce gracefully: archive/pause, never delete user work.
4. Industry-agnostic: no use case may hard-code an industry; templates parameterize verticals.

---

# PART C — INDUSTRY-SPECIFIC USE CASES

Vertical use case libraries (Real Estate deep-dive + Healthcare, Law Firm, CA/Accounting, Education, Manufacturing, Retail, Agency, Recruitment, Hospitality, Logistics) are maintained in the companion **Industry Use Case Document (13)**. All vertical use cases execute on the shared engines defined in this document (UC-01…UC-25) and the SaaS use cases (UC-S01…S18); industry templates contribute only data (agent rosters, workflows, rules, phrase packs) per FR-G1.

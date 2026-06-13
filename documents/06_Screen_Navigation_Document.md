# AI OFFICE ASSISTANT — SCREEN NAVIGATION DOCUMENT
**Version 1.0 | Voice-First AI Workforce Platform**

---

## 1. NAVIGATION PHILOSOPHY

The application is **voice-first**: every screen is reachable by voice command, and the **Voice Orb** is a persistent global element on every screen. Visual navigation (sidebar + keyboard) is the full-parity fallback. Navigation depth never exceeds 3 levels.

**Global voice navigation grammar:** "Go to [screen]", "Open [agent name]", "Show me [department/workflow/task]", "Back", "Home".

---

## 2. SCREEN INVENTORY

| ID | Screen | Voice Command Examples |
|---|---|---|
| S00 | Splash / Unlock | "Unlock" (voice-print, where enabled) |
| S01 | Onboarding Wizard (voice-guided) | — (first run only) |
| S02 | **Home Dashboard** | "Go home", "Dashboard" |
| S03 | **Org Chart (Digital Employee Org Chart UI)** | "Show my company", "Open the org chart" |
| S04 | Department View | "Show Marketing" |
| S05 | Agent Profile | "Open Maya", "Show the Accountant" |
| S06 | Agent Creation / Hire Wizard | "Hire a new employee" |
| S07 | Agent Training Center | "Train this agent" |
| S08 | Task Board (Kanban + list) | "Show my tasks" |
| S09 | Task Detail | "Open the GST task" |
| S10 | Workflow List | "Show workflows" |
| S11 | Workflow Builder Canvas | "Create a workflow", "Edit the Monday report workflow" |
| S12 | Workflow Run History | "Show last runs of [workflow]" |
| S13 | Scheduler / Calendar View | "Show the schedule" |
| S14 | **Communication Hub (Unified Inbox)** | "Open my inbox", "Show urgent messages" |
| S15 | Message Thread / Composer | "Read the Mehta thread" |
| S16 | Call Center Console | "Open the call center", "Show today's calls" |
| S17 | Call Detail (transcript + outcome) | "Play the last call" |
| S18 | **Second Brain Explorer** | "Open memory", "Search the brain for…" |
| S19 | Knowledge Graph View | "Show the knowledge graph", "Show everything about Mehta & Sons" |
| S20 | Knowledge Ingestion / Upload | "Add documents" |
| S21 | Approvals Inbox | "Show pending approvals" |
| S22 | Approval Detail | "Open the LinkedIn job approval" |
| S23 | Agent Messaging Bus Viewer | "What are the agents discussing?" |
| S24 | Analytics Dashboard | "Show analytics", "How productive was Finance?" |
| S25 | Agent Performance Report | "Show Maya's performance" |
| S26 | Marketplace Home | "Open the marketplace" |
| S27 | Marketplace Item Detail / Install | "Install the HR pack" |
| S28 | Industry Template Gallery | "Show industry templates" |
| S29 | Skill Builder Studio | "Create a new skill", "Teach a skill" |
| S30 | Plugin Manager (SDK) | "Show plugins" |
| S31 | LLM / Model Manager | "Show my models" |
| S32 | GPU Resource Manager | "Show GPU usage" |
| S33 | Multi-Computer Network Console | "Show my machines", "Add a computer" |
| S34 | Integrations / Connections (MCP) | "Show integrations", "Connect Zoho" |
| S35 | Vault & Credentials | "Open the vault" |
| S36 | Audit Log Viewer | "Show the audit log" |
| S37 | Settings — General | "Open settings" |
| S38 | Settings — Voice (wake word, voices, languages, DND) | "Voice settings" |
| S39 | Settings — Security & RBAC | "Security settings" |
| S40 | Users & Teams (Enterprise Admin) | "Manage users" |
| S41 | Document Studio (generated docs) | "Show my documents", "Open the proposal" |
| S42 | Notification Center | "Show notifications" |
| S43 | Command Palette / Voice Help | "What can I say?" |
| S44 | Voice Overlay (full-screen ambient mode) | "Go full voice mode" |

---

## 3. NAVIGATION MAP (HIERARCHY)

```
S00 Unlock
 └── S01 Onboarding (first run) ──► S02
S02 HOME DASHBOARD  ◄──────────────── global "Home"
 ├── S03 Org Chart
 │    ├── S04 Department View
 │    │    └── S05 Agent Profile
 │    │         ├── S07 Training Center
 │    │         ├── S25 Performance Report
 │    │         └── S09 (agent's tasks)
 │    └── S06 Hire Wizard
 ├── S08 Task Board ──► S09 Task Detail ──► S22 Approval Detail / S23 Bus thread
 ├── S10 Workflow List
 │    ├── S11 Workflow Builder
 │    └── S12 Run History ──► S09
 ├── S13 Scheduler
 ├── S14 Communication Hub
 │    ├── S15 Thread/Composer
 │    └── S16 Call Center ──► S17 Call Detail
 ├── S18 Second Brain
 │    ├── S19 Knowledge Graph ──► S05 / S09 / S15 (entity jumps)
 │    └── S20 Ingestion
 ├── S21 Approvals Inbox ──► S22 Approval Detail
 ├── S24 Analytics ──► S25
 ├── S26 Marketplace ──► S27 Install / S28 Templates
 ├── S29 Skill Builder
 ├── S30 Plugin Manager
 ├── S31 Model Manager ──► S32 GPU Manager
 ├── S33 Network Console
 ├── S34 Integrations ──► S35 Vault
 ├── S36 Audit Log
 └── S37 Settings ──► S38 Voice / S39 Security / S40 Users
Persistent overlays on all screens: Voice Orb, S42 Notifications, S43 Command Palette, S44 Voice Overlay
```

---

## 4. PERSISTENT GLOBAL ELEMENTS (ALL SCREENS)

| Element | Behavior |
|---|---|
| **Voice Orb** (bottom-right) | Shows the 7 voice states (Design Flow §2.1); click = push-to-talk; displays live transcript chip while listening |
| **Sidebar** (collapsible) | Home, Org, Tasks, Workflows, Inbox, Brain, Approvals (badge), Analytics, Marketplace, Settings |
| **Global Search / Command Palette** (`Ctrl+K` or "What can I say?") | Unified search across agents, tasks, memory, screens; lists voice commands contextually |
| **Approval Badge** | Live count; click/voice → S21 |
| **Agent Activity Ticker** (optional top strip) | Live one-line feed of agent actions ("Auditor reviewing March invoices…") |
| **Node Badge** (multi-computer mode) | Which machine you're on / network health |

---

## 5. KEY SCREEN-BY-SCREEN NAVIGATION NOTES

### S02 Home Dashboard
- **Widgets:** Today's briefing card (playable ▶ voice brief), active tasks, pending approvals, urgent messages, KPI tiles, agent activity feed.
- **Voice:** "Play my briefing", "What's pending?"
- **Navigates to:** every major section in one tap/utterance.

### S03 Org Chart (Digital Employee Org Chart UI)
- Interactive tree: CEO Agent at top → departments → agents. Live status rings (Idle/Working/Waiting/Reviewing/Escalated/Error) and node badges (which machine hosts the agent).
- **Interactions:** click agent → S05; drag agent between departments (with approval if enterprise); "+" on a department → S06 Hire Wizard.
- **Voice:** "Who's busy right now?", "Move Maya under the Marketing Head."

### S05 Agent Profile
- Tabs: Overview (profile fields), Tasks, Skills & Tools, Memory Scope, Model (LLM assignment), Schedule, Permissions, Performance, Training, Bus Messages.
- **Voice:** "Give Maya the WhatsApp tool", "Change her model to Qwen", "Pause this agent."

### S08 Task Board
- Columns mirror agent/task states; filter by department/agent/priority/deadline.
- **Voice:** "Show overdue tasks", "What is the Accountant working on?"

### S11 Workflow Builder Canvas
- Node palette (Trigger, Condition, Action, Agent, Approval, Notification) + canvas. **Voice-to-Workflow bar** at top: speak a sentence → graph generates; further voice edits modify the graph live.
- Buttons: Dry-run, Activate, Version history.

### S14 Communication Hub
- Three panes: channel/category list → thread list → reading/composer pane. Category chips: Urgent / Action / FYI / Spam.
- **Voice:** "Read the next urgent one", "Reply formally that payment releases Tuesday", "Auto-handle FYI."

### S16 Call Center Console
- Live calls strip (active inbound/outbound with real-time transcript), queue, agent assignment, compliance settings (hours, opt-out list), campaign list for outbound.
- **Voice:** "Barge into the active call" (listen-in), "Take over this call."

### S19 Knowledge Graph View
- Force-directed graph; entity types color-coded (Customer, Vendor, Project, Task, Document, Agent, Policy). Click node → side panel with records + jump links. Conflict markers (MC-02) shown in amber.
- **Voice:** "Show everything connected to the Riverside project."

### S21 Approvals Inbox
- List grouped by tier reached (awaiting me / handled by AI tiers today). Each card: requester agent, action, amount/impact, rationale, chain history.
- **Voice on card:** "Approve", "Reject", "Ask the CFO agent first", "Show me details" → S22.

### S29 Skill Builder Studio
- Modes: **Record** (capture demonstration), **Describe** (voice/text steps), **Edit** (parameter mapping, test inputs). Sandbox test runner with logs; Publish-to-agents picker.

### S32 GPU Resource Manager
- VRAM bars per GPU/per node; loaded models list with evict/pin controls; voice-pipeline reservation shown as locked block; routing rules editor.

### S33 Multi-Computer Network Console
- Node cards (name, OS, GPU, tools, hosted agents/models, health); "Add computer" → pairing code flow; task-routing visual.

### S44 Voice Overlay (Ambient Mode)
- Full-screen minimal mode: large orb, live transcript, spoken-response captions, context cards that appear only when "Show me" is said. For desk-away, meeting, and accessibility use.

---

## 6. NAVIGATION RULES

1. **Every screen voice-addressable** by at least one natural phrase (table §2); synonyms maintained in the intent layer.
2. **"Show me" rule:** any spoken information can be pushed to the relevant screen with "Show me."
3. **Back behavior:** "Back" = previous screen; "Home" = S02; breadcrumb visible at depth ≥2.
4. **Deep links:** every entity (agent, task, workflow, message, approval, call, document, graph node) has a stable internal URL for cross-navigation and notifications.
5. **State preservation:** returning to a screen restores filters/scroll within session.
6. **Enterprise scoping:** sidebar and search results auto-filter to the user's RBAC scope; isolated departments are invisible, not greyed out.
7. **Notification routing:** every notification deep-links to its source screen; voice notifications offer "Open it."
8. **Keyboard parity:** full navigation via `Ctrl+K` palette + arrow keys; no mouse-only or voice-only action exists.

---

# PART B — SAAS WEB SCREENS (React Web Apps)

Two web applications join the desktop app: the **User Web Portal** and the **Product Admin Dashboard**. Both are React; both call the cloud FastAPI.

## B1. USER WEB PORTAL — SCREEN INVENTORY
| ID | Screen | Notes |
|---|---|---|
| W01 | Marketing site / Landing | Pricing, industry pages (template-driven, generic core) |
| W02 | Sign Up / Login / SSO / Verify | Email + Google; 2FA setup |
| W03 | Plan Selection & Checkout | Gateway-hosted payment element; coupons; tax display |
| W04 | **User Dashboard Home** | Plan card, usage vs limits (agents/workflows/seats/devices), quick download |
| W05 | Subscription & Billing | Upgrade/downgrade/cancel, invoices (PDF), payment methods |
| W06 | Devices | Activated machines, last seen, deactivate, installer downloads |
| W07 | Team & Seats (Pro+) | Invite, roles, seat usage |
| W08 | Marketplace (web) | Browse; "Send to my desktop" |
| W09 | Support Center | Tickets, docs, status page |
| W10 | Account & Security | Profile, 2FA, sessions, privacy/data controls, delete account |
| W11 | Enterprise Licensing | Offline license file generation (Enterprise) |

**Navigation:** top nav (Dashboard, Billing, Devices, Team, Marketplace, Support) + account menu. Deep links from desktop app (e.g., upsell → W05 with plan preselected).

## B2. PRODUCT ADMIN DASHBOARD — SCREEN INVENTORY
| ID | Screen | Admin Role |
|---|---|---|
| A01 | Admin Login (SSO + 2FA mandatory) | All |
| A02 | **Admin Home** — KPIs: MRR/ARR, churn, activations, open approvals, rollout health | All (scoped) |
| A03 | Tenants List & Detail | Support+ |
| A04 | Onboarding & Approval Queue (tenants, enterprise requests, KYC) | Support/Super |
| A05 | Tenant Actions: suspend/reactivate, plan override, consent impersonation | Support (four-eyes for destructive) |
| A06 | Plans & Feature Flags Editor | Finance/Super |
| A07 | Coupons & Promotions | Finance |
| A08 | Payment Gateways Config (keys, webhooks health) | Finance/Super |
| A09 | Invoices, Refunds & Disputes (approval flow) | Finance |
| A10 | Dunning & Recovery Monitor | Finance |
| A11 | **Common Configurations Studio** — model catalog, connector catalog, template library, voice locales, compliance presets, thresholds; lock/override flags; canary → publish → rollback | Catalog/Super |
| A12 | Config Adoption Monitor (version spread across fleet) | Catalog |
| A13 | Marketplace Admin — publisher queue, package review/signing, takedowns, revenue share | Catalog |
| A14 | Releases — installer upload, staged rollout %, crash gate, force-update floor | Super |
| A15 | Aggregate Analytics (privacy-safe) | All (scoped) |
| A16 | Admin Audit Log | Super |
| A17 | Platform Settings — email/SMS providers, legal docs, status page, admin RBAC | Super |

**Navigation:** left rail grouped: Overview / Tenants / Billing / Configurations / Marketplace / Releases / Analytics / Settings. Global tenant search (`Ctrl+K`). Every queue item deep-links to its detail with full audit trail tab.

## B3. CROSS-PLANE NAVIGATION RULES
1. Desktop upsells deep-link to W05 with context (`?reason=agent_limit&plan=pro`).
2. Web "Send to desktop" actions appear in desktop Notification Center (S42) within one heartbeat.
3. Admin config publishes show desktop-side as "Managed by provider" labels on affected settings screens (S31/S34/S37).
4. Suspension state renders a consistent lock screen on desktop with support deep-link to W09.

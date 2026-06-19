# HERMUS PERSONAL — COMPLETE PRODUCT SPECIFICATION
**Version 1.0 | The horizontal personal-assistant product: the foundation every profession pack sits on**
**Grounded in the shipped build (React + FastAPI + PostgreSQL + Ollama; CEO-Agent planner, approval chains, Second Brain, org chart)**

This document answers, in order, every question raised: what's included, UI alignment, modules, implementation, admin enablement, the working environment, common + enhanced features, how agents work/assign/retry/summarize/store, user-created agents, voice per agent, output storage, and the dashboard. A consolidated Q→A map is in Part 14.

---

# PART 1 — WHAT HERMUS PERSONAL IS

A single-user, voice-first AI assistant that runs **one person's** life and admin: capture, memory, reminders, communication, documents, research, and a small team of agents that quietly do recurring work — all running locally on the user's machine, private by default.

**It is the horizontal base.** Every profession pack (Doctor, CA, Realtor…) = HERMUS Personal + a roster + phrase pack + locked rules + templates. So building Personal well *is* building the foundation of the entire catalog.

**Promise:** *"Talk to it. It remembers everything, handles your admin, and works while you don't — privately, on your machine."*

---

# PART 2 — FEATURES INCLUDED (the complete list)

Tagged: ✅ already in the build · 🔨 extend existing · 🆕 new for Personal.

## 2.1 Capture
- Voice-to-action (speak → agent acts) ✅
- Voice-to-text dictation (speak → polished text into notes/comms; in-app first) 🔨
- Quick capture ("remember this", voice memos) 🆕
- Document/file ingestion (PDF, image, sheet → understood + filed) ✅
- Forward-to-assistant (email/message → read, file, or act) 🔨

## 2.2 Memory (Second Brain — the differentiator)
- Personal knowledge base, voice-searchable ✅
- Contacts & relationship history 🔨
- Preferences/routine memory (tone, habits) 🆕
- Notes & linked second brain ✅
- Smart recall ("what was that restaurant?") ✅
- User-controlled memory: view/edit/forget/export ✅ (MC-04 soft-delete shipped)

## 2.3 Time
- Calendar management by voice 🔨
- Reminders & nudges (appointments, meds, bills, renewals) 🆕
- Recurring routines 🔨 (scheduler exists)
- Deadline/renewal tracking 🆕
- "Plan my day" morning briefing 🆕

## 2.4 Communication
- Draft & send messages/email in user's voice, review-before-send ✅ (comms hub)
- Inbox triage (urgent/action/FYI) ✅
- Follow-up engine 🔨
- Remote command from WhatsApp/Telegram 🆕
- Read-it-to-me + reply by voice 🔨

## 2.5 Documents
- Generate letters/invoices/summaries from templates 🔨 (Document Factory)
- Summarize anything (email/PDF/article) 🔨
- Fill forms from memory 🆕
- Polish/format rough text 🔨

## 2.6 Work-while-you-don't
- Scheduled autonomous tasks 24×7 ✅ (scheduler + CEO-Agent)
- Weekly ROI note ("what I did for you") 🆕

## 2.7 Trust layer (always-on, every plan)
- Local-first privacy ✅
- Backup & restore (encrypted, user-keyed) 🆕 (launch-blocking)
- Approval gates (money/new-contact) ✅ (AC chain shipped)
- 60-second undo/recall 🆕
- "Why did you do that?" explainability 🔨 (audit exists; surface it)
- Honest-AI (never impersonates human) 🆕 (policy + UI)

## 2.8 Proactive/delight layer (later phase)
- Anticipation ("you usually pay this now…") 🆕
- Pattern spotting ("rescheduled 3×…") 🆕
- Gentle personal nudges 🆕
- Notification intelligence (digest vs interrupt) 🆕

---

# PART 3 — MODULES INVOLVED (from the 35-module catalog, Doc 19)

| Module | In Personal? | Role |
|---|---|---|
| M1 Voice Interface | ✅ core | the primary UI |
| M2 CEO-Agent Orchestrator | ✅ core | plans & assigns tasks |
| M3 Agent Roster & Org Chart | ✅ (simplified) | the user's small team |
| M4 Approval Chains | ✅ (single-tier: agent→human) | money/new-contact gates |
| M5 Second Brain | ✅ core | memory + KB |
| M6 Knowledge Graph | ✅ (light) | contacts/entities |
| M7 Messaging Bus | ✅ | agent-to-agent for multi-step tasks |
| M8 Audit Log | ✅ | powers "Why?" + history |
| M9 Subscription/Billing | ✅ | plan enforcement |
| M10 Local-LLM Runtime | ✅ core | private inference |
| M11 Workflow Engine | ✅ (simple recipes) | recurring automations |
| M12 Scheduling | ✅ | 24×7 tasks |
| M13 Communication Hub | ✅ | inbox/drafts |
| M14 Channel Connectors | ✅ (Email + WhatsApp + Telegram) | the personal channels |
| M16 Document Factory | ✅ (light) | letters/summaries |
| M19 Analytics + ROI Ledger | ✅ (personal view) | the value note |
| M24 Rehearsal Mode | ✅ | safe practice/onboarding |
| M25 Import Wizard | ✅ | bring contacts/data in |
| M26 Backup & Restore | ✅ | launch-blocking |
| M27 Eval/Quality Layer | ✅ (background) | no-bad-output guard |
| M31 BYOK | ✅ (optional) | bring your own key |
| M32 Model Gateway tiers | ✅ | Local default / BYO / Managed |
| M33 Remote Command Channels | ✅ | command from phone |
| M34 Glass-Box Console | ✅ (simplified "activity") | watch agents work |
| M_Dictate Voice-Type | 🆕 | the Wispr-style capture |

**Excluded from Personal** (these belong to business editions): M15 Call Center, M17 Receivables, M18 Compliance Calendar, M20 Marketplace (read-only in Personal), M21 Skill Builder (Pro+ only), M22 heavy automation (Pro+), M28 Multi-user/RBAC, M29 Multi-node, M30 Offline-enterprise, M35 Confidential pack. They stay flag-off — turning them on is literally how you graduate a user to an edition.

---

# PART 4 — UI ALIGNMENT (how it's laid out)

## 4.1 The single guiding idea
**One window, three zones, voice everywhere.** A non-technical individual must never feel they're "operating software." The screen is calm; the Voice Orb is always present; everything is reachable by speaking or one click.

```
┌─────────────────────────────────────────────────────────────┐
│  TOP BAR:  "Good morning, Anil"   ·  ▶ Play briefing  ·  ⚙   │
├──────────────┬──────────────────────────────────────────────┤
│              │                                              │
│  LEFT RAIL   │            WORKSPACE (center)                │
│  (simple):   │                                              │
│  • Home      │   The active view: Home dashboard, or a      │
│  • Tasks     │   Task, Conversation, Document, Memory,      │
│  • Messages  │   or an Agent — whatever the user is on      │
│  • Memory    │                                              │
│  • My Agents │                                              │
│  • Activity  │                                              │
│              │                                              │
├──────────────┴──────────────────────────────────────────────┤
│  VOICE ORB (always, bottom-right) + live transcript chip     │
└─────────────────────────────────────────────────────────────┘
```

## 4.2 The screens (kept to ~7 — fewer than any business edition)
1. **Home Dashboard** — briefing card, today's tasks, what agents did, what needs you (Part 13)
2. **Tasks** — everything in flight + history; per-task detail with agent, steps, output
3. **Messages** — unified inbox + drafts (review-before-send)
4. **Memory (Second Brain)** — search your knowledge, see/edit what it knows, drop files in
5. **My Agents** — the user's team: status, what each is doing, each one's summary
6. **Activity** — the plain-language "what happened & why" log (simplified Glass-Box)
7. **Settings** — voice, channels, backup, model source (Local/BYO/Managed), privacy

Plus the **Dictation overlay** (system-wide later) and **Voice Overlay** (full-screen ambient mode) as non-screen surfaces.

## 4.3 Simple/Advanced
One toggle. **Simple** (default): plain words, big buttons, "everything's OK ✅". **Advanced**: raw logs, model/router detail, payloads — *same screens*, more revealed. A non-tech user and their techie nephew share one install.

---

# PART 5 — THE WORKING ENVIRONMENT (the heart of your questions)

> *"How will the working environment look? Will it cover all common features? All enhanced features?"*

The **working environment = the Home Dashboard + the Voice Orb + the always-running agent layer.** It is where the user lives. Yes — it surfaces **all common features** (capture, memory, time, comms, documents, briefing) directly, and **all enhanced features** (proactive nudges, ROI note, explainability, glass-box activity) as *ambient surfaces* rather than separate destinations:

- **Common features** appear as dashboard cards + voice commands (you don't "go to a feature," you ask or glance).
- **Enhanced features** appear *in context*: the proactive nudge appears on Home ("you usually pay this now"); the ROI note appears weekly on Home; "Why?" appears on every task/action inline; the activity stream is one rail click away.

The design rule: **the user accomplishes everything from Home by voice; the other screens are for when they want to look closer.** No feature is buried where a non-technical person can't find it by simply asking "what can you do?"

---

# PART 6 — HOW AGENTS WORK (assignment, execution, per-feature)

> *"How do agents work for specific tasks? Are they assigned automatically? How do they work feature-wise?"*

## 6.1 The default team (auto-provisioned at setup)
HERMUS Personal ships with a small fixed roster so the user never starts empty:
- **Aria — Chief of Staff (CEO-Agent)**: the one the user mostly talks to; plans, assigns, briefs, reports.
- **Scheduler** — calendar, reminders, routines.
- **Inbox** — triage, drafts, follow-ups.
- **Scribe** — dictation, notes, document generation, summaries.
- **Finder** — memory search & research.

(Profession packs add specialists on top; in Personal these five cover the universal needs.)

## 6.2 Automatic assignment (yes — by default)
**The user does not pick agents.** They state a goal; the **CEO-Agent decomposes it into steps and assigns each step to the best-fit agent** by capability — exactly the planner you already shipped (UC-03/04, TC-04). Example:

```
User: "Remind me to pay the electricity bill every month and email me the receipt."
Aria (CEO-Agent) plans:
  → Scheduler: create monthly reminder
  → Inbox: on confirmation, email receipt to user
Assignment is automatic; the user just hears the plan read back and says "yes."
```

The user *can* address an agent directly if they want ("ask Scribe to summarize this PDF"), but they never *have to*. Auto-assignment is the default; direct address is an option.

## 6.3 Feature-wise execution
Each agent executes through the **Tool Execution Framework** (MCP tools) scoped to its grants: Scheduler calls calendar tools, Inbox calls email/WhatsApp tools, Scribe calls document tools, Finder calls memory/search. The CEO-Agent coordinates multi-agent tasks over the **Messaging Bus** (e.g., Finder pulls a fact → Scribe writes it into a letter). Approval rules fire automatically when a step touches money or a new contact.

---

# PART 7 — TRACKING, RETRY, SUMMARIES, OUTPUT, STORAGE

> *"How does the user track each agent? How do agents retry on failure? How do they summarize? Where does the user see summaries? Where is output stored? How are actions stored in the Second Brain?"*

## 7.1 Tracking each agent's work
- **My Agents screen:** each agent card shows live status (Idle/Working/Waiting/Done), current task, and a one-line "doing now."
- **Activity stream:** plain-language feed ("Scheduler set your reminder · 9:02", "Inbox drafted a reply to Ravi — waiting for you").
- **Per-task view:** the task's step timeline shows which agent did which step, with the "Why?" affordance on each.

## 7.2 Retry & self-healing (automatic, bounded)
When a step fails (tool timeout, expired channel token, ambiguous data), the **Self-Healing pattern** applies:
- **Transient** (timeout/network) → auto-retry with backoff, up to 3×.
- **Credential** (e.g., WhatsApp token expired) → pauses, asks the user once: "I need you to reconnect WhatsApp — tap here."
- **Ambiguous data** (ask-don't-guess) → asks the user one crisp question rather than guessing.
- **Hard failure** → marks the task "needs you," surfaces it on Home, never fails silently.
The user sees retries transparently in Activity ("retried twice, then asked you").

## 7.3 Summaries — how & where
- **Per-agent summary:** on each agent's card/detail — "This week: 14 reminders set, 9 emails drafted, 2 waiting for you."
- **Per-task summary:** at task completion, a one-paragraph plain-language result + artifacts.
- **Daily briefing:** Aria's 2-minute spoken summary on Home each morning (overnight results, today, what needs you).
- **Weekly ROI note:** "what I did for you this week" — the retention feature — on Home + optionally to WhatsApp.
**Where the user sees them:** Home (daily/weekly), My Agents (per-agent), Tasks (per-task). Three altitudes of the same truth.

## 7.4 Output & storage — on the user's machine
**Yes — all output is stored locally.** Generated documents, drafts, notes, and task results live in the local store on the user's machine (local PostgreSQL + a local files folder). The cloud plane never receives them (privacy invariant). The user can open, export, or share any output; backups go to *their* chosen destination with *their* key (Part 2.7).

## 7.5 How actions are stored in the Second Brain
Every completed task writes to **Operational Memory** (one of the four memory classes already in the build): what was asked, the plan, which agents acted, the outcome, and links to artifacts. This is why the assistant gets smarter — "you did this last month, want the same?" — and it feeds the proactive layer. Entities touched (contacts, bills, documents) are linked in the Knowledge Graph. All of it is local, searchable by voice, and user-editable/forgettable.

---

# PART 8 — USER-CREATED AGENTS, SUB-AGENTS & CUSTOM TASKS

> *"Can the user create more agents and sub-agents, define their own tasks, and assign them?"*

**Yes — with a deliberate simplicity ceiling in Personal:**
- **Create an agent** by voice/wizard: "Make me an agent that watches my favorite sites for deals." Name, what it does, when, which tools — read back, confirm. (The Hire Wizard you shipped, simplified.)
- **Sub-agents / delegation:** the CEO-Agent already delegates; a user-made agent can be allowed to call others (`can_delegate`) for multi-step jobs. In Personal we cap delegation depth low (e.g., 3) to keep it understandable and cost-bounded.
- **Custom tasks & assignment:** the user defines a task and either lets Aria auto-assign (default) or pins it to a specific agent ("Scribe handles all my meeting notes").
- **Where the power tools live:** full **Skill Builder** (record/describe new skills) is a **Pro** feature, not free — in free Personal the user creates agents from presets and simple parameters; building brand-new *skills* from scratch is the upsell. This is both a simplicity guard and a monetization lever.

---

# PART 9 — VOICE PER AGENT

> *"How does voice command work with each agent?"*

- **One wake word, many ears:** "Hey HERMUS" reaches Aria (the orchestrator) by default; the user can address any agent by name ("Hey HERMUS, ask Scribe…" or just "Scribe, summarize this").
- **Each agent can have its own voice** (TTS), so replies are distinguishable — optional in Personal, on by default in Pro.
- **The flow per command:** wake → STT → intent + entity resolution (uses Knowledge Graph to resolve "my accountant", "the gas bill") → route to the right agent (or CEO-Agent to plan) → confirm if sensitive → execute → spoken result. Barge-in supported (interrupt the assistant mid-sentence).
- **No voice-only dead ends:** everything voice does is also clickable; everything spoken can be shown with "show me."

---

# PART 10 — IMPLEMENTATION (how it's built on what exists)

1. **It's a configuration, not a fork.** HERMUS Personal = the existing codebase with the Part-3 module flag-set, the 5-agent default roster seeded, the 7-screen simplified shell, and a "Personal" edition skin.
2. **Reuse the shipped engine:** CEO-Agent planner, approval chains, Second Brain, scheduler, comms hub, audit, Ollama runtime — all already real. New work concentrates in: the dictation module, the proactive layer, backup/restore, remote-command channels, and the simplified UI shell.
3. **Local-first:** local PostgreSQL (+pgvector in prod) + local files folder; cloud only for identity/billing/entitlements/config (the two-plane split already built).
4. **Model sourcing:** Local (Ollama) default; BYOK and Managed Gateway as options (M31/M32).
5. **Quality gate:** the eval layer runs golden personal-tasks on every model/prompt change; send-time validators ensure no wrong figures/dates leave (universal rule U4).
6. **Build order:** capture+memory+reminders+briefing (the daily-habit core) → comms+documents → proactive+ROI → dictation system-wide overlay. Trust features (backup, undo, approvals, explainability) are in from day one, not bolted on.

---

# PART 11 — ADMIN PANEL ENABLEMENT

> *"How do we enable this from the admin panel?"*

HERMUS Personal is enabled the same way every sub-product is — **through the admin factory you already shipped**, no code deploy:
1. **Define the "Personal" edition** in the Plans/feature-flag editor: the Part-3 module flag-set (on/off per module), the plan tiers (Free / Personal / Pro), and limits (agents, tasks, devices, channels).
2. **Seed the default roster & templates** via the Common Configuration Studio: the 5 default agents, personal phrase pack, starter document templates, default thresholds — each flagged locked / overridable / suggestion.
3. **Set the price book** (Free ₹0 / Personal ₹1,999 / Pro ₹3,999; ×region; BYOK discount) in the Plans editor.
4. **Skin** the edition (name "HERMUS Personal", branding, hidden modules) via the edition theme config.
5. **Publish** as a signed config bundle → desktops pick it up on activation. Toggling a module (e.g., enabling Skill Builder for Pro) is a flag change in this same panel.
The admin can canary the Personal edition to a few users, watch adoption, and roll back if needed — all existing Config-Studio capabilities.

---

# PART 12 — ENHANCED FEATURES (the differentiators to add)

Beyond the universal set, these make HERMUS Personal stand out and fill gaps generic assistants leave:
- **Local-private dictation** (the Wispr-style feature, but on-device) — a daily-habit hook competitors can't match on privacy.
- **Proactive anticipation** — it suggests before you ask, from Operational Memory patterns.
- **Life-admin autopilot** — bills, renewals, subscriptions, document expiries tracked and chased automatically.
- **Personal ROI ledger** — the weekly "here's the time I saved you" note.
- **Rehearsal Mode** — practice with the assistant on fake data before trusting it (confidence-builder for non-tech users).
- **Remote command from your phone** — full assistant access via WhatsApp/Telegram when away.
- **"Why?" everywhere** — total transparency, plain-language, on every action.
- **Honest-AI + wellbeing guards** — never impersonates a human; encourages real human contact (critical groundwork for the eldercare pack later).
- **BYOK** — bring your own model key; your data, your key, your terms.

---

# PART 13 — THE COMPLETE DASHBOARD (with per-task status)

> *"How does the user see the complete dashboard with the status of each task?"*

The **Home Dashboard** is the answer to "how is everything going?" at a glance:

```
┌──────────────────────────────────────────────────────────────┐
│  Good morning, Anil          ▶ Play your briefing (2 min)     │
├──────────────────────────────────────────────────────────────┤
│  NEEDS YOU (2)                                                │
│   • Inbox drafted a reply to Ravi — [Review & send] [Why?]    │
│   • Reconnect WhatsApp to resume reminders — [Fix]            │
├──────────────────────────────────────────────────────────────┤
│  IN PROGRESS (3)                  │  DONE TODAY (7)            │
│   ⟳ Finder: researching insurance │  ✓ Reminder set (bill)    │
│   ⟳ Scribe: drafting summary      │  ✓ Replied to landlord    │
│   ⏸ Scheduler: waiting on calendar│  ✓ Summarized 3 PDFs …    │
├──────────────────────────────────┴───────────────────────────┤
│  YOUR AGENTS                                                  │
│   Aria ●idle  Scheduler ●working  Inbox ●waiting  Scribe ●working │
│   [tap any agent → its tasks + this-week summary]            │
├──────────────────────────────────────────────────────────────┤
│  THIS WEEK (ROI):  31 tasks done · ~6 hours saved  [details] │
└──────────────────────────────────────────────────────────────┘
              Voice Orb ●  "show me what Scribe is doing"
```

**Per-task status** is visible at three levels: the dashboard buckets (Needs you / In progress / Done), the Tasks screen (full list + filters), and the task detail (step-by-step timeline with the responsible agent and "Why?" on each step). Status updates stream live via WebSocket (already in the build: `task.status_changed`, `agent.status`). Nothing requires the user to dig — the dashboard tells them what's done, what's running, and the one or two things that need them.

---

# PART 14 — CONSOLIDATED Q→A MAP

| Your question | Answered in |
|---|---|
| Features included | Part 2, 12 |
| UI alignment | Part 4 |
| Modules involved | Part 3 |
| How implemented | Part 10 |
| Enable from admin panel | Part 11 |
| Working environment look | Part 5 |
| Covers all common features? | Part 5 (yes) |
| Covers all enhanced features? | Part 5, 12 (yes, ambient) |
| How agents work for tasks | Part 6 |
| Agents auto-assigned? | Part 6.2 (yes, by CEO-Agent; manual optional) |
| Track each agent's work | Part 7.1 |
| How agents summarize | Part 7.3 |
| Where user sees summaries | Part 7.3 (Home / My Agents / Tasks) |
| Create agents/sub-agents + own tasks | Part 8 (yes; Skill Builder = Pro) |
| Feature-wise agent execution | Part 6.3 |
| Retry on failure | Part 7.2 |
| How user gets output | Part 7.3, 7.4 |
| Output stored on user's machine? | Part 7.4 (yes, local) |
| Actions stored in Second Brain | Part 7.5 (Operational Memory + KG) |
| Voice command per agent | Part 9 |
| Complete dashboard with task status | Part 13 |

## Cases you didn't ask but should consider (added)
- **Onboarding** — first-run wizard + Rehearsal Mode so a non-tech user reaches first value in minutes (Part 12).
- **What happens offline / cloud down** — full function locally; entitlements cached with grace.
- **Plan limits & upsell** — graceful (archive, never delete); Skill Builder/automation as Pro upsell.
- **Notification fatigue** — digest-vs-interrupt intelligence so proactivity doesn't annoy.
- **Wellbeing/honest-AI** — never impersonates a human; encourages real contact (eldercare-ready).
- **Backup drill** — restore on a new machine from recovery phrase (launch-blocking test).
- **Quality** — eval suite + send-time validators so no wrong output reaches anyone.

---

# PART 15 — BUILD-READY SUMMARY

HERMUS Personal is **~80% configuration of what you've shipped**: the engine, planner, approval chains, Second Brain, scheduler, comms, audit, and local LLM are real. The net-new work is focused — dictation module, proactive layer, backup/restore, remote-command channels, and the simplified 7-screen shell — plus seeding the 5-agent roster and defining the Personal edition in the admin factory. Build the daily-habit core first (capture + memory + reminders + briefing), keep the trust layer on from day one, and HERMUS Personal becomes both a sellable product *and* the proven foundation every profession pack inherits.

# HERMUS PERSONAL — "PERSONAL AI OS" FEATURE ANALYSIS & IMPLEMENTATION PLAN
**Version 1.0 | Mapping the researched 23-module vision (LifeOS/Chief-of-Staff) onto HERMUS architecture**
**Answers the core question: feature-wise engines vs horizontal engines + domain packs**

---

# PART 1 — THE ARCHITECTURE DECISION (read first)

## 1.1 The question
"Should we keep engines feature-wise so the agent calls the specific engine?"

## 1.2 The answer: NO feature-engines. Horizontal engines + domain packs.

**Two ways to build a 23-module product:**

**❌ Feature-Engine model (the trap):**
```
Finance Engine | Travel Engine | Health Engine | Family Engine | ... (×20)
   each re-implements: memory, scheduling, reminders, docs, tools, approvals
   → 20 mini-apps, duplicated logic, drift, painful cross-domain tasks
```

**✅ Horizontal-Engine + Domain-Pack model (what your repo already is):**
```
┌─── HORIZONTAL ENGINES (the real engines — ~8, you have them) ───────────┐
│  CEO-Agent Orchestrator · Second Brain (memory) · Knowledge Graph ·     │
│  Scheduler · Approval Chains · Tool Framework (MCP) · Voice · Audit      │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ every domain uses the SAME engines
   ┌───────────┬───────────┬───┴───────┬───────────┬──────────────┐
 Finance     Travel      Health      Family      Research   ...  (DOMAIN PACKS)
 = persona   = persona   = persona   = persona   = persona
 + tools     + tools     + tools     + tools     + tools
 + KG types  + KG types  + KG types  + KG types  + KG types
```

**A "domain" (Finance, Travel…) is not an engine. It is three data artifacts on the shared engines:**
1. **An agent persona** — instructions + tool grants + (optional) its own voice
2. **A set of tools** — the Tier-1/2/3 functions it's allowed to call (Docs 22–23)
3. **A slice of the Knowledge Graph** — its entity types (Account, Trip, Medication, FamilyMember)

## 1.3 Why this wins (the four reasons)
1. **Cross-domain tasks just work.** "Plan a Europe trip under ₹2 lakh" → CEO-Agent dispatches Travel + Finance + Calendar personas, all calling tools against *one shared brain*. No engine-to-engine glue — the orchestrator you shipped already coordinates this.
2. **Build cost stays flat.** Adding "Health" = write health tools + define a persona + add KG types. Days, not a new subsystem. (This is the same insight that lets one codebase serve 20 industry editions — Doc 19.)
3. **One memory, not 23.** Every domain reads/writes the same Second Brain + KG, so the assistant is *one mind that knows your whole life*, not 23 silos. This is the entire point of "Personal AI OS."
4. **A bug fixed once is fixed everywhere.** Memory, scheduling, approvals, retry, voice — fixed in the engine, every domain benefits.

## 1.4 The proof test
*Can two domains collaborate without special glue between them?* Feature-engines: no. Horizontal + packs: yes. Your repo is already the second model. **The decision is: do NOT add feature-engines — extend the engines you have and express every researched module as a domain pack (persona + tools + KG types).**

---

# PART 2 — MAPPING THE 23 RESEARCHED MODULES ONTO HERMUS

Each researched module is classified as: **ENGINE** (extend a horizontal engine — rare), **PACK** (a domain = persona+tools+KG — most), or **CROSS** (a cross-cutting capability all packs use).

| # | Researched module | HERMUS classification | How it's built |
|---|---|---|---|
| 1 | AI Core (multi-model, routing) | **ENGINE** | Extend M10/M32 Model Gateway: add OpenAI/Anthropic/Gemini providers + routing. You have Ollama + BYOK scaffolding |
| 2 | Voice & Conversation | **ENGINE** | Extend M1 Voice: wake word, continuous mode, multilingual, voice memory search |
| 3 | Personal Memory OS (explicit/implicit/episodic/semantic/procedural) | **ENGINE** | Extend M5 Second Brain with the 5 memory *types* as a typed schema + auto-extraction. Your biggest engine upgrade |
| 4 | Personal Knowledge Graph | **ENGINE** | Extend M6 KG: People/Project/Event/Asset/Document entity types + relations |
| 5 | Universal Search | **ENGINE** | New retrieval engine over local + connected sources (the one genuinely new horizontal engine) |
| 6 | Desktop Agent (OS control) | **CROSS** | M22 computer-control tools (Tier-3 class); any persona can be granted them |
| 7 | Browser Agent | **CROSS** | M22 browser tools (Tier-3, Doc 23 Part 5); shared |
| 8 | Email Agent | **PACK** | persona + email.* tools (Tier-2, Doc 23) + KG(Email) |
| 9 | Calendar Agent | **PACK** | persona + calendar.* tools (Tier-2) + KG(Event) |
| 10 | Meeting Agent | **PACK** | persona + transcription tools + KG(Meeting); needs audio capture |
| 11 | Personal CRM | **PACK** | persona + contact tools + KG(Person) + relationship intelligence |
| 12 | Travel Agent | **PACK** | persona + travel/booking tools + KG(Trip) |
| 13 | Finance Agent | **PACK** | persona + finance tools + KG(Account/Bill/Subscription) |
| 14 | Health Agent | **PACK** | persona + health tools + KG(Medication/Appointment); PII-locked |
| 15 | Learning Agent | **PACK** | persona + learning tools + KG(Course/Note) |
| 16 | Family OS | **PACK** (special) | persona + family tools + KG(FamilyMember); multi-user later |
| 17 | Digital Life Vault | **PACK** | persona + document/OCR tools + KG(Document) + expiry tracking |
| 18 | Goal & Habit | **PACK** | persona + goal/habit tools + KG(Goal) |
| 19 | Research Agent | **PACK** | persona + web/research/report tools |
| 20 | Multi-Agent Ecosystem | **ENGINE** | Already M2 CEO-Agent + M7 Bus — this IS your orchestration; packs plug in |
| 21 | Proactive Intelligence | **ENGINE** | New proactive engine over memory+KG (the differentiator — Part 4) |
| 22 | Digital Twin | **ENGINE** (future) | Style/decision modeling over accumulated memory; long-term |
| 23 | Privacy & Security | **ENGINE** | Already your two-plane local-first + Vault + audit; extend, don't rebuild |

**Result: ~8 engine extensions (mostly you already have), ~12 domain packs (persona+tools+KG each), 2 cross-cutting tool sets.** Not 23 engines. This is the difference between a buildable product and an unmaintainable one.

---

# PART 3 — THE ENGINE EXTENSIONS NEEDED (the real work)

Only these touch the core. Everything else is packs.

## 3.1 Memory OS upgrade (M5) — highest priority
Add the **five memory types** as a typed layer over your existing memory:
```
memory_items.memory_type ∈ {explicit, implicit, episodic, semantic, procedural}
  explicit   — user-stated ("I prefer aisle seats")           [direct write]
  semantic   — facts about the user                            [extracted]
  episodic   — events/experiences, time-ordered                [from actions/calendar]
  procedural — recurring workflows                             [from repeated task patterns → auto-skills]
  implicit   — learned preferences                             [inferred, low-confidence, user-confirmable]
```
- **Automatic memory extraction:** a background job mines emails/chats/files/completed-tasks → proposes memory entries (implicit, flagged for optional confirmation — never silently asserts).
- Preference learning feeds the proactive engine and the digital twin.
- All user-viewable/editable/forgettable (Memory Control Center — you have soft-delete).

## 3.2 Universal Search engine (new horizontal)
One retrieval layer over: local files/notes (you have), + connected sources (Gmail/Drive/Dropbox/Notion/Slack via Tier-2 connectors), + OCR'd documents. Hybrid (keyword+semantic+KG-expansion). "Find the PDF Raj sent about Marketplace migration" → searches across sources, resolves "Raj" via KG, returns the file. Build *after* Tier-2 connectors exist (it depends on them).

## 3.3 Model Gateway upgrade (M10/M32)
Add cloud providers (OpenAI/Anthropic/Gemini) alongside Ollama; capability-tier routing (Fast/Smart/Reasoning/Vision); BYOK key vault per provider (you have the BYOK concept — Doc 19 Part 6). Per-data-class rule: PII/Confidential memory never routed to cloud regardless of setting.

## 3.4 Proactive Intelligence engine (the differentiator)
A scheduled reasoner over memory+KG+calendar that, without being asked, produces: daily briefing, risk alerts (passport/insurance/subscription expiry — from KG asset/document dates), opportunity detection, smart nudges. **This is what makes it an "assistant" not a "tool"** — but it only works once memory+KG are rich, so it comes *after* the foundation, not first. Notification-intelligence (digest vs interrupt) is mandatory so proactivity doesn't annoy.

## 3.5 Voice engine upgrade (M1)
Wake word, continuous conversation mode, multilingual STT/TTS, voice memory search, per-agent voices. (Voice cloning: defer — consent/abuse concerns.)

---

# PART 4 — DOMAIN PACK PATTERN (how you add each of the 12)

Every pack is the **same four files** — this is the repeatable unit:
```
packs/finance/
  persona.yaml       # name, instructions, tone, tool_grants[], default model tier
  tools.py           # finance.* tools (Tier-1/2/3 contract from Docs 22-23)
  entities.yaml      # KG entity types: Account, Bill, Subscription, Budget + relations
  templates/         # finance document templates (expense report, budget summary)
  rules.yaml         # locked rules (e.g., never move money autonomously)
  evals/             # golden tasks for this pack
```
The CEO-Agent discovers the pack's persona + tools; the KG absorbs its entity types; the scheduler runs its routines; approvals/voice/audit apply automatically. **No engine change to add a pack.** This is identical to how industry editions are built (Doc 19) — packs and editions are the same mechanism at different scales.

### Example: Finance pack tools
`finance.import_transactions` (from connected bank/statement), `finance.categorize`, `finance.track_subscription`, `finance.bill_reminder` (→ scheduler), `finance.budget_status`, `finance.spending_insight`, `finance.report` (→ Document Factory). All reuse the wrapper, write Operational Memory, link KG entities. **Money movement: never autonomous — handoff/approval only.**

---

# PART 5 — IMPLEMENTATION SEQUENCE (don't build 23 at once)

The fatal mistake would be building all modules in parallel. Sequence by dependency and value:

## Wave 0 — Foundation (you largely have this; finish it)
Tier-1 internal tools (Doc 22) · Memory OS five-type upgrade · KG entity-type expansion · Model Gateway cloud providers + BYOK · the 5 default agents. **Without this, no pack works.**

## Wave 1 — The daily-life packs (highest use frequency)
Email · Calendar · Personal CRM · Finance (bills/subscriptions/reminders) · Digital Life Vault (documents/expiry). These cover what people do *every day*; they need Tier-2 connectors (Doc 23). **Universal Search** lands here (depends on connectors).

## Wave 2 — The proactive layer (the differentiator)
Proactive Intelligence engine · daily briefing · risk/opportunity detection · smart nudges. Only valuable once Wave-1 data exists. **This is what makes users love it** — but it's earned, not first.

## Wave 3 — The depth packs
Travel · Health · Learning · Research · Goals/Habits · Meeting agent. Each is one pack (persona+tools+KG), added as demand shows.

## Wave 4 — The moat & differentiators
Family OS (multi-user) · Digital Twin (style/decision modeling) · Desktop/Browser automation depth. Highest value, highest complexity, latest.

**Rule:** ship Wave 0 + a slice of Wave 1 as the first real product. A personal assistant that nails email + calendar + finance-reminders + documents + memory, locally and privately, is already better than most of the market. Breadth comes after that proves out.

---

# PART 6 — WHAT TO BUILD vs DEFER (honest calls)

**Build (high value, fits your architecture):** Memory OS upgrade, KG expansion, Email/Calendar/CRM/Finance/Vault packs, Universal Search, Proactive engine, multi-model gateway. These are the spine of "Personal AI OS" and mostly configuration + tools on your engines.

**Defer (real, but premature or risky):**
- **Voice cloning** — consent/abuse/deepfake risk; skip until there's a safe, clearly-consented use.
- **Digital Twin / AI Proxy Mode** — powerful moat, but needs months of accumulated data to be good and raises "acting as me" liability; design the data capture now, build the twin later.
- **Meeting recording** — legal two-party-consent issues per region; ship transcription with explicit consent prompts, not silent recording.
- **Health Agent** — build the vault/reminders/records, but lock it hard: never interprets results or gives medical advice (routing only), PII-locked, local-only. Same care as the clinic edition.
- **Deep desktop/browser automation** — start with prepare-and-handoff (Doc 23 Part 5); add automation recipes opt-in, sandboxed.

**The wellbeing line (applies to the whole product):** never impersonate a human, encourage real human contact, approval-gate anything touching money or sending to new people, and make proactivity respectful (digest, not nagging). These aren't features — they're the conditions for a product that lives this deep in someone's life.

---

# PART 7 — DIRECT ANSWERS

- **"Is feature-wise engines a good way?"** No. Feature-engines duplicate logic and make cross-domain tasks painful. Use **horizontal engines + domain packs** — which your repo already is. Domains are personas+tools+KG-types on shared engines, not separate engines.
- **"How does the agent call the right thing?"** The CEO-Agent plans a task and assigns steps to the persona whose **tool grants** match — it doesn't call an "engine," it picks tools. Cross-domain tasks dispatch multiple personas against one shared brain, coordinated by the orchestrator you already shipped.
- **"How do we implement these 23 modules?"** ~8 engine extensions (most already exist — Parts 3) + ~12 domain packs (the repeatable 4-file pattern — Part 4) + 2 shared tool sets. Sequenced in 5 waves (Part 5), foundation first, proactive layer earned, depth and moat last.
- **"Will it stay maintainable at 23 modules?"** Yes — because there aren't 23 engines, there are ~8 engines and a repeatable pack pattern. Adding a module is adding data (persona+tools+KG), not a subsystem. A bug fixed in an engine fixes all packs.

**One-line architecture verdict:** *Keep your horizontal engines; express every "module" as a domain pack (persona + tools + KG types) on top of them. That's how 23 modules stay one coherent assistant instead of becoming 23 brittle apps.*

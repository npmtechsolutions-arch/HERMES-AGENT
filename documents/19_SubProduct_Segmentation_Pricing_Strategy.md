# HERMUS — SUB-PRODUCT SEGMENTATION, MODULE & PRICING STRATEGY
**Version 1.0 | How the universal HERMUS platform splits into industry sub-products**
**Grounded in the shipped build: React + FastAPI + PostgreSQL + Ollama; CEO-Agent planner, approval chains, Second Brain, org chart, cloud/admin plane (repo: npmtechsolutions-arch/HERMES-AGENT)**

---

# PART 0 — THE SEGMENTATION MODEL (read this first)

## 0.1 What you actually have
HERMUS is a **universal engine** (the 8 universal engines, the CEO-Agent orchestrator, approval chains, Second Brain, comms hub, local-LLM runtime) plus a **template/config layer** the admin plane already controls (Common Configuration Studio with locked/overridable/suggestion scopes, Plans & feature-flag editor with no code deploy). **This is exactly the machinery needed to spin up sub-products without forking code.**

## 0.2 The core principle of sub-products
**A "sub-product" is NOT a new codebase. It is a packaged configuration of the one platform:**

```
SUB-PRODUCT = curated agent roster
            + enabled modules (feature flags)
            + industry templates, workflows, document templates
            + phrase pack + entity types (Knowledge Graph)
            + locked rules (safety/compliance)
            + a price book
            + its own branding/onboarding skin
```

Everything on the left is **data and flags your admin plane already serves.** That means each sub-product costs *days of configuration*, not months of engineering — the whole reason this strategy works. The discipline that keeps it true: **no sub-product is allowed to require a code change in the universal core.** If it does, the capability belongs in the core (behind a flag), not in the sub-product.

## 0.3 The three packaging layers (how a buyer experiences it)
1. **HERMUS Universal** — the full platform; for users who want everything and will configure it themselves (power users, agencies, enterprises). Highest price, widest scope.
2. **HERMUS Industry Editions** — pre-packaged verticals (Real Estate, Clinic, CA, Legal…). Buyer sees only their industry's agents, words, workflows, and screens. Mid price, fastest time-to-value. **This is the primary revenue engine.**
3. **HERMUS Role Apps** — ultra-focused single-role products for individuals (Doctor's Assistant, Developer's Assistant, Engineer's Assistant). Lowest price, self-serve, highest volume, lowest support. The top-of-funnel and the consumer/prosumer play.

A buyer can start at layer 3 (cheap, personal), graduate to layer 2 (their business), and large accounts land at layer 1. **Same engine throughout — upgrades are flag changes, not migrations.**

---

# PART 1 — HOW MANY SUB-PRODUCTS (and which to build, in order)

You can technically create *dozens*; you should *launch few and sequence the rest by demand*. Below is the full catalog with a build-priority tier.

## 1.1 Industry Editions (layer 2) — business sub-products

| # | Edition | Primary buyer | Build tier | Why |
|---|---|---|---|---|
| 1 | **HERMUS RealEstate** | Brokerages, developers | **Wave 1 (flagship)** | Document- & comms-heavy; highest ticket; your Doc 13 deep-dive exists |
| 2 | **HERMUS CA/Accounting** | CA & accounting firms | **Wave 1** | Already your seeded persona (Mehul); deadline-driven; multi-client leverage |
| 3 | **HERMUS Clinic** | Clinics, dental, diagnostics | **Wave 1** | Call-center showcase; privacy is the moat; recurring reminders |
| 4 | **HERMUS Legal** | Law firms, advocates | Wave 2 | Dictation-native users; document-heavy |
| 5 | **HERMUS Agency** | Marketing/digital agencies | Wave 2 | SaaS-native buyers; per-client multi-tenancy |
| 6 | **HERMUS Retail** | Shops, D2C, e-commerce | Wave 2 | High volume; order/return flows |
| 7 | **HERMUS Manufacturing** | SME factories | Wave 3 | Offline-mode showcase; regional-language |
| 8 | **HERMUS Education** | Schools, colleges, coaching | Wave 3 | Seasonal admission surges |
| 9 | **HERMUS Recruitment** | Staffing agencies | Wave 3 | Screening + scheduling |
| 10 | **HERMUS Hospitality** | Hotels, restaurants | Wave 3 | Reservation/concierge (matches your hotel example) |
| 11 | **HERMUS Logistics** | Fleet, transport SMEs | Wave 4 | Document-expiry + dispatch |
| 12 | **HERMUS Finance/NBFC** | Lenders, brokers | Wave 4 | Collections + compliance heavy |

## 1.2 Role Apps (layer 3) — individual sub-products

| # | Role App | Buyer | Build tier | Core promise |
|---|---|---|---|---|
| R1 | **HERMUS for Doctors** | Individual physicians | **Wave 1** | "Your AI front desk + dictation + recall — private, on your machine" |
| R2 | **HERMUS for Developers** | Software engineers | **Wave 1** | "Your AI dev-ops chief of staff: PRs, issues, standups, docs, 24x7 agents" |
| R3 | **HERMUS for Engineers** (civil/mech/site) | Engineers, contractors | Wave 2 | "Site reports, vendor follow-ups, drawings & docs by voice" |
| R4 | **HERMUS for Consultants** | Solo consultants | Wave 2 | "Proposals, follow-ups, research, invoicing — your back office" |
| R5 | **HERMUS for Lawyers (Solo)** | Individual advocates | Wave 2 | "Dictate drafts, track hearings, chase fees" |
| R6 | **HERMUS for Creators** | Content creators | Wave 3 | "Content calendar, scripts, comments, sponsorship outreach" |
| R7 | **HERMUS for Realtors (Solo)** | Independent agents | Wave 3 | "Answer leads in 5 min, follow up forever, book visits" |
| R8 | **HERMUS for Accountants (Solo)** | Freelance accountants | Wave 3 | "Client doc-chase, GST calendar, reconciliations" |

## 1.3 Recommended launch set (don't build all 20 — build 6)
**Wave 1 (next 2 quarters):** RealEstate, CA/Accounting, Clinic (editions) + Doctors, Developers (role apps). Plus **HERMUS Universal** for the power/agency/enterprise tail.
Six sellable SKUs from one codebase. Everything else is a configuration you add when a paying lead asks for it — **demand-pull, not build-push.**

---

# PART 2 — MODULE CATALOG (the building blocks every sub-product is assembled from)

Your platform's capabilities, expressed as **toggleable modules**. A sub-product = a subset of these modules switched on via the admin Plans/feature-flag editor.

## 2.1 Universal Core Modules (present in every sub-product — the engine)
| M# | Module | Already built? |
|---|---|---|
| M1 | Voice Interface (orb, push-to-talk, STT/TTS, intent) | ✅ (Web Speech now; native STT/TTS productionizing) |
| M2 | CEO-Agent Orchestrator (task decomposition, assignment) | ✅ |
| M3 | Agent Roster & Org Chart (hire, status, reporting lines) | ✅ |
| M4 | Approval Chains (tiered, decision trails) | ✅ |
| M5 | Second Brain (typed memory, ingestion, hybrid search) | ✅ |
| M6 | Knowledge Graph (entities + relations) | ✅ |
| M7 | Agent Messaging Bus | ✅ |
| M8 | Audit Log (append-only, both planes) | ✅ |
| M9 | Subscription/Billing/Entitlements | ✅ |
| M10 | Local-LLM Runtime + routing (Ollama) | ✅ |

## 2.2 Functional Modules (mixed on/off per sub-product & plan)
| M# | Module | Notes |
|---|---|---|
| M11 | Workflow Engine + voice-to-workflow | ✅ shipped |
| M12 | Scheduling/Autonomous tasks (cron) | core |
| M13 | Communication Hub (unified inbox, triage, drafts) | ✅ |
| M14 | Channel Connectors (WhatsApp, Email, Telegram, SMS, Slack…) | per edition |
| M15 | AI Call Center (inbound/outbound voice) | premium add-on |
| M16 | Document Factory (templates → validated docs: PDF/DOCX/XLSX/PPTX) | per edition templates |
| M17 | Receivables/Collections engine | finance-heavy editions |
| M18 | Compliance Calendar (statutory dates + alerts) | per edition (RERA/GST/licenses) |
| M19 | Analytics + ROI Ledger | all; depth varies by plan |
| M20 | Marketplace (install agents/skills/templates) | all |
| M21 | Skill Builder / Auto-Skill Capture | Pro+ |
| M22 | Browser & Computer Automation | Pro+ |
| M23 | Integrations (CRM/ERP/Accounting via MCP) | per edition |
| M24 | Rehearsal Mode (simulated practice) | onboarding/all |
| M25 | Import Wizard (messy data onboarding) | all |
| M26 | Backup & Restore (encrypted, user-controlled) | all (launch-blocking) |
| M27 | Eval/Quality Layer (golden tasks, validators) | all (background) |
| M28 | Multi-User RBAC + Department Isolation | Business+/enterprise |
| M29 | Multi-Computer Agent Network | Enterprise |
| M30 | Offline Enterprise Mode | Enterprise |
| M31 | BYOK — Bring Your Own Key (LLM keys) | cross-cutting (Part 6) |
| M32 | Model Gateway tiers (Local / BYO / Managed cloud) | cross-cutting |
| M33 | Remote Command Channels (command agents from WhatsApp/Telegram) | all (high UX value) |
| M34 | Glass-Box Agent Console (watch agents work) | Pro+ |
| M35 | Confidential/Tamper-evident compliance pack | Enterprise/regulated |

**That's 35 modules.** Each sub-product's spec below is just "which of these 35 are ON, and with what industry data."

---

# PART 3 — SUB-PRODUCT SPECIFICATIONS (modules + features, product-wise)

For each: the agent roster (what the buyer sees), modules ON, the standout features, and the **enhanced/gap-filling features** unique to that edition.

## 3.1 HERMUS RealEstate
**Agents:** Lead Qualifier, Property Recommendation, Follow-Up, Site Visit Coordinator, Proposal/Document, Loan Assistance, CRM/Lifecycle, Collections (milestone billing), Compliance (RERA), Channel-Partner, Market Intelligence, Voice Receptionist, CEO/Briefing.
**Modules ON:** M1–M14, M16–M20, M23, M24–M27, M33; +M15 Call Center (add-on), +M28 for multi-branch.
**Standout features:** speed-to-lead (5-min response), site-visit route optimization + reminders, construction-linked **payment-milestone billing** with escalating demand letters, RERA quarterly-report autopilot + ad-compliance gate, channel-partner commission automation.
**Enhanced / gap-filling features:** unit-level inventory by voice ("how many 3BHKs unsold in Tower B?"), NRI buyer track (timezone-aware + POA checklist), loan-file stage tracker across banks, possession snagging workflow, **rental & society management** premium pack (recurring revenue most RE tools miss).

## 3.2 HERMUS CA/Accounting
**Agents:** Document Collector, Bookkeeping, GST Specialist, TDS, IT-Filing, Auditor, Reconciliation, Client Reminder, Billing — CEO/Briefing (your seeded Aria).
**Modules ON:** M1–M13, M16–M19, M23 (Tally/Zoho), M24–M27, M33; +M28 multi-staff.
**Standout features:** multi-client compliance calendar ("what's due in 7 days across all clients?"), document-chase sequences, OCR→ledger drafts, variance-gated filings (Auditor before partner), fee receivables.
**Enhanced / gap-filling:** notice-handling (client forwards tax notice → deadline + draft reply), per-client confidentiality walls, source-citation enforced on every figure (the trust feature competitors skip), **"exceptions-only" partner dashboard** — partner sees only what needs a human, the rest runs silent.

## 3.3 HERMUS Clinic
**Agents:** Front-Desk/Patient Coordinator, Appointment, Recall/Preventive-care, Billing & Insurance, Pharmacy Inventory, Lab Coordination, Feedback — CEO/Briefing.
**Modules ON:** M1–M16 (incl. **M15 Call Center** as the hero), M18–M19, M24–M27, M33; PII-lock hardened.
**Standout features:** 24x7 voice booking, no-show reduction (confirm + reminder + waitlist backfill), recall engine, insurance pre-auth tracker, end-of-day reconciliation by voice.
**Enhanced / gap-filling:** **locked safety rules** — AI never communicates diagnoses/results without practitioner release; privacy-safe reminder phrasing (no condition names on shared channels); lab-loop closure (result → doctor release → patient). These locked rules are a *selling point* (regulatory safety), and a genuine gap in generic bots.

## 3.4 HERMUS for Doctors (Role App)
**Scope:** a single physician's personal back office — not a clinic's multi-user system.
**Agents:** Front Desk (calls/WhatsApp), Dictation/Notes, Recall, Billing — light CEO/Briefing.
**Modules ON:** M1–M6, M13, M15 (call answering — the headline), M16 (letters), M19, M24–M27, M31 BYOK option.
**Standout features:** "answer my phone when I'm with a patient," voice dictation → structured note, follow-up reminders, simple daily briefing.
**Enhanced / gap-filling:** **personal privacy framing** ("patient data never leaves your laptop") as the entire pitch; works solo without IT; one-tap "I'll call them back" handoff.

## 3.5 HERMUS for Developers (Role App)
**Scope:** an engineer's autonomous dev chief-of-staff — leans into the *original* Hermes coding-agent DNA.
**Agents:** Repo/PR Agent, Issue-Triage Agent, Standup/Reporting Agent, Docs Agent, On-Call/Monitoring Agent, Research Agent — CEO/Orchestrator.
**Modules ON:** M1–M8, M10–M12, M21 Skill Builder, M22 automation, M23 (GitHub/GitLab/Jira via MCP), M31 BYOK (devs *want* their own keys), M33 (command from Slack/Telegram), M34 Glass-Box.
**Standout features:** "summarize overnight PRs," "triage new issues," "draft the standup," scheduled agents that watch CI and file fixes, voice/Slack command from anywhere.
**Enhanced / gap-filling:** **local-first code privacy** (proprietary code never leaves the machine — unlike cloud coding agents), MCP-native tool attach, auto-skill capture so it learns the team's workflows, CLI-first (you already ship a `cli/`).

*(Legal, Agency, Retail, Engineers, Consultants etc. follow the identical template — roster + module set + 3 standout + 3 gap-filling features. Build the spec when the edition enters its wave.)*

---

# PART 4 — THE "FINEST FEATURES" TO ADD PER SUB-PRODUCT (the differentiators)

These are the high-value features that make each edition feel purpose-built and fill gaps generic competitors leave. They are **mostly configuration of existing modules**, which is the point.

| Edition | The killer feature competitors lack |
|---|---|
| RealEstate | Construction-milestone billing autopilot + RERA ad-compliance gate |
| CA/Accounting | Exceptions-only partner view + source-cited figures (audit-grade trust) |
| Clinic | Locked clinical-safety rules (no AI medical comms) sold as compliance |
| Doctors (role) | Phone-answered-during-surgery + 100% local patient data |
| Developers (role) | Local-first code privacy + MCP-native + learns-your-workflow |
| Legal | Limitation-period sentinel that no AI tier can snooze |
| Agency | Per-client brand-voice training + per-client memory walls |
| Retail | RTO-reduction calling + margin-floor discount blocking |
| Manufacturing | Full offline operation + safety-incident instant alert |
| Education | Multilingual parent comms + minor-data protection rules |

**Cross-cutting finest features (add to all, they lift retention):** ROI Ledger weekly value note (M19), Rehearsal Mode (M24), Backup/Restore (M26), Remote Command Channels (M33), "Why did you do that?" explainability (M34). These are the dual-audience trust features — build once, every sub-product inherits.

---

# PART 5 — PRICING (industry-standard, plan-wise, per sub-product)

## 5.1 Pricing philosophy
- **Anchor to replaced cost, not to features.** Editions replace staff functions → priced higher. Role apps replace personal admin time → priced lower, volume play.
- **Three plans per product** keeps choice simple (good/better/best) + a free or trial entry.
- **Regional price books** (India shown; ×2–2.5 for US/EU per the global model).
- **Call Center, Multi-node, Confidential pack = add-ons**, never bundled (they carry real cost).

## 5.2 HERMUS Universal (layer 1 — the full platform)
| Plan | India /mo | Global /mo | Agents | Key gates |
|---|---|---|---|---|
| Free Solo | ₹0 | $0 | 2 | 1 device, email channel, full voice & local privacy |
| Starter | ₹7,999 | $99 | 5 | 1 device, core modules, no Call Center |
| Pro | ₹14,999 | $199 | 25 | workflows, skill builder, glass-box, 3 devices |
| Business | ₹39,999 | $499 | 100 | multi-user RBAC, isolation, analytics+ |
| Enterprise | custom | custom | ∞ | multi-node, offline mode, confidential pack, SLA |
| Add-ons | Call Center +₹6,000 / Managed Gateway metered / Confidential +₹15,000 |

## 5.3 Industry Editions (layer 2) — RealEstate / CA / Clinic / Legal / Agency…
Editions price ~10–20% above Universal-equivalent tiers because they include the vertical templates, workflows, and compliance packs (more out-of-box value, faster ROI).

| Plan | India /mo | Global /mo | Scope |
|---|---|---|---|
| **Edition Trial (14d)** | ₹0 | $0 | full edition, no card |
| **Solo/Starter** | ₹9,999 | $129 | 1 branch/seat, full vertical roster (≤6 active agents), core channels |
| **Growth/Pro** | ₹19,999 | $249 | up to 5 seats, full roster, workflows, edition compliance pack, 3 devices |
| **Business** | ₹49,999 | $599 | up to 25 seats, multi-branch isolation, analytics+, priority support |
| **Enterprise** | custom | custom | unlimited, multi-node, offline, dedicated success |
| **Edition add-ons** | Call Center (Clinic/RE hero) +₹6–8k · Rental/Society pack (RE) +₹5k · extra branch metered |

## 5.4 Role Apps (layer 3) — Doctors / Developers / Engineers…
Consumer/prosumer pricing — self-serve, high volume, low touch.

| Plan | India /mo | Global /mo | Scope |
|---|---|---|---|
| **Free** | ₹0 | $0 | 1 agent, limited tasks/mo, local only — the funnel |
| **Personal** | ₹1,999 | $29 | full role app, 1 device, BYOK allowed |
| **Pro** | ₹3,999 | $59 | + Call Center (Doctors) / + automation & MCP (Developers), 2 devices |
| **Annual** | 2 months free on Personal/Pro | | prepay lever |

**Why role apps are cheap but lucrative:** near-zero marginal cost (local compute + BYOK), self-serve onboarding (Rehearsal + Import wizards), and they feed upgrades into Editions (a solo doctor's clinic grows → Clinic edition).

## 5.5 Plan-wise feature segregation (the matrix that governs flags)
| Capability | Free | Personal/Starter | Pro/Growth | Business | Enterprise |
|---|---|---|---|---|---|
| Active agents | 1–2 | 5–6 | 25 | 100 | ∞ |
| Voice (full) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Channels | email | +1 | +3 | all | all+custom |
| Workflows | ❌ | basic | ✅ | ✅ | ✅ |
| Call Center | ❌ | add-on | add-on | ✅ | ✅ |
| Multi-user/RBAC | ❌ | ❌ | ❌ | ✅ | ✅ |
| Multi-node/Offline | ❌ | ❌ | ❌ | ❌ | ✅ |
| BYOK (M31) | ✅ (own cost) | ✅ | ✅ | ✅ | ✅ |
| Managed Gateway | ❌ | metered | metered | metered | metered/committed |
| Confidential pack | ❌ | ❌ | ❌ | ❌ | ✅ |
| Backup/Restore | ✅ | ✅ | ✅ | ✅ | ✅ |
| Support | community | email | priority email | Slack 4h | dedicated TAM |

This matrix is literally your admin Plans/feature-flag editor's job — every cell is a flag you already toggle.

---

# PART 6 — BYOK (BRING YOUR OWN KEY) MODEL

## 6.1 What BYOK means here
The tenant supplies their **own LLM provider API key** (OpenAI/Anthropic/Azure/DeepSeek/etc.) or points at their **own local Ollama** — HERMUS orchestrates, the tenant pays the model bill directly. This fits your local-first DNA and removes your biggest variable cost.

## 6.2 The three model-sourcing tiers (M32) — make this explicit in UI
1. **Local (default, green):** Ollama on the tenant's machine. Zero model cost to anyone, fully private. Your differentiator.
2. **BYOK (amber):** tenant's own cloud key. Tenant pays provider directly; HERMUS adds no token margin. Best quality on weak local hardware, tenant controls spend & data terms.
3. **Managed Gateway (amber):** HERMUS-provided metered inference (you resell tokens at margin). Convenience tier for non-technical users who don't want keys.

**Per-data-class rule (sell this hard):** memory tagged PII/Confidential **never leaves Local tier** regardless of agent setting — a guarantee pure-cloud competitors can't make.

## 6.3 BYOK pricing logic
Because BYOK removes your inference cost, price it as **platform-fee software**, not usage:

| Model sourcing | What the tenant pays you | What they pay elsewhere |
|---|---|---|
| Local | full plan price (no model cost anywhere) | nothing |
| BYOK | **plan price − small discount** (you save support/compute, pass some back) OR a dedicated **"BYOK plan"** | their provider bill directly |
| Managed Gateway | plan price + **metered tokens at ~3× marginal cost** | nothing (you handle it) |

### Recommended BYOK packaging
- **BYOK is allowed on every paid plan** (a toggle), AND
- offer a **"BYOK Plan" variant** at ~15–20% lower price than the standard plan, since you carry no token cost and less inference support. Example:
  - Edition Pro (managed/local): ₹19,999 → **Edition Pro BYOK: ₹16,999**
  - Universal Business: ₹39,999 → **Business BYOK: ₹33,999**
  - Role App Personal: ₹1,999 → **Personal BYOK: ₹1,599**
- **Enterprise BYOK** is the default expectation (they bring Azure OpenAI / their own infra) — price on seats/nodes/support, not tokens.

## 6.4 BYOK feature list (what to build/expose)
- Key vault per tenant (M31): add/rotate/revoke provider keys, scoped per agent, stored in the existing Vault (secrets injected as references, never echoed).
- Provider routing + failover (M32): set chains per task profile (BYOK-Claude → local-Qwen fallback).
- Spend visibility for BYOK: show *estimated* provider cost per agent/task even though the tenant pays the provider (so they trust it) — built on the budget-gate estimator you already need.
- Pre-dispatch budget gates apply to BYOK too (protect the tenant's *own* bill).
- "Local-only for sensitive data" enforcement (per-data-class rule) — a checkbox that's also a compliance claim.
- Clear labeling everywhere: every agent card shows its model-sourcing tier (green/amber) and speaks it on assignment ("Maya will use your cloud key — her tasks won't be fully offline. Confirm?").

## 6.5 Why BYOK is strategically right for you
- **Kills your worst cost** (variable LLM spend) → protects margins at low price points, enabling the cheap Role Apps to be profitable.
- **Strengthens the privacy story** (tenant's data, tenant's key, tenant's terms).
- **Removes a sales objection** for enterprises with existing AI contracts.
- **Caps your liability** for model spend and content.

---

# PART 7 — EXECUTION: HOW TO SHIP SUB-PRODUCTS WITHOUT FORKING

1. **One codebase, config-driven editions.** Each sub-product = a signed "Edition Bundle" (roster + flags + templates + rules + phrase pack + price book + skin) delivered through the Common Configuration / Marketplace machinery you already built.
2. **The admin plane is your factory.** Plans/feature-flag editor + Config Studio already let you define a new plan and toggle modules with no deploy — that *is* sub-product creation. Add an "Edition" object that bundles a flag-set + template-set + skin.
3. **Branding skin layer.** Same React app, edition-themed (logo, name, color, hidden modules, edition-specific onboarding copy). A `theme/edition` config, not a new frontend.
4. **Time-to-new-edition target: ≤ 2 weeks.** Roster + entity types + lifecycle stages + workflows + document templates + phrase pack + locked rules + price book. If it takes longer, industry logic leaked into core — fix the leak.
5. **Sequence by demand.** Launch Wave 1 (6 SKUs). Add an edition only when a paying customer asks — the config-driven model means you can say "yes, in two weeks" instead of "that's a roadmap item."
6. **Pricing governance.** All price books live in the Plans editor; regional books are config; BYOK variants are flag-derived discounts. No code owns a price.

---

# PART 8 — SUMMARY ANSWERS (to your 6 questions)

1. **How many sub-products:** ~20 viable (12 Industry Editions + 8 Role Apps) + 1 Universal. **Launch 6** (RealEstate, CA, Clinic, Doctors, Developers, Universal); add the rest demand-pull.
2. **Modules:** **35 modules** (10 universal-core + 25 functional), each a flag. Per-product module sets specified in Part 3.
3. **Features per sub-product:** roster + standout features + gap-filling features per edition (Part 3 & 4); all are configurations of the 35 modules.
4. **Enhanced/gap-filling features:** the per-edition killer features in Part 4 (e.g., RERA milestone billing, clinical-safety locked rules, developer local-code privacy) + the cross-cutting retention five (ROI ledger, rehearsal, backup, remote command, explainability).
5. **Pricing:** three packaging layers with 3–4 plans each + add-ons + regional books (Part 5); plan-wise feature matrix governs flags.
6. **BYOK:** three model-sourcing tiers (Local/BYOK/Managed), BYOK allowed on all plans + discounted BYOK plan variants (~15–20% off), per-data-class local-only enforcement, full key-vault + spend-visibility feature set (Part 6).

**The one-sentence strategy:** *You don't build 20 products — you configure 20 packagings of one product through the admin factory you've already shipped, price each to the staff-cost it replaces, and let BYOK protect the margins so even the ₹1,999 role apps make money.*

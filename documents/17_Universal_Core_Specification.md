# AI OFFICE ASSISTANT — UNIVERSAL CORE SPECIFICATION
**Version 1.0 | The optimum cross-vertical set: build these once, at 100% quality — every industry inherits them**
**Distilled from: Industry Library (13), MVP (16), PRD (02), Conditional (04)**

---

## 1. THE PRINCIPLE

Analysis of all ten verticals (Doc 13) shows ~85% of every industry's value comes from the **same underlying behaviors** wearing different vocabulary. A "lead" is a "patient inquiry" is a "client intake." A "site visit" is an "appointment" is a "hearing" is a "demo class." A "demand letter" is a "fee reminder" is an "invoice chase."

**The optimum strategy:** build the universal layer below to production excellence; let verticals contribute only *words, templates, and thresholds*. A feature that only one industry needs is, by definition, not in this document.

---

## 2. THE 8 UNIVERSAL ENGINES (the product's true core)

| # | Engine | What it does everywhere | RE / Clinic / CA / Agency example |
|---|---|---|---|
| E1 | **Inquiry Pipeline** | Capture from any channel → dedupe → qualify → respond fast → route | Lead / patient inquiry / client intake / RFP |
| E2 | **Follow-Up Sequencer** | Multi-step, multi-channel nurture with stop conditions, opt-outs, and human-pause | Lead nurture / recall reminders / document chase / proposal follow-up |
| E3 | **Appointment Engine** | Slot offering from calendars, confirmations, T-24h/T-2h reminders, no-show recovery, outcome capture by voice | Site visit / consultation / client meeting / hearing prep |
| E4 | **Document Factory** | Template + data + validation (every figure source-cited) + approval gate + send + archive | Proposal / prescription-adjacent letters / GST filing pack / client report |
| E5 | **Receivables Engine** | Invoice/dues tracking → escalating polite reminders → human escalation → reconciliation | Milestone payments / patient billing / fee collection / retainer invoices |
| E6 | **Compliance Calendar** | Recurring statutory/contractual dates → preparation checklists → escalating alerts → evidence archive | RERA QPR / license renewals / GST-TDS dates / contract renewals |
| E7 | **Front Desk** | Inbound voice/WhatsApp/email reception: identify, answer from knowledge, book, route, escalate | Receptionist in every vertical, 24x7 |
| E8 | **Daily Briefing + ROI Ledger** | Morning 2-minute spoken summary + weekly value note ("19 staff-hours replaced") | Identical everywhere — and it is the renewal engine |

Everything in Doc 13's vertical libraries decomposes into these eight. Nothing here is industry-specific; everything here is needed by every industry.

---

## 3. THE UNIVERSAL AGENT ROSTER (7 roles every business hires first)

| Agent | Engine(s) | Universal job description |
|---|---|---|
| **Front Desk Agent** | E7, E1 | Answers every inbound contact within minutes, any hour; identifies the person; answers from knowledge; books; routes |
| **Follow-Up Agent** | E2 | Never lets a conversation die; respects opt-outs; pauses the instant a human steps in |
| **Scheduler Agent** | E3 | Owns the calendar: offers, confirms, reminds, recovers no-shows, captures outcomes |
| **Document Agent** | E4 | Drafts anything from templates with validated data; nothing leaves without its approval stamp chain |
| **Collections Agent** | E5 | Tracks every rupee owed; firm but polite; knows when to hand to a human |
| **Compliance Agent** | E6 | Keeps the statutory calendar; nags with escalating urgency; archives proof |
| **Chief of Staff (CEO) Agent** | E8 + orchestration | Briefs the owner, decomposes big asks, assigns the others, escalates, reports value |

Vertical templates **rename and re-skin** these (Front Desk → "Patient Coordinator"; Collections → "Payment Milestone Agent") and add at most 2–3 truly vertical specialists on top. The optimum default install for ANY business = these 7.

---

## 4. UNIVERSAL DATA MODEL (the KG core every vertical extends)

Six abstract entities cover all verticals; templates add typed attributes, never new structure:

```
PARTY      (person/org: customer, patient, client, vendor, partner)
ITEM       (the thing transacted: property, treatment, service, case, product, course)
ENGAGEMENT (the relationship lifecycle: lead→…→closed; stages template-defined)
EVENT      (appointment, visit, hearing, call — anything with a time)
DOCUMENT   (anything generated or received, with source citations)
MONEY      (invoice, payment, due, commission — anything with an amount)
```

Universal relations: `PARTY engages-in ENGAGEMENT about ITEM`, `ENGAGEMENT has EVENTs/DOCUMENTs/MONEY`. The lifecycle-stage tracker, stuck-stage alerts, and every engine query run on this spine identically in all verticals — which is exactly why the engines are buildable once.

---

## 5. UNIVERSAL RULE SET (the 12 rules every vertical keeps)

| ID | Rule | Why it's universal |
|---|---|---|
| U1 | **Speed-to-response SLA** — new inquiry answered ≤ X min or escalate | Revenue physics in every industry |
| U2 | **No double-texting** — human activity on a thread hard-pauses agent sequences | Trust killer everywhere |
| U3 | **Ask-don't-guess** — low-confidence data is clarified, never invented | One wrong fact ends adoption |
| U4 | **Source-cited figures** — outbound numbers/dates must match a record or the message holds | Money & dates are universal liabilities |
| U5 | **Money gate** — anything mentioning amounts above threshold needs human approval | Universal legal exposure |
| U6 | **New-contact gate** — first outbound to an unknown party needs approval until whitelisted | Anti-mistake, anti-spam |
| U7 | **Opt-out is sacred** — across all channels, permanently, instantly | Law + decency everywhere |
| U8 | **Quiet hours** — no proactive contact outside configured windows (per-region defaults) | Universal etiquette/compliance |
| U9 | **Three-strike escalation** — N unanswered AI attempts → human task, stop automating | Prevents robotic harassment |
| U10 | **Undo window** — outbound queues 60s, recallable by voice | Mistakes recoverable in every vertical |
| U11 | **Destructive ops are human-only** — delete/cancel/refund never auto-approved | Universal blast-radius control |
| U12 | **Everything audited** — five-layer identity chain on every action | Trust, liability, compliance everywhere |

Templates tune thresholds (U1's X, U5's amount) — never disable U2–U4, U7, U10–U12 (`locked_rules`).

---

## 6. UNIVERSAL VOICE GRAMMAR (works on day one in any industry)

The 20 commands that must work identically everywhere — vertical phrase packs add vocabulary, not verbs:

**Status:** "What's pending?" · "What happened today/overnight?" · "Where do we stand with [PARTY]?" · "Play my briefing"
**Action:** "Follow up with [PARTY]" · "Schedule [EVENT] with [PARTY] [time]" · "Draft a [DOCUMENT] for [PARTY]" · "Remind [PARTY] about [MONEY/EVENT]" · "Send it" / "Hold it" / "Stop that message"
**Control:** "Approve / Reject" · "I've got this one" (take over thread) · "Hand it back" · "Pause everything for [PARTY]"
**Knowledge:** "What did we tell [PARTY] about [topic]?" · "Who owes us money?" · "What's due this week?" (compliance + receivables)
**Meta:** "What did you do for me this week?" (ROI ledger) · "That was wrong" (mistake report) · "What can I say?"

---

## 7. UNIVERSAL METRICS (one scoreboard, every vertical)

Owner-facing (the weekly value note): inquiries answered + median response time · follow-ups executed · events booked & kept (no-show rate) · documents produced · money collected vs outstanding · after-hours actions · estimated staff-hours replaced.
Health (internal): validator-block rate (U4 catches) · clarification rate (U3) · human-takeover rate (U2) · sequence opt-out rate · golden-task pass rate.

---

## 8. WHAT THIS MEANS PRACTICALLY

1. **Engineering:** the roadmap after MVP is "harden E1–E8 to excellence," not "add vertical features." Doc 16's MVP already builds E1, E2, E3, E8 and slices of E4/E7 — the universal core IS the MVP grown to completion.
2. **Templates become thin:** a new vertical = entity attributes + lifecycle stages + document templates + phrase pack + thresholds + 2–3 specialist agents. Target: a new vertical authored in **2 weeks**, not a quarter — that's the scaling test of this architecture.
3. **Sales:** demo the 7-agent universal roster generically, then re-skin live into the prospect's industry in front of them ("watch — now it's a clinic"). The re-skin moment is the close.
4. **Quality bar:** because every vertical shares the engines, a bug fixed once is fixed for all industries — and a golden-task suite per engine (Doc 16 GAP-2) protects all verticals simultaneously.

---

## 9. DUAL-AUDIENCE LAYER (one surface, two doors)

The universal core serves owners who never open a settings page and the technical person who set the system up — **on the same screens**. The governing discipline: one interface paradigm with progressive disclosure (voice and recipes on top, workflows and webhooks underneath, CLI/API at the bottom, all describing the same objects). No second "developer console" app, no proprietary scripting language — ever.

### 9.1 Simple/Advanced Mode (first-class, not an afterthought)
- One switch (global in Settings, overridable per screen). **Simple:** plain language, fewer numbers, bigger touch targets, health expressed as "Everything is OK ✅ — 2 things need you." **Advanced:** the same screens additionally expose raw logs, payload JSON, rule IDs, model/router decisions, and CLI hints.
- Same objects, same data, same URLs — so a non-tech owner and their technical helper share one installation without living in two products. Mode is per-user in multi-user installs.
- Default: Simple. The product must be fully operable without ever leaving Simple mode (a Simple-mode-only walkthrough is a release gate).

### 9.2 Recipes (the layer below workflows — E2/E3/E5 pre-packaged)
- One-toggle automations with plain-language names: "Reply to missed calls on WhatsApp" · "Wish customers on their birthdays" · "Chase invoices 7 days after due" · "Confirm tomorrow's appointments every evening."
- Each recipe = a parameterized workflow underneath. **Two doors:** non-tech users toggle and tune 1–2 plain parameters ("how many days after due?"); tech users tap "Open as workflow" to fork any recipe into the full builder.
- Recipes are the graduation path (toggle today → edit a fork next month → author workflows later) and the template authors' unit of shipping: every vertical template expresses its automations as recipes first.
- Governance: recipes obey all universal rules (U1–U12) by construction; a recipe cannot be authored that bypasses a locked rule.

### 9.3 "Why?" Everywhere (explainability as a universal affordance)
- Every agent action — every sent message, booking, reminder, hold — carries a one-tap / one-voice **"Why?"**.
- **Plain answer first:** "I sent the reminder because the invoice was 7 days overdue and your 'Chase invoices' recipe says to." **"Show technical detail" expander:** rule ID, workflow node, source records cited (U4 trail), model used, identity chain.
- Same machinery as the audit log and Glass-Box console — surfaced as a question anyone can ask rather than a screen only admins visit. Voice grammar addition (→ §6): "Why did you do that?" / "Why did you send that to [PARTY]?"

### 9.4 Plain-Language Health ("Is everything okay?")
- Voice/tap question with a mode-appropriate answer. **Simple:** "Yes — all agents running, backup done this morning, WhatsApp connected, 2 approvals waiting." **Advanced (same question):** service states, queue depths, model load, last config version, sync lag.
- Proactive corollary: when something is NOT okay, the system says so in plain language with one suggested action ("WhatsApp disconnected an hour ago — tap to reconnect") rather than a silent red dot. Silence reads as breakage to non-technical owners; specificity reads as competence to technical ones.
- Voice grammar addition (→ §6): "Is everything okay?"

### 9.5 Outbound Webhooks + Zapier/Make Connector
- Every platform event (PARTY created, ENGAGEMENT stage changed, EVENT booked/kept/missed, MONEY received/overdue, DOCUMENT generated, approval decided) can fire a signed outbound webhook (HMAC, retries, dead-letter list). Built on the existing local event bus — thin to implement.
- Official Zapier/Make connectors wrap the webhooks + a minimal action API (create PARTY, start recipe, send approved template).
- **Two doors:** tech users integrate with anything not yet built natively; non-tech users benefit because *their consultant* can wire integrations without touching the core — the ecosystem serves them invisibly.
- Boundary: webhooks carry IDs and metadata by default; payloads containing business content require an explicit per-endpoint consent toggle (privacy invariant preserved by default).

### 9.6 Low-Literacy & Accessibility Mode
- Icon-forward navigation, voice-dominant flows, regional-language defaults (STT/TTS + UI strings), large type, numerals localized, color-independent status (icons + words, never color alone).
- Targets real market reach (factory floors, field sales, first-generation business owners), not edge-case compliance — and it is largely free, because the product is voice-first by design: this mode is mostly *turning screens down*, not building new ones.
- Ships as a one-question onboarding choice ("Prefer talking or typing?") rather than a buried setting.

### 9.7 What This Layer Refuses To Add
A separate developer app · a proprietary scripting language · expert-only features with no Simple-mode representation · Simple-mode features that silently lose data or capability relative to Advanced. The two doors must always open into the same room.

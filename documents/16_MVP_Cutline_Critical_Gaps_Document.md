# AI OFFICE ASSISTANT — MVP CUT LINE & CRITICAL GAPS DOCUMENT
**Version 1.0 | The launch definition: what's IN, what's OUT, and what's newly LAUNCH-BLOCKING**
**Supersedes the release plan in PRD (02) §9 for the first launch. All other documents remain the roadmap.**

---

## 1. THE STRATEGY IN THREE SENTENCES

The product's risk is not missing features — it is unproven demand. Therefore the MVP is **one vertical (Real Estate), one buyer (the 5–50 person developer/brokerage office), one killer workflow (Lead → Follow-up → Site Visit, fully autonomous), operated by voice, running locally**. Success is **10 offices paying and using it daily for 60 days** — every other feature in documents 1–15 waits for that proof.

**The pitch we must prove:** *"Speak to your office. Your leads get answered in 5 minutes, followed up forever, and your site visits schedule themselves — and none of your data leaves your machine."*

---

## 2. MVP SCOPE — WHAT'S IN

### 2.1 The Killer Workflow (the product IS this, end to end)

```
Lead arrives (portal email / WhatsApp / manual voice entry)
  → captured & deduplicated (phone-number match)
  → speed-to-lead: qualification questions sent on WhatsApp within 5 min
  → owner voice-briefed: "New lead: 3BHK, OMR, budget 90L. Reply sent. Hot."
  → follow-up sequences run automatically (day 1/3/7, opt-out respected)
  → interested → site visit offered, slots from calendar, confirmed, reminded (T-24h, T-2h)
  → visit outcome captured by voice in the car → CRM note + next step
  → owner's daily 2-minute voice briefing ties it all together
```

If this loop runs reliably for 60 days in 10 real offices, the company is real. If it doesn't, no other feature would have saved it.

### 2.2 In-Scope Capability List (and nothing more)

| Area | MVP Cut |
|---|---|
| **Agents** | Exactly 4 from the RE template: Lead Qualifier, Follow-Up, Site Visit Coordinator, CEO/Briefing Agent. No hire-wizard creativity — preconfigured, lightly customizable (names, tone, working hours) |
| **Voice** | Wake word + push-to-talk, STT/TTS local, the briefing, task commands for the killer workflow, voice confirmations. ≤2 languages (English + one regional). NO continuous-meeting mode, NO per-agent voices, NO speaker-ID |
| **Channels** | WhatsApp + email + Google Calendar. That's all. NO Slack/Teams/Telegram/SMS/Discord |
| **Memory** | Leads, contacts, properties (simple list with price/location/type), interaction history. Semantic search over these. NO knowledge graph UI, NO document ingestion beyond a property-list spreadsheet import |
| **Approvals** | One human gate: first message to any new contact + anything mentioning money. NO multi-tier AI chains |
| **Workflows** | The 3 shipped workflows (lead intake, follow-up sequence, visit scheduling), editable parameters only (timings, message templates). NO visual builder, NO voice-to-workflow |
| **LLM** | One local model tier chosen by hardware scan (e.g., Qwen 7B/14B via Ollama) + ONE managed-cloud fallback for weak machines (clearly labeled). NO model manager UI, NO multi-runtime |
| **SaaS** | Signup, one paid plan + 14-day no-card trial (Stripe OR Razorpay — one, not both), device activation, basic user dashboard (subscription, devices, download), kill-switch admin tools (suspend, refund, entitlements). NO plans engine UI, NO marketplace, NO config studio (configs shipped as signed static bundles, edited by us in SQL/scripts) |
| **Desktop UI** | 5 screens: Home/briefing, Lead pipeline board, Conversation view, Visit calendar, Settings. Voice Orb everywhere. NO org chart, NO analytics dashboard, NO glass-box console (a simple activity log instead) |

### 2.3 Explicitly OUT (deferred, with the doc that holds the spec)

Org chart & hire wizard (06/D2-D4) · multi-tier approval chains (04 §3) · knowledge graph UI (09 §3.3) · workflow builder & voice-to-workflow (01 F5) · Call Center (01 F8) · marketplace & community (14 G9) · skill builder & auto-skill capture (14 G3) · multi-computer network (01 F10) · enterprise multi-user/RBAC (08 §3.x) · other 9 verticals (13) · model gateway tiers beyond the single fallback (14 G5) · remote command channels (14 G2 — *partially in*: approval quick-replies on WhatsApp ARE in, because the owner is never at a desk) · plugin SDK/MCP public framework (07) · confidential computing & sandbox S2-S5 (15) · offline enterprise mode · mobile app (the WhatsApp command channel is the interim mobile story).

**One deliberate exception pulled INTO MVP from the gap analysis:** WhatsApp approval quick-replies + the daily briefing delivered to the owner's WhatsApp (14 G2, minimal slice). Reason: our buyer lives on their phone at site offices; a desktop-only approval flow would kill the killer workflow in practice.

---

## 3. CRITICAL GAPS — NOW LAUNCH-BLOCKING

These five were missing or under-specified across documents 1–15. For a product holding a business's data and acting on its behalf, they are not enhancements; they are conditions of launch.

### GAP-1 — Local Data Resilience (Backup & Restore)
**Problem:** the privacy architecture concentrates all business data on one machine; a dead disk = the business loses its leads, history, and AI memory. No SMB will (or should) accept that.
**MVP requirement:**
- Automatic encrypted backups (age/AES-256, key derived from a recovery phrase shown ONCE at setup, never stored by us) to the tenant's own destination: a folder/USB, their Google Drive/OneDrive, or a second machine on the LAN. Default: daily full + hourly incremental of the local Postgres + artifacts.
- One-command restore onto a fresh install: enter recovery phrase → full state back (agents, leads, conversations, schedules) ≤ 30 minutes.
- Backup health surfaced in the daily briefing ("Last backup: this morning, 6:14"). A failed backup for 48h is an URGENT voice alert.
- Privacy invariant intact: backups are tenant-destination, tenant-key; we never hold content or keys. (Schema: `backup_jobs`, `backup_destinations`; restore is a first-class onboarding path.)
**Acceptance test:** kill the machine, restore on new hardware from recovery phrase, killer workflow resumes — rehearsed with every pilot customer in week 1.

### GAP-2 — Agent Reliability & Evaluation Layer
**Problem:** nothing verifies agents do a *good* job, only that tasks finish. One wrong price in a WhatsApp message destroys trust permanently.
**MVP requirement:**
- **Golden-task suite:** ~50 canonical scenarios per shipped workflow (lead variants, edge phrasings, regional formats) run automatically on every model/prompt/template change — a release gate, exactly like unit tests. Stored as `eval_cases`, results as `eval_runs`.
- **Output validators at send-time:** every outbound message passes deterministic checks — prices/dates/names must match a source record (CC-03 enforced in code, not convention), template variables resolved, opt-out honored, language matches recipient. Validator failure = message held for human, never sent.
- **Confidence surfacing:** low-confidence extractions (mumbled budget, ambiguous location) are asked back to the lead or flagged to the owner — never silently guessed.
**Acceptance test:** seeded with 200 synthetic leads including 40 adversarial ones, zero factually-wrong outbound messages.

### GAP-3 — Mistake & Recall UX (Liability by Design)
**Problem:** agents WILL err; the product must make errors small, visible, and recoverable — and keep us legally positioned.
**MVP requirement:**
- **Undo window:** outbound messages queue 60 seconds (configurable) before sending; "Hey Office, stop that message" or one tap recalls it. After send: one-tap "send correction" flow with an owner-approved template.
- **Mistake report:** any user can mark an agent action as wrong by voice ("that was wrong"); it pauses the related sequence, files a correction record, and feeds GAP-2's eval suite as a new case.
- **Liability framing:** in-product and contractual: AI drafts, human owns; money-mentioning messages always show "reviewed by [user]" stamps in the audit log; Terms of Service drafted accordingly (get a lawyer before pilot 1, not after).
**Acceptance test:** wrong-price scenario → recall within window, correction sent, sequence paused, eval case created — under 90 seconds, by voice.

### GAP-4 — Human Handoff & Clarification as a First-Class Flow
**Problem:** the difference between "delightful" and "infuriating" autonomy is what happens when the agent is unsure or the human must take over.
**MVP requirement:**
- **Ask-don't-guess:** agents hitting ambiguity send ONE crisp question to the owner's WhatsApp/voice ("Kumar asked about registration charges — should I quote the standard 7.5% or have you call him?") with tap/voice answers; unanswered in N hours → safe default = do nothing + briefing mention.
- **Take-over handle:** "I've got this one" on any conversation instantly silences the agent on that thread (and ONLY that thread), with a "hand back" action. The agent summarizes context when handing over and resumes sequences only when told.
- **No double-texting ever:** human reply on a thread auto-pauses agent sequences on it (hard rule, validator-enforced).
**Acceptance test:** owner and agent interleave on one lead thread for a week with zero duplicate/conflicting messages.

### GAP-5 — ROI Ledger (the Renewal Engine)
**Problem:** "hours saved" is a vanity metric buried in analytics; renewals need a felt, weekly number.
**MVP requirement:**
- Every completed agent action logs a value entry: response-time saved, follow-ups executed, visits scheduled, after-hours actions (the 11pm lead answered in 4 minutes).
- **Weekly value note** to the owner (WhatsApp + briefing): "This week: 34 leads answered in avg 4 min, 61 follow-ups, 9 site visits booked, 14 after-hours responses. Estimated staff-time replaced: 19 hours." Conservative math, methodology one tap away — credibility over flattery.
- Renewal screens & emails lead with the cumulative ledger.
**Acceptance test:** pilot owners can state, unprompted, what the product did for them last week. If they can't, the ledger has failed regardless of dashboards.

---

## 4. BUILD SEQUENCE (16 WEEKS TO PILOT)

| Phase | Weeks | Deliverable | Gate to proceed |
|---|---|---|---|
| P0 Spike | 1–2 | Voice loop (wake→STT→intent→TTS) + WhatsApp send/receive + local Postgres, on reference hardware | Command-to-speech < 2s; WhatsApp round-trip works |
| P1 Workflow core | 3–6 | Lead intake + dedupe + qualification + follow-up engine + validators (GAP-2 send-time checks) | 200-synthetic-lead test passes, zero bad sends |
| P2 Trust layer | 7–9 | Backup/restore (GAP-1), undo/recall (GAP-3), handoff (GAP-4), audit log | Kill-machine restore drill passes; interleaving test passes |
| P3 Visits + briefing | 10–11 | Calendar slots, reminders, visit-outcome voice capture, daily briefing, ROI ledger v1 (GAP-5) | Full killer-workflow demo, voice-only, no keyboard |
| P4 SaaS minimum | 12–13 | Signup→pay→download→activate, entitlements, suspend/refund admin scripts, installer + auto-update | New machine: signup→first voice task ≤ 15 min |
| P5 Pilot hardening | 14–16 | Golden-task suite to 50 cases, onboarding script, recovery-phrase ceremony, support runbook | Internal team runs a fake brokerage on it for 2 weeks |
| **Pilot** | 17+ | 10 design-partner offices, founder-led onboarding, weekly value notes | See §5 |

Team-sizing reality: this is ~3–4 strong engineers + 1 founder doing sales/onboarding. If the team is smaller, stretch the timeline — do not cut GAP-1/2/3.

## 5. PROOF METRICS (what "validated" means)

| Metric | Target at day 60 of pilot |
|---|---|
| Offices still using it daily (10 started) | ≥ 7 |
| Leads touched by agents / office / week | ≥ 25 |
| Speed-to-lead (median, automated) | ≤ 5 min (vs their baseline, measured in week 0) |
| Factually-wrong outbound messages | 0 (GAP-2 standard) |
| Owners paying full price post-pilot | ≥ 6 of 10 |
| Owner can state last week's ROI unprompted | ≥ 8 of 10 |
| Restore drill success | 10 of 10 |

**Kill/pivot criteria (decided in advance, honestly):** if ≤3 offices remain daily-active at day 60, or owners won't pay even at half price, the vertical or the form factor is wrong — revisit before building anything from the roadmap docs.

## 6. WHAT HAPPENS AFTER PROOF (the unlock order)

1. **V1.0:** widen RE template (proposal/booking docs, payment-milestone reminders — Doc 13 UC-RE-13/14), CA/Accounting vertical (Doc 13 §3.3), instant-start onboarding polish (Doc 14 G1), free Solo tier (G4).
2. **V1.5:** workflow builder + voice-to-workflow, auto-skill capture (G3), glass-box console (G6), marketplace seed, mobile companion.
3. **V2.0:** Call Center, enterprise multi-user, multi-node, model gateway tiers — then the multi-tenancy/sandbox program (Doc 15) as hosted features arrive.

Every deferred item already has a spec; nothing is lost by cutting it now. The documents are the map; the MVP is the first step that proves the map is worth walking.

---

## 7. MVP-ADJACENT ADDITIONS (dual-audience features promoted into the launch window)

Two features were identified after the original cut as serving both technical and non-technical users at the moment of adoption. Both attack day-one barriers, so they join the MVP scope — sized minimally.

### GAP-6 — Rehearsal Mode (confidence before autonomy)
**Problem:** the #1 adoption barrier for autonomy is fear of the first mistake. Owners won't hand their real leads to agents they've never watched work; technical users have no staging environment to test changes safely.
**MVP requirement:**
- A sandbox toggle that runs the entire killer workflow against **simulated contacts**: a built-in cast of fake leads (eager, rude, haggling, silent, off-topic) message in over a simulated channel; agents qualify, follow up, and book exactly as in production — nothing real is ever sent (hard-enforced: rehearsal mode swaps the channel layer for a simulator; validators verify zero real egress).
- The owner can play any contact ("let me be the angry customer") by voice or chat and watch the agent respond live.
- **Two doors:** non-tech users get "Watch your AI team practice" during onboarding (rehearsal is step 3 of setup, before connecting real WhatsApp); tech users get the same mode as a staging environment — edit a message template or threshold, replay the simulated cast, diff the outputs.
- Rehearsal transcripts feed GAP-2's eval suite (the simulated cast IS the seed of the golden-task suite — one build, two purposes).
**Acceptance test:** a new owner, unprompted, lets agents go live on real channels after ≤30 minutes of rehearsal; zero real messages sent during any rehearsal session.

### GAP-7 — Business Data Import Wizard (no empty-brain day one)
**Problem:** every real customer starts with a messy Excel of leads, phone contacts, WhatsApp exports, and old accounting data. Without import, day one begins with an empty Second Brain — which kills the demo and delays time-to-value past the trial window.
**MVP requirement:**
- Accepts: XLSX/CSV (leads/contacts), Google/phone contact exports (vCard/CSV), WhatsApp chat export (.txt) for history seeding. (Tally/CRM imports deferred to V1.0.)
- **Conversational mapping:** the assistant inspects columns and asks, by voice or tap, "This column looks like phone numbers — correct?" / "Is 'Anil 3bhk omr' a name plus requirements? I'll split it." Dedupe on phone/email with merge preview. Confidence-flagged rows go to a review list, never silently guessed (rule U3 applies to imports too).
- Output: populated PARTY/ENGAGEMENT records with lifecycle stages inferred where safe ("last contacted 8 months ago" → cold), ready for the killer workflow within minutes of install.
- **Two doors:** non-tech users experience drop-file-and-answer-questions magic; tech users get the explicit column-mapping table, a downloadable error report, and a documented CSV schema for clean re-imports.
**Acceptance test:** a realistic dirty file (500 rows, 12% duplicates, mixed formats, two junk columns) imports in ≤10 minutes of user attention with zero wrong-number records created.

**Build-sequence impact (§4):** GAP-7 lands in P2 (it is part of onboarding trust); GAP-6 lands in P3 (it requires the workflow core to exist) and becomes step 3 of the pilot onboarding script in P5. Timeline absorbs +1 week in P2 and +1 week in P3 — accept the slip; both gaps repay it in pilot conversion.

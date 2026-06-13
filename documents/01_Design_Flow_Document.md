# AI OFFICE ASSISTANT — DESIGN FLOW DOCUMENT
**Version 1.0 | Voice-First AI Workforce Platform**

---

## 1. PURPOSE

This document defines all user interaction flows for AI Office Assistant. Because the product is **voice-first**, every flow is defined in two parallel tracks:

- **Voice Track (Primary)** — how the flow executes through spoken interaction
- **Visual Track (Secondary)** — how the same flow appears on screen for confirmation, review, and fallback

Design Principle: **"The screen confirms what the voice commands."** The UI is a mirror of voice activity, never a prerequisite for it.

---

## 2. GLOBAL VOICE INTERACTION MODEL

### 2.1 Voice States

| State | Description | Visual Indicator |
|---|---|---|
| Sleeping | Wake-word listener active only | Dim orb, gray |
| Listening | Capturing user speech (STT active) | Pulsing orb, blue |
| Thinking | Intent parsing + LLM processing | Rotating orb, purple |
| Speaking | TTS playback of response | Waveform orb, green |
| Acting | Agent executing tools/tasks | Progress orb, orange |
| Confirming | Awaiting voice confirmation (yes/no) | Amber orb + on-screen card |
| Error | STT/intent/execution failure | Red orb + spoken fallback |

### 2.2 Wake & Address Model

- Global wake word: **"Hey Office"** (user-customizable)
- Direct agent addressing: **"Hey Office, ask the Accountant…"** or **"Hey Riya…"** (agent names act as sub-wake-words once registered)
- Push-to-talk hotkey: configurable (default `Ctrl+Space`)
- Continuous meeting mode: always-listening session with explicit start/stop commands

### 2.3 Universal Voice Grammar

Every flow supports these global utterances at any point:

- "Cancel" / "Stop" → abort current flow
- "Repeat" → replay last TTS output
- "Show me" → push current context to screen
- "Who is doing this?" → speak active agent + status
- "Escalate to CEO" → route to CEO Agent
- "Save this to memory" → write to Second Brain
- "Approve" / "Reject" → resolve pending approval

---

## 3. FLOW 1 — FIRST-TIME ONBOARDING (VOICE-GUIDED)

```
App Launch (first run)
   ↓
Welcome Screen + TTS greeting: "Welcome. I'll set up your AI company. May I ask a few questions?"
   ↓
Voice Q&A Wizard:
   1. "What is your name?"            → Personal Memory
   2. "What is your business called?" → Business Memory
   3. "What industry are you in?"     → Industry Template suggestion
   4. "What language do you prefer?"  → Voice locale setting
   ↓
Hardware Scan (automatic)
   - Detect GPU / VRAM / RAM / CPU
   - GPU Resource Manager proposes model tier (e.g., "Your machine can run Qwen 14B locally.")
   ↓
Model Download Flow
   - Voice: "Shall I download the recommended models? It is about 9 GB."
   - User: "Yes" → background download with spoken progress milestones
   ↓
Industry Template Selection
   - Voice: "Based on 'law firm', I suggest the Law Firm Template with 6 agents. Want to hear them?"
   - User confirms → Org auto-created (departments + agents + workflows)
   ↓
Voice Calibration
   - Wake word test → mic level test → optional voice-print enrollment (speaker ID)
   ↓
First Task Suggestion
   - "Try saying: 'Hey Office, summarize this document' or 'Create my first task.'"
   ↓
Dashboard (Org Chart view)
```

**Exit criteria:** ≥1 department, ≥1 agent, working wake word, default LLM loaded.

---

## 4. FLOW 2 — CREATE AN AI EMPLOYEE (VOICE)

```
User: "Hey Office, hire a new employee."
   ↓
CEO Agent (voice): "What role should I hire for?"
User: "A social media manager for the marketing department."
   ↓
System drafts Agent Profile (name, designation, dept, objectives, default skills)
   ↓
Voice readback: "I propose 'Maya, Social Media Manager, Marketing. Skills: content
calendar, post drafting, analytics. Tools: browser automation, image folder access.
Model: Gemma 9B.' Confirm, edit, or cancel?"
   ↓
[Confirm] → Agent instantiated → appears on Org Chart with "Idle" status
[Edit]    → field-by-field voice editing ("Change the model to Qwen", "Add WhatsApp tool")
[Cancel]  → discard draft
   ↓
Optional: "Should Maya report to the Marketing Head?" → Reporting line set
   ↓
Optional Training: "Do you want to train Maya now?" → FLOW 6 (Agent Training Center)
```

---

## 5. FLOW 3 — VOICE TASK ASSIGNMENT & EXECUTION

```
User: "Hey Office, prepare the monthly GST report and email it to my CA by Friday."
   ↓
Intent Layer extracts: {task: GST report, agents: Finance, deadline: Friday,
                        post-action: email, recipient: "my CA" → resolved via Knowledge Graph}
   ↓
CEO Agent decomposes:
   Subtask 1 → Accountant Agent: compile transactions (Tally integration)
   Subtask 2 → GST Specialist: prepare GSTR summary
   Subtask 3 → Auditor Agent: verification pass
   Subtask 4 → Email tool: send to CA contact
   ↓
Voice plan readback: "Here's my plan… 4 steps, 3 agents, estimated 20 minutes. Proceed?"
   ↓
User: "Proceed."
   ↓
Execution (Agent Messaging Bus coordinates; statuses stream to Task Board)
   ↓
Approval Gate (Conditional): Auditor flags variance > threshold
   → Voice interrupt: "The Auditor found a ₹12,400 mismatch in March invoices.
     Approve sending anyway, or hold?"
   ↓
User: "Hold. Show me." → Variance screen opens
   ↓
Resolution → Task completes → Voice summary + entry in Operational Memory
```

---

## 6. FLOW 4 — UNIFIED COMMUNICATION HUB (VOICE TRIAGE)

```
Trigger: New messages arrive (Email/WhatsApp/Slack/Telegram/Teams/SMS)
   ↓
Support/Comms agents categorize: Urgent | Action Needed | FYI | Spam
   ↓
Proactive voice brief (if enabled, respecting Do-Not-Disturb schedule):
   "You have 3 urgent messages. One is from Mehta & Sons about the pending invoice."
   ↓
User: "Read the Mehta one." → TTS reads message
User: "Reply that payment will be released Tuesday, keep it formal."
   ↓
Agent drafts reply → Voice readback → "Send it" → Sent + logged to Business Memory
   ↓
Alternative: "Auto-handle the rest under rule set two." → Auto-responder workflow runs
```

---

## 7. FLOW 5 — WORKFLOW BUILDER (VOICE + VISUAL HYBRID)

```
User: "Hey Office, create a workflow: every Monday at 9, pull last week's sales
from Zoho, make a summary deck, and Slack it to the founders channel."
   ↓
System converts utterance → Workflow Graph:
   [Schedule Trigger: CRON Mon 09:00]
        → [Action: Zoho CRM fetch]
        → [Agent: Sales Manager → summarize]
        → [Action: Generate PPTX]
        → [Approval: CEO Agent (auto-approve if no anomalies)]
        → [Action: Slack post #founders]
   ↓
Visual canvas opens showing the generated graph
   ↓
Voice editing: "Add a condition — if sales dropped more than 10%, also email me."
   → Condition node inserted, branch added
   ↓
"Test it now" → Dry-run with sandbox flags → spoken result
   ↓
"Activate" → Workflow live, registered in Scheduling Engine
```

---

## 8. FLOW 6 — AGENT TRAINING CENTER

```
Entry: "Train the HR Manager on our leave policy." OR drag-drop files onto agent card
   ↓
Ingestion: PDFs/DOCX/Videos/Audio/URLs → OCR/transcription → chunk → embed
   ↓
Knowledge Graph linking: policy ↔ department ↔ agent ↔ related SOPs
   ↓
Voice verification quiz (optional):
   "I've learned the policy. Test me?" → User asks 2–3 questions → confidence check
   ↓
Knowledge scoped to agent's Assigned Memory → Training log saved
```

---

## 9. FLOW 7 — APPROVAL CHAIN FLOW

```
Agent action hits an approval rule (e.g., expense > ₹50,000, external email to new contact)
   ↓
Chain resolution: Specialist → Manager Agent → CEO Agent → Human User
(Each AI tier can auto-approve within its delegated limits)
   ↓
Human-stage notification:
   Voice: "Approval needed: the Recruiter wants to post a job on LinkedIn,
   budget ₹15,000. Approve?"
   ↓
"Approve" / "Reject" / "Show me" / "Ask the CFO agent first"
   ↓
Decision logged (who/when/why) → Audit Log + Operational Memory
```

---

## 10. FLOW 8 — AI CALL CENTER (VOICE CALLS MODULE)

```
INBOUND:
Call arrives (SIP/VoIP) → Speaker greeting by assigned Voice Agent
   → Real-time STT → Intent → Knowledge Graph lookup → TTS response
   → If unresolved/angry-caller detection → warm transfer to human + spoken summary
   → Call transcript + outcome → Business Memory + CRM sync

OUTBOUND:
Workflow/Schedule triggers call (e.g., payment reminder)
   → Compliance check (call-hours window, opt-out list)
   → Scripted-but-adaptive conversation → outcome coded → follow-up task auto-created
```

---

## 11. FLOW 9 — SELF-HEALING & ERROR RECOVERY

```
Tool/workflow failure detected (timeout, API error, browser automation break)
   ↓
Self-Healing Agent classifies: Transient | Config | Credential | Logic
   ↓
Transient  → exponential backoff retry (max 3)
Credential → Vault prompt: voice alert "Your Gmail token expired. Re-connect now?"
Config     → propose fix ("The Zoho field name changed; I can remap it. Approve?")
Logic      → escalate to CEO Agent → human if unresolved
   ↓
All incidents → Error Log + pattern stored so the same failure is pre-empted next time
```

---

## 12. FLOW 10 — MULTI-COMPUTER AGENT NETWORK

```
Admin machine: "Hey Office, add the reception PC to the network."
   ↓
Pairing: QR/code displayed → entered on second machine → mutual TLS handshake (LAN)
   ↓
Node capabilities advertised (GPU, tools, peripherals)
   ↓
GPU Resource Manager redistributes: heavy models → workstation node,
voice agents → reception node
   ↓
Agents now route tasks across nodes via Messaging Bus; org chart shows node badges
```

---

## 13. FLOW 11 — DAILY VOICE BRIEFING (PROACTIVE)

```
Scheduled (e.g., 9:00 AM) or "Hey Office, give me my briefing."
   ↓
CEO Agent compiles: overnight task results, pending approvals, urgent messages,
today's schedule, KPI deltas, anomalies
   ↓
Spoken briefing (60–120 seconds) with interruptible drill-down:
   User: "More on the sales drop." → deeper spoken analysis + chart pushed to screen
   ↓
"Done" → briefing logged; undone items become tasks
```

---

## 14. ERROR & FALLBACK DESIGN (ALL FLOWS)

| Failure | Voice Behavior | Visual Behavior |
|---|---|---|
| STT low confidence | "I didn't catch that — did you mean X or Y?" | Show top-3 transcript candidates |
| Unknown intent | Offer nearest capability + "show commands" | Command palette opens |
| Agent busy | "Riya is mid-task. Queue this, or interrupt?" | Queue position shown |
| LLM unloaded | "Loading the model, ~20 seconds." | Progress bar |
| Mic unavailable | Visual banner + text input fallback | Keyboard-first mode |
| Offline + cloud tool needed | "That needs internet. I'll queue it for when we're back online." | Pending-sync badge |

---

## 15. ACCESSIBILITY & MODALITY RULES

- Every voice flow has a complete keyboard/click equivalent (no voice-only dead ends).
- Every visual notification has an optional spoken equivalent.
- TTS speed, pitch, voice, and verbosity (Brief/Normal/Detailed) are user-configurable.
- Multilingual: STT/TTS locale switchable per session ("Switch to Hindi").
- Speaker identification gates sensitive actions in multi-user enterprise mode.

---

# PART B — SAAS PLATFORM FLOWS (Cloud Layer)

The product is delivered as SaaS: users sign up on the **web portal (React)**, subscribe to a plan, download the desktop app, and activate it with their account. A **Product Admin** operates a separate cloud dashboard for administration, plans, payments, and common configurations pushed to all tenants.

## B1. FLOW 12 — SIGNUP → SUBSCRIBE → DOWNLOAD → ACTIVATE

```
Web Portal (React)
   ↓
Sign Up (email/password, Google SSO) → email verification
   ↓
Industry selection (generic — any industry; drives template suggestions only)
   ↓
Plan Selection (Free Trial / Starter / Pro / Enterprise) → Payment Gateway (Razorpay/Stripe)
   ↓
User Web Dashboard → "Download Desktop App" (Win/Mac/Linux auto-detected)
   ↓
Desktop App first launch → Login with SaaS account (OAuth device flow)
   ↓
License + entitlements fetched (plan limits: #agents, #workflows, channels, seats)
   ↓
Common Configurations sync (admin-managed: default templates, model catalog,
integration catalog, compliance rules, voice locales)
   ↓
Local voice onboarding continues (FLOW 1) — all business data stays local
```

**Key rule:** the cloud knows *who* you are and *what plan* you have. It never receives your business data, memory, transcripts, or documents (privacy pillar preserved). Telemetry is opt-in, aggregate-only.

## B2. FLOW 13 — USER WEB DASHBOARD (SELF-SERVICE)

```
Login → User Dashboard (web)
 ├── My Subscription: plan, usage vs limits (agents, workflows, seats), invoices, upgrade/downgrade
 ├── My Devices: activated machines, deactivate device, download installers
 ├── My Team (Pro/Enterprise): invite members, assign seats & roles
 ├── Marketplace (web view): browse packs/templates → "send to my desktop app"
 ├── License Keys & Offline Activation (Enterprise): generate offline license file
 ├── Support: tickets, docs, feature requests
 └── Account: profile, security (2FA), notification preferences, data/privacy controls
```

## B3. FLOW 14 — PRODUCT ADMIN DASHBOARD

```
Admin Login (separate RBAC: Super Admin, Support Admin, Finance Admin, Catalog Admin)
 ├── User & Tenant Management
 │     onboarding pipeline, KYC/approval queue, suspend/reactivate, impersonate-for-support (consented)
 ├── Approvals
 │     new tenant approvals, enterprise/offline-license requests, marketplace publisher approvals,
 │     refund approvals, plan-override approvals
 ├── Plans & Billing
 │     create/edit plans, feature flags & limits per plan, coupons, taxes (GST/VAT),
 │     payment gateway configuration (Stripe/Razorpay keys, webhooks), dunning rules
 ├── Common Configurations (pushed to all desktop apps)
 │     model catalog (approved LLMs, sizes, quants), default industry templates,
 │     integration/MCP connector catalog & versions, voice locale packs,
 │     compliance presets (call-hour windows by region), default thresholds (Conditional doc §11)
 ├── Marketplace Administration
 │     review/sign packages, version & rollout management, takedowns, revenue share reports
 ├── Releases & Updates
 │     desktop app versions, staged rollout %, force-update policy, release notes
 ├── Analytics (aggregate, privacy-safe)
 │     MRR/ARR, churn, activations, plan distribution, crash rates, feature adoption (opt-in)
 └── Platform Settings
      email/SMS provider config, SSO config, legal docs versions, status page
```

## B4. FLOW 15 — PLAN ENFORCEMENT & ENTITLEMENT SYNC

```
Desktop app heartbeat (daily or on launch) → GET /entitlements
   ↓
Within limits → continue
Limit exceeded (e.g., 6th agent on Starter plan)
   → Voice: "Your plan allows 5 agents. Upgrade to Pro, or archive an agent?"
   → "Upgrade" → web checkout deep-link → entitlement refresh → continue
Offline grace: entitlements cached, valid for N days (Enterprise: offline license file, no heartbeat)
Payment failure → dunning emails → grace period → soft-lock (read-only agents) → reactivation on payment
```

## B5. FLOW 16 — COMMON CONFIGURATION PUSH

```
Product Admin edits a common config (e.g., adds new approved model, updates WhatsApp connector)
   ↓
Versioned config published → CDN/config service
   ↓
Desktop apps poll/receive push → validate signature → apply on next safe window
   ↓
Tenant-local overrides always win where permitted (admin marks each config as
"locked", "default-overridable", or "suggestion")
```

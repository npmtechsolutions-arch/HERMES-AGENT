# AI OFFICE ASSISTANT — SCREEN DESIGN PROMPT DOCUMENT
**Version 2.0 | Ready-to-use prompts for designers / AI design tools (Figma AI, v0, Claude Design, Midjourney UI)**

Each prompt is self-contained: paste it into your design tool. All screens share the Global Design System prompt (§1).

---

## 1. GLOBAL DESIGN SYSTEM PROMPT (prepend to every screen prompt)

> Design for "AI Office Assistant," a voice-first AI workforce platform. Visual language: modern enterprise SaaS, calm and trustworthy, dark-mode-first with light mode variant. Primary color deep indigo (#4F46E5), success emerald, warning amber, danger rose; neutral slate grays. Typography: Inter; generous whitespace; 8px spacing grid; 12px corner radius on cards; subtle elevation, no heavy shadows. Signature element: the **Voice Orb** — a glowing animated sphere bottom-right on every desktop screen with 7 states (sleeping gray, listening pulsing blue, thinking rotating purple, speaking green waveform, acting orange progress ring, confirming amber, error red) and a live transcript chip above it when listening. Iconography: Lucide line icons. Components: React + Tailwind aesthetic. Density: comfortable, data-rich but never cluttered. Accessibility: WCAG AA contrast, visible focus rings.

---

## 2. DESKTOP APP SCREENS

### Prompt D1 — Home Dashboard (S02)
> Design the desktop home dashboard. Layout: collapsible left sidebar (Home, Org, Tasks, Workflows, Inbox, Brain, Approvals with badge, Analytics, Marketplace, Settings). Main area: top "Daily Briefing" card with a large play button and waveform preview ("Your 9:00 briefing — 2 min"); a 4-tile KPI row (Tasks automated today, Hours saved this week, Pending approvals, Urgent messages); an "Agent Activity" live feed column with avatar chips and one-line status ("Auditor — reviewing March invoices"); a "Today's Schedule" column. Voice Orb bottom-right in listening state with transcript chip "show me pending approvals". Include a subtle "Plan: Pro — 18/25 agents" usage pill in the sidebar footer.

### Prompt D2 — Digital Employee Org Chart (S03)
> Design an interactive organizational chart of AI employees. Top node: "CEO Agent" with crown glyph; below, department clusters (Sales, Marketing, Finance, HR, Support) as soft-tinted groups; agent cards inside each: circular AI avatar, name, designation, live status ring (color-coded Idle/Working/Waiting/Reviewing/Escalated/Error), tiny machine badge for multi-computer mode ("Node: Reception-PC"). A "+ Hire" ghost card in each department. Right side panel previews the selected agent (mini profile, current task, KPIs sparkline). Top toolbar: search, filter by status, zoom controls, "Talk to org" mic button. Show one agent mid-handoff with an animated dotted line to another agent (Messaging Bus moment).

### Prompt D3 — Agent Profile (S05)
> Design an AI employee profile screen. Header: large avatar, name "Maya", designation "Social Media Manager — Marketing", status pill "Working", reporting line breadcrumb ("Reports to: Marketing Head"), voice selector dropdown (her TTS voice), Pause/Archive actions. Tabs: Overview, Tasks, Skills & Tools, Memory Scope, Model, Schedule, Permissions, Performance, Training, Bus Messages. Show Overview: objectives checklist, KPI cards with progress (Tasks 34/40, Success 96%), assigned tools as permission chips (Browser ✓, WhatsApp ✓, Payments ✕ greyed "requires approval"), assigned model card "Qwen 14B Q4 — via Ollama" with VRAM mini-bar.

### Prompt D4 — Hire Wizard (S06)
> Design a conversational "Hire an AI Employee" wizard that feels like voice-first onboarding: large centered transcript of the dialog ("You: Hire a social media manager" / "CEO Agent: I propose Maya…"), a generated profile preview card updating live on the right (name, designation, skills chips, tools, model suggestion with VRAM check ✓), and three big actions: Confirm (voice hint: say "confirm"), Edit fields, Cancel. Voice Orb in confirming amber state.

### Prompt D5 — Task Board (S08) & Task Detail (S09)
> Design a Kanban task board with columns Queued / Working / Waiting / Reviewing / Escalated / Completed. Cards: title, assignee agent avatar, department tint, priority flag, deadline countdown, dependency link icon, approval-gate badge where applicable. Detail drawer (right slide-over) for "Monthly GST Report": subtask DAG mini-map, live agent log timeline, artifacts list (PDF chips), linked Bus thread, linked approval, voice command hint footer ("Say: 'status of the GST task'").

### Prompt D6 — Workflow Builder (S11)
> Design a node-based workflow canvas. Left palette: Trigger (lightning), Condition (diamond), Action (gear), Agent Task (avatar), Approval (shield), Notification (bell). Canvas shows: [CRON Mon 9:00] → [Zoho: fetch sales] → [Agent: Sales Manager summarize] → [Condition: drop >10%?] branching to [Email owner] and continuing to [Generate PPTX] → [Approval: CEO Agent] → [Slack #founders]. Top: a prominent **voice-to-workflow bar** with mic icon and the original spoken sentence shown as the source ("Every Monday at 9, pull last week's sales…"). Buttons: Dry-run, Activate, Versions. A dry-run result panel shows step-by-step green checks with timings.

### Prompt D7 — Communication Hub (S14)
> Design a unified inbox with three panes: channels/categories (Email, WhatsApp, Telegram, Slack, Teams, SMS; chips Urgent 3 / Action 7 / FYI 12 / Spam), thread list with channel glyphs and AI category labels, and reading pane with an AI-drafted reply in an editable composer marked "Drafted by Support Agent — review before send" plus buttons Send / Edit / Escalate and a source-citation footnote ("amount from Invoice #214"). Include a voice triage hint banner: "Say: 'read the next urgent one'".

### Prompt D8 — Call Center Console (S16)
> Design a live AI call console. Top strip: active call card — caller identity from CRM ("Mehta & Sons — Ramesh"), live scrolling transcript with speaker turns, real-time sentiment meter, big buttons "Listen in", "Take over", "Whisper to agent". Below: call queue, outbound campaign list with compliance window indicator ("Calling allowed 10:00–19:00 IST"), opt-out list link, and today's outcomes summary (Booked 12 / Callback 4 / Transferred 2).

### Prompt D9 — Second Brain & Knowledge Graph (S18/S19)
> Design a knowledge explorer: top universal search ("Ask your Second Brain…") with voice mic; left filters by memory type (Personal, Business, Knowledge, Operational); results as source-cited cards. A "Graph" toggle reveals a force-directed knowledge graph: color-coded nodes (Customer indigo, Project teal, Document slate, Agent violet, Policy amber), a selected node "Mehta & Sons" with side panel of linked records and an amber conflict marker ("2 GST numbers on file — resolve"). Include an ingestion dropzone card ("Drop PDFs, audio, spreadsheets — I'll learn them").

### Prompt D10 — Approvals Inbox (S21)
> Design an approvals screen: cards grouped "Awaiting you (3)" and "Auto-handled by AI tiers today (14)". Card anatomy: requesting agent avatar, action summary ("Recruiter wants to post LinkedIn job — ₹15,000"), rationale snippet, chain visualization (Specialist ✓ → Manager ✓ → CEO ⏸ → You), big Approve / Reject buttons + "Ask CFO agent" tertiary, voice hint ("Say: approve the LinkedIn request"). Header shows delegation toggle ("Auto-approve from Finance today — expires midnight").

### Prompt D11 — GPU & Model Manager (S31/S32)
> Design a compute management screen: per-GPU VRAM bars with stacked loaded-model segments; a locked segment labeled "Voice pipeline — reserved"; model cards (family logo, size, quantization, runtime badge Ollama/vLLM, pin/evict buttons); a routing rules table (Task complexity → Model tier); multi-node view tabs showing other machines' GPUs. Include a recommendation toast: "Free 3.2 GB by unloading Mistral 7B (idle 2h)?"

### Prompt D12 — Skill Builder Studio (S29)
> Design a no-code skill creation studio: mode switch Record / Describe; in Record mode a captured step list (click, type, extract) each editable with parameter pills ("{client_name}", "{amount}"); a sandbox test panel with sample inputs and a green run log; publish dialog selecting target agents. Friendly empty state: "Show me once — I'll learn it."

### Prompt D13 — Voice Overlay Ambient Mode (S44)
> Design a minimal full-screen voice mode: near-black backdrop, large centered Voice Orb, live transcript line in large type, spoken-response captions below, and small context cards that slide in only when the user says "show me" (e.g., a chart card). Corner exit hint "Esc / say 'exit voice mode'".

---

## 3. USER WEB PORTAL (React)

### Prompt W1 — Pricing & Checkout (W03)
> Design a SaaS pricing page + checkout. Four plan cards (Trial, Starter, Pro highlighted, Enterprise "Talk to us") listing limits (agents, workflows, seats, devices, channels, call minutes) with a comparison toggle. Checkout step: order summary with GST/VAT line, coupon field, gateway-hosted card element placeholder (Stripe/Razorpay logos), trust badges ("Your business data never leaves your machines").

### Prompt W2 — User Dashboard Home (W04)
> Design the account dashboard: plan card with usage meters (Agents 18/25, Workflows 42/100, Seats 3/5, Devices 2/3) each with upgrade affordance at >80%; a prominent "Download Desktop App" card with OS auto-detect; recent invoices table; devices list with last-seen and Deactivate buttons; team members section with role chips and Invite button; support entry point. Top nav: Dashboard, Billing, Devices, Team, Marketplace, Support, account avatar.

### Prompt W3 — Billing & Subscription (W05)
> Design subscription management: current plan summary with renewal date, Change Plan flow with proration preview ("You'll be charged ₹1,240 today"), cancel flow with retention offer and clear "your local data is never deleted" reassurance, payment methods list, invoice history with PDF download icons, and a dunning banner state variant ("Payment failed — retrying. Full access until June 12").

---

## 4. PRODUCT ADMIN DASHBOARD (React)

### Prompt A1 — Admin Home (A02)
> Design a platform operations overview: KPI header (MRR ₹42.8L ▲6%, Active tenants 8,214, Churn 2.1%, Activations today 134); an "Open approvals" queue widget (tenant onboarding 12, refunds 3, marketplace 5) with SLA timers; rollout health widget (Desktop v2.4.1 — 25% fleet, crash rate 0.3% green); config adoption donut (bundle v118: 94%); revenue chart. Left rail: Overview, Tenants, Billing, Configurations, Marketplace, Releases, Analytics, Settings. Global tenant search bar.

### Prompt A2 — Tenant Detail & Approval Queue (A03/A04)
> Design tenant management: queue table (tenant, plan, region, signup date, risk flags, SLA countdown) with row actions Approve / Reject / Request info; tenant detail page with status timeline (trial → active → past_due), subscription panel, devices count, seats, support tickets, and action buttons Suspend / Reactivate / Impersonate (the impersonate button shows a consent-required modal with time-box selector and warning banner). Four-eyes modal variant for destructive actions ("Second admin approval required — request sent to…").

### Prompt A3 — Plans & Feature Flags Editor (A06)
> Design a plan editor: left list of plans; main form with numeric limit fields (agents, workflows, seats, devices, call minutes), feature flag toggle matrix (Call Center, Multi-Computer Network, Offline Mode, Marketplace private catalog), price fields per currency with tax class, effective-date scheduler, and a live preview of the public pricing card. Diff banner before save ("3 changes affect 1,204 active subscriptions — apply at next renewal / immediately").

### Prompt A4 — Common Configurations Studio (A11)
> Design the configuration studio: domain tabs (Model Catalog, Connector Catalog, Industry Templates, Voice Locales, Compliance Presets, Default Thresholds). Show Model Catalog: table of approved models (family, size, quant, runtime, min hardware tier) with per-row scope selector Locked / Overridable / Suggestion; right panel "Bundle v119 — draft" listing changed items; publish flow stepper: Validate → Canary (2% fleet) with live error-rate gauge → Publish All → Rollback button persistent. Adoption sparkline per bundle version.

### Prompt A5 — Payments, Refunds & Dunning (A08–A10)
> Design billing operations: gateway config cards (Stripe, Razorpay) with webhook health indicators (last event 2m ago ✓) and test-mode toggle; refunds queue with four-eyes status column (Requested → Approved by → Executed); dunning monitor: funnel (Failed 312 → Recovered 178 → Grace 96 → Soft-locked 38) with cohort table and retry schedule editor.

### Prompt A6 — Releases & Rollout (A14)
> Design release management: version cards per platform (Win/Mac/Linux) with signature status; staged rollout slider (5% → 25% → 100%) and live crash-rate gauge with auto-pause threshold marker; force-update floor field with warning copy; release notes markdown editor with preview; fleet version distribution stacked bar.

---

## 5. PROMPT USAGE NOTES

1. Generate desktop screens at 1440×900, web portal at 1440 desktop + 390 mobile variants, admin at 1536 desktop.
2. Always include the Voice Orb on desktop-app screens; never on web portal/admin screens.
3. Locked admin-managed settings on desktop must show a "Managed by provider" lock chip — include it in D11 (model catalog rows) when generating variants.
4. Produce dark mode first; light mode as variant.
5. For each screen also request empty, loading (skeleton), error, and plan-limit (upsell) states.

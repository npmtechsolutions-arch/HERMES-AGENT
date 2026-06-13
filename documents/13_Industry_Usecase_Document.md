# AI OFFICE ASSISTANT — INDUSTRY USE CASE DOCUMENT
**Version 1.0 | Vertical Use Case Library for Industry Templates**
**Companion to: Usecase Document (03), PRD (02), Table Design (12)**

---

# PART 1 — HOW INDUSTRY USE CASES MAP TO THE PLATFORM

The core product is industry-agnostic (PRD FR-G1). Every vertical below ships as an **Industry Template** — a signed data package managed by the Product Admin (Common Configurations / Marketplace) containing:

| Template Component | Maps To (Platform) |
|---|---|
| Agent roster (names, designations, objectives, skills, tool grants, model tier) | `agents`, `agent_skills`, `tool_grants` |
| Department structure | `departments` |
| Pre-built workflows | `workflows.graph` |
| Document templates (proposals, agreements, invoices…) | Document Intelligence templates |
| KG entity types & relations (e.g., Property, Unit, Lead, Tenant) | `kg_entities.type = 'custom'` + template-defined schemas |
| Industry conditional rules (thresholds, compliance gates) | Conditional doc rule engine, extends AC/CC/TC families |
| Connector preset list (which integrations matter) | Connector catalog subset |
| Voice phrase packs (industry vocabulary for intent layer) | Intent grammar extensions + STT custom vocabulary |

**Plan gating:** Starter installs 1 template with ≤5 agents active; Pro unlocks the full roster; Call-Center-dependent agents (Voice Receptionist, AI Sales Caller) require the Call Center add-on/Enterprise.

**Cross-industry shared patterns** (implemented once, reused by every template):
1. **Lead-to-Customer pipeline** (capture → qualify → recommend → follow up → convert)
2. **Lifecycle stage tracking** on KG entities (real estate: Lead→Possession; clinic: Inquiry→Treatment→Follow-up; legal: Inquiry→Matter→Closure)
3. **Document generation + approval chain** before anything external
4. **Receivables & reminders** (overdue detection → polite escalating sequences → human escalation)
5. **Compliance calendar** (RERA / GST / court dates / accreditation / license renewals — same scheduler, different data)
6. **Voice receptionist** (inbound call → identify → answer/book/route)

---

# PART 2 — REAL ESTATE (FLAGSHIP TEMPLATE, DEEP)

## 2.1 Org Roster (as provided, structured for the template schema)

| Department | Agents |
|---|---|
| Executive | CEO Agent (forecasting, revenue, project profitability, competitor & agent performance) |
| Sales | Sales Manager (lead assignment/scoring/distribution), Property Recommendation, Follow-Up, Proposal |
| CRM | CRM Executive (lifecycle: Lead→Prospect→Site Visit→Booking→Agreement→Registration→Possession), Customer Success (post-sales) |
| Marketing | Marketing Manager (FB/Google/WhatsApp/SMS campaigns), Content Writer, SEO Specialist, Social Media |
| Site Visits | Site Visit Coordinator (scheduling, vehicles, reminder calls, route planning), Virtual Tour |
| Legal | Legal Documentation (sale agreements, booking forms, NOCs), Compliance (RERA, approvals, tax) |
| Finance | Loan Assistance (eligibility, EMI, bank comparison), Accounts (payments, receivables, commissions) |
| Builder Ops | Project Monitoring, Material Management, Vendor Management |
| Partners | Channel Partner Agent (commissions, lead source, conversions) |
| Research | Market Research, Investment Advisor, Property Intelligence |
| Support | Ticket Management, Voice Receptionist (24x7) |

**KG entity types:** Project, Tower/Phase, Unit, Lead, Customer, Channel Partner, Bank, Contractor, Vendor, Document(Agreement/NOC/Allotment), SiteVisit, Loan, Ticket, Tenant (rental ext.).

## 2.2 Expanded Use Cases (gaps the original misses)

### A. Inventory & Pricing Intelligence
- UC-RE-01: **Live inventory by voice** — "How many 3BHKs are unsold in Tower B?" → unit-level availability with hold/blocked status.
- UC-RE-02: **Dynamic pricing watch** — alert when a micro-market competitor cuts price >3%; propose price-sheet revision (approval-gated, AC chain).
- UC-RE-03: **Unit hold management** — "Hold unit B-1204 for Mr. Kumar for 48 hours" → auto-release workflow with reminder at T-6h.
- UC-RE-04: **Dead-stock analysis** — units unsold >180 days → Investment Advisor proposes repositioning (payment plan, broker incentive).

### B. Lead Lifecycle (deeper than assign/score)
- UC-RE-05: **Source attribution** — every lead tagged portal/walk-in/partner/campaign; "Which campaign produced the most site visits per rupee?"
- UC-RE-06: **Stale-lead resurrection** — quarterly workflow re-engages 90-day-cold leads with new-launch content; opt-out enforced (CC-04).
- UC-RE-07: **Duplicate-lead merge** — same phone via two portals → KG merge with both sources credited (partner commission disputes prevented).
- UC-RE-08: **Speed-to-lead SLA** — new portal lead uncontacted in 15 min → escalate to Sales Manager Agent → human (TC-06 pattern).
- UC-RE-09: **NRI buyer track** — timezone-aware follow-ups, POA document checklist, TDS-on-purchase guidance docs, video-call site tours.

### C. Site Visits
- UC-RE-10: **Route optimization** — cluster tomorrow's visits geographically; driver itinerary generated; WhatsApp confirmations night before; reminder call 2h prior (outbound Call Center).
- UC-RE-11: **No-show recovery** — missed visit → same-day empathetic reschedule sequence; 2 no-shows → human review flag.
- UC-RE-12: **Visit outcome capture by voice** — sales rep dictates in the car: "Kumar liked B-1204, concerned about east facing, budget stretch 5L" → structured CRM note + objection tags + next-step task.

### D. Booking → Registration (document-heavy core)
- UC-RE-13: **Booking pack generation** — booking form + cost sheet + payment schedule + allotment letter in one command; Legal agent review state; human approval before send (AC-05/07).
- UC-RE-14: **Payment-milestone engine** — construction-linked plans: slab completion event → demand letters to all linked customers → receivables tracking → escalating reminders → legal notice draft at 60 days overdue (human-gated).
- UC-RE-15: **Registration coordinator** — checklist per customer (sale deed draft, stamp duty calc, slot booking, document verification); "Who is ready for registration this week?"
- UC-RE-16: **Loan file pilot** — Loan Assistance Agent tracks each customer's bank file stage (login→legal→technical→sanction→disbursement); chases banks; alerts when disbursement blocks a milestone payment.

### E. Post-Sales, Rental & Society (recurring-revenue extensions)
- UC-RE-17: **Snagging/defect management** — possession inspection tickets with photos → contractor assignment → closure verification → customer sign-off.
- UC-RE-18: **Rental Management** (premium) — tenant KYC, rent agreements, monthly rent collection reminders, renewal alerts at T-60 days, yield reports for investor-owners.
- UC-RE-19: **Society Management** (premium) — maintenance billing, notices, complaint tickets, AMC vendor schedules, meeting minute generation.
- UC-RE-20: **Resale & referral loop** — possession +12 months → satisfaction check call → referral program enrollment → resale valuation on request.

### F. Builder Operations
- UC-RE-21: **Construction progress from photos** (premium AI Construction Supervisor) — weekly site photos → progress estimate vs plan → delay flags into Project Monitoring.
- UC-RE-22: **Material reorder automation** — cement/steel below threshold → PO draft to lowest-quote approved vendor → approval chain → order + delivery tracking.
- UC-RE-23: **Contractor scorecards** — delay %, rework tickets, billing disputes → quarterly vendor performance report.

### G. Compliance (RERA-specific)
- UC-RE-24: **RERA QPR autopilot** — quarterly progress report data assembled from Project Monitoring + Accounts; draft filing pack; deadline countdown with escalating alerts (compliance calendar pattern).
- UC-RE-25: **Advertisement compliance check** — every marketing creative auto-checked for RERA number presence + claims vs approved specs before publishing (blocking gate in marketing workflows).
- UC-RE-26: **Escrow/collection account monitor** — collections vs withdrawal rules; anomaly → CFO-tier alert.

### H. Channel Partners
- UC-RE-27: **Partner portal-by-WhatsApp** — partners query inventory & price sheets via WhatsApp bot; watermarked collateral per partner.
- UC-RE-28: **Commission automation** — registration event → slab-based commission calc → dispute window → payout schedule → TDS handling; "Calculate commissions for all channel partners" returns per-partner statements.

## 2.3 Real-Estate Workflows (template-shipped)

1. **New Lead** (as provided): Capture → Qualify → Recommend → Proposal → Follow-up → Site Visit → Sales Manager → Booking; plus SLA branch (UC-RE-08) and dedupe branch (UC-RE-07).
2. **Property Launch**: CEO brief → Marketing plan → Content/SEO/Social production (approval gate: RERA ad check UC-RE-25) → Campaign live → Lead intake → CRM distribution.
3. **Purchase Journey**: Inquiry → Recommendation → Visit → Proposal → Loan → Legal docs → Registration → Possession → Customer Success (each stage = KG lifecycle state with stuck-stage alerts).
4. **Milestone Billing**: Slab event → demand letters → receivables → reminders → escalation (UC-RE-14).
5. **Possession**: Snag list → fixes → handover pack (NOC, manuals, warranty docs) → key handover scheduling → society onboarding.
6. **RERA Quarterly**: data assembly → draft QPR → CA/legal human review → filing → archive (UC-RE-24).

## 2.4 Real-Estate Conditional Rules (extends Conditional doc)

| ID | Condition | Behavior |
|---|---|---|
| RE-01 | New lead uncontacted > 15 min | Escalate (speed-to-lead) |
| RE-02 | Unit hold expires | Auto-release + notify holder & sales rep |
| RE-03 | Marketing creative lacks RERA number / claims unapproved spec | Block publish; route to Compliance Agent |
| RE-04 | Payment overdue 15/30/60 days | Reminder → firm notice → legal-notice draft (human-gated) |
| RE-05 | Same customer phone on 2+ partner leads | Merge; first-source commission rule applied; dispute log |
| RE-06 | Discount request > sales-head limit | CEO-Agent → human approval (AC extension) |
| RE-07 | Loan file stuck at one bank stage > 7 days | Loan agent chases; alert customer-facing rep |
| RE-08 | Site-visit no-show ×2 | Pause automation; human callback task |

**Integrations preset:** real-estate portals (lead webhooks), WhatsApp Business, Google/Meta Ads, Tally/Zoho Books, Google Calendar, telephony (Call Center), maps API (routing).

---

# PART 3 — OTHER INDUSTRY TEMPLATES (USE CASE LIBRARIES)

## 3.1 HEALTHCARE / CLINIC

**Roster:** Front Desk Voice Receptionist, Appointment Coordinator, Patient Follow-up Agent, Billing & Insurance Agent, Inventory (pharmacy/consumables) Agent, Lab Coordination Agent, Recall/Preventive-care Agent, Compliance & Records Agent, Feedback Agent.

**KG entities:** Patient, Appointment, Practitioner, Treatment Plan, Prescription(record), Insurance Policy, Lab Order, Invoice. **PII default = true** (MC-08 — restricts agent access, blocks any cloud-opt-in paths).

**Use cases:**
- UC-HC-01 Voice scheduling — inbound call → identify patient → book/reschedule per practitioner calendar rules (buffer times, procedure durations).
- UC-HC-02 No-show reduction — T-24h WhatsApp confirm + T-2h reminder call; unanswered → waitlist backfill offer to next patient.
- UC-HC-03 Recall engine — "all diabetic patients due for HbA1c this quarter" → consent-checked reminder sequence.
- UC-HC-04 Post-procedure follow-up — day 1/3/7 check-in messages; negative response keywords → urgent flag to doctor (never medical advice by AI — routing only, hard rule).
- UC-HC-05 Insurance pre-auth tracker — document checklist per insurer, status chasing, expiry alerts.
- UC-HC-06 Pharmacy reorder — stock thresholds → supplier PO drafts → approval chain.
- UC-HC-07 Lab loop closure — order placed → result received → doctor notified → patient informed only after doctor release (blocking gate).
- UC-HC-08 End-of-day reconciliation — appointments vs billing vs collections variance report by voice: "How did today close?"

**Hard conditional rules:** HC-R1: AI never communicates diagnoses/results without practitioner release. HC-R2: All patient data local-only, no exceptions (template locks the BYO-cloud toggle). HC-R3: Reminder content excludes condition names on shared channels (privacy-safe phrasing).

**Workflows:** Inquiry→Booking→Visit→Treatment→Billing→Follow-up→Recall; Insurance claim lifecycle; Daily close.

## 3.2 LAW FIRM

**Roster:** Intake/Conflict-Check Agent, Paralegal (drafting) Agent, Legal Research Agent, Court Diary Agent, Client Communication Agent, Billing & Trust-Accounting Agent, Compliance Agent, Document Vault Agent.

**KG entities:** Client, Matter, Opposing Party, Court, Hearing, Filing, Document, TimeEntry, Invoice.

**Use cases:**
- UC-LF-01 Conflict check on intake — new client vs KG of past parties; conflict → block with report.
- UC-LF-02 Dictation-to-draft — lawyer dictates notice/petition; Paralegal formats to court template; precedent suggestions from firm's trained knowledge (Agent Training Center on precedent bank).
- UC-LF-03 Court diary — hearing dates parsed from orders; D-7/D-2/D-1 briefings: "What's tomorrow's cause list and what does each matter need?"
- UC-LF-04 Limitation-period sentinel — statutory deadlines per matter type; escalating alerts; never auto-dismissible by AI tiers.
- UC-LF-05 Client status updates — post-hearing voice note by lawyer → formal client update drafted → lawyer-approved send.
- UC-LF-06 Time capture by voice — "Log 2 hours drafting on the Mehta matter" → billable entry → monthly invoice assembly.
- UC-LF-07 Bundle preparation — compile, paginate, index hearing bundles from matter documents (PDF skillset).
- UC-LF-08 Research memo — "Find precedents on specific performance in sale agreements" → cited memo for lawyer review (clearly draft-marked).

**Rules:** LF-R1: nothing leaves the firm without named-lawyer approval (AC-05 hardened to all matters). LF-R2: limitation alerts cannot be auto-approved/snoozed by AI tiers. LF-R3: matter-level confidentiality walls (TC-10) between practice groups.

## 3.3 CA / ACCOUNTING FIRM

**Roster:** Client Document Collector, Bookkeeping Agent, GST Specialist, TDS Agent, Income-Tax Filing Agent, Audit Assistant, Reconciliation Agent, Client Reminder Agent, Engagement/Billing Agent.

**Use cases:**
- UC-CA-01 Multi-client compliance calendar — every client's GST/TDS/IT/ROC dates in one engine; "What's due in the next 7 days across all clients?"
- UC-CA-02 Document chase — per-filing checklists; WhatsApp/email chase sequences; received docs auto-filed to client KG node; "Which clients haven't sent purchase invoices?"
- UC-CA-03 OCR → ledger — scanned invoices to draft ledger entries (Tally/Zoho push) with low-confidence items queued for staff (MC-06).
- UC-CA-04 Reconciliation runs — books vs GSTR-2B / bank statement diffs → exception list only.
- UC-CA-05 Variance-gated filings — Auditor agent variance check before any filing pack reaches the human partner (the GST flow from doc 01).
- UC-CA-06 Fee receivables — engagement-wise billing, overdue follow-ups, "Stop-work list" suggestion at 90 days (human-decided).
- UC-CA-07 Notice handling — client forwards a tax notice → classified, deadline extracted, response checklist created, draft reply prepared.

**Rules:** CA-R1: every figure in outbound documents must carry a source citation (CC-03 hardened). CA-R2: no filing submitted without human partner approval. CA-R3: per-client confidentiality walls.

## 3.4 EDUCATION (SCHOOL / COLLEGE / TRAINING CENTER)

**Roster:** Admissions Counselor Agent, Inquiry Voice Receptionist, Fee Reminder Agent, Timetable & Notice Agent, Parent Communication Agent, Certificate/Document Agent, Alumni & Placement Agent (college), Batch Scheduler (training centers).

**Use cases:**
- UC-ED-01 Admission season surge — inbound calls/WhatsApp answered 24x7 from prospectus knowledge; tour bookings; application status tracking; counselor escalation for fee negotiations.
- UC-ED-02 Fee cycles — installment schedules per student; reminder ladder; receipt generation; defaulter report excluding hardship-flagged families (human-managed flag).
- UC-ED-03 Circular blast — "Notify all Grade 9 parents about Saturday's PTM in English and Tamil" → multilingual, channel-preferred delivery with read tracking.
- UC-ED-04 Certificate mill — bonafide/TC/completion certificates from templates; registrar approval gate; tamper-evident numbering.
- UC-ED-05 Training-center batch ops — lead → demo class booking → enrollment → batch assignment → attendance nudges → completion certificate → review request.
- UC-ED-06 Placement cell — student-skill matching to employer requirements; drive scheduling; offer tracking.

**Rules:** ED-R1: all student data PII-locked; ED-R2: parent communications never include other students' information; ED-R3: minor-related external comms restricted to enrolled-guardian contacts only.

## 3.5 MANUFACTURING UNIT

**Roster:** Production Reporter Agent, Inventory/Stores Agent, Procurement Agent, Vendor Management Agent, Quality (NCR) Agent, Dispatch & Logistics Agent, Maintenance Scheduler Agent, Order-Desk Agent.

**Use cases:**
- UC-MF-01 Voice production logging — supervisor dictates shift output/downtime/rejections → structured daily production report to owner's morning briefing.
- UC-MF-02 Reorder automation — min-stock breach → quote comparison from approved vendors → PO approval chain → delivery follow-up (mirrors UC-RE-22).
- UC-MF-03 Order-to-dispatch tracking — "Where is the Sharma Industries order?" → stage answer (production/QC/packed/dispatched) with delay reasons.
- UC-MF-04 Preventive maintenance — machine-wise schedules; spares check before due date; breakdown ticket triage.
- UC-MF-05 Quality NCR loop — rejection logged → root-cause checklist → vendor debit note draft where supplier-caused.
- UC-MF-06 Dispatch documentation — invoice + e-way bill data assembly + LR tracking + delivery confirmation → receivables start.
- UC-MF-07 Offline-first operations — full function with no internet (Offline Enterprise Mode); syncs comms when connectivity returns (Persona: Rajesh).

**Rules:** MF-R1: safety-incident keywords in any log → immediate owner alert, no batching; MF-R2: PO above threshold → human approval; MF-R3: Hindi/regional voice pack default-on.

## 3.6 RETAIL / D2C

**Roster:** Order Management Agent, Customer Support (WhatsApp/IG) Agent, Inventory Agent, Supplier PO Agent, Reviews & Reputation Agent, Promotions Agent, Loyalty/Winback Agent, COD-Reconciliation Agent.

**Use cases:** order-status self-service across channels; abandoned-checkout recovery sequences; low-stock + dead-stock weekly voice brief; review responses (negative reviews → human-approved); festival campaign builder; COD remittance reconciliation against courier reports; RTO (return-to-origin) reduction calling via Call Center add-on; "Which SKUs made money this month after returns and ads?"

**Rules:** RT-R1: refunds beyond policy auto-routed to human; RT-R2: promo discounts above margin floor blocked; RT-R3: review responses never admit legal liability (phrase-block list).

## 3.7 MARKETING / DIGITAL AGENCY

**Roster:** Account Manager Agent per-client (instantiable), Content Writer, SEO Specialist, Social Media Manager, Ads Performance Agent, Reporting Agent, New-Business (proposal) Agent.

**Use cases:** per-client brand-voice training (Training Center) so outputs aren't generic (Persona Priya's churn risk); weekly client report autopilot (data pull → insight summary → deck → AM review → send); content calendar generation + scheduling; ad-spend anomaly alerts ("CPL doubled on Meta for client X overnight"); proposal generation from discovery-call transcript; client approval portals via email/WhatsApp with version tracking; capacity view — "Which client is consuming the most agent hours vs retainer?"

**Rules:** AG-R1: client-confidentiality walls between client memory scopes (department isolation per client); AG-R2: nothing publishes without client-approval token recorded; AG-R3: competitor-client conflict check on new business.

## 3.8 RECRUITMENT / STAFFING

**Roster:** Sourcing Agent, Screening Agent, Interview Scheduler, Candidate Communication Agent, Client (employer) Account Agent, Offer & Joining Tracker, Invoice/Replacement-Guarantee Agent.

**Use cases:** JD intake by voice → sourcing checklist; resume screening to shortlist with reasoning (human reviews before rejection — fairness rule); interview slot negotiation across candidate/panel calendars; candidate ghosting-prevention nurture (offer-to-join period check-ins); joining confirmation → invoice trigger → replacement-guarantee countdown tracking; "Which positions are aging past 30 days and why?"

**Rules:** RC-R1: no automated rejection without human review; RC-R2: candidate PII walls between client accounts; RC-R3: screening criteria logged for auditability (bias review).

## 3.9 HOSPITALITY / RESTAURANT (marketplace pack)

Voice Receptionist for reservations; table/turn optimization; event-booking proposals (banquets); supplier ordering from par levels; review reputation loop; loyalty winback ("guests not seen in 60 days"); daily flash report by voice ("How did we do tonight vs last Friday?").

## 3.10 LOGISTICS / FLEET (marketplace pack)

Booking desk agent; trip assignment & driver communication; POD (proof-of-delivery) chase; vehicle maintenance & document expiry calendar (insurance/permit/fitness); detention/demurrage alerting; client rate-card quoting; "Which vehicles are idle today and why?"

---

# PART 4 — CROSS-INDUSTRY ANALYSIS (WHAT THIS MEANS FOR THE PRODUCT)

## 4.1 The 6 reusable engines cover ~85% of all vertical use cases
Every use case above decomposes into the shared patterns from Part 1 (pipeline, lifecycle, doc+approval, receivables, compliance calendar, voice receptionist). **Build the engines once; templates contribute only data.** This validates FR-G1 and keeps engineering cost flat as verticals multiply.

## 4.2 Template schema additions required (feeds back into Table Design doc)
- `template_lifecycles` — named stage sequences per entity type (Lead→Possession; Inquiry→Treatment) powering stuck-stage alerts.
- `template_rules` — industry conditional rules (RE-01…, HC-R1…) loaded into the rule engine namespace.
- `phrase_packs` — industry vocabulary for intent grammar + STT custom dictionary ("OMR", "RERA", "GSTR-2B", "cause list").
- `compliance_calendars` — recurring statutory events per region/industry (admin-maintained via Common Config, since laws change centrally).

## 4.3 Hard-rule classes that templates may LOCK (safety)
Healthcare (no AI medical communication), Legal (no unapproved external docs, no snoozable limitation alerts), Education (minor-data restrictions), Recruitment (no auto-rejection). Template schema therefore needs a `locked_rules` block the tenant cannot disable — same mechanism as admin-locked configs (PA-03).

## 4.4 Monetization mapping
| Capability | Packaging |
|---|---|
| Base template (roster ≤5 agents) | Starter |
| Full roster + workflows | Pro |
| Voice Receptionist / AI Sales Caller / outbound reminder calls | Call Center add-on |
| Rental Mgmt, Society Mgmt, Construction Supervisor, Investor Advisor | Premium marketplace packs |
| Multi-branch / multi-site | Enterprise (multi-node + isolation) |

## 4.5 Rollout priority (pain × repetitiveness × willingness-to-pay × template completeness)
1. **Real Estate** (flagship — document-heavy, communication-heavy, high ticket)
2. CA/Accounting (deadline-driven, multi-client leverage)
3. Clinic/Healthcare (Call Center showcase; strict privacy = our moat)
4. Agency (SaaS-native buyers, fast adoption)
5. Law Firm (dictation-native users)
6. Education, Manufacturing, Retail, Recruitment (V1.5–V2 with marketplace packs)

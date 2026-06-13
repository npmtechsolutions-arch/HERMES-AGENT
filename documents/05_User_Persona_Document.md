# AI OFFICE ASSISTANT — USER PERSONA DOCUMENT
**Version 1.0 | Voice-First AI Workforce Platform**

---

## PERSONA 1 — "ADVOCATE ARJUN" (Individual Professional: Lawyer)

| Attribute | Detail |
|---|---|
| Age / Role | 38, founding partner, 3-lawyer firm, Tier-2 city |
| Tech comfort | Medium — uses Word, email, court e-filing portals |
| Devices | Windows laptop (16 GB RAM, RTX 3060), office desktop |
| Day | Client calls, drafting, court appearances, chasing payments |

**Goals:** Draft contracts/notices faster; never miss a hearing date; keep client matters strictly confidential; bill more hours, do less admin.

**Pain Points:** Cloud AI is a confidentiality risk for client documents; typing long prompts is slower than dictating; junior staff turnover; follow-up chaos.

**Why Voice-First Matters:** Dictation is already his natural workflow (lawyers dictate). He drafts a legal notice by speaking while pacing his office.

**Key Features Used:** Law Firm Industry Template (Paralegal Agent, Research Agent, Billing Agent), Document Intelligence (notices, contracts), Knowledge Graph (client ↔ case ↔ hearing ↔ document), Scheduling (hearing reminders + voice briefing), Offline/local privacy, Agent Training Center (firm's precedent bank).

**Success Quote:** *"I dictate a notice at 7 PM, the Paralegal Agent formats it, the Billing Agent logs the hours, and nothing ever leaves my laptop."*

**Adoption Risks:** Skeptical of AI legal accuracy → needs Reviewing state + human approval on all outbound legal documents (AC-07/AC-05 rules).

---

## PERSONA 2 — "DR. KAVITA" (Individual Professional: Clinic Owner)

| Attribute | Detail |
|---|---|
| Age / Role | 45, runs a 2-doctor clinic with 1 receptionist |
| Tech comfort | Low-medium — practice management software, WhatsApp |
| Devices | Clinic desktop + reception PC (Multi-Computer Network candidate) |

**Goals:** Reduce no-shows; automate appointment booking and reminders; keep patient data on-premises (regulatory); free the receptionist for in-person care.

**Pain Points:** Phone rings constantly for bookings; patient records must not go to cloud; staff can't manage software complexity.

**Why Voice-First Matters:** Hands are busy with patients; she speaks orders between consultations. The **AI Call Center Module** answers booking calls; the **reception node** runs the front-desk Voice Agent.

**Key Features Used:** Doctor Office Template, AI Call Center (inbound booking, outbound reminders), Multi-Computer Agent Network (consult room + reception), WhatsApp automation, PII handling rules (MC-08), Offline mode.

**Success Quote:** *"The phone gets answered even during surgery hours, and reminder calls cut no-shows by a third."*

**Adoption Risks:** Very low tolerance for setup complexity → relies entirely on Industry Template + voice onboarding.

---

## PERSONA 3 — "CA MEHUL" (Individual Professional: Chartered Accountant)

| Attribute | Detail |
|---|---|
| Age / Role | 41, CA office serving 60 SMB clients |
| Tech comfort | High in Tally/Excel, low in programming |
| Devices | Windows workstation, 32 GB RAM, mid GPU |

**Goals:** Automate monthly GST prep across clients; bulk reminders for document collection; audit-ready trails of everything.

**Pain Points:** Deadline crunch every filing cycle; clients send documents late and in messy formats; hiring seasonal staff is expensive.

**Key Features Used:** CA Office Template (Accountant, GST Specialist, Auditor agents), Tally + Zoho Books integrations via MCP, Scheduled workflows (monthly GST per client), Approval Chains (auditor variance gates), OCR ingestion of scanned invoices, Audit Logs, Skill Builder ("teach it my reconciliation routine").

**Success Quote:** *"Sixty clients' GST workflows fire on the 1st automatically. I only see the exceptions."*

**Adoption Risks:** Numbers must be exact → CC-03 source-citation rule and Reviewing state are essential to his trust.

---

## PERSONA 4 — "PRIYA THE AGENCY OWNER" (Small Business)

| Attribute | Detail |
|---|---|
| Age / Role | 29, founder of a 6-person digital marketing agency |
| Tech comfort | High — SaaS-native, no-code tools |
| Devices | MacBook Pro M-series |

**Goals:** Scale output without hiring; consistent content calendars per client; instant client reporting; look bigger than she is.

**Pain Points:** Context-switching across 12 client accounts; reporting eats weekends; freelancer reliability.

**Why Voice-First Matters:** Operates like a director — speaks briefs while reviewing creatives: *"Maya, draft next week's posts for the bakery client, upbeat tone, festival theme."*

**Key Features Used:** Marketing department agents (SEO, Content Writer, Social Media Manager), Workflow Engine (weekly client reports), Marketplace skill packs, Slack/Drive integrations, Analytics dashboard, Agent-to-Agent Bus (Content Writer ↔ SEO collaboration), Agent Performance System to "promote" the best-configured agents.

**Success Quote:** *"My AI team handles drafts and reports; my humans handle creativity and clients."*

**Adoption Risks:** Will churn if outputs are generic → Agent Training Center on each client's brand voice is the retention hook.

---

## PERSONA 5 — "RAJESH THE FACTORY MANAGER" (Small Business: Manufacturing)

| Attribute | Detail |
|---|---|
| Age / Role | 52, operations head, 40-worker components unit |
| Tech comfort | Low — Excel, WhatsApp, Tally via accountant |
| Devices | Office desktop; spotty internet |

**Goals:** Daily production/dispatch reports without chasing supervisors; vendor follow-ups; inventory alerts.

**Pain Points:** Unreliable internet rules out cloud tools; can't type fast; data scattered in registers and Excel.

**Why Voice-First Matters:** He asks questions like he asks a clerk: *"How much stock of grade-2 steel is left?"* — and gets a spoken answer. Voice removes the literacy/typing barrier entirely.

**Key Features Used:** Manufacturing Plant Template, **Offline Enterprise Mode** (works with no internet), voice queries on Second Brain, scheduled vendor reminder calls (outbound Call Center), Excel ingestion, Hindi/multilingual STT-TTS.

**Success Quote:** *"It works when the internet doesn't, and it speaks my language."*

**Adoption Risks:** Hardware may be weak → CPU-fallback tier (LC-06) and small-model defaults must still feel useful.

---

## PERSONA 6 — "SNEHA THE HR LEAD" (Enterprise Team)

| Attribute | Detail |
|---|---|
| Age / Role | 34, HR manager, 400-employee company |
| Tech comfort | Medium-high — HRMS, ATS, Teams |
| Context | Enterprise multi-user deployment, IT-managed |

**Goals:** Automate screening, interview scheduling, onboarding paperwork; consistent policy answers to employees; compliance trails.

**Pain Points:** 300 resumes per opening; policy questions interrupt her all day; data residency rules forbid external AI processing of employee data.

**Key Features Used:** HR Department agents (Recruiter, Payroll Executive), Recruitment Pack from Marketplace, Approval Chains (offer letters need human sign-off), Department Isolation (HR data invisible to other departments), Shared Memory (policy knowledge base answers employee FAQs), RBAC, Audit Logs, Voice-print authorization for sensitive actions.

**Success Quote:** *"The Recruiter Agent shortlists overnight; I approve offers by voice on my way in; and Legal can audit every step."*

**Adoption Risks:** IT security review is the gatekeeper → SC-rules, vault, on-prem story must be airtight.

---

## PERSONA 7 — "PROF. IQBAL" (Educational Institution)

| Attribute | Detail |
|---|---|
| Age / Role | 47, vice-principal of a private college |
| Tech comfort | Medium |
| Context | Admin office of 8 staff; budget-constrained |

**Goals:** Automate admissions inquiries, fee reminders, timetable changes, circulars; multilingual parent communication.

**Pain Points:** Seasonal inquiry floods; small admin staff; parents prefer calls/WhatsApp over portals.

**Key Features Used:** Inquiry-handling Voice Agent (Call Center inbound), WhatsApp/SMS automation, scheduled fee-reminder workflows, document generation (circulars, certificates), multilingual TTS, Training Center (prospectus + rulebook ingestion).

**Success Quote:** *"Admission season used to need 4 temps. Now two agents and the AI handle it."*

---

## PERSONA 8 — "DEV THE IT ADMINISTRATOR" (Enterprise Buyer-Operator)

| Attribute | Detail |
|---|---|
| Age / Role | 36, IT admin responsible for the enterprise deployment |
| Tech comfort | Expert |

**Goals:** Deploy across 30 machines; centrally manage users, permissions, nodes, models; pass security audit; zero data egress.

**Key Features Used:** Central Administration console, Multi-Computer Agent Network management, GPU Resource Manager (fleet view), Offline Enterprise Mode, Vault + RBAC policy editor, Plugin SDK governance (signed plugins only), Audit log export to SIEM.

**Success Criteria:** Deployment in < 1 day; no WAN egress detectable; per-department isolation verified; SSO-equivalent local auth.

**Adoption Risks:** Will reject the product on a single security gap — SC-07 (no unaudited privileged actions) and SC-08 (hard offline) are his evaluation tests.

---

## PERSONA PRIORITIZATION

| Tier | Personas | Rationale |
|---|---|---|
| **Primary (design for first)** | CA Mehul, Advocate Arjun, Priya | Highest pain × willingness-to-pay × fit with MVP scope |
| **Secondary (V1.5)** | Dr. Kavita, Sneha | Need Call Center / enterprise features |
| **Tertiary (V2.0)** | Rajesh, Prof. Iqbal, Dev | Need offline enterprise, multi-node, multilingual depth |

## CROSS-PERSONA DESIGN MANDATES

1. **Voice must work for low-typing users** (Rajesh) and **fast power users** (Priya) — verbosity settings and barge-in are not optional.
2. **Trust is earned through approvals and citations**, not autonomy claims (Mehul, Arjun, Sneha).
3. **Templates are the onboarding**, not documentation (Kavita, Iqbal).
4. **Privacy is the purchase reason**, not a feature bullet (all personas).

---

# PART B — SAAS PERSONAS

## PERSONA 9 — "ANITA THE PRODUCT ADMIN" (Platform Operator)
| Attribute | Detail |
|---|---|
| Role | Product operations lead at the company selling AI Office Assistant |
| Tools | Admin Dashboard (React web), Stripe/Razorpay consoles, support desk |

**Goals:** Approve and onboard tenants fast; keep MRR growing; zero billing disputes; push safe configurations to thousands of desktops; keep marketplace clean.

**Pain Points:** Refund disputes; risky config pushes breaking customer desktops; abuse (spam senders); needing engineering for every plan change.

**Key Features Used:** Onboarding/approval queues, Plans engine (self-serve plan & flag editing — no deploys), payment gateway config + dunning, Common Configuration push with canary + rollback, release staged rollouts with crash gates, four-eyes approvals, aggregate analytics.

**Success Quote:** *"I changed the Pro plan limits, pushed a new Tally connector to 8,000 desktops, and approved 40 tenants — before lunch, without engineering."*

## PERSONA 10 — "VIKRAM THE ACCOUNT OWNER" (SaaS Buyer)
The subscription-managing facet of every end-user persona (Mehul, Priya, Sneha…).

**Goals:** Know exactly what he's paying for; add/remove seats as the team changes; move his license to a new laptop; never lose work on downgrade.

**Key Features Used:** User Web Dashboard (usage vs limits, invoices, upgrade), device management, team seats, support tickets, data/privacy controls.

**Trust requirement:** "My business data stays on my machines" must be visibly true (privacy page, DB-01 guarantee) — it's why he chose this over cloud AI suites.

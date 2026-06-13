"""
Industry Template library (implements doc 13 — Industry Use Case Document).

Each vertical ships as a data-only template (FR-G1): an agent roster + department
structure, pre-built workflow *pipelines*, a task library (the UC-xx use cases),
plus the template components doc 13 adds:

  * lifecycle    — named stage sequence for the vertical (Lead→Possession, …),
                   powering stuck-stage tracking.
  * kg_entities  — the Knowledge-Graph entity types that matter for the vertical.
  * rules        — industry conditional rules (RE-01…, HC-R1…); `locked=True`
                   marks safety rules a tenant cannot disable (doc 13 §4.3).

Two sources, combined in the API:
  * CURATED — `curated(industry)` returns the hand-built pack (instant).
  * LLM     — `generate_with_ai(industry, product)` tailors agents/pipelines/
              tasks to the user's product, merging curated lifecycle/kg/rules.

Compact spec per industry:
  roles:     [(key, designation, department, reports_to_key)]
  pipelines: [(name, description, approvals, [(role_key, instruction)])]
  tasks:     [(role_key, title)]
  lifecycle: [stage, ...]
  kg_entities: [type, ...]
  rules:     [(id, condition, behavior, locked)]
A CEO Agent is prepended automatically.
"""
from . import llm

_NAMES = ["Aria", "Ravi", "Maya", "Arjun", "Geeta", "Sam", "Neha", "Vikram",
          "Priya", "Karan", "Diya", "Rohan", "Tara", "Aman", "Isha", "Dev",
          "Kavya", "Nikhil", "Sara", "Yash", "Anya", "Imran", "Lata", "Omar",
          "Riya", "Zara", "Kabir", "Mira", "Veer", "Anu", "Jay", "Pooja"]

_SKILLS = {
    "research": ["research", "analysis"], "draft": ["drafting", "writing"],
    "review": ["review", "qa"], "data": ["data_fetch", "reconciliation"],
    "sales": ["lead_scoring", "outreach", "crm"], "market": ["content", "campaigns"],
    "finance": ["accounting", "compliance"], "legal": ["legal", "compliance"],
    "voice": ["telephony", "scheduling"], "support": ["triage", "drafting"],
    "ops": ["coordination", "tracking"],
}


def _ceo(extra="forecasting, revenue, performance"):
    return ("ceo", "CEO Agent", "Executive", None)


# ════════════════════════════ INDUSTRY PACKS ════════════════════════════════
INDUSTRIES = {

    # ─────────────────────────── REAL ESTATE (flagship) ─────────────────────
    "Real Estate": {
        "lifecycle": ["Lead", "Prospect", "Site Visit", "Booking", "Agreement",
                      "Registration", "Possession"],
        "kg_entities": ["Project", "Tower/Phase", "Unit", "Lead", "Customer",
                        "Channel Partner", "Bank", "Contractor", "Vendor",
                        "Document", "Site Visit", "Loan", "Ticket", "Tenant"],
        "rules": [
            ("RE-01", "New lead uncontacted > 15 min", "Escalate (speed-to-lead) to Sales Manager → human", False),
            ("RE-02", "Unit hold expires", "Auto-release unit + notify holder & sales rep", False),
            ("RE-03", "Marketing creative lacks RERA number / unapproved claim", "Block publish; route to Compliance Agent", True),
            ("RE-04", "Payment overdue 15 / 30 / 60 days", "Reminder → firm notice → legal-notice draft (human-gated)", False),
            ("RE-05", "Same customer phone on 2+ partner leads", "Merge; first-source commission rule; log dispute", False),
            ("RE-06", "Discount request > sales-head limit", "CEO Agent → human approval", False),
            ("RE-07", "Loan file stuck at one bank stage > 7 days", "Loan agent chases bank; alert customer rep", False),
            ("RE-08", "Site-visit no-show ×2", "Pause automation; create human callback task", False),
        ],
        "roles": [
            ("sales_mgr", "Sales Manager", "Sales", "ceo"),
            ("recommend", "Property Recommendation", "Sales", "sales_mgr"),
            ("followup", "Follow-Up Agent", "Sales", "sales_mgr"),
            ("proposal", "Proposal Agent", "Sales", "sales_mgr"),
            ("crm", "CRM Executive", "CRM", "ceo"),
            ("success", "Customer Success", "CRM", "crm"),
            ("mkt_mgr", "Marketing Manager", "Marketing", "ceo"),
            ("content", "Content Writer", "Marketing", "mkt_mgr"),
            ("seo", "SEO Specialist", "Marketing", "mkt_mgr"),
            ("social", "Social Media", "Marketing", "mkt_mgr"),
            ("visit", "Site Visit Coordinator", "Site Visits", "ceo"),
            ("legal", "Legal Documentation", "Legal", "ceo"),
            ("compliance", "Compliance (RERA)", "Legal", "ceo"),
            ("loan", "Loan Assistance", "Finance", "ceo"),
            ("accounts", "Accounts & Receivables", "Finance", "ceo"),
            ("monitor", "Project Monitoring", "Builder Ops", "ceo"),
            ("material", "Material Management", "Builder Ops", "ceo"),
            ("partner", "Channel Partner Agent", "Partners", "ceo"),
            ("research", "Market Research", "Research", "ceo"),
            ("advisor", "Investment Advisor", "Research", "ceo"),
            ("reception", "Voice Receptionist (24x7)", "Support", "ceo"),
        ],
        "pipelines": [
            ("New Lead", "Capture → qualify → recommend → proposal → site visit → booking", True, [
                ("crm", "Capture and de-duplicate the new lead for {product}; tag the source."),
                ("recommend", "Match the lead's budget and needs to available inventory."),
                ("proposal", "Draft a property proposal with cost sheet and payment plan."),
                ("visit", "Schedule a site visit and draft confirmation + reminder messages."),
                ("sales_mgr", "Review fit, assign the rep, and set the next action."),
            ]),
            ("Property Launch", "Brief → content → RERA ad-check → campaign → intake", True, [
                ("mkt_mgr", "Plan the launch campaign for {product} across channels."),
                ("content", "Write the listing copy, ad creatives and landing content."),
                ("compliance", "Check every creative for RERA number and approved-spec claims (block if missing)."),
                ("social", "Schedule the campaign and define the lead-intake routing."),
            ]),
            ("Milestone Billing", "Slab event → demand letters → receivables → escalation", True, [
                ("monitor", "Confirm the construction slab/milestone completion for {product}."),
                ("accounts", "Generate demand letters for all linked customers and track receivables."),
                ("accounts", "Prepare the overdue reminder ladder (15/30/60 days)."),
            ]),
            ("RERA Quarterly", "Assemble → draft QPR → human review → file", True, [
                ("monitor", "Assemble construction progress data for the quarter."),
                ("accounts", "Compile collections and escrow figures."),
                ("compliance", "Draft the RERA QPR filing pack for partner review."),
            ]),
        ],
        "tasks": [
            ("recommend", "Live inventory query (3BHK availability)"),       # UC-RE-01
            ("advisor", "Dead-stock repositioning proposal"),                # UC-RE-04
            ("crm", "Stale-lead resurrection campaign"),                     # UC-RE-06
            ("crm", "Merge duplicate leads"),                               # UC-RE-07
            ("visit", "Optimize tomorrow's site-visit route"),              # UC-RE-10
            ("followup", "No-show recovery sequence"),                      # UC-RE-11
            ("legal", "Generate booking pack (form + cost sheet)"),         # UC-RE-13
            ("accounts", "Run milestone demand letters"),                   # UC-RE-14
            ("legal", "Registration readiness this week"),                  # UC-RE-15
            ("loan", "Chase stuck loan files"),                            # UC-RE-16
            ("success", "Snagging / defect ticket round"),                  # UC-RE-17
            ("compliance", "RERA QPR autopilot"),                          # UC-RE-24
            ("partner", "Calculate channel-partner commissions"),          # UC-RE-28
            ("reception", "Answer inbound enquiry & book visit"),
        ],
    },

    # ─────────────────────────── HEALTHCARE / CLINIC ────────────────────────
    "Healthcare": {
        "lifecycle": ["Inquiry", "Booking", "Visit", "Treatment", "Billing",
                      "Follow-up", "Recall"],
        "kg_entities": ["Patient", "Appointment", "Practitioner", "Treatment Plan",
                        "Prescription", "Insurance Policy", "Lab Order", "Invoice"],
        "rules": [
            ("HC-R1", "AI asked to share a diagnosis or result", "Never communicate diagnoses/results without practitioner release — route only", True),
            ("HC-R2", "Any patient data", "Local-only; BYO-cloud toggle locked off", True),
            ("HC-R3", "Reminder on a shared channel", "Use privacy-safe phrasing; exclude condition names", True),
            ("HC-R4", "Negative response keyword in follow-up", "Urgent flag to doctor (no AI advice)", True),
        ],
        "roles": [
            ("reception", "Front-Desk Voice Receptionist", "Front Office", "ceo"),
            ("appt", "Appointment Coordinator", "Front Office", "ceo"),
            ("followup", "Patient Follow-up Agent", "Care", "ceo"),
            ("billing", "Billing & Insurance Agent", "Finance", "ceo"),
            ("pharmacy", "Pharmacy Inventory Agent", "Operations", "ceo"),
            ("lab", "Lab Coordination Agent", "Care", "ceo"),
            ("recall", "Recall / Preventive-care Agent", "Care", "ceo"),
            ("records", "Compliance & Records Agent", "Operations", "ceo"),
            ("feedback", "Feedback Agent", "Support", "ceo"),
        ],
        "pipelines": [
            ("Appointment & reminder", "Book → confirm → remind → backfill", False, [
                ("reception", "Take the inbound request and identify the patient for {product}."),
                ("appt", "Book per practitioner calendar rules (buffers, durations)."),
                ("followup", "Draft T-24h WhatsApp confirm and T-2h reminder (privacy-safe)."),
            ]),
            ("Insurance claim", "Collect → verify → submit → chase", True, [
                ("records", "Compile the patient record and treatment summary."),
                ("billing", "Prepare the insurer pre-auth/claim with the document checklist."),
            ]),
            ("Lab loop closure", "Order → result → doctor release → inform", True, [
                ("lab", "Track the lab order to result received."),
                ("followup", "Inform the patient ONLY after doctor release (blocking gate)."),
            ]),
        ],
        "tasks": [
            ("reception", "Voice scheduling (inbound)"), ("followup", "No-show reduction sequence"),
            ("recall", "Quarterly recall (e.g. HbA1c)"), ("followup", "Post-procedure day 1/3/7 check-in"),
            ("billing", "Insurance pre-auth tracking"), ("pharmacy", "Pharmacy reorder PO draft"),
            ("billing", "End-of-day reconciliation"), ("feedback", "Collect visit feedback"),
        ],
    },

    # ─────────────────────────── LAW FIRM ───────────────────────────────────
    "Legal Industry": {
        "lifecycle": ["Inquiry", "Conflict Check", "Matter", "Hearings", "Closure"],
        "kg_entities": ["Client", "Matter", "Opposing Party", "Court", "Hearing",
                        "Filing", "Document", "Time Entry", "Invoice"],
        "rules": [
            ("LF-R1", "Any outbound document/communication", "Requires named-lawyer approval (AC-05 hardened)", True),
            ("LF-R2", "Limitation / statutory deadline", "Alerts cannot be auto-approved or snoozed by AI tiers", True),
            ("LF-R3", "Cross practice-group access", "Matter-level confidentiality walls enforced", True),
            ("LF-R4", "New client intake", "Run conflict check vs past parties; block on conflict", False),
        ],
        "roles": [
            ("intake", "Intake / Conflict-Check Agent", "Intake", "ceo"),
            ("para", "Paralegal (Drafting)", "Practice", "ceo"),
            ("research", "Legal Research Agent", "Practice", "ceo"),
            ("diary", "Court Diary Agent", "Practice", "ceo"),
            ("client", "Client Communication Agent", "Client Care", "ceo"),
            ("billing", "Billing & Trust-Accounting", "Finance", "ceo"),
            ("compliance", "Compliance Agent", "Practice", "ceo"),
            ("vault", "Document Vault Agent", "Operations", "ceo"),
        ],
        "pipelines": [
            ("Draft a legal notice", "Research → draft → proof → bill", True, [
                ("research", "Research precedent and sections relevant to {product}."),
                ("para", "Draft the notice/petition to the court template."),
                ("para", "Proofread, paginate and format for filing."),
                ("billing", "Log billable time and assemble the invoice."),
            ]),
            ("Court diary brief", "Parse → brief", False, [
                ("diary", "Parse hearing dates from orders for {product}."),
                ("diary", "Prepare a D-1 cause-list brief: what each matter needs."),
            ]),
        ],
        "tasks": [
            ("intake", "Conflict check on intake"), ("para", "Dictation-to-draft"),
            ("diary", "Court diary D-7/D-2/D-1 brief"), ("compliance", "Limitation-period sentinel"),
            ("client", "Post-hearing client update"), ("billing", "Voice time capture"),
            ("para", "Prepare hearing bundle"), ("research", "Cited research memo"),
        ],
    },

    # ─────────────────────────── CA / ACCOUNTING ────────────────────────────
    "Chartered Accountants & Tax Consultants": {
        "lifecycle": ["Onboard", "Collect", "Prepare", "Review", "File", "Bill"],
        "kg_entities": ["Client", "Filing", "Document", "Ledger", "Invoice",
                        "Notice", "Engagement"],
        "rules": [
            ("CA-R1", "Outbound document contains figures", "Every figure must carry a source citation (CC-03 hardened)", True),
            ("CA-R2", "Any statutory filing", "No filing submitted without human partner approval", True),
            ("CA-R3", "Cross-client access", "Per-client confidentiality walls", True),
            ("CA-R4", "OCR confidence below threshold", "Queue the item for staff verification (MC-06)", False),
        ],
        "roles": [
            ("collector", "Client Document Collector", "Client Ops", "ceo"),
            ("books", "Bookkeeping Agent", "Compliance", "ceo"),
            ("gst", "GST Specialist", "Compliance", "ceo"),
            ("tds", "TDS Agent", "Compliance", "ceo"),
            ("itr", "Income-Tax Filing Agent", "Compliance", "ceo"),
            ("audit", "Audit Assistant", "Audit", "ceo"),
            ("recon", "Reconciliation Agent", "Compliance", "ceo"),
            ("reminder", "Client Reminder Agent", "Client Ops", "ceo"),
            ("billing", "Engagement / Billing Agent", "Finance", "ceo"),
        ],
        "pipelines": [
            ("Monthly GST filing", "Collect → prepare → variance-gate → notify", True, [
                ("collector", "Confirm documents received for {product}; chase missing ones."),
                ("books", "Post the transactions and reconcile the ledger."),
                ("gst", "Prepare the GSTR-3B and GSTR-1 summary."),
                ("audit", "Run a variance check; flag anomalies before the partner sees it."),
                ("reminder", "Draft the client update summarizing the filing."),
            ]),
            ("Notice handling", "Classify → checklist → draft reply", True, [
                ("itr", "Classify the tax notice and extract the deadline for {product}."),
                ("itr", "Create a response checklist and draft the reply."),
            ]),
        ],
        "tasks": [
            ("reminder", "Multi-client compliance calendar (next 7 days)"),
            ("collector", "Document chase (who hasn't sent invoices)"),
            ("books", "OCR invoices → ledger entries"), ("recon", "Books vs GSTR-2B reconciliation"),
            ("audit", "Variance-gated filing check"), ("billing", "Fee receivables follow-up"),
            ("itr", "Notice classification & reply"), ("gst", "Prepare GSTR-3B"),
        ],
    },

    # ─────────────────────────── EDUCATION ──────────────────────────────────
    "Schools & Colleges": {
        "lifecycle": ["Inquiry", "Application", "Admission", "Enrolled", "Alumni"],
        "kg_entities": ["Student", "Parent", "Class", "Fee", "Certificate", "Inquiry"],
        "rules": [
            ("ED-R1", "Any student data", "PII-locked; restricted access", True),
            ("ED-R2", "Parent communication", "Never include other students' information", True),
            ("ED-R3", "Minor-related external comms", "Restricted to enrolled-guardian contacts only", True),
        ],
        "roles": [
            ("admissions", "Admissions Counselor", "Admissions", "ceo"),
            ("reception", "Inquiry Voice Receptionist", "Admissions", "ceo"),
            ("fees", "Fee Reminder Agent", "Finance", "ceo"),
            ("notices", "Timetable & Notice Agent", "Academics", "ceo"),
            ("parent", "Parent Communication Agent", "Support", "ceo"),
            ("certs", "Certificate / Document Agent", "Registrar", "ceo"),
            ("placement", "Alumni & Placement Agent", "Placement", "ceo"),
        ],
        "pipelines": [
            ("Admission enquiry", "Answer → tour → status", False, [
                ("reception", "Answer the admission enquiry from the prospectus for {product}."),
                ("admissions", "Book a tour and track the application status."),
            ]),
            ("Circular blast", "Compose → translate → deliver", False, [
                ("notices", "Compose the notice for {product} (e.g. PTM) for the right grade."),
                ("parent", "Deliver multilingually on each parent's preferred channel with read tracking."),
            ]),
            ("Certificate issue", "Prepare → registrar approval", True, [
                ("certs", "Generate the bonafide/TC/completion certificate from template."),
            ]),
        ],
        "tasks": [
            ("reception", "Admission-season call handling"), ("fees", "Fee reminder ladder"),
            ("notices", "Multilingual circular blast"), ("certs", "Issue bonafide/TC certificate"),
            ("placement", "Student-employer matching"),
        ],
    },

    # ─────────────────────────── MANUFACTURING ──────────────────────────────
    "Manufacturing": {
        "lifecycle": ["Order", "Production", "QC", "Packed", "Dispatched", "Delivered"],
        "kg_entities": ["Order", "Product", "Vendor", "Purchase Order", "Machine",
                        "Dispatch", "NCR"],
        "rules": [
            ("MF-R1", "Safety-incident keyword in any log", "Immediate owner alert, never batched", True),
            ("MF-R2", "PO above threshold", "Human approval required", False),
            ("MF-R3", "Voice interaction", "Hindi/regional voice pack default-on", False),
        ],
        "roles": [
            ("production", "Production Reporter", "Operations", "ceo"),
            ("stores", "Inventory / Stores Agent", "Operations", "ceo"),
            ("procure", "Procurement Agent", "Procurement", "ceo"),
            ("vendor", "Vendor Management Agent", "Procurement", "ceo"),
            ("quality", "Quality (NCR) Agent", "Quality", "ceo"),
            ("dispatch", "Dispatch & Logistics Agent", "Logistics", "ceo"),
            ("maint", "Maintenance Scheduler Agent", "Operations", "ceo"),
            ("orderdesk", "Order-Desk Agent", "Sales", "ceo"),
        ],
        "pipelines": [
            ("Daily production report", "Log → summarize → flag", False, [
                ("production", "Capture today's output, downtime and rejections for {product}."),
                ("stores", "Report stock levels and flag low-inventory items."),
                ("quality", "Note quality issues / NCRs from the shift."),
            ]),
            ("Reorder automation", "Breach → quote → PO", True, [
                ("stores", "Detect min-stock breach for {product}."),
                ("procure", "Compare approved-vendor quotes and draft the PO."),
            ]),
        ],
        "tasks": [
            ("production", "Voice production logging"), ("procure", "Reorder automation"),
            ("orderdesk", "Order-to-dispatch status"), ("maint", "Preventive maintenance schedule"),
            ("quality", "Quality NCR loop"), ("dispatch", "Dispatch docs + e-way bill"),
        ],
    },

    # ─────────────────────────── RETAIL / D2C ───────────────────────────────
    "Retail Shops": {
        "lifecycle": ["Browse", "Cart", "Order", "Fulfil", "Delivered", "Repeat"],
        "kg_entities": ["Order", "Product", "Customer", "Supplier", "Review", "Campaign"],
        "rules": [
            ("RT-R1", "Refund beyond policy", "Auto-route to human", False),
            ("RT-R2", "Promo discount below margin floor", "Block", False),
            ("RT-R3", "Review response", "Never admit legal liability (phrase-block list)", True),
        ],
        "roles": [
            ("orders", "Order Management Agent", "Operations", "ceo"),
            ("support", "Customer Support (WhatsApp/IG)", "Support", "ceo"),
            ("inventory", "Inventory Agent", "Operations", "ceo"),
            ("supplier", "Supplier PO Agent", "Procurement", "ceo"),
            ("reviews", "Reviews & Reputation Agent", "Marketing", "ceo"),
            ("promo", "Promotions Agent", "Marketing", "ceo"),
            ("loyalty", "Loyalty / Winback Agent", "Marketing", "ceo"),
            ("cod", "COD-Reconciliation Agent", "Finance", "ceo"),
        ],
        "pipelines": [
            ("Festival campaign", "Plan → create → schedule", False, [
                ("promo", "Plan the festival campaign for {product}."),
                ("promo", "Draft WhatsApp/Instagram promo messages within the margin floor."),
            ]),
            ("Abandoned-checkout recovery", "Detect → sequence", False, [
                ("loyalty", "Draft an abandoned-checkout recovery sequence for {product}."),
            ]),
        ],
        "tasks": [
            ("support", "Order-status self-service"), ("loyalty", "Abandoned-checkout recovery"),
            ("inventory", "Low-stock & dead-stock brief"), ("reviews", "Respond to reviews (human-gated)"),
            ("cod", "COD remittance reconciliation"), ("promo", "Festival campaign builder"),
        ],
    },

    # ─────────────────────────── MARKETING / AGENCY ─────────────────────────
    "Marketing / Digital Agency": {
        "lifecycle": ["Lead", "Pitch", "Onboard", "Deliver", "Retain"],
        "kg_entities": ["Client", "Campaign", "Content", "Ad Account", "Report", "Proposal"],
        "rules": [
            ("AG-R1", "Cross-client memory access", "Client-confidentiality walls (per-client isolation)", True),
            ("AG-R2", "Publish content", "Requires recorded client-approval token", True),
            ("AG-R3", "New business pitch", "Run competitor-client conflict check", False),
        ],
        "roles": [
            ("am", "Account Manager", "Accounts", "ceo"),
            ("content", "Content Writer", "Creative", "ceo"),
            ("seo", "SEO Specialist", "Creative", "ceo"),
            ("social", "Social Media Manager", "Creative", "ceo"),
            ("ads", "Ads Performance Agent", "Performance", "ceo"),
            ("reporting", "Reporting Agent", "Accounts", "ceo"),
            ("newbiz", "New-Business (Proposal) Agent", "Growth", "ceo"),
        ],
        "pipelines": [
            ("Weekly client report", "Pull → insight → deck → review → send", True, [
                ("ads", "Pull the week's ad and channel performance for {product}."),
                ("reporting", "Summarize insights and build the report deck."),
                ("am", "Review and send to the client with the approval token."),
            ]),
            ("Proposal from discovery call", "Transcript → proposal", True, [
                ("newbiz", "Turn the discovery-call notes into a tailored proposal for {product}."),
            ]),
        ],
        "tasks": [
            ("content", "Content calendar generation"), ("ads", "Ad-spend anomaly alert"),
            ("reporting", "Weekly client report autopilot"), ("newbiz", "Proposal from transcript"),
            ("am", "Capacity vs retainer view"),
        ],
    },

    # ─────────────────────────── RECRUITMENT ────────────────────────────────
    "Recruitment Agencies": {
        "lifecycle": ["Sourced", "Screened", "Interview", "Offer", "Joined"],
        "kg_entities": ["Candidate", "Job", "Client", "Interview", "Offer", "Invoice"],
        "rules": [
            ("RC-R1", "Candidate rejection", "No automated rejection without human review (fairness)", True),
            ("RC-R2", "Cross-client candidate access", "Candidate PII walls between client accounts", True),
            ("RC-R3", "Screening decision", "Criteria logged for auditability (bias review)", True),
        ],
        "roles": [
            ("sourcer", "Sourcing Agent", "Delivery", "ceo"),
            ("screen", "Screening Agent", "Delivery", "ceo"),
            ("scheduler", "Interview Scheduler", "Delivery", "ceo"),
            ("candcomm", "Candidate Communication Agent", "Delivery", "ceo"),
            ("client", "Client (Employer) Account Agent", "Accounts", "ceo"),
            ("offer", "Offer & Joining Tracker", "Delivery", "ceo"),
            ("invoice", "Invoice / Replacement-Guarantee Agent", "Finance", "ceo"),
        ],
        "pipelines": [
            ("Fill a role", "JD → source → screen → schedule", True, [
                ("client", "Capture the JD and sourcing plan for {product}."),
                ("sourcer", "Source candidates and build a longlist."),
                ("screen", "Screen to a shortlist with reasoning (human reviews rejections)."),
                ("scheduler", "Negotiate interview slots across candidate and panel."),
            ]),
        ],
        "tasks": [
            ("sourcer", "JD intake → sourcing checklist"), ("screen", "Resume screening to shortlist"),
            ("scheduler", "Interview slot negotiation"), ("candcomm", "Ghosting-prevention nurture"),
            ("offer", "Joining confirmation → invoice"), ("client", "Aging positions report"),
        ],
    },

    # ─────────────────────────── HOSPITALITY ────────────────────────────────
    "Hospitality / Restaurant": {
        "lifecycle": ["Inquiry", "Reservation", "Visit", "Feedback", "Loyalty"],
        "kg_entities": ["Reservation", "Table", "Guest", "Event", "Supplier", "Review"],
        "rules": [
            ("HO-R1", "Comp / refund beyond policy", "Route to human", False),
            ("HO-R2", "Review response", "Never admit liability; brand-safe phrasing", True),
        ],
        "roles": [
            ("reception", "Voice Receptionist (Reservations)", "Front Office", "ceo"),
            ("tables", "Table / Turn Optimizer", "Operations", "ceo"),
            ("events", "Event Booking Agent", "Sales", "ceo"),
            ("supply", "Supplier Ordering Agent", "Procurement", "ceo"),
            ("reviews", "Reviews & Reputation Agent", "Marketing", "ceo"),
            ("loyalty", "Loyalty Winback Agent", "Marketing", "ceo"),
        ],
        "pipelines": [
            ("Event proposal", "Enquiry → proposal", True, [
                ("events", "Turn the banquet enquiry into a tailored event proposal for {product}."),
            ]),
            ("Daily flash report", "Collect → summarize", False, [
                ("tables", "Summarize tonight's covers and turns vs last week for {product}."),
            ]),
        ],
        "tasks": [
            ("reception", "Reservation handling"), ("supply", "Supplier order from par levels"),
            ("reviews", "Review reputation loop"), ("loyalty", "60-day guest winback"),
            ("tables", "Daily flash report"),
        ],
    },

    # ─────────────────────────── LOGISTICS / FLEET ──────────────────────────
    "Logistics": {
        "lifecycle": ["Booking", "Assigned", "In-Transit", "Delivered", "Billed"],
        "kg_entities": ["Trip", "Vehicle", "Driver", "Client", "POD", "Document"],
        "rules": [
            ("LG-R1", "Vehicle document (insurance/permit/fitness) nearing expiry", "Alert + block dispatch on expiry", False),
            ("LG-R2", "Detention / demurrage threshold crossed", "Alert client and ops", False),
        ],
        "roles": [
            ("booking", "Booking Desk Agent", "Operations", "ceo"),
            ("trips", "Trip Assignment & Driver Comms", "Operations", "ceo"),
            ("pod", "POD Chase Agent", "Operations", "ceo"),
            ("maint", "Vehicle Maintenance & Doc Expiry", "Fleet", "ceo"),
            ("alerts", "Detention / Demurrage Alerting", "Operations", "ceo"),
            ("quote", "Rate-Card Quoting Agent", "Sales", "ceo"),
        ],
        "pipelines": [
            ("Shipment cycle", "Book → assign → track → POD", False, [
                ("booking", "Take the booking and rate for {product}."),
                ("trips", "Assign a vehicle/driver and send trip instructions."),
                ("pod", "Chase proof-of-delivery and update the client."),
            ]),
        ],
        "tasks": [
            ("booking", "Booking desk intake"), ("trips", "Trip assignment & driver comms"),
            ("pod", "POD chase"), ("maint", "Vehicle doc-expiry calendar"),
            ("quote", "Client rate-card quote"), ("alerts", "Idle-vehicle report"),
        ],
    },

    # ─────────────────────────── LIGHTER VERTICALS ──────────────────────────
    "Insurance": {
        "lifecycle": ["Lead", "Quote", "Policy", "Claim", "Renewal"],
        "kg_entities": ["Lead", "Policy", "Customer", "Claim", "Premium"],
        "rules": [("IN-R1", "Claim decision", "Human approval before settlement", False)],
        "roles": [
            ("advisor", "Policy Advisor", "Sales", "ceo"),
            ("claims", "Claims Processor", "Operations", "ceo"),
            ("renew", "Renewals Specialist", "Support", "ceo"),
        ],
        "pipelines": [
            ("New policy quote", "Assess → quote", False, [
                ("advisor", "Assess needs and recommend a policy for {product}."),
                ("advisor", "Prepare a clear quote summary."),
            ]),
            ("Claim processing", "Collect → verify → decide", True, [
                ("claims", "Compile and verify the claim documents."),
                ("claims", "Summarize and recommend a decision."),
            ]),
        ],
        "tasks": [("advisor", "Recommend policy"), ("renew", "Renewal reminder"),
                  ("claims", "Process claim"), ("renew", "Lapse follow-up")],
    },
    "Agriculture": {
        "lifecycle": ["Plan", "Sow", "Grow", "Harvest", "Sell"],
        "kg_entities": ["Farm", "Crop", "Input", "Mandi Price", "Buyer"],
        "rules": [("AG2-R1", "Advisory output", "Cite source guidance; regional language default", False)],
        "roles": [
            ("advisory", "Crop Advisor", "Operations", "ceo"),
            ("market", "Mandi Price Tracker", "Operations", "ceo"),
            ("supply", "Input Supply Coordinator", "Procurement", "ceo"),
        ],
        "pipelines": [("Crop advisory", "Assess → advise", False, [
            ("advisory", "Give a sowing/irrigation advisory for {product}."),
            ("market", "Summarize mandi prices and the best selling window."),
        ])],
        "tasks": [("advisory", "Pest advisory"), ("market", "Price update"), ("supply", "Order inputs")],
    },
    "Construction": {
        "lifecycle": ["Plan", "Procure", "Build", "Inspect", "Handover"],
        "kg_entities": ["Project", "Material", "Vendor", "Milestone", "Safety Report"],
        "rules": [("CN-R1", "Safety item open", "Immediate flag; block sign-off", True)],
        "roles": [
            ("pm", "Project Coordinator", "Operations", "ceo"),
            ("procure", "Procurement Officer", "Procurement", "ceo"),
            ("safety", "Safety & Compliance", "Operations", "ceo"),
        ],
        "pipelines": [("Site progress report", "Collect → summarize → flag", False, [
            ("pm", "Summarize site progress and milestones for {product}."),
            ("procure", "List material requirements and pending orders."),
            ("safety", "Note safety/compliance items to address."),
        ])],
        "tasks": [("pm", "Daily progress report"), ("procure", "Raise material indent"), ("safety", "Safety checklist")],
    },
    "Small Business Owners": {
        "lifecycle": ["Lead", "Sale", "Deliver", "Repeat"],
        "kg_entities": ["Customer", "Order", "Expense", "Supplier"],
        "rules": [("SB-R1", "Payment/external send", "Owner approval for money or new contacts", False)],
        "roles": [
            ("ops", "Operations Assistant", "Operations", "ceo"),
            ("market", "Marketing Assistant", "Marketing", "ceo"),
            ("books", "Bookkeeper", "Finance", "ceo"),
        ],
        "pipelines": [("Get more customers", "Plan → content → outreach", False, [
            ("market", "Suggest a simple marketing plan for {product}."),
            ("market", "Draft 3 promotional messages."),
        ])],
        "tasks": [("market", "Promote on WhatsApp"), ("books", "Track expenses"), ("ops", "Manage orders")],
    },
    "Senior Citizens": {
        "lifecycle": ["Onboard", "Daily Care", "Check-in"],
        "kg_entities": ["Routine", "Medicine", "Appointment", "Family Contact"],
        "rules": [("SC-R1", "Health reminder", "Never give medical advice; reminders only", True)],
        "roles": [
            ("assist", "Daily Assistant", "Care", "ceo"),
            ("health", "Health Reminder", "Care", "ceo"),
            ("family", "Family Liaison", "Care", "ceo"),
        ],
        "pipelines": [("Daily check-in", "Plan → remind → update family", False, [
            ("assist", "Prepare a simple daily plan and reminders for {product}."),
            ("health", "List medicine and appointment reminders for today."),
            ("family", "Draft a short update for family."),
        ])],
        "tasks": [("health", "Medicine reminder"), ("assist", "Read the news"), ("family", "Call family")],
    },
    "Personal Productivity Assistant": {
        "lifecycle": ["Capture", "Plan", "Do", "Review"],
        "kg_entities": ["Task", "Note", "Contact", "Event"],
        "rules": [("PP-R1", "External send", "Confirm before sending on your behalf", False)],
        "roles": [
            ("planner", "Day Planner", "Personal", "ceo"),
            ("inbox", "Inbox Assistant", "Personal", "ceo"),
            ("notes", "Notes & Research", "Personal", "ceo"),
        ],
        "pipelines": [("Plan my day", "Triage → plan → summarize", False, [
            ("inbox", "Summarize and categorize today's messages about {product}."),
            ("planner", "Build a prioritized to-do list and schedule."),
            ("notes", "Draft notes and follow-ups to remember."),
        ])],
        "tasks": [("planner", "Plan the week"), ("inbox", "Triage email"), ("notes", "Summarize a document")],
    },
    "Software company": {
        "lifecycle": ["Idea", "Spec", "Build", "QA", "Launch"],
        "kg_entities": ["Product", "Feature", "Ticket", "Release", "Customer"],
        "rules": [("SW-R1", "Production deploy", "Human approval (change gate)", False)],
        "roles": [
            ("cpo", "Product Manager", "Product", "ceo"),
            ("cto", "Engineering Lead", "Engineering", "ceo"),
            ("eng", "Software Engineer", "Engineering", "cto"),
            ("qa", "QA Engineer", "Engineering", "cto"),
            ("design", "Product Designer", "Product", "cpo"),
            ("market", "Growth Marketer", "Marketing", "ceo"),
        ],
        "pipelines": [
            ("Ship a feature", "PRD → design → build → QA → launch", True, [
                ("cpo", "Write a crisp PRD for {product}: problem, users, scope, metrics."),
                ("design", "Propose the UX flow and key screens."),
                ("eng", "Produce an implementation plan and task breakdown."),
                ("qa", "Write a test plan and edge cases."),
                ("market", "Draft a launch announcement for {product}."),
            ]),
            ("Go-to-market", "Positioning → content", False, [
                ("market", "Define positioning and messaging for {product}."),
                ("market", "Draft a 3-post launch calendar."),
            ]),
        ],
        "tasks": [("cpo", "Write product spec"), ("cpo", "Prioritize backlog"),
                  ("eng", "Plan a sprint"), ("qa", "Regression checklist"),
                  ("market", "Draft launch email"), ("design", "Audit onboarding UX")],
    },
}

GENERIC = {
    "lifecycle": ["Lead", "Engage", "Deliver", "Retain"],
    "kg_entities": ["Customer", "Order", "Document", "Vendor"],
    "rules": [("G-R1", "Money / external send / deletion", "Routes through the approval chain", False)],
    "roles": [
        ("ops", "Operations Lead", "Operations", "ceo"),
        ("market", "Marketing Lead", "Marketing", "ceo"),
        ("support", "Support Lead", "Support", "ceo"),
        ("finance", "Finance Lead", "Finance", "ceo"),
    ],
    "pipelines": [("Plan & execute", "Plan → produce → review", True, [
        ("ops", "Create a plan to deliver {product}."),
        ("market", "Draft the communications for {product}."),
        ("support", "Review the output and list follow-ups."),
    ])],
    "tasks": [("ops", "Operational checklist"), ("market", "Draft announcement"),
              ("finance", "Cost summary"), ("support", "Customer follow-up")],
}

# Ordered list shown in the UI (the user's 16 + doc 13's Agency & Hospitality).
SUPPORTED = [
    "Real Estate", "Chartered Accountants & Tax Consultants", "Healthcare",
    "Legal Industry", "Marketing / Digital Agency", "Recruitment Agencies",
    "Manufacturing", "Retail Shops", "Schools & Colleges", "Insurance",
    "Logistics", "Hospitality / Restaurant", "Construction", "Agriculture",
    "Small Business Owners", "Senior Citizens", "Personal Productivity Assistant",
    "Software company",
]


def _expand(industry, spec):
    """Compact spec → full suggestion dict (agents, pipelines, tasks, lifecycle, kg, rules)."""
    roles = [_ceo()] + list(spec["roles"])
    role_to_name, agents, departments = {}, [], []
    for i, (key, desig, dept, mgr) in enumerate(roles):
        name = _NAMES[i % len(_NAMES)]
        role_to_name[key] = name
        if dept not in departments:
            departments.append(dept)
        agents.append({
            "role": key, "name": name, "designation": desig, "department": dept,
            "reports_to": role_to_name.get(mgr) if mgr else None,
            "is_ceo": key == "ceo",
            "skills": _SKILLS.get(key, ["general"]),
            "model": "smart" if key == "ceo" else "fast",
        })

    pipelines = [{
        "name": name, "description": desc, "approvals": approvals,
        "steps": [{"role": r, "agent_name": role_to_name.get(r, _NAMES[0]),
                   "instruction": ins} for r, ins in steps],
    } for name, desc, approvals, steps in spec["pipelines"]]

    tasks = [{"role": r, "agent_name": role_to_name.get(r, _NAMES[0]), "title": t}
             for r, t in spec["tasks"]]

    rules = [{"id": rid, "condition": cond, "behavior": beh, "locked": locked}
             for rid, cond, beh, locked in spec.get("rules", [])]

    return {"industry": industry, "source": "curated", "departments": departments,
            "agents": agents, "pipelines": pipelines, "tasks": tasks,
            "lifecycle": spec.get("lifecycle", []),
            "kg_entities": spec.get("kg_entities", []), "rules": rules}


def curated(industry: str) -> dict:
    return _expand(industry, INDUSTRIES.get(industry, GENERIC))


def generate_with_ai(industry: str, product: str | None = None) -> dict:
    """Tailor agents/pipelines/tasks via the local LLM; keep curated lifecycle/kg/rules."""
    base = curated(industry)
    system = (
        "You design an AI employee org for a company. Given an industry and a "
        "product, return ONLY JSON: {\"agents\":[{\"designation\":\"..\","
        "\"department\":\"..\",\"reports_to\":\"CEO Agent\"}],\"pipelines\":"
        "[{\"name\":\"..\",\"description\":\"..\",\"approvals\":true,\"steps\":"
        "[{\"designation\":\"..\",\"instruction\":\"..\"}]}],\"tasks\":"
        "[{\"designation\":\"..\",\"title\":\"..\"}]}. 5-7 agents, 1-2 pipelines "
        "of 3-5 steps, 6 tasks. Specific to the product.")
    prompt = (f"Industry: {industry}\nProduct: {product or 'general operations'}\n"
              "Design the AI org and return the JSON.")
    data = llm.chat_json(prompt, system=system, smart=False, timeout=150, num_predict=750)
    if not data or not isinstance(data.get("agents"), list) or not data["agents"]:
        base = dict(base)
        base["note"] = "AI generation unavailable — showing the curated template."
        return base

    agents = [{"role": "ceo", "name": _NAMES[0], "designation": "CEO Agent",
               "department": "Executive", "reports_to": None, "is_ceo": True,
               "skills": ["orchestration"], "model": "smart"}]
    departments, by_desig = ["Executive"], {"CEO Agent": _NAMES[0]}
    for i, a in enumerate(data["agents"][:7], start=1):
        desig = str(a.get("designation", f"Specialist {i}"))[:60]
        dept = str(a.get("department", "Operations"))[:40]
        name = _NAMES[i % len(_NAMES)]
        by_desig[desig] = name
        if dept not in departments:
            departments.append(dept)
        agents.append({"role": desig.lower().replace(" ", "_")[:20], "name": name,
                       "designation": desig, "department": dept, "reports_to": _NAMES[0],
                       "is_ceo": False, "skills": ["general"], "model": "fast"})

    def name_for(d):
        return by_desig.get(str(d), _NAMES[1])

    pipelines = []
    for pl in (data.get("pipelines") or [])[:3]:
        steps = [{"role": "", "agent_name": name_for(s.get("designation", "")),
                  "instruction": str(s.get("instruction", ""))[:300]}
                 for s in (pl.get("steps") or [])[:6]]
        if steps:
            pipelines.append({"name": str(pl.get("name", "Pipeline"))[:80],
                              "description": str(pl.get("description", ""))[:160],
                              "approvals": bool(pl.get("approvals")), "steps": steps})
    tasks = [{"role": "", "agent_name": name_for(t.get("designation", "")),
              "title": str(t.get("title", ""))[:80]}
             for t in (data.get("tasks") or [])[:8] if t.get("title")]

    return {"industry": industry, "source": "ai", "departments": departments,
            "agents": agents, "pipelines": pipelines or base["pipelines"],
            "tasks": tasks or base["tasks"], "lifecycle": base["lifecycle"],
            "kg_entities": base["kg_entities"], "rules": base["rules"]}

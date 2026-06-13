"""
Vertical Full Agents — the packaged, named, out-of-the-box products ("Dentist
Agent", "Restaurant Agent", "Plumber Agent"…). Build once, sell many. Each is a
thin configuration over the same core: an industry template (roster + lifecycle
+ skin) + the right Solutions/recipes + a persona front-desk chatbot + the
applicable compliance pack.

One click **deploys** a complete, working workspace for that vertical; one click
**undeploys** it (a manifest records everything created, so teardown is clean).
Actions are also voice-drivable via `/verticals/resolve`.
"""
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import industry_templates as tpl
from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import (Agent, Chatbot, ChatbotChannel, Pipeline, PipelineStep,
                      Recipe, Tenant, VerticalDeployment)
from ..routers.company import ApplyIn, apply_suggestion
from ..routers.recipes import _BYID as RECIPE_BYID
from ..security import ulid

router = APIRouter(tags=["verticals"])

# Recipe bundles (all ids are valid against recipes.CATALOG)
_APPT = ["confirm_appts", "noshow_prevent", "review_request", "onboarding", "daily_briefing"]   # appointment businesses
_LEAD = ["speed_to_lead", "quote_followup", "stale_revival", "review_request", "daily_briefing"]  # lead/quote businesses
_SHOP = ["missed_call_wa", "review_request", "inventory_alert", "retention", "daily_briefing"]     # retail/commerce
_PRO = ["chase_invoices", "onboarding", "stale_revival", "daily_briefing"]                          # professional/finance
_CARE = ["confirm_appts", "noshow_prevent", "retention", "birthday", "daily_briefing"]              # recurring care


def V(vid, name, emoji, industry, tagline, who, included, recipes, *, price, category,
      compliance=(), integrations=("WhatsApp", "Email"), persona=None):
    return {
        "id": vid, "name": name, "emoji": emoji, "industry": industry, "tagline": tagline,
        "for": who, "included": list(included), "recipes": list(recipes), "price": price,
        "category": category, "compliance": list(compliance), "integrations": list(integrations),
        "persona": persona or (f"You are the warm, professional AI front desk for a {who.lower()} "
                               "business. You answer questions, capture details, book and confirm "
                               "appointments, follow up, and never invent facts — if unsure, you hand off."),
    }


# Common "what's included" snippets
_INC_APPT = ["Appointment booking + T-24h / T-2h reminders", "No-show prevention with waitlist backfill",
             "Review generation after each visit", "New-customer onboarding by chat", "Daily 8am briefing"]
_INC_LEAD = ["Instant lead capture + qualify", "Speed-to-lead (under 5 min)", "Quote / estimate follow-up",
             "Long-term nurture with reminders", "Daily briefing"]
_INC_SHOP = ["Missed-call → WhatsApp auto-reply", "Order / availability questions", "Review reputation loop",
             "Low-stock alerts", "Customer win-back + daily briefing"]
_INC_PRO = ["Client document chasing", "Deadline / compliance reminders", "Fee / invoice follow-up",
            "Client onboarding", "Daily briefing"]

VERTICALS = [
    # ───────────── Healthcare & Wellness ─────────────
    V("dentist", "Dentist Agent", "🦷", "Healthcare", "A front desk that never sleeps",
      "Dental practices", _INC_APPT, _APPT, price="$49-99", category="Healthcare & Wellness",
      compliance=["HIPAA-adjacent (Clinic)"], integrations=("Google Calendar", "Twilio SMS"),
      persona="You are a friendly, HIPAA-aware dental front-desk assistant. You book and confirm "
              "appointments and answer common questions, but never give clinical advice."),
    V("clinic", "Clinic / GP Agent", "🏥", "Healthcare", "Bookings, reminders and triage intake",
      "Clinics & GPs", _INC_APPT, _APPT, price="$49-99", category="Healthcare & Wellness",
      compliance=["HIPAA-adjacent (Clinic)"], integrations=("Google Calendar", "Twilio SMS")),
    V("physio", "Physiotherapy Agent", "🧑‍⚕️", "Healthcare", "Keep the schedule full, cut no-shows",
      "Physio & rehab clinics", _INC_APPT, _APPT, price="$39-79", category="Healthcare & Wellness",
      compliance=["HIPAA-adjacent (Clinic)"]),
    V("optometry", "Optometry Agent", "👓", "Healthcare", "Eye-test bookings and recall reminders",
      "Opticians & eye clinics", _INC_APPT, _CARE, price="$39-79", category="Healthcare & Wellness"),
    V("vet", "Veterinary Agent", "🐾", "Healthcare", "Pet appointments, reminders and recalls",
      "Vet clinics", _INC_APPT, _CARE, price="$39-79", category="Healthcare & Wellness"),
    V("mentalhealth", "Therapy / Counseling Agent", "🧠", "Healthcare", "Confidential booking and gentle reminders",
      "Therapists & counselors", _INC_APPT, _APPT, price="$39-79", category="Healthcare & Wellness",
      compliance=["HIPAA-adjacent (Clinic)"]),
    V("diagnostics", "Diagnostic Lab Agent", "🔬", "Healthcare", "Test bookings, prep instructions, reports",
      "Pathology & imaging labs", _INC_APPT, _APPT, price="$49-99", category="Healthcare & Wellness",
      compliance=["HIPAA-adjacent (Clinic)"]),
    V("pharmacy", "Pharmacy Agent", "💊", "Retail Shops", "Refill reminders and stock questions",
      "Pharmacies", _INC_SHOP, _SHOP, price="$39-79", category="Healthcare & Wellness"),

    # ───────────── Hospitality & Food ─────────────
    V("restaurant", "Restaurant Agent", "🍽️", "Hospitality / Restaurant", "Reservations, reviews and a nightly report",
      "Restaurants & cafes", ["Reservation handling + confirmations", "No-show / waitlist management",
      "Review reputation loop", "60-day guest win-back", "Nightly flash report"], _APPT,
      price="$39-79", category="Hospitality & Food", integrations=("Google Calendar", "WhatsApp")),
    V("cafe", "Café Agent", "☕", "Hospitality / Restaurant", "Orders, loyalty and reviews",
      "Cafés & coffee shops", _INC_SHOP, _SHOP, price="$19-39", category="Hospitality & Food"),
    V("hotel", "Hotel Agent", "🏨", "Hospitality / Restaurant", "Room bookings and guest concierge",
      "Hotels & B&Bs", ["Room booking + confirmations", "Pre-arrival + checkout messaging",
      "Upsell add-ons", "Review reputation loop", "Daily occupancy briefing"], _APPT,
      price="$49-99", category="Hospitality & Food", integrations=("Google Calendar", "WhatsApp")),
    V("bakery", "Bakery Agent", "🥐", "Retail Shops", "Custom-order taking and pickups",
      "Bakeries & patisseries", _INC_SHOP, _SHOP, price="$19-39", category="Hospitality & Food"),
    V("catering", "Catering Agent", "🍱", "Hospitality / Restaurant", "Quote, confirm and follow up events",
      "Caterers & cloud kitchens", _INC_LEAD, _LEAD, price="$39-79", category="Hospitality & Food"),

    # ───────────── Beauty & Personal Care ─────────────
    V("salon", "Salon Agent", "💇", "Hospitality / Restaurant", "Fill the chair, cut no-shows",
      "Hair & beauty salons", _INC_APPT, _APPT, price="$29-59", category="Beauty & Personal Care"),
    V("spa", "Spa Agent", "💆", "Hospitality / Restaurant", "Relaxed booking and rebooking",
      "Spas & wellness", _INC_APPT, _CARE, price="$29-59", category="Beauty & Personal Care"),
    V("barber", "Barber Agent", "💈", "Hospitality / Restaurant", "Walk-in queue and rebooking",
      "Barbershops", _INC_APPT, _APPT, price="$19-39", category="Beauty & Personal Care"),
    V("nails", "Nail Studio Agent", "💅", "Hospitality / Restaurant", "Bookings, reminders, loyalty",
      "Nail & beauty studios", _INC_APPT, _CARE, price="$19-39", category="Beauty & Personal Care"),

    # ───────────── Fitness ─────────────
    V("gym", "Gym Agent", "🏋️", "Small Business Owners", "Trials, memberships and retention",
      "Gyms & fitness studios", ["Free-trial capture + follow-up", "Class booking + reminders",
      "Membership renewals", "Win-back lapsed members", "Daily briefing"], _CARE,
      price="$39-79", category="Fitness"),
    V("yoga", "Yoga Studio Agent", "🧘", "Small Business Owners", "Class bookings and gentle nudges",
      "Yoga & pilates studios", _INC_APPT, _CARE, price="$29-59", category="Fitness"),
    V("trainer", "Personal Trainer Agent", "🤸", "Personal Productivity Assistant", "Sessions, check-ins, renewals",
      "Personal trainers & coaches", _INC_APPT, _CARE, price="$19-39", category="Fitness"),

    # ───────────── Real Estate & Property ─────────────
    V("realestate", "Real Estate Agent", "🏠", "Real Estate", "Answer leads in 60 seconds, nurture forever",
      "Agents & brokerages", ["Instant lead capture + qualify", "Speed-to-lead (under 5 min)",
      "Site-visit scheduling", "Long-term nurture with market updates", "Daily briefing"], _LEAD,
      price="$49-99", category="Real Estate & Property", compliance=["RERA (Real Estate)"],
      integrations=("WhatsApp", "Google Calendar", "Portal webhooks")),
    V("property", "Property Management Agent", "🏢", "Real Estate", "Tenant requests and rent reminders",
      "Property managers & landlords", ["Tenant request intake", "Rent reminders + follow-up",
      "Maintenance scheduling", "Lease-renewal nudges", "Daily briefing"], _PRO,
      price="$49-99", category="Real Estate & Property"),
    V("interior", "Interior Designer Agent", "🛋️", "Marketing / Digital Agency", "Lead-to-quote, then project nurture",
      "Interior designers & decorators", _INC_LEAD, _LEAD, price="$39-79", category="Real Estate & Property"),

    # ───────────── Trades & Home Services ─────────────
    V("plumber", "Plumber Agent", "🔧", "Construction", "Never miss a job — book it in seconds",
      "Plumbers", _INC_LEAD, _LEAD, price="$29-59", category="Trades & Home Services"),
    V("electrician", "Electrician Agent", "⚡", "Construction", "Capture call-outs and quote fast",
      "Electricians", _INC_LEAD, _LEAD, price="$29-59", category="Trades & Home Services"),
    V("hvac", "HVAC Agent", "❄️", "Construction", "Service bookings and seasonal recalls",
      "HVAC & AC technicians", _INC_LEAD, _LEAD, price="$39-79", category="Trades & Home Services"),
    V("cleaning", "Cleaning Service Agent", "🧹", "Small Business Owners", "Quote, schedule and rebook cleans",
      "Cleaning companies", _INC_LEAD, _CARE, price="$19-39", category="Trades & Home Services"),
    V("pest", "Pest Control Agent", "🐜", "Small Business Owners", "Bookings and recurring treatments",
      "Pest-control firms", _INC_LEAD, _CARE, price="$29-59", category="Trades & Home Services"),
    V("landscaping", "Landscaping Agent", "🌳", "Construction", "Estimates and seasonal follow-up",
      "Landscapers & gardeners", _INC_LEAD, _LEAD, price="$19-39", category="Trades & Home Services"),
    V("painter", "Painter Agent", "🎨", "Construction", "Quote follow-up that wins the job",
      "Painters & decorators", _INC_LEAD, _LEAD, price="$19-39", category="Trades & Home Services"),
    V("construction", "Construction / Contractor Agent", "🏗️", "Construction", "Bid, schedule and update clients",
      "Builders & contractors", _INC_LEAD, _LEAD, price="$49-99", category="Trades & Home Services"),

    # ───────────── Professional Services ─────────────
    V("accountant", "Accountant Agent", "📒", "Chartered Accountants & Tax Consultants",
      "Chase documents, file on time, never miss a deadline", "CA / tax / bookkeeping firms",
      _INC_PRO, _PRO, price="$39-79", category="Professional Services",
      compliance=["GDPR"], integrations=("Tally", "Email", "WhatsApp")),
    V("legal", "Law Firm Agent", "⚖️", "Legal Industry", "Intake, conflict-check prompts, scheduling",
      "Law firms & solicitors", ["Client intake + qualify", "Consultation scheduling",
      "Document chasing", "Matter status updates", "Daily briefing"], _PRO,
      price="$49-99", category="Professional Services", compliance=["Attorney-client confidentiality"]),
    V("consultant", "Consultant Agent", "💼", "Marketing / Digital Agency", "Proposals and follow-ups handled",
      "Independent consultants", _INC_LEAD, _LEAD, price="$29-59", category="Professional Services"),
    V("architect", "Architect Agent", "📐", "Construction", "Lead-to-brief, then project nurture",
      "Architects & design studios", _INC_LEAD, _LEAD, price="$39-79", category="Professional Services"),
    V("freelancer", "Freelancer Agent", "🧑‍💻", "Marketing / Digital Agency", "Proposals, follow-ups, onboarding — handled",
      "Freelancers & solo agencies", ["Quote / proposal follow-up until decided", "Lead nurture",
      "Client onboarding", "Retention check-ins", "Daily briefing"],
      ["quote_followup", "speed_to_lead", "onboarding", "retention", "daily_briefing"],
      price="$19-39", category="Professional Services"),

    # ───────────── Marketing & Creative ─────────────
    V("agency", "Digital Agency Agent", "📣", "Marketing / Digital Agency", "Pipeline and client comms on autopilot",
      "Marketing & creative agencies", _INC_LEAD, _LEAD, price="$39-79", category="Marketing & Creative"),
    V("photographer", "Photographer Agent", "📷", "Marketing / Digital Agency", "Enquiry-to-booking for shoots",
      "Photographers & videographers", _INC_LEAD, _LEAD, price="$19-39", category="Marketing & Creative"),
    V("event", "Event Planner Agent", "🎉", "Marketing / Digital Agency", "Quote, confirm and coordinate events",
      "Event planners", _INC_LEAD, _LEAD, price="$39-79", category="Marketing & Creative"),

    # ───────────── Education ─────────────
    V("school", "School Agent", "🏫", "Schools & Colleges", "Admissions, queries and reminders",
      "Schools & colleges", ["Admission enquiry capture", "Tour / interview scheduling",
      "Fee reminders", "Parent communication", "Daily briefing"], _PRO,
      price="$49-99", category="Education"),
    V("coaching", "Coaching / Tuition Agent", "📚", "Schools & Colleges", "Enrolments, batches and fee follow-up",
      "Coaching & tuition centres", ["Enrolment enquiry capture", "Demo-class scheduling",
      "Fee reminders", "Batch/renewal nudges", "Daily briefing"], _PRO,
      price="$29-59", category="Education"),
    V("driving", "Driving School Agent", "🚗", "Schools & Colleges", "Bookings and lesson reminders",
      "Driving schools & instructors", _INC_APPT, _APPT, price="$19-39", category="Education"),
    V("musicschool", "Music School Agent", "🎵", "Schools & Colleges", "Class bookings and renewals",
      "Music & arts schools", _INC_APPT, _CARE, price="$19-39", category="Education"),
    V("daycare", "Daycare Agent", "🧸", "Schools & Colleges", "Enquiries, tours and parent updates",
      "Daycares & preschools", _INC_APPT, _PRO, price="$29-59", category="Education"),

    # ───────────── Retail & Commerce ─────────────
    V("retail", "Retail Shop Agent", "🛍️", "Retail Shops", "Answer every customer, recover every cart",
      "Retail stores", _INC_SHOP, _SHOP, price="$29-59", category="Retail & Commerce"),
    V("ecommerce", "E-commerce Agent", "🛒", "Retail Shops", "Order status, returns and recommendations",
      "Online stores & D2C", ["Order-status deflection", "Returns & refunds handling",
      "Product recommendations", "Cart recovery", "Daily briefing"], _SHOP,
      price="$39-79", category="Retail & Commerce"),
    V("grocery", "Grocery Agent", "🥦", "Retail Shops", "Orders, delivery slots and stock",
      "Grocery & kirana stores", _INC_SHOP, _SHOP, price="$19-39", category="Retail & Commerce"),
    V("fashion", "Fashion Boutique Agent", "👗", "Retail Shops", "Styling questions and loyalty",
      "Fashion & apparel", _INC_SHOP, _SHOP, price="$29-59", category="Retail & Commerce"),
    V("jewelry", "Jewelry Store Agent", "💍", "Retail Shops", "Appointments, custom orders, loyalty",
      "Jewellers", _INC_SHOP, _SHOP, price="$39-79", category="Retail & Commerce"),
    V("electronics", "Electronics Store Agent", "📱", "Retail Shops", "Stock, warranty and support",
      "Electronics retailers", _INC_SHOP, _SHOP, price="$29-59", category="Retail & Commerce"),
    V("furniture", "Furniture Store Agent", "🛋️", "Retail Shops", "Quotes, delivery and follow-up",
      "Furniture & home stores", _INC_SHOP, _LEAD, price="$29-59", category="Retail & Commerce"),
    V("autodealer", "Auto Dealership Agent", "🚙", "Retail Shops", "Test-drives, quotes and follow-up",
      "Car & bike dealerships", _INC_LEAD, _LEAD, price="$49-99", category="Retail & Commerce"),
    V("autorepair", "Auto Repair Agent", "🔧", "Small Business Owners", "Service bookings and reminders",
      "Garages & service centres", _INC_APPT, _CARE, price="$29-59", category="Retail & Commerce"),

    # ───────────── Finance & Insurance ─────────────
    V("insurance", "Insurance Agent", "🛡️", "Insurance", "Quote, renew and never miss a policy",
      "Insurance agents & brokers", ["Quote enquiry capture", "Policy renewal reminders",
      "Claim intake", "Cross-sell nudges", "Daily briefing"], _PRO,
      price="$39-79", category="Finance & Insurance", compliance=["GDPR"]),
    V("financial", "Financial Advisor Agent", "💰", "Insurance", "Reviews, reminders and onboarding",
      "Financial & wealth advisors", _INC_PRO, _PRO, price="$49-99", category="Finance & Insurance",
      compliance=["GDPR"]),
    V("loan", "Loan / Mortgage Agent", "🏦", "Insurance", "Lead-to-application, then status updates",
      "Loan & mortgage brokers", _INC_LEAD, _PRO, price="$39-79", category="Finance & Insurance",
      compliance=["GDPR"]),

    # ───────────── Logistics & Industrial ─────────────
    V("logistics", "Logistics Agent", "🚚", "Logistics", "Track, update and quote shipments",
      "Logistics & transport", ["Shipment-status queries", "Booking + quotes",
      "Proactive delay alerts", "Invoice follow-up", "Daily briefing"], _PRO,
      price="$49-99", category="Logistics & Industrial"),
    V("courier", "Courier Agent", "📦", "Logistics", "Pickups, tracking and PODs",
      "Courier & delivery firms", _INC_SHOP, _SHOP, price="$29-59", category="Logistics & Industrial"),
    V("manufacturer", "Manufacturing Agent", "🏭", "Manufacturing", "RFQs, orders and dispatch updates",
      "Manufacturers & suppliers", _INC_LEAD, _PRO, price="$49-99", category="Logistics & Industrial"),
    V("wholesale", "Wholesale / Distributor Agent", "📦", "Retail Shops", "Orders, stock and reorders",
      "Wholesalers & distributors", _INC_SHOP, _SHOP, price="$39-79", category="Logistics & Industrial"),

    # ───────────── Agriculture ─────────────
    V("agri", "Agriculture Agent", "🌾", "Agriculture", "Advisory, orders and reminders",
      "Agri-businesses & input dealers", _INC_SHOP, _SHOP, price="$19-39", category="Agriculture & Rural"),
    V("dairy", "Dairy Agent", "🐄", "Agriculture", "Orders, subscriptions and reminders",
      "Dairies & farms", _INC_SHOP, _CARE, price="$19-39", category="Agriculture & Rural"),

    # ───────────── Travel & Tourism ─────────────
    V("travel", "Travel Agency Agent", "✈️", "Hospitality / Restaurant", "Enquiry-to-booking for trips",
      "Travel agencies", _INC_LEAD, _LEAD, price="$39-79", category="Travel & Tourism"),
    V("tours", "Tours & Activities Agent", "🗺️", "Hospitality / Restaurant", "Bookings, reminders and reviews",
      "Tour & activity operators", _INC_APPT, _APPT, price="$29-59", category="Travel & Tourism"),

    # ───────────── Software & Tech ─────────────
    V("saas", "SaaS Support Agent", "💻", "Software company", "Onboard users, answer docs, deflect tickets",
      "SaaS & software companies", ["Onboarding by chat", "Docs/product Q&A", "Ticket deflection",
      "Billing questions", "Daily briefing"], ["onboarding", "retention", "daily_briefing"],
      price="$49-99", category="Software & Tech"),
    V("itservices", "IT Services Agent", "🖥️", "Software company", "Support tickets and project comms",
      "IT services & MSPs", _INC_LEAD, _PRO, price="$39-79", category="Software & Tech"),

    # ───────────── Recruitment & HR ─────────────
    V("recruiter", "Recruiter Agent", "🧑‍💼", "Recruitment Agencies", "Source, screen, schedule — without the ghosting",
      "Recruitment & staffing", ["Candidate nurture (anti-ghosting)", "Interview scheduling",
      "Onboarding to joining", "Re-engage cold candidates", "Daily briefing"],
      ["confirm_appts", "onboarding", "stale_revival", "daily_briefing"],
      price="$39-79", category="Recruitment & HR"),

    # ───────────── Personal & Community ─────────────
    V("personal", "Personal Assistant Agent", "🤖", "Personal Productivity Assistant", "Your inbox, calendar and reminders",
      "Individuals & solopreneurs", ["Inbox triage", "Calendar & reminders", "Follow-ups",
      "Daily plan", "Daily briefing"], ["daily_briefing", "onboarding"],
      price="$9-19", category="Personal & Community"),
    V("senior", "Senior Care Agent", "👵", "Senior Citizens", "Check-ins, reminders and simple help",
      "Senior-care & home-care", ["Wellness check-ins", "Medication/appointment reminders",
      "Family updates", "Simple Q&A", "Daily briefing"], _CARE,
      price="$29-59", category="Personal & Community"),
    V("smb", "Small Business Agent", "🏪", "Small Business Owners", "One agent for the whole shop",
      "Any small business", _INC_SHOP, ["missed_call_wa", "review_request", "onboarding", "daily_briefing"],
      price="$19-39", category="Personal & Community"),
    V("nonprofit", "Nonprofit Agent", "🤝", "Small Business Owners", "Donors, volunteers and events",
      "Nonprofits & NGOs", ["Donor / volunteer enquiry", "Event sign-ups + reminders",
      "Thank-you + follow-up", "Re-engagement", "Daily briefing"], ["onboarding", "retention", "daily_briefing"],
      price="$19-39", category="Personal & Community"),
]
_BY = {v["id"]: v for v in VERTICALS}

# Stable category order for the UI
CATEGORIES = []
for _v in VERTICALS:
    if _v["category"] not in CATEGORIES:
        CATEGORIES.append(_v["category"])


def _deployed(db, tenant_id):
    """Set of deployed vertical ids (authoritative = a deployment record exists)."""
    return {d.vid for d in db.query(VerticalDeployment).filter_by(tenant_id=tenant_id).all()}


def _pub(db, tenant_id, action, name):
    """Capture the activity on the live event stream (top-bar ticker + feed)."""
    hub.emit(tenant_id, "vertical.changed", {"action": action, "name": name})


# ───────────────────────────── catalog ──────────────────────────────────────
@router.get("/verticals")
def list_verticals(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    from ..catalog_flags import disabled_set
    dep = _deployed(db, p.tenant_id)
    dis = disabled_set(db, "verticals")   # admin-hidden verticals
    items = [{**v, "deployed": v["id"] in dep} for v in VERTICALS if v["id"] not in dis]
    return {"categories": CATEGORIES, "count": len(items), "verticals": items}


@router.get("/verticals/{vid}")
def get_vertical(vid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    v = _BY.get(vid)
    if not v:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Vertical not found"})
    return {**v, "deployed": vid in _deployed(db, p.tenant_id),
            "recipe_detail": [RECIPE_BYID.get(r) for r in v["recipes"] if r in RECIPE_BYID]}


# ───────────────────────────── deploy ───────────────────────────────────────
@router.post("/verticals/{vid}/deploy")
def deploy_vertical(vid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """One click → a complete, working vertical workspace (records a manifest for clean undeploy)."""
    v = _BY.get(vid)
    if not v:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Vertical not found"})
    if vid in _deployed(db, p.tenant_id):
        raise HTTPException(409, detail={"code": "ALREADY_DEPLOYED",
                            "message": f"{v['name']} is already deployed. Undeploy it first to redeploy."})
    created = {"agents": 0, "pipelines": 0, "tasks": 0, "recipes": 0, "chatbot": False}

    # snapshot so we know exactly what THIS deploy creates
    before_agents = {a.id for a in db.query(Agent.id).filter_by(tenant_id=p.tenant_id).all()}
    before_pipes = {x.id for x in db.query(Pipeline.id).filter_by(tenant_id=p.tenant_id).all()}

    # 1) Set the industry → re-skins the universal engines + picks the template.
    t = db.get(Tenant, p.tenant_id)
    t.industry = v["industry"]

    # 2) Apply the industry template org (roster + pipelines).
    sug = tpl.curated(v["industry"])
    res = apply_suggestion(ApplyIn(suggestion=sug, adopt_agents=True, adopt_pipelines=True,
                                   adopt_tasks=False, product_name=v["name"]), p, db)
    created.update(res.get("created", {}))
    db.flush()

    # 3) Enable the vertical's recipes (track which we created vs merely enabled).
    recipes_created, recipes_enabled = [], []
    for rid in v["recipes"]:
        r = db.query(Recipe).filter_by(tenant_id=p.tenant_id, recipe_id=rid).first()
        if not r:
            r = Recipe(id=ulid("rcp"), tenant_id=p.tenant_id, recipe_id=rid,
                       params=RECIPE_BYID.get(rid, {}).get("params", {}))
            db.add(r); db.flush()
            recipes_created.append(r.id)
        else:
            recipes_enabled.append(r.id)
        r.enabled = True
        created["recipes"] += 1

    # 4) A persona front-desk chatbot + a marker (concierge) agent tagged to this vertical.
    bot = Chatbot(id=ulid("cbt"), tenant_id=p.tenant_id, name=v["name"], purpose=v["tagline"],
                  department="Front Office", model_id="mdl_gemma9b", persona=v["persona"],
                  memory_scopes=["business", "knowledge"], color="violet", status="active")
    db.add(bot); db.flush()
    db.add(ChatbotChannel(id=ulid("chc"), chatbot_id=bot.id, tenant_id=p.tenant_id,
                          type="website", status="connected", config={}))
    marker = Agent(id=ulid("agt"), tenant_id=p.tenant_id, name=f"{v['name']} (concierge)",
                   designation="Front Desk", description=v["tagline"],
                   objectives=[f"vertical:{vid}"], status="idle", model_id="mdl_gemma9b")
    db.add(marker); db.flush()
    created["chatbot"] = True

    # manifest = everything this deploy created → enables clean undeploy
    new_agents = [a.id for a in db.query(Agent.id).filter_by(tenant_id=p.tenant_id).all()
                  if a.id not in before_agents]
    new_pipes = [x.id for x in db.query(Pipeline.id).filter_by(tenant_id=p.tenant_id).all()
                 if x.id not in before_pipes]
    manifest = {"agents": new_agents, "pipelines": new_pipes, "chatbots": [bot.id],
                "recipes_created": recipes_created, "recipes_enabled": recipes_enabled}
    db.add(VerticalDeployment(id=ulid("vdp"), tenant_id=p.tenant_id, vid=vid,
                              name=v["name"], industry=v["industry"], manifest=manifest))

    audit(db, plane="local", actor=f"user:{p.user_id}", action="vertical.deploy",
          target=vid, tenant_id=p.tenant_id,
          meta={"industry": v["industry"], "created": created})
    db.commit()
    _pub(db, p.tenant_id, "deploy", v["name"])
    return {"status": "deployed", "name": v["name"], "industry": v["industry"],
            "created": created, "compliance_active": v["compliance"],
            "message": f"{v['name']} is live — roster, automations, a {v['name']} concierge and "
                       f"{v['industry']} compliance are all set up. Your screens now speak this vertical's language."}


# ───────────────────────────── undeploy ─────────────────────────────────────
@router.post("/verticals/{vid}/undeploy")
def undeploy_vertical(vid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Reverse a deploy — remove the roster, pipelines, concierge and recipes it created."""
    v = _BY.get(vid)
    dep = db.query(VerticalDeployment).filter_by(tenant_id=p.tenant_id, vid=vid).first()
    if not dep:
        raise HTTPException(409, detail={"code": "NOT_DEPLOYED",
                            "message": f"{(v or {}).get('name', vid)} is not deployed."})
    m = dep.manifest or {}
    removed = {"agents": 0, "pipelines": 0, "chatbots": 0, "recipes": 0}

    # chatbots: channels first, then the bot
    for cid in m.get("chatbots", []):
        db.query(ChatbotChannel).filter_by(chatbot_id=cid).delete(synchronize_session=False)
        removed["chatbots"] += db.query(Chatbot).filter_by(id=cid).delete(synchronize_session=False)
    db.flush()
    # pipelines: steps first, then the pipeline
    for pid in m.get("pipelines", []):
        db.query(PipelineStep).filter_by(pipeline_id=pid).delete(synchronize_session=False)
        removed["pipelines"] += db.query(Pipeline).filter_by(id=pid).delete(synchronize_session=False)
    db.flush()
    # agents (roster + concierge marker) — clear self-referential manager links first
    agent_ids = m.get("agents", [])
    for aid in agent_ids:
        db.query(Agent).filter_by(id=aid).update({"reporting_manager_id": None},
                                                 synchronize_session=False)
    db.flush()
    for aid in agent_ids:
        removed["agents"] += db.query(Agent).filter_by(id=aid).delete(synchronize_session=False)
    # recipes we created → delete; recipes we only enabled → turn back off — UNLESS
    # another live deployment (another vertical or a solution) still needs that recipe.
    from .solutions import recipe_rows_in_use
    still_used = recipe_rows_in_use(db, p.tenant_id, skip_vertical=dep.id)
    for rid in m.get("recipes_created", []):
        if rid not in still_used:
            removed["recipes"] += db.query(Recipe).filter_by(id=rid).delete(synchronize_session=False)
    for rid in m.get("recipes_enabled", []):
        if rid not in still_used:
            db.query(Recipe).filter_by(id=rid).update({"enabled": False}, synchronize_session=False)
    db.flush()
    db.query(VerticalDeployment).filter_by(id=dep.id).delete(synchronize_session=False)

    # industry skin: fall back to a remaining vertical, else clear (generic skin)
    remaining = db.query(VerticalDeployment).filter_by(tenant_id=p.tenant_id).order_by(
        VerticalDeployment.created_at.desc()).first()
    t = db.get(Tenant, p.tenant_id)
    t.industry = remaining.industry if remaining else None

    name = dep.name
    audit(db, plane="local", actor=f"user:{p.user_id}", action="vertical.undeploy",
          target=vid, tenant_id=p.tenant_id, meta={"removed": removed})
    db.commit()
    _pub(db, p.tenant_id, "undeploy", name)
    return {"status": "undeployed", "name": name, "removed": removed,
            "message": f"{name} has been removed — its agents, pipelines, concierge and automations are gone, "
                       + ("and your screens are back to the generic layout." if not remaining
                          else f"and your screens now reflect {remaining.name}.")}


# ──────────────────────── voice / natural-language control ───────────────────
class ResolveIn(BaseModel):
    transcript: str


_DEPLOY_RE = re.compile(r"\b(deploy|install|set ?up|activate|enable|launch|add|create|start)\b", re.I)
_UNDEPLOY_RE = re.compile(r"\b(undeploy|uninstall|remove|delete|disable|deactivate|tear ?down|turn off)\b", re.I)
_OPEN_RE = re.compile(r"\b(open|show|view|see|details?|what'?s included|tell me about|info)\b", re.I)
_CLOSE_RE = re.compile(r"\b(close|cancel|dismiss|go back|never ?mind)\b", re.I)


def _match_vertical(text):
    """Find the best vertical in a spoken phrase by name / id / industry / 'for' words."""
    low = text.lower()
    best, score = None, 0
    for v in VERTICALS:
        s = 0
        # strongest: the distinctive word in the name (e.g. "dentist", "plumber")
        head = re.sub(r"\s*(agent|/.*)$", "", v["name"].lower()).strip()
        for w in re.findall(r"[a-z]+", head):
            if len(w) > 3 and w in low:
                s += 3
        if v["id"] in low:
            s += 3
        if v["industry"].lower().split(" /")[0] in low:
            s += 1
        for w in re.findall(r"[a-z]{4,}", v["for"].lower()):
            if w in low:
                s += 1
        if s > score:
            best, score = v, s
    return best if score >= 2 else None


@router.post("/verticals/resolve")
def resolve_voice(body: ResolveIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Turn a spoken/typed phrase into a concrete page action."""
    text = (body.transcript or "").strip()
    if not text:
        return {"action": "none", "message": "I didn't catch that."}
    if _CLOSE_RE.search(text) and not _match_vertical(text):
        return {"action": "close", "message": "Closing."}

    v = _match_vertical(text)
    is_undeploy = bool(_UNDEPLOY_RE.search(text))
    is_deploy = bool(_DEPLOY_RE.search(text)) and not is_undeploy
    is_open = bool(_OPEN_RE.search(text))

    if not v:
        return {"action": "none",
                "message": "Tell me which vertical, e.g. \"deploy the dentist agent\" or "
                           "\"uninstall the restaurant agent\"."}
    deployed = v["id"] in _deployed(db, p.tenant_id)
    if is_undeploy:
        return {"action": "undeploy", "vid": v["id"], "name": v["name"], "deployed": deployed,
                "message": f"Undeploying {v['name']}."}
    if is_deploy:
        return {"action": "deploy", "vid": v["id"], "name": v["name"], "deployed": deployed,
                "message": f"Deploying {v['name']}."}
    if is_open:
        return {"action": "open", "vid": v["id"], "name": v["name"], "deployed": deployed,
                "message": f"Opening {v['name']}."}
    # named a vertical but no clear verb → open its details
    return {"action": "open", "vid": v["id"], "name": v["name"], "deployed": deployed,
            "message": f"Here's {v['name']}."}

"""Company profile, Products, and the Industry AI-suggestion + adopt flow."""
import hashlib
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import industry_templates as tpl
from .. import llm
from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import (Agent, Chatbot, ChatbotChannel, Department, MemoryItem,
                      Pipeline, PipelineStep, Product, Task, Tenant, now)
from ..security import ulid

router = APIRouter(tags=["company"])

# ── Focus areas (what to staff the org AROUND) — drives the AI Org Builder ────
FOCUS_AREAS = [
    "General operations", "Sales & Lead Generation", "Customer Support",
    "Client Onboarding", "Billing & Collections", "Marketing & Outreach",
    "Appointments & Scheduling", "Retention & Loyalty",
    "Compliance & Documentation", "Recruitment & Hiring", "Operations & Admin",
]
# Each focus injects a tailored pipeline into the suggestion (agent names fall back
# gracefully in apply_suggestion if a roster doesn't have that exact agent).
_FOCUS_PIPELINE = {
    "Sales & Lead Generation": ("Lead-to-Close", "Capture, qualify, nurture and close new business.", False,
        [("Front Desk Agent", "Capture and qualify every new lead for {product} within minutes."),
         ("Follow-Up Agent", "Nurture undecided leads until they convert or opt out."),
         ("Chief of Staff (CEO) Agent", "Review hot leads and drive them to close.")]),
    "Customer Support": ("Support Resolution", "Answer, resolve, and escalate customer issues.", False,
        [("Front Desk Agent", "Greet and triage every inbound support request."),
         ("Follow-Up Agent", "Follow up until the issue is resolved; collect feedback."),
         ("Chief of Staff (CEO) Agent", "Handle escalations a human must see.")]),
    "Client Onboarding": ("Onboarding Journey", "Welcome, collect documents, and get clients live.", True,
        [("Front Desk Agent", "Welcome the new client and set expectations."),
         ("Document Agent", "Collect and validate the required documents."),
         ("Follow-Up Agent", "Chase anything missing; confirm go-live.")]),
    "Billing & Collections": ("Get Paid On Time", "Invoice, remind, and recover outstanding dues.", True,
        [("Collections Agent", "Issue invoices and track what's owed for {product}."),
         ("Follow-Up Agent", "Send polite escalating reminders before and after due."),
         ("Chief of Staff (CEO) Agent", "Escalate the stubborn accounts.")]),
    "Marketing & Outreach": ("Outreach Engine", "Run campaigns and warm the audience.", False,
        [("Follow-Up Agent", "Run the outreach sequence; respect opt-outs."),
         ("Document Agent", "Draft the campaign content for review."),
         ("Chief of Staff (CEO) Agent", "Approve messaging and report results.")]),
    "Appointments & Scheduling": ("Booking & Reminders", "Fill the calendar and cut no-shows.", False,
        [("Scheduler Agent", "Offer slots, confirm, and remind at T-24h / T-2h."),
         ("Follow-Up Agent", "Recover no-shows and rebook."),
         ("Front Desk Agent", "Answer scheduling questions instantly.")]),
    "Retention & Loyalty": ("Keep Them Happy", "Check in, reward loyalty, prevent churn.", False,
        [("Follow-Up Agent", "Run timed value check-ins for {product}."),
         ("Chief of Staff (CEO) Agent", "Flag at-risk accounts before they leave.")]),
    "Compliance & Documentation": ("Compliance Calendar", "Never miss a deadline or a document.", True,
        [("Compliance Agent", "Track statutory dates and prep checklists."),
         ("Document Agent", "Assemble and archive the evidence pack."),
         ("Follow-Up Agent", "Chase the documents and confirm filing.")]),
    "Recruitment & Hiring": ("Source to Hire", "Source, screen, schedule and onboard talent.", False,
        [("Front Desk Agent", "Capture and screen applicants."),
         ("Scheduler Agent", "Coordinate interviews across calendars."),
         ("Follow-Up Agent", "Keep candidates warm to joining.")]),
    "Operations & Admin": ("Run the Back Office", "Keep daily operations moving.", False,
        [("Chief of Staff (CEO) Agent", "Decompose the day's work and assign it."),
         ("Document Agent", "Prepare the recurring paperwork."),
         ("Follow-Up Agent", "Close the loop on every open item.")]),
}


def _focus_pipeline(focus):
    spec = _FOCUS_PIPELINE.get(focus)
    if not spec:
        return None
    name, desc, approvals, steps = spec
    return {"name": name, "description": desc, "approvals": approvals,
            "steps": [{"agent_name": a, "instruction": i} for a, i in steps]}


# ───────────────────────────── Company profile ──────────────────────────────
@router.get("/company")
def get_company(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(Tenant, p.tenant_id)
    return {"id": t.id, "company_name": t.company_name, "industry": t.industry,
            "description": t.onboarding_note, "region": t.region}


class CompanyPatch(BaseModel):
    company_name: str | None = None
    industry: str | None = None
    description: str | None = None


@router.patch("/company")
def update_company(body: CompanyPatch, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    t = db.get(Tenant, p.tenant_id)
    if body.company_name is not None:
        t.company_name = body.company_name
    reskinned = False
    if body.industry is not None:
        reskinned = t.industry != body.industry
        t.industry = body.industry
    if body.description is not None:
        t.onboarding_note = body.description
    audit(db, plane="cloud", actor=f"user:{p.user_id}", action="company.update",
          target=t.id, tenant_id=t.id, meta={"industry": t.industry})
    db.commit()
    hub.emit(t.id, "company.changed", {"action": "update", "name": t.company_name or "Company"})
    if reskinned:
        hub.emit(t.id, "vertical.changed", {"action": "deploy", "name": f"{t.industry} skin"})
    return {"id": t.id, "company_name": t.company_name, "industry": t.industry,
            "description": t.onboarding_note,
            "message": f"Company saved{f' · industry set to {t.industry}' if body.industry else ''}."}


@router.get("/company/industries")
def industries():
    return {"industries": tpl.SUPPORTED}


@router.get("/company/focus-areas")
def focus_areas():
    """Preset focuses to staff the AI org around (beyond the user's own products)."""
    return {"focus_areas": FOCUS_AREAS}


# ───────────────────────────── Products ─────────────────────────────────────
def product_dto(pr: Product):
    return {"id": pr.id, "name": pr.name, "description": pr.description,
            "stage": pr.stage, "status": pr.status,
            "created_at": pr.created_at.isoformat() if pr.created_at else None}


@router.get("/products")
def list_products(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Product).filter_by(tenant_id=p.tenant_id, status="active").order_by(
        Product.created_at.desc()).all()
    return [product_dto(pr) for pr in rows]


class ProductIn(BaseModel):
    name: str
    description: str | None = None
    stage: str = "idea"


@router.post("/products")
def create_product(body: ProductIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    pr = Product(id=ulid("prd"), tenant_id=p.tenant_id, name=body.name,
                 description=body.description, stage=body.stage)
    db.add(pr)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="product.create",
          target=pr.id, tenant_id=p.tenant_id, meta={"name": body.name})
    db.commit()
    hub.emit(p.tenant_id, "product.changed", {"action": "add", "name": body.name})
    return product_dto(pr)


class ProductPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    stage: str | None = None


@router.patch("/products/{pid}")
def update_product(pid: str, body: ProductPatch, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    pr = db.get(Product, pid)
    if not pr or pr.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Product not found"})
    for f, v in body.model_dump(exclude_none=True).items():
        setattr(pr, f, v)
    db.commit()
    return product_dto(pr)


@router.delete("/products/{pid}")
def delete_product(pid: str, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    pr = db.get(Product, pid)
    if not pr or pr.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Product not found"})
    pr.status = "deleted"
    name = pr.name
    audit(db, plane="local", actor=f"user:{p.user_id}", action="product.delete",
          target=pid, tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "product.changed", {"action": "delete", "name": name})
    return {"status": "deleted", "message": f"Removed product '{name}'."}


# ───────────────────────────── Suggestions ──────────────────────────────────
@router.get("/suggestions")
def suggestions(industry: str | None = None, product: str | None = None,
                ai: bool = False, p: Principal = Depends(current_user),
                db: Session = Depends(get_db)):
    """AI-suggested org + pipelines + task library for an industry (curated or LLM)."""
    ind = industry or (db.get(Tenant, p.tenant_id).industry) or "Small Business Owners"
    if ind not in tpl.SUPPORTED:
        ind = "Small Business Owners"
    sug = dict(tpl.generate_with_ai(ind, product) if ai else tpl.curated(ind))
    # If a focus area was chosen, lead with a focus-tailored pipeline.
    fp = _focus_pipeline(product) if product else None
    if fp:
        sug["pipelines"] = [fp] + list(sug.get("pipelines", []))
        sug["focus"] = product
    return sug


class BootstrapIn(BaseModel):
    industry: str = "Chartered Accountants & Tax Consultants"


@router.post("/demo/bootstrap")
def demo_bootstrap(body: BootstrapIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    """G1 Instant-Start: one-click sample workspace so the first command works
    before any setup — agents, pipelines, tasks, memory and a chatbot."""
    t = db.get(Tenant, p.tenant_id)
    if db.query(Agent).filter_by(tenant_id=p.tenant_id).count() > 0:
        return {"status": "exists", "message": "Workspace already has agents."}
    industry = body.industry if body.industry in tpl.SUPPORTED else "Small Business Owners"
    t.industry = industry
    sug = tpl.curated(industry)
    apply_suggestion(ApplyIn(suggestion=sug, adopt_agents=True, adopt_pipelines=True,
                             adopt_tasks=True, product_name="your business"), p, db)

    # A little Second-Brain memory so chatbots/search have something to ground on.
    mems = [
        ("knowledge", f"{industry} SOP",
         "Standard operating procedure: collect documents by the 25th, prepare the filing, "
         "run a variance check, and notify the client. File before the deadline."),
        ("business", "Sample client — Sharma Traders",
         "Sharma Traders, monthly turnover ~₹18 lakh, prefers WhatsApp, retainer ₹8,000/month."),
        ("operational", "Last cycle notes",
         "Completed 58 of 60 client filings on time last cycle; two delayed due to late documents."),
    ]
    for cls, title, b in mems:
        db.add(MemoryItem(id=ulid("mem"), tenant_id=p.tenant_id, memory_class=cls, title=title,
                          source_type="note", body=b, content_hash=hashlib.sha256(b.encode()).hexdigest(),
                          tier="hot", confidence=1.0, embedding=llm.embed(f"{title}. {b}")))

    bot = Chatbot(id=ulid("cbt"), tenant_id=p.tenant_id, name="Client Helpdesk",
                  purpose="Answers client questions from your company memory.", department="Support",
                  model_id="mdl_gemma9b", persona="You are the Client Helpdesk. Help clients "
                  "using the company records. Be warm and concise.",
                  memory_scopes=["business", "knowledge"], color="violet", status="active")
    db.add(bot)
    db.flush()
    db.add(ChatbotChannel(id=ulid("chc"), chatbot_id=bot.id, tenant_id=p.tenant_id,
                          type="website", status="connected", config={}))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="demo.bootstrap",
          tenant_id=p.tenant_id, meta={"industry": industry})
    db.commit()
    hub.emit(p.tenant_id, "org.updated", {"bootstrap": True})
    return {"status": "ready", "industry": industry,
            "agents": db.query(Agent).filter_by(tenant_id=p.tenant_id).count()}


class ApplyIn(BaseModel):
    suggestion: dict
    adopt_agents: bool = True
    adopt_pipelines: bool = True
    adopt_tasks: bool = False
    product_id: str | None = None
    product_name: str | None = None


@router.post("/suggestions/apply")
def apply_suggestion(body: ApplyIn, p: Principal = Depends(current_user),
                     db: Session = Depends(get_db)):
    """Bootstrap the org from a (possibly user-edited) suggestion."""
    s = body.suggestion
    product = body.product_name or "your product"
    created = {"agents": 0, "pipelines": 0, "tasks": 0}

    # Departments (create missing by name).
    dept_by_name = {d.name: d for d in db.query(Department).filter_by(tenant_id=p.tenant_id).all()}

    def dept_id(name):
        if not name:
            return None
        d = dept_by_name.get(name)
        if not d:
            d = Department(id=ulid("dep"), tenant_id=p.tenant_id, name=name)
            db.add(d)
            db.flush()
            dept_by_name[name] = d
        return d.id

    name_to_agent = {}     # suggestion agent name -> created/existing Agent
    if body.adopt_agents:
        # First pass: create agents (no manager links yet to avoid FK ordering).
        existing_ceo = db.query(Agent).filter_by(tenant_id=p.tenant_id, is_ceo=True).first()
        for a in s.get("agents", []):
            if a.get("is_ceo") and existing_ceo:
                name_to_agent[a["name"]] = existing_ceo
                continue
            ag = Agent(id=ulid("agt"), tenant_id=p.tenant_id, name=a.get("name"),
                       designation=a.get("designation"),
                       department_id=dept_id(a.get("department")),
                       description=f"{a.get('designation')} ({s.get('industry')}).",
                       skills=a.get("skills", []), is_ceo=bool(a.get("is_ceo")),
                       model_id="mdl_qwen14b_q4" if a.get("model") == "smart" else "mdl_gemma9b",
                       status="idle",
                       permissions={"spend_limit": 5000, "external_send": "approval_required"})
            db.add(ag)
            db.flush()
            name_to_agent[a.get("name")] = ag
            created["agents"] += 1
        # Second pass: reporting links.
        for a in s.get("agents", []):
            mgr = a.get("reports_to")
            ag = name_to_agent.get(a.get("name"))
            if ag and mgr and name_to_agent.get(mgr):
                ag.reporting_manager_id = name_to_agent[mgr].id
        db.flush()

    # Helper to resolve an agent by suggestion name (fallback to CEO/any).
    def resolve_agent(nm):
        if nm in name_to_agent:
            return name_to_agent[nm]
        a = db.query(Agent).filter(Agent.tenant_id == p.tenant_id,
                                   Agent.name == nm).first()
        if a:
            return a
        return db.query(Agent).filter_by(tenant_id=p.tenant_id, is_ceo=True).first() \
            or db.query(Agent).filter_by(tenant_id=p.tenant_id).first()

    if body.adopt_pipelines:
        for pl in s.get("pipelines", []):
            pipeline = Pipeline(id=ulid("ppl"), tenant_id=p.tenant_id,
                                product_id=body.product_id, name=pl.get("name"),
                                description=pl.get("description"), status="ready",
                                source=s.get("source", "template"))
            db.add(pipeline)
            db.flush()
            for i, st in enumerate(pl.get("steps", []), start=1):
                ag = resolve_agent(st.get("agent_name"))
                db.add(PipelineStep(
                    id=ulid("pst"), pipeline_id=pipeline.id, seq=i,
                    agent_id=ag.id if ag else None,
                    instruction=(st.get("instruction", "")).replace("{product}", product)
                                .replace("{company}", db.get(Tenant, p.tenant_id).company_name or "the company"),
                    requires_approval=bool(pl.get("approvals"))))
            created["pipelines"] += 1

    if body.adopt_tasks:
        for t in s.get("tasks", []):
            ag = resolve_agent(t.get("agent_name"))
            db.add(Task(id=ulid("tsk"), tenant_id=p.tenant_id, title=t.get("title"),
                        source="template", status="queued",
                        assignee_agent_id=ag.id if ag else None))
            created["tasks"] += 1

    audit(db, plane="local", actor=f"user:{p.user_id}", action="suggestion.apply",
          tenant_id=p.tenant_id, meta=created)
    db.commit()
    hub.emit(p.tenant_id, "org.updated", created)
    return {"status": "applied", "created": created,
            "message": f"Adopted {created['agents']} agents, {created['pipelines']} pipelines, "
                       f"{created['tasks']} tasks into your org."}


# ──────────────────────── voice / natural-language control ───────────────────
class ResolveIn(BaseModel):
    transcript: str


_IND_SYN = {"clinic": "Healthcare", "dental": "Healthcare", "dentist": "Healthcare", "hospital": "Healthcare",
            "doctor": "Healthcare", "law": "Legal Industry", "lawyer": "Legal Industry", "legal": "Legal Industry",
            "restaurant": "Hospitality / Restaurant", "hotel": "Hospitality / Restaurant", "cafe": "Hospitality / Restaurant",
            "shop": "Retail Shops", "store": "Retail Shops", "retail": "Retail Shops",
            "school": "Schools & Colleges", "college": "Schools & Colleges", "factory": "Manufacturing",
            "manufacturing": "Manufacturing", "accountant": "Chartered Accountants & Tax Consultants",
            "accounting": "Chartered Accountants & Tax Consultants", "tax": "Chartered Accountants & Tax Consultants",
            "agency": "Marketing / Digital Agency", "marketing": "Marketing / Digital Agency",
            "recruit": "Recruitment Agencies", "staffing": "Recruitment Agencies", "real estate": "Real Estate"}


def _match_industry(text):
    low = text.lower()
    for ind in tpl.SUPPORTED:
        head = ind.lower().split(" /")[0].split(" &")[0].strip()
        if head and head in low:
            return ind
    for k, v in _IND_SYN.items():
        if k in low:
            return v
    return None


def _match_focus(text):
    low = text.lower()
    for f in FOCUS_AREAS:
        for w in re.findall(r"[a-z]+", f.lower()):
            if len(w) > 3 and w in low:
                return f
    if "sales" in low or "lead" in low:
        return "Sales & Lead Generation"
    return None


@router.post("/company/resolve")
def resolve_voice(body: ResolveIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Turn a spoken/typed phrase into a concrete Company action."""
    text = (body.transcript or "").strip()
    low = text.lower()
    if not text:
        return {"action": "none", "message": "I didn't catch that."}

    # add a product:  "add a product called X" / "new product named X"
    m = re.search(r"\b(?:add|create|new)\b.*\bproduct\b\s*(?:called|named|:)?\s*(.+)$", text, re.I)
    if m and m.group(1).strip():
        name = re.sub(r"^(called|named|the|a|an)\s+", "", m.group(1).strip(), flags=re.I).strip(" '\".")
        if name:
            return {"action": "add_product", "name": name, "message": f"Adding product “{name}”."}

    # delete a product: match against existing products
    if re.search(r"\b(delete|remove|drop)\b.*\bproduct\b", low) or re.search(r"\b(delete|remove)\b", low):
        prods = db.query(Product).filter_by(tenant_id=p.tenant_id, status="active").all()
        for pr in prods:
            if pr.name and pr.name.lower() in low:
                return {"action": "delete_product", "id": pr.id, "name": pr.name,
                        "message": f"Removing product “{pr.name}”."}

    # rename the company
    m = re.search(r"\b(?:rename|call)\b.*?\b(?:company|business|it)\b\s*(?:to|as)?\s*(.+)$", text, re.I) \
        or re.search(r"\bcompany name\b\s*(?:to|is|:)?\s*(.+)$", text, re.I)
    if m and m.group(1).strip():
        name = m.group(1).strip(" '\".")
        return {"action": "rename_company", "name": name, "message": f"Renaming company to “{name}”."}

    # set industry
    if re.search(r"\b(industry|sector|we are|we'?re|it'?s)\b", low) or re.search(r"\bset.*industry\b", low):
        ind = _match_industry(text)
        if ind:
            return {"action": "set_industry", "industry": ind, "message": f"Setting industry to {ind}."}

    # adopt / apply the suggestion
    if re.search(r"\b(adopt|apply|build it|staff (it|my org)|create the org|use this)\b", low):
        return {"action": "apply", "message": "Adopting the suggested org."}

    # generate / suggest an org (optionally with AI / industry / focus)
    if re.search(r"\b(suggest|generate|build|staff|org builder|organi[sz]ation|recommend)\b", low):
        ai = bool(re.search(r"\b(ai|with ai|generate)\b", low))
        return {"action": "suggest", "ai": ai, "industry": _match_industry(text),
                "focus": _match_focus(text), "message": "Building a suggested org."}

    # set focus
    focus = _match_focus(text)
    if focus and re.search(r"\bfocus\b", low):
        return {"action": "set_focus", "focus": focus, "message": f"Focusing on {focus}."}

    # bare industry mention
    ind = _match_industry(text)
    if ind:
        return {"action": "set_industry", "industry": ind, "message": f"Setting industry to {ind}."}

    return {"action": "none",
            "message": "Try \"set industry to healthcare\", \"add a product called GST Filing\", "
                       "\"build my org focused on sales\", or \"adopt the org\"."}

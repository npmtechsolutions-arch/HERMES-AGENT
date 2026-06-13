"""
Seed the HERMUS database with a CLEAN starting state:
  * Two logins: user@gmail.com/user (account owner) and admin@gmail.com/admin
  * Plan catalog (Trial / Starter / Pro / Enterprise)
  * An EMPTY company ("My Company") owned by the user, on the Pro plan, with a
    device, the local model catalog, and a starter set of (empty) departments.
  * Platform catalogs (marketplace items, releases, common config) for the admin
    console and marketplace page.

No demo workspace data (no agents, tasks, workflows, products, pipelines,
memory, chatbots, comms) — the user builds their own.

Idempotent: running twice will not duplicate (checks for the user).
"""
from datetime import timedelta

from .database import Base, SessionLocal, engine
from .models import (AdminUser, ConfigItem, Department, Device, LLMModel,
                     MarketplaceItem, Plan, Release, Subscription, Tenant,
                     TenantMember, User, now)
from .security import hash_password, ulid


PLANS = [
    # G4 — Free Solo tier (forever): the open-source counter-offer.
    ("pln_free", "Free Solo", "monthly", 0,
     {"agents": 2, "workflows": 2, "seats": 1, "devices": 1, "channels": ["email"]},
     {"call_center": False, "multi_node": False, "offline_mode": False, "marketplace": "free",
      "free_forever": True, "full_voice": True, "local_privacy": True}),
    ("pln_trial", "Trial", "monthly", 0,
     {"agents": 3, "workflows": 3, "seats": 1, "devices": 1, "channels": ["email"]},
     {"call_center": False, "multi_node": False, "offline_mode": False, "marketplace": "free"}),
    ("pln_starter", "Starter", "monthly", 999,
     {"agents": 5, "workflows": 10, "seats": 1, "devices": 1,
      "channels": ["email", "whatsapp", "telegram"]},
     {"call_center": False, "multi_node": False, "offline_mode": False, "marketplace": True}),
    ("pln_pro", "Pro", "monthly", 3999,
     {"agents": 25, "workflows": 100, "seats": 5, "devices": 3, "channels": ["all"]},
     {"call_center": "add_on", "multi_node": False, "offline_mode": False, "marketplace": True}),
    ("pln_enterprise", "Enterprise", "monthly", 19999,
     {"agents": "unlimited", "workflows": "unlimited", "seats": "custom",
      "devices": "fleet", "channels": ["all"]},
     {"call_center": True, "multi_node": True, "offline_mode": True,
      "marketplace": "private"}),
]

STARTER_DEPARTMENTS = ["Executive", "Sales", "Marketing", "Finance", "Support", "Operations"]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).filter_by(email="user@gmail.com").first():
            print("Seed already present — skipping.")
            return

        # ── Plans ──────────────────────────────────────────────────────────
        for pid, name, period, price, limits, flags in PLANS:
            db.add(Plan(id=pid, name=name, billing_period=period, currency="INR",
                        price=price, limits=limits, feature_flags=flags))
        db.flush()

        # ── Admin login ────────────────────────────────────────────────────
        db.add(AdminUser(id="adm_super", email="admin@gmail.com",
                         full_name="Product Admin", password_hash=hash_password("admin"),
                         roles=["super", "support", "finance", "catalog"]))
        db.flush()

        # ── Account owner + empty company ──────────────────────────────────
        user = User(id="usr_demo", email="user@gmail.com",
                    password_hash=hash_password("user"), full_name="User",
                    email_verified=True)
        db.add(user)
        db.flush()
        tenant = Tenant(id="tnt_demo", owner_user_id=user.id, company_name="My Company",
                        industry=None, region="IN", status="active", onboarding_note=None)
        db.add(tenant)
        db.flush()
        db.add_all([
            TenantMember(id="mem_demo", tenant_id=tenant.id, user_id=user.id, role="owner"),
            Subscription(id="sub_demo", tenant_id=tenant.id, plan_id="pln_pro",
                         status="active", gateway="razorpay", current_period_start=now(),
                         current_period_end=now() + timedelta(days=30)),
            Device(id="dev_demo", tenant_id=tenant.id, user_id=user.id,
                   name="My-Workstation", os="Windows 11", app_version="1.0.0",
                   last_seen_at=now(), status="active"),
        ])
        db.flush()

        # ── Starter (empty) departments ────────────────────────────────────
        for name in STARTER_DEPARTMENTS:
            db.add(Department(id=ulid("dep"), tenant_id=tenant.id, name=name))

        # ── Local model catalog (so model pickers work) ────────────────────
        db.add_all([
            LLMModel(id="mdl_qwen14b_q4", tenant_id=tenant.id, family="Qwen", size="14B",
                     quant="Q4_K_M", runtime="ollama", vram_mb=9000, status="available"),
            LLMModel(id="mdl_gemma9b", tenant_id=tenant.id, family="Gemma", size="9B",
                     quant="Q4", runtime="ollama", vram_mb=6000, status="available"),
            LLMModel(id="mdl_phi3", tenant_id=tenant.id, family="Phi", size="3.8B",
                     quant="Q4", runtime="llamacpp", vram_mb=2500, status="available"),
        ])

        # ── Platform catalogs (admin console + marketplace) ────────────────
        db.add_all([
            MarketplaceItem(id="mp_ca", type="industry_template", name="CA Office Pack",
                            description="Accountant, GST Specialist, Auditor agents + monthly "
                                        "filing workflows.", industry_tags=["accounting"],
                            is_free=True, status="approved", publisher="HERMUS", installs=1240),
            MarketplaceItem(id="mp_re", type="industry_template", name="Real Estate Pack",
                            description="Sales, CRM, Legal, Site-visit agents + RERA workflows.",
                            industry_tags=["real_estate"], price=2499, status="approved",
                            publisher="HERMUS", installs=980),
            MarketplaceItem(id="mp_law", type="industry_template", name="Law Firm Pack",
                            description="Paralegal, Research, Billing agents + document templates.",
                            industry_tags=["legal"], price=1999, status="approved",
                            publisher="LegalAI Co", installs=820),
            MarketplaceItem(id="mp_hr", type="agent_pack", name="Recruitment Pack",
                            description="Recruiter + Payroll agents with screening skills.",
                            industry_tags=["hr"], price=999, status="approved",
                            publisher="PeopleOps", installs=540),
            MarketplaceItem(id="mp_review", type="skill", name="WhatsApp Auto-Responder",
                            description="Rule-based WhatsApp triage skill.",
                            industry_tags=["support"], status="in_review",
                            publisher="ChatTools", installs=0),
        ])
        db.add_all([
            Release(id="rel_100", version="1.0.0", channel="stable",
                    platforms={"win": {"url": "#"}, "mac": {"url": "#"}, "linux": {"url": "#"}},
                    notes_md="Initial GA release.", rollout_percent=100, state="complete"),
            Release(id="rel_110", version="1.1.0", channel="beta",
                    platforms={"win": {"url": "#"}}, notes_md="Workflow builder v2, "
                    "self-healing improvements.", rollout_percent=25, state="rolling"),
        ])
        db.add_all([
            ConfigItem(id="cfg_model", domain="model_catalog", key="qwen14b",
                       value={"family": "Qwen", "size": "14B", "approved": True}, scope="locked"),
            ConfigItem(id="cfg_conn", domain="connector_catalog", key="tally",
                       value={"name": "Tally", "version": "2.3"}, scope="overridable"),
            ConfigItem(id="cfg_thr", domain="default_thresholds", key="ceo_limit",
                       value={"amount": 50000, "currency": "INR"}, scope="suggestion"),
            ConfigItem(id="cfg_loc", domain="voice_locales", key="hi-IN",
                       value={"name": "Hindi (India)", "tts": "piper-hi"}, scope="overridable"),
        ])

        # ── §3.10 Compliance-as-Code platform policy packs ─────────────────
        from .models import PolicyPack
        db.add_all([
            PolicyPack(id="pol_gdpr", tenant_id=None, name="GDPR", version="1.0", scope="all",
                       locked=True, rules=[
                {"policy_id": "GDPR-1", "condition": {"if": "cross_border"}, "effect": "deny",
                 "evidence": "Block cross-border transfer of personal data without a lawful basis."},
                {"policy_id": "GDPR-2", "condition": {"if": "export"}, "effect": "require_approval",
                 "evidence": "Data export requires human approval (Art. 15/20)."},
                {"policy_id": "GDPR-3", "condition": {"if": "pii"}, "effect": "redact",
                 "evidence": "Redact PII from logs/telemetry."}]),
            PolicyPack(id="pol_hipaa", tenant_id=None, name="HIPAA-adjacent (Clinic)", version="1.0",
                       scope="all", locked=True, rules=[
                {"policy_id": "HIPAA-1", "condition": {"if": "medical_advice"}, "effect": "deny",
                 "evidence": "AI never communicates diagnoses/results without practitioner release."},
                {"policy_id": "HIPAA-2", "condition": {"if": "phi"}, "effect": "deny",
                 "evidence": "PHI is local-only; never sent to a cloud tier."}]),
            PolicyPack(id="pol_rera", tenant_id=None, name="RERA (Real Estate)", version="1.0",
                       scope="comms", locked=True, rules=[
                {"policy_id": "RERA-1", "condition": {"if": "ad_publish"}, "effect": "require_approval",
                 "evidence": "Marketing creatives must carry the RERA number; route to Compliance."}]),
            PolicyPack(id="pol_euai", tenant_id=None, name="EU AI Act logging", version="1.0",
                       scope="all", locked=True, rules=[
                {"policy_id": "EUAI-1", "condition": {"if": "autonomous_decision"}, "effect": "require_approval",
                 "evidence": "High-risk autonomous decisions are logged and human-reviewable."}]),
        ])

        db.commit()
        print("✅ Clean seed complete (empty company).")
        print("   User : user@gmail.com / user")
        print("   Admin: admin@gmail.com / admin")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

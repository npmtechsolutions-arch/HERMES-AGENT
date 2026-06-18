"""
SQLAlchemy ORM models for HERMUS / AI Office Assistant.

Mirrors the Table Design Document (doc 12). Two logical planes share one
PostgreSQL database for this single-deployment demo:

  * CLOUD plane  : identity, tenants, plans, subscriptions, billing, devices,
                   entitlements, common config, releases, marketplace, admin, audit.
  * LOCAL plane  : departments, agents, skills, tasks, workflows, approvals,
                   second brain (memory + knowledge graph), messaging bus,
                   communications, calls, models, analytics, audit.

Privacy invariant (SRS-INV-1): in production the two planes are separate
databases and business content never leaves the local plane. Here they coexist
for a runnable demo; tenant_id scopes every local row.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, Numeric,
    String, Text,
)
from sqlalchemy.orm import relationship

from .database import Base


def now():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), default=now)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)


# ───────────────────────────── CLOUD: Identity & Tenancy ─────────────────────
class User(Base, TimestampMixin):
    __tablename__ = "users"
    id = Column(String, primary_key=True)            # usr_...
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String)
    full_name = Column(String, nullable=False)
    email_verified = Column(Boolean, default=True)
    status = Column(String, default="active")        # active | disabled
    last_login_at = Column(DateTime(timezone=True))


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"
    id = Column(String, primary_key=True)            # tnt_...
    owner_user_id = Column(String, ForeignKey("users.id"))
    company_name = Column(String)
    industry = Column(String)
    region = Column(String)
    tax_id = Column(String)
    # pending_approval|active|suspended|grace|soft_locked|closed
    status = Column(String, default="active")
    onboarding_note = Column(Text)
    agent_config = Column(JSON, default=dict)        # Hermes agent settings (models, gen params, behavior, voice, safety)
    setup = Column(JSON, default=dict)               # guided-setup state {goal, skipped:[], dismissed:bool}
    active_edition_id = Column(String)               # the sub-product (Edition) this tenant is running


class TenantMember(Base, TimestampMixin):
    __tablename__ = "tenant_members"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"))
    user_id = Column(String, ForeignKey("users.id"))
    role = Column(String, nullable=False)            # owner | admin | member
    seat_active = Column(Boolean, default=True)


class Device(Base, TimestampMixin):
    __tablename__ = "devices"
    id = Column(String, primary_key=True)            # dev_...
    tenant_id = Column(String, ForeignKey("tenants.id"))
    user_id = Column(String, ForeignKey("users.id"))
    name = Column(String)
    os = Column(String)
    fingerprint = Column(String)
    app_version = Column(String)
    config_version = Column(Integer, default=1)
    last_seen_at = Column(DateTime(timezone=True))
    status = Column(String, default="active")        # active | deactivated


# ───────────────────────────── CLOUD: Plans & Billing ───────────────────────
class Plan(Base, TimestampMixin):
    __tablename__ = "plans"
    id = Column(String, primary_key=True)            # pln_pro_monthly_inr
    name = Column(String, nullable=False)
    billing_period = Column(String)                  # monthly | yearly
    currency = Column(String, default="INR")
    price = Column(Numeric(12, 2), default=0)
    limits = Column(JSON, nullable=False)            # {agents, workflows, seats, devices, ...}
    feature_flags = Column(JSON, nullable=False)
    is_public = Column(Boolean, default=True)
    version = Column(Integer, default=1)


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"
    id = Column(String, primary_key=True)            # sub_...
    tenant_id = Column(String, ForeignKey("tenants.id"))
    plan_id = Column(String, ForeignKey("plans.id"))
    # trialing|active|past_due|grace|soft_locked|canceled
    status = Column(String, nullable=False, default="trialing")
    gateway = Column(String)                         # stripe | razorpay
    gateway_sub_id = Column(String)
    current_period_start = Column(DateTime(timezone=True))
    current_period_end = Column(DateTime(timezone=True))
    cancel_at_period_end = Column(Boolean, default=False)
    trial_ends_at = Column(DateTime(timezone=True))


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"))
    subscription_id = Column(String, ForeignKey("subscriptions.id"))
    number = Column(String, unique=True)
    currency = Column(String, default="INR")
    subtotal = Column(Numeric(12, 2))
    tax = Column(Numeric(12, 2))
    total = Column(Numeric(12, 2))
    tax_breakup = Column(JSON)
    status = Column(String, default="paid")          # draft|open|paid|void|refunded
    issued_at = Column(DateTime(timezone=True), default=now)
    paid_at = Column(DateTime(timezone=True))


class Coupon(Base, TimestampMixin):
    __tablename__ = "coupons"
    id = Column(String, primary_key=True)
    code = Column(String, unique=True)
    percent_off = Column(Numeric(5, 2))
    amount_off = Column(Numeric(12, 2))
    currency = Column(String)
    max_redemptions = Column(Integer)
    redeemed = Column(Integer, default=0)
    valid_until = Column(DateTime(timezone=True))


# ───────────────────────────── CLOUD: Config, Releases, Marketplace ──────────
class ConfigItem(Base, TimestampMixin):
    __tablename__ = "config_items"
    id = Column(String, primary_key=True)
    domain = Column(String)   # model_catalog|connector_catalog|industry_templates|voice_locales|compliance_presets|default_thresholds
    key = Column(String)
    value = Column(JSON)
    scope = Column(String, nullable=False)           # locked | overridable | suggestion
    active = Column(Boolean, default=True)


class ConfigBundle(Base, TimestampMixin):
    __tablename__ = "config_bundles"
    version = Column(Integer, primary_key=True)
    manifest = Column(JSON)
    sha256 = Column(String)
    state = Column(String, default="draft")          # draft|canary|published|rolled_back
    published_at = Column(DateTime(timezone=True))


class Release(Base, TimestampMixin):
    __tablename__ = "releases"
    id = Column(String, primary_key=True)
    version = Column(String, unique=True)
    channel = Column(String, default="stable")
    platforms = Column(JSON)
    notes_md = Column(Text)
    force_floor = Column(String)
    rollout_percent = Column(Integer, default=0)
    crash_gate_pct = Column(Numeric(5, 2), default=1.0)
    state = Column(String, default="draft")          # draft|rolling|paused|complete|withdrawn


class MarketplaceItem(Base, TimestampMixin):
    __tablename__ = "mp_items"
    id = Column(String, primary_key=True)
    type = Column(String)   # agent_pack|skill|workflow|integration|industry_template
    name = Column(String)
    description = Column(Text)
    industry_tags = Column(JSON)
    price = Column(Numeric(12, 2), default=0)
    currency = Column(String, default="INR")
    is_free = Column(Boolean, default=False)
    status = Column(String, default="approved")      # in_review|approved|rejected|taken_down
    publisher = Column(String)
    installs = Column(Integer, default=0)


# ───────────────────────────── CLOUD: Admin & Audit ─────────────────────────
class AdminUser(Base, TimestampMixin):
    __tablename__ = "admin_users"
    id = Column(String, primary_key=True)
    email = Column(String, unique=True)
    full_name = Column(String)
    password_hash = Column(String)
    roles = Column(JSON, default=list)               # [super, support, finance, catalog]
    status = Column(String, default="active")
    last_login_at = Column(DateTime(timezone=True))


class AdminApproval(Base, TimestampMixin):
    __tablename__ = "admin_approvals"
    id = Column(String, primary_key=True)
    action_type = Column(String)
    payload = Column(JSON)
    requested_by = Column(String)
    approved_by = Column(String)
    state = Column(String, default="pending")        # pending|approved|rejected|expired


class SupportTicket(Base, TimestampMixin):
    __tablename__ = "support_tickets"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"))
    subject = Column(String)
    body = Column(Text)
    status = Column(String, default="open")
    priority = Column(String, default="normal")
    assigned_admin = Column(String)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    plane = Column(String)                            # cloud | local
    actor = Column(String, nullable=False)           # user:.. | admin:.. | agent:.. | system
    tenant_id = Column(String)
    action = Column(String, nullable=False)
    target = Column(String)
    meta = Column(JSON)
    # §3.1 — five-layer identity chain (L1 tenant, L2 human/speaker/session, L3 agent,
    #        L4 capability, L5 substrate). A record is invalid without all keys present.
    identity_chain = Column(JSON)
    # §3.4 — tamper-evident hash chain (per chain_key: tenant_id or 'global').
    chain_key = Column(String, index=True)
    prev_hash = Column(String)
    this_hash = Column(String)
    at = Column(DateTime(timezone=True), default=now, index=True)


class AuditAnchor(Base):
    """§3.4 — periodic head-hash anchor (content-free; signed)."""
    __tablename__ = "audit_anchors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_key = Column(String, index=True)
    head_hash = Column(String)
    range_to_id = Column(Integer)
    signature = Column(String)
    signed_at = Column(DateTime(timezone=True), default=now)


class MetricDaily(Base):
    __tablename__ = "metrics_daily"
    id = Column(Integer, primary_key=True, autoincrement=True)
    day = Column(String)
    metric = Column(String)
    dims = Column(JSON)
    value = Column(Float)


# ───────────────────────────── LOCAL: Org & Agents ──────────────────────────
class Department(Base, TimestampMixin):
    __tablename__ = "departments"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    name = Column(String)
    parent_id = Column(String, ForeignKey("departments.id"))
    isolation = Column(Boolean, default=False)


class Agent(Base, TimestampMixin):
    __tablename__ = "agents"
    id = Column(String, primary_key=True)            # agt_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    name = Column(String)
    designation = Column(String)
    department_id = Column(String, ForeignKey("departments.id"))
    description = Column(Text)
    objectives = Column(JSON, default=list)
    model_id = Column(String)
    permissions = Column(JSON, default=dict)         # {spend_limit, external_send}
    kpis = Column(JSON, default=list)
    schedule = Column(JSON, default=dict)
    reporting_manager_id = Column(String, ForeignKey("agents.id"))
    # idle|working|waiting|reviewing|escalated|completed|error|paused|archived
    status = Column(String, default="idle")
    voice_id = Column(String, default="piper-female-1")
    is_ceo = Column(Boolean, default=False)
    skills = Column(JSON, default=list)              # skill names
    tools = Column(JSON, default=list)               # mcp tool names
    model_tier = Column(String, default="local")     # local|byo|managed (G5 Model Gateway)


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    name = Column(String)
    description = Column(Text)
    # builtin|marketplace|skill_builder|auto_captured|imported (G3, G10)
    source = Column(String, default="builtin")
    definition = Column(JSON)
    version = Column(String, default="1.0")
    status = Column(String, default="active")            # proposed|active|archived (G3 review gate)
    learned_from_task_id = Column(String)                # G3
    confidence = Column(Float, default=1.0)              # G3
    sandbox_level = Column(String, default="process")    # process|docker (G8)
    runs = Column(Integer, default=0)


class RemoteChannel(Base, TimestampMixin):
    """G2 — a paired personal channel used to COMMAND the workforce remotely."""
    __tablename__ = "remote_channels"
    id = Column(String, primary_key=True)            # rch_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    type = Column(String)                            # whatsapp|telegram|signal|email
    label = Column(String)
    pairing_code = Column(String)
    sender_allowlist = Column(JSON, default=list)
    scopes = Column(JSON, default=list)              # query|approve|briefing (scoped grammar; SC-11)
    status = Column(String, default="pending")       # pending|paired|revoked
    last_seen_at = Column(DateTime(timezone=True))


class RemoteCommand(Base):
    """G2 — audit/history of remote commands (channel identity, intent, response)."""
    __tablename__ = "remote_commands"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    channel_id = Column(String, ForeignKey("remote_channels.id"))
    sender = Column(String)
    message = Column(Text)
    intent = Column(String)
    response = Column(Text)
    allowed = Column(Boolean, default=True)
    at = Column(DateTime(timezone=True), default=now)


class AgentPerformance(Base):
    __tablename__ = "agent_performance"
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agents.id"))
    period = Column(String)
    tasks_completed = Column(Integer, default=0)
    success_rate = Column(Float, default=0)
    error_rate = Column(Float, default=0)
    productivity_score = Column(Float, default=0)
    utilization = Column(Float, default=0)


# ───────────────────────────── LOCAL: Tasks & Workflows ─────────────────────
class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True)            # tsk_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    title = Column(String)
    description = Column(Text)
    source = Column(String, default="manual")        # voice|manual|workflow|trigger|schedule
    parent_task_id = Column(String, ForeignKey("tasks.id"))
    assignee_agent_id = Column(String, ForeignKey("agents.id"))
    priority = Column(String, default="normal")      # low|normal|high|urgent
    deadline = Column(DateTime(timezone=True))
    # queued|planning|working|waiting|reviewing|escalated|completed|failed|canceled
    status = Column(String, default="queued")
    plan = Column(JSON)                              # CEO Agent DAG
    result = Column(JSON)
    utterance = Column(Text)


class Workflow(Base, TimestampMixin):
    __tablename__ = "workflows"
    id = Column(String, primary_key=True)            # wfl_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    name = Column(String)
    graph = Column(JSON, nullable=False)             # {nodes, edges}
    status = Column(String, default="draft")         # draft|active|paused|archived
    version = Column(Integer, default=1)
    source_utterance = Column(Text)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id = Column(String, primary_key=True)
    workflow_id = Column(String, ForeignKey("workflows.id"))
    trigger_info = Column(JSON)
    started_at = Column(DateTime(timezone=True), default=now)
    ended_at = Column(DateTime(timezone=True))
    status = Column(String, default="running")       # running|succeeded|failed|partial|canceled
    node_results = Column(JSON)


class Schedule(Base, TimestampMixin):
    __tablename__ = "schedules"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    workflow_id = Column(String, ForeignKey("workflows.id"))
    kind = Column(String)                            # cron|interval|event
    expression = Column(String)
    timezone = Column(String, default="Asia/Kolkata")
    run_policy = Column(String, default="run_on_wake")
    next_run_at = Column(DateTime(timezone=True))
    consecutive_failures = Column(Integer, default=0)


class Approval(Base, TimestampMixin):
    __tablename__ = "approvals"
    id = Column(String, primary_key=True)            # apv_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    requester_agent_id = Column(String, ForeignKey("agents.id"))
    task_id = Column(String, ForeignKey("tasks.id"))
    action_summary = Column(String)
    payload = Column(JSON)
    rule_id = Column(String)                         # e.g., AC-05
    current_tier = Column(String, default="human")   # specialist|manager|ceo|human
    state = Column(String, default="pending")        # pending|approved|rejected|expired
    chain = Column(JSON, default=list)               # [{tier, actor, decision, reason, at}]
    expires_at = Column(DateTime(timezone=True))


# ───────────────────────────── LOCAL: Second Brain & KG ─────────────────────
class MemoryItem(Base, TimestampMixin):
    __tablename__ = "memory_items"
    id = Column(String, primary_key=True)            # mem_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    memory_class = Column(String)                    # personal|business|knowledge|operational
    title = Column(String)
    source_type = Column(String)                     # pdf|email|audio|web|db|note
    body = Column(Text)                              # plaintext content (full-text searchable)
    file_path = Column(String)
    content_hash = Column(String)
    tier = Column(String, default="hot")             # hot|cold
    pii = Column(Boolean, default=False)
    confidence = Column(Float, default=1.0)
    confidential = Column(Boolean, default=False)
    embedding = Column(JSON)                          # nomic-embed-text vector (pgvector in prod)


class KGEntity(Base, TimestampMixin):
    __tablename__ = "kg_entities"
    id = Column(String, primary_key=True)            # ent_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    type = Column(String)   # customer|vendor|contact|project|task|document|agent|policy|product|custom
    name = Column(String)
    aliases = Column(JSON, default=list)
    attrs = Column(JSON, default=dict)
    confidential = Column(Boolean, default=False)


class KGRelation(Base, TimestampMixin):
    __tablename__ = "kg_relations"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    from_id = Column(String, ForeignKey("kg_entities.id"))
    to_id = Column(String, ForeignKey("kg_entities.id"))
    relation = Column(String)                        # works_for|belongs_to|quoted_in...
    attrs = Column(JSON, default=dict)


# ───────────────────────────── LOCAL: Bus, Comms, Calls ─────────────────────
class BusThread(Base, TimestampMixin):
    __tablename__ = "bus_threads"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    task_id = Column(String, ForeignKey("tasks.id"))
    topic = Column(String)
    participants = Column(JSON, default=list)


class BusMessage(Base):
    __tablename__ = "bus_messages"
    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("bus_threads.id"))
    from_agent_id = Column(String, ForeignKey("agents.id"))
    kind = Column(String)                            # query|handoff|result|status
    content = Column(JSON)
    at = Column(DateTime(timezone=True), default=now)


class CommChannel(Base, TimestampMixin):
    __tablename__ = "comm_channels"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    type = Column(String)   # email|whatsapp|telegram|slack|teams|discord|sms
    account_ref = Column(String)
    status = Column(String, default="connected")


class CommThread(Base, TimestampMixin):
    __tablename__ = "comm_threads"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    channel_id = Column(String, ForeignKey("comm_channels.id"))
    subject = Column(String)
    counterpart = Column(String)
    counterpart_entity_id = Column(String, ForeignKey("kg_entities.id"))
    category = Column(String, default="fyi")         # urgent|action|fyi|spam
    ai_reply_count = Column(Integer, default=0)
    unread = Column(Boolean, default=True)


class CommMessage(Base):
    __tablename__ = "comm_messages"
    id = Column(String, primary_key=True)
    thread_id = Column(String, ForeignKey("comm_threads.id"))
    direction = Column(String)                       # in | out
    body = Column(Text)
    drafted_by_agent = Column(String, ForeignKey("agents.id"))
    sent_at = Column(DateTime(timezone=True), default=now)
    source_citations = Column(JSON)


class Call(Base):
    __tablename__ = "calls"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    direction = Column(String)                       # inbound | outbound
    agent_id = Column(String, ForeignKey("agents.id"))
    contact = Column(String)
    started_at = Column(DateTime(timezone=True), default=now)
    ended_at = Column(DateTime(timezone=True))
    transcript = Column(JSON)
    sentiment = Column(String)
    outcome_code = Column(String)
    consent_recorded = Column(Boolean, default=False)


# ───────────────────────────── LOCAL: Models & Compute ──────────────────────
class LLMModel(Base, TimestampMixin):
    __tablename__ = "llm_models"
    id = Column(String, primary_key=True)            # mdl_qwen14b_q4
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    family = Column(String)
    size = Column(String)
    quant = Column(String)
    runtime = Column(String)                         # ollama|llamacpp|vllm|lmstudio
    vram_mb = Column(Integer)
    catalog_approved = Column(Boolean, default=True)
    status = Column(String, default="available")     # available|downloading|loaded|error


class Chatbot(Base, TimestampMixin):
    """A purpose-built conversational assistant inside a profile (tenant).
    Sales Bot / HR Bot / Finance Bot… each with its own persona, memory scope,
    tools, permissions, model and channels. Powered by the agent engine."""
    __tablename__ = "chatbots"
    id = Column(String, primary_key=True)            # cbt_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    name = Column(String, nullable=False)
    purpose = Column(Text)
    department = Column(String)
    model_id = Column(String, default="mdl_gemma9b")
    persona = Column(Text)                            # system prompt / personality
    memory_scopes = Column(JSON, default=list)       # ['business','knowledge',...]
    tools = Column(JSON, default=list)
    permissions = Column(JSON, default=dict)
    linked_pipeline_id = Column(String, ForeignKey("pipelines.id"))
    color = Column(String, default="violet")
    status = Column(String, default="active")        # active|paused|archived
    # AgentSphere multi-agent layer (Doc 18 FR-2/FR-4)
    role = Column(String, default="specialist")      # manager(router) | specialist
    capabilities = Column(JSON, default=list)        # ['reservations','billing','support',...] (FR-4.4 registry tags)
    confidence_threshold = Column(Float, default=0.55)  # below → human handoff (FR-6.1)
    can_delegate = Column(Boolean, default=True)     # may call peers via consult_agent (FR-4.1)
    published = Column(Boolean, default=True)        # draft/publish (FR-2.2); editing never mutates live
    version = Column(Integer, default=1)


class ChatbotChannel(Base, TimestampMixin):
    __tablename__ = "chatbot_channels"
    id = Column(String, primary_key=True)
    chatbot_id = Column(String, ForeignKey("chatbots.id"), index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    type = Column(String)   # website|desktop|voice|telegram|whatsapp|slack|teams|discord|email
    config = Column(JSON, default=dict)              # token / account ref (never returned in full)
    status = Column(String, default="disconnected")  # connected|disconnected


class ChatConversation(Base, TimestampMixin):
    __tablename__ = "chat_conversations"
    id = Column(String, primary_key=True)            # cvn_...
    chatbot_id = Column(String, ForeignKey("chatbots.id"), index=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    channel = Column(String, default="website")
    external_user = Column(String)                   # platform user id (external channels)
    title = Column(String)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("chat_conversations.id"), index=True)
    role = Column(String)                            # user|assistant|human-agent
    body = Column(Text)
    channel = Column(String)
    citations = Column(JSON)
    engine = Column(String)
    trace = Column(JSON)                             # AgentSphere transparency: routing + internal consult dialogue + per-hop tokens/cost + guardrail/handoff (FR-4.5)
    at = Column(DateTime(timezone=True), default=now)


class Escalation(Base, TimestampMixin):
    """Human handoff queue item (Doc 18 FR-6). First-class, not an add-on."""
    __tablename__ = "escalations"
    id = Column(String, primary_key=True)            # esc_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    conversation_id = Column(String, ForeignKey("chat_conversations.id"), index=True)
    chatbot_id = Column(String, ForeignKey("chatbots.id"))
    reason = Column(String)                          # low_confidence|asked_for_human|guardrail|misroute|handoff_tool|sentiment
    summary = Column(Text)                           # AI-drafted summary + suggested reply
    suggested_reply = Column(Text)
    status = Column(String, default="queued")        # queued|claimed|resolved
    claimed_by = Column(String)
    sla_due_at = Column(DateTime(timezone=True))     # FR-6.3 SLA timer
    resolution = Column(Text)
    resume_instructions = Column(Text)               # "I resolved billing; resume upsell" (FR-6.2)


class VerticalDeployment(Base, TimestampMixin):
    """Record of a deployed Vertical Full Agent, with a manifest of everything it
    created so it can be cleanly **undeployed** (Doc 18 product line)."""
    __tablename__ = "vertical_deployments"
    id = Column(String, primary_key=True)            # vdp_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    vid = Column(String, index=True)                 # vertical catalog id
    name = Column(String)
    industry = Column(String)
    manifest = Column(JSON, default=dict)            # {agents, pipelines, chatbots, recipes_created, recipes_enabled}


class SolutionDeployment(Base, TimestampMixin):
    """Record of a deployed Solution (focused agent + recipes), with a manifest so
    it can be cleanly **undeployed**."""
    __tablename__ = "solution_deployments"
    id = Column(String, primary_key=True)            # sdp_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    sid = Column(String, index=True)                 # solution catalog id
    name = Column(String)
    manifest = Column(JSON, default=dict)            # {agent_id, recipes_created, recipes_enabled}


class EngineDeployment(Base, TimestampMixin):
    """Record of a deployed Universal Engine (engine worker agent + recipes), with a
    manifest so it can be cleanly **undeployed**."""
    __tablename__ = "engine_deployments"
    id = Column(String, primary_key=True)            # edp_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    eid = Column(String, index=True)                 # engine id (E1..E8)
    name = Column(String)
    manifest = Column(JSON, default=dict)            # {agent_id, recipes_created, recipes_enabled}


class Edition(Base, TimestampMixin):
    """A sub-product packaging of the one engine (Docs 19/20). Admin-defined and
    publishable: a roster source + module flags + branding skin + price book.
    'HERMUS Personal', industry editions and role apps are all rows here — no
    code fork. Created/edited/published from the product admin dashboard."""
    __tablename__ = "editions"
    id = Column(String, primary_key=True)            # edn_...
    slug = Column(String, unique=True, index=True)   # "personal", "clinic", "doctors"
    name = Column(String, nullable=False)            # "HERMUS Personal"
    layer = Column(String, default="role_app")       # universal | edition | role_app
    template_key = Column(String)                    # industry_templates.py key for the roster
    tagline = Column(String)
    description = Column(Text)
    enabled_engines = Column(JSON, default=list)     # subset of E1..E8
    enabled_modules = Column(JSON, default=list)     # subset of the 35 module flags (M1..M35)
    skin = Column(JSON, default=dict)                # {brand, color, hidden_nav:[], onboarding}
    price_book = Column(JSON, default=dict)          # {plans:[{name, price_inr, price_usd, ...}], add_ons:[]}
    locked_rules = Column(JSON, default=list)        # edition-level locked rule ids/specs
    status = Column(String, default="draft", index=True)  # draft | published | retired
    is_default = Column(Boolean, default=False)      # the default edition new tenants land on
    version = Column(Integer, default=1)
    sort = Column(Integer, default=100)


class EditionDeployment(Base, TimestampMixin):
    """Record of an Edition activated for a tenant, with a manifest of everything
    it created so it can be cleanly switched/undeployed (same pattern as verticals)."""
    __tablename__ = "edition_deployments"
    id = Column(String, primary_key=True)            # eddp_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    edition_id = Column(String, index=True)
    slug = Column(String, index=True)
    name = Column(String)
    manifest = Column(JSON, default=dict)            # {agents, pipelines, recipes_created, recipes_enabled}


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    id = Column(String, primary_key=True)            # prd_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    stage = Column(String, default="idea")           # idea|building|launched|paused
    status = Column(String, default="active")


# ───────────────────────────── Agent Pipelines (the "AI crew") ──────────────
class Pipeline(Base, TimestampMixin):
    __tablename__ = "pipelines"
    id = Column(String, primary_key=True)            # ppl_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    product_id = Column(String, ForeignKey("products.id"))
    name = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="draft")         # draft|ready|archived
    source = Column(String, default="custom")        # custom|template|ai


class PipelineStep(Base, TimestampMixin):
    __tablename__ = "pipeline_steps"
    id = Column(String, primary_key=True)
    pipeline_id = Column(String, ForeignKey("pipelines.id"), index=True)
    seq = Column(Integer)                            # order in the chain
    agent_id = Column(String, ForeignKey("agents.id"))
    instruction = Column(Text)                       # what this agent should do
    requires_approval = Column(Boolean, default=False)


class PipelineRun(Base, TimestampMixin):
    __tablename__ = "pipeline_runs"
    id = Column(String, primary_key=True)            # ppr_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    pipeline_id = Column(String, ForeignKey("pipelines.id"))
    # running|waiting_approval|completed|failed|canceled
    status = Column(String, default="running")
    use_ai = Column(Boolean, default=True)
    final_report = Column(Text)
    started_at = Column(DateTime(timezone=True), default=now)
    ended_at = Column(DateTime(timezone=True))


class PipelineStepRun(Base, TimestampMixin):
    __tablename__ = "pipeline_step_runs"
    id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("pipeline_runs.id"), index=True)
    step_id = Column(String, ForeignKey("pipeline_steps.id"))
    seq = Column(Integer)
    agent_id = Column(String, ForeignKey("agents.id"))
    agent_name = Column(String)
    instruction = Column(Text)
    requires_approval = Column(Boolean, default=False)
    # pending|running|awaiting_approval|approved|rejected|done
    status = Column(String, default="pending")
    output = Column(Text)
    engine = Column(String)


# ───────────────────── Multi-Tenancy, Isolation & Compliance (Doc 15) ────────
class BudgetLedger(Base, TimestampMixin):
    """§3.2 — per-scope spend ledger (tenant → department → agent → task)."""
    __tablename__ = "budget_ledgers"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    scope = Column(String)                            # tenant|department|agent
    scope_ref = Column(String)                        # dept name / agent id (null = tenant)
    period = Column(String)                           # e.g. 2026-06
    limit = Column(Numeric(12, 2), default=0)
    spent = Column(Numeric(12, 2), default=0)
    reserved = Column(Numeric(12, 2), default=0)
    currency = Column(String, default="INR")


class BudgetReservation(Base):
    __tablename__ = "budget_reservations"
    id = Column(String, primary_key=True)
    ledger_id = Column(String, ForeignKey("budget_ledgers.id"))
    tenant_id = Column(String, index=True)
    est_cost = Column(Numeric(12, 2))
    actual_cost = Column(Numeric(12, 2))
    task_ref = Column(String)
    state = Column(String, default="reserved")        # reserved|settled|released
    at = Column(DateTime(timezone=True), default=now)


class GatewayCall(Base):
    """§3.6 — content-free per-tenant gateway telemetry (sizes/timings/model, no bodies)."""
    __tablename__ = "gateway_calls"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    agent_ref = Column(String)
    model = Column(String)
    tier = Column(String)                             # local|byo|managed
    task_profile = Column(String)
    prompt_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    latency_ms = Column(Integer, default=0)
    cost = Column(Numeric(12, 4), default=0)
    policy_decision = Column(String)
    at = Column(DateTime(timezone=True), default=now)


class RoutingPolicy(Base, TimestampMixin):
    """§3.3 — per-tenant ordered model preference + failover per task profile."""
    __tablename__ = "routing_policies"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    task_profile = Column(String)                     # drafting|extraction|planning|...
    chain = Column(JSON, default=list)                # ordered [{model, tier}]
    regions = Column(JSON, default=list)              # allowed regions
    active = Column(Boolean, default=True)


class TenantCeiling(Base, TimestampMixin):
    """§P1 — tool policy ceiling: agent grants can never exceed these."""
    __tablename__ = "tenant_ceilings"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    tool_pattern = Column(String)                     # e.g. payments.execute
    effect = Column(String, default="deny")           # deny|require_approval


class PolicyPack(Base, TimestampMixin):
    """§3.10 — Compliance-as-Code: declarative policies evaluated by the PDP."""
    __tablename__ = "policy_packs"
    id = Column(String, primary_key=True)             # pol_gdpr
    tenant_id = Column(String, index=True)            # null = platform pack
    name = Column(String)
    version = Column(String, default="1.0")
    scope = Column(String)                            # all|gateway|tool|comms|memory
    rules = Column(JSON, default=list)                # [{policy_id, condition, effect, evidence}]
    locked = Column(Boolean, default=False)           # PA-03: tenant can tighten, not loosen
    active = Column(Boolean, default=True)


class DeletionSaga(Base, TimestampMixin):
    """§3.5 — one-click tenant offboarding deletion saga + certificate."""
    __tablename__ = "deletion_sagas"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    steps = Column(JSON, default=list)                # ordered [{system, state, at}]
    state = Column(String, default="running")         # running|completed|failed
    certificate_hash = Column(String)
    certificate = Column(JSON)


class SandboxLease(Base):
    """§4 — Tenant-Aware Execution Sandbox lease (golden snapshot + ephemeral overlay)."""
    __tablename__ = "sandbox_leases"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    qos = Column(String, default="standard")          # standard|enterprise
    golden_hash = Column(String)
    task_ref = Column(String)
    leased_at = Column(DateTime(timezone=True), default=now)
    recycled_at = Column(DateTime(timezone=True))
    sanitize_ms = Column(Integer)
    scrub_proof = Column(String)                       # key-shred proof
    state = Column(String, default="leased")           # leased|recycled


# ───────────────────── MVP Real-Estate vertical (Doc 16) ────────────────────
class Property(Base, TimestampMixin):
    __tablename__ = "properties"
    id = Column(String, primary_key=True)            # prop_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    name = Column(String)
    type = Column(String)                            # 2BHK|3BHK|villa|plot
    price = Column(Numeric(14, 2))
    location = Column(String)
    status = Column(String, default="available")     # available|hold|sold


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"
    id = Column(String, primary_key=True)            # led_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    name = Column(String)
    phone = Column(String, index=True)               # dedupe key
    requirement = Column(String)                     # e.g. 3BHK
    budget = Column(Numeric(14, 2))
    location = Column(String)
    source = Column(String, default="manual")        # portal|whatsapp|manual|voice
    stage = Column(String, default="new")            # new|qualified|follow_up|site_visit|booking|won|lost
    score = Column(String, default="warm")           # hot|warm|cold
    confidence = Column(Float, default=1.0)          # extraction confidence (GAP-2)
    property_id = Column(String, ForeignKey("properties.id"))
    agent_paused = Column(Boolean, default=False)    # GAP-4 take-over
    opt_out = Column(Boolean, default=False)
    rehearsal = Column(Boolean, default=False)       # GAP-6 simulated cast (never egresses)
    persona = Column(String)                          # rehearsal cast persona
    followup_step = Column(Integer, default=0)       # 0→day1→day3→day7
    last_contacted_at = Column(DateTime(timezone=True))


class LeadInteraction(Base):
    __tablename__ = "lead_interactions"
    id = Column(String, primary_key=True)            # lix_...
    tenant_id = Column(String, index=True)
    lead_id = Column(String, ForeignKey("leads.id"), index=True)
    channel = Column(String)                         # whatsapp|email|voice|note
    direction = Column(String)                       # in|out
    body = Column(Text)
    drafted_by = Column(String, default="agent")     # agent|human
    # GAP-3 undo window: queued → sent | recalled ; GAP-2: held (validator)
    status = Column(String, default="sent")          # queued|sent|recalled|held|received
    send_after = Column(DateTime(timezone=True))     # undo deadline
    validator = Column(JSON)                          # violations (GAP-2)
    reviewed_by = Column(String)                     # GAP-3 liability stamp
    at = Column(DateTime(timezone=True), default=now)


class SiteVisit(Base, TimestampMixin):
    __tablename__ = "site_visits"
    id = Column(String, primary_key=True)            # svt_...
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    lead_id = Column(String, ForeignKey("leads.id"))
    property_id = Column(String, ForeignKey("properties.id"))
    slot = Column(DateTime(timezone=True))
    status = Column(String, default="offered")       # offered|confirmed|reminded|done|no_show
    reminders = Column(JSON, default=list)           # [{when, sent}]
    outcome = Column(Text)                           # voice-captured note


# ───────────────────── GAP-1 Backup & Restore ───────────────────────────────
class BackupDestination(Base, TimestampMixin):
    __tablename__ = "backup_destinations"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    type = Column(String)                            # folder|usb|gdrive|onedrive|lan
    path = Column(String)
    status = Column(String, default="active")
    last_backup_at = Column(DateTime(timezone=True))


class BackupJob(Base):
    __tablename__ = "backup_jobs"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    destination_id = Column(String, ForeignKey("backup_destinations.id"))
    kind = Column(String, default="full")            # full|incremental
    status = Column(String, default="completed")     # completed|failed
    size_bytes = Column(Integer, default=0)
    blob_ref = Column(String)                        # path to the encrypted blob
    at = Column(DateTime(timezone=True), default=now)


class RecoveryKey(Base):
    """Phrase verification hash + (keychain-stored) derived key for ongoing backups.
    We never store the phrase or content; the phrase regenerates the key for restore."""
    __tablename__ = "recovery_keys"
    tenant_id = Column(String, primary_key=True)
    phrase_hash = Column(String)
    enc_key = Column(String)                          # represents OS-keychain storage (local)
    created_at = Column(DateTime(timezone=True), default=now)


# ───────────────────── GAP-2 Agent reliability & evaluation ──────────────────
class EvalCase(Base, TimestampMixin):
    __tablename__ = "eval_cases"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)           # null = builtin golden set
    workflow = Column(String)                        # lead_intake|follow_up|visit
    kind = Column(String, default="golden")          # golden|adversarial|from_mistake
    input = Column(JSON)
    expected = Column(JSON)


class EvalRun(Base):
    __tablename__ = "eval_runs"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    suite_run_id = Column(String, index=True)
    case_id = Column(String, ForeignKey("eval_cases.id"))
    workflow = Column(String)
    passed = Column(Boolean)
    detail = Column(String)
    at = Column(DateTime(timezone=True), default=now)


# ───────────────────── GAP-3 Mistake & recall ───────────────────────────────
class Correction(Base):
    __tablename__ = "corrections"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    interaction_id = Column(String)
    lead_id = Column(String)
    note = Column(Text)
    eval_case_id = Column(String)                    # the new case this fed
    at = Column(DateTime(timezone=True), default=now)


# ───────────────────── GAP-4 Clarifications (ask-don't-guess) ────────────────
class Clarification(Base):
    __tablename__ = "clarifications"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    lead_id = Column(String, ForeignKey("leads.id"))
    question = Column(Text)
    options = Column(JSON, default=list)
    answer = Column(String)
    status = Column(String, default="open")          # open|answered|defaulted
    at = Column(DateTime(timezone=True), default=now)


# ───────────────────── GAP-5 ROI ledger ─────────────────────────────────────
class RoiEntry(Base):
    __tablename__ = "roi_entries"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, index=True)
    kind = Column(String)        # response_time_saved|followup|visit_booked|after_hours|lead_answered
    value_minutes = Column(Float, default=0)
    detail = Column(String)
    lead_id = Column(String)
    after_hours = Column(Boolean, default=False)
    at = Column(DateTime(timezone=True), default=now)


class Recipe(Base, TimestampMixin):
    """Doc 17 §9.2 — one-toggle automation (a parameterized workflow underneath)."""
    __tablename__ = "recipes"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    recipe_id = Column(String)                        # catalog key
    enabled = Column(Boolean, default=False)
    params = Column(JSON, default=dict)


class Webhook(Base, TimestampMixin):
    """Doc 17 §9.5 — outbound webhook (signed, IDs/metadata by default)."""
    __tablename__ = "webhooks"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    url = Column(String)
    events = Column(JSON, default=list)
    secret = Column(String)
    include_content = Column(Boolean, default=False)  # privacy: content needs explicit consent
    status = Column(String, default="active")
    last_fired_at = Column(DateTime(timezone=True))
    deliveries = Column(Integer, default=0)


class UniversalRule(Base, TimestampMixin):
    """Doc 17 §5 — the 12 universal rules every vertical inherits. Templates tune
    thresholds; locked rules can never be disabled."""
    __tablename__ = "universal_rules"
    id = Column(String, primary_key=True)            # urule_<tenant>_U1
    tenant_id = Column(String, index=True)
    rule_id = Column(String)                          # U1..U12
    title = Column(String)
    why = Column(String)
    scope = Column(String)                            # inquiry|outbound|all|...
    locked = Column(Boolean, default=False)          # can't be disabled
    enabled = Column(Boolean, default=True)
    threshold = Column(JSON, default=dict)


class HealingIncident(Base, TimestampMixin):
    __tablename__ = "healing_incidents"
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), index=True)
    source = Column(String)
    error_class = Column(String)                     # transient|credential|config|logic
    signature = Column(String)
    action_taken = Column(String)
    resolved = Column(Boolean, default=False)
    occurrences = Column(Integer, default=1)
    remediation_proposal = Column(JSON)

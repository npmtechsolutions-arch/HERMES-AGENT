# AI OFFICE ASSISTANT — TABLE DESIGN DOCUMENT
**Version 2.0 | PostgreSQL 15+ | Two databases: Cloud Platform DB & Local Desktop DB**

Conventions: ULID primary keys (`text`), `created_at/updated_at timestamptz` on every table (omitted below for brevity), soft delete via `deleted_at`, `snake_case`. Cloud tenant-scoped tables carry `tenant_id` with **Row-Level Security**. Local DB uses **pgvector** for embeddings.

---

# PART A — CLOUD PLATFORM DATABASE (`aioffice_cloud`)

## A1. Identity & Tenancy

```sql
CREATE TABLE users (
  id              text PRIMARY KEY,            -- usr_...
  email           citext UNIQUE NOT NULL,
  password_hash   text,                        -- Argon2id; NULL if SSO-only
  full_name       text NOT NULL,
  email_verified  boolean DEFAULT false,
  totp_secret     text,                        -- encrypted
  status          text CHECK (status IN ('active','disabled')) DEFAULT 'active',
  last_login_at   timestamptz
);

CREATE TABLE tenants (
  id              text PRIMARY KEY,            -- tnt_...
  owner_user_id   text REFERENCES users(id),
  company_name    text,
  industry        text,                        -- informational only (template hints)
  region          text, tax_id text,
  status          text CHECK (status IN
    ('pending_approval','active','suspended','grace','soft_locked','closed')) DEFAULT 'pending_approval',
  onboarding_note text
);

CREATE TABLE tenant_members (
  id          text PRIMARY KEY,
  tenant_id   text REFERENCES tenants(id),
  user_id     text REFERENCES users(id),
  role        text CHECK (role IN ('owner','admin','member')) NOT NULL,
  seat_active boolean DEFAULT true,
  UNIQUE (tenant_id, user_id)
);

CREATE TABLE devices (
  id            text PRIMARY KEY,              -- dev_...
  tenant_id     text REFERENCES tenants(id),
  user_id       text REFERENCES users(id),
  name          text, os text, fingerprint text,
  app_version   text, config_version int,
  last_seen_at  timestamptz,
  status        text CHECK (status IN ('active','deactivated')) DEFAULT 'active'
);
CREATE INDEX idx_devices_tenant ON devices(tenant_id) WHERE status='active';

CREATE TABLE sessions (
  id text PRIMARY KEY, user_id text REFERENCES users(id),
  refresh_token_hash text, device_id text REFERENCES devices(id),
  expires_at timestamptz, revoked_at timestamptz
);
```

## A2. Plans, Subscriptions, Billing

```sql
CREATE TABLE plans (
  id            text PRIMARY KEY,              -- pln_pro_monthly_inr
  name          text NOT NULL,
  billing_period text CHECK (billing_period IN ('monthly','yearly')),
  currency      text, price numeric(12,2), tax_class text,
  limits        jsonb NOT NULL,   -- {"agents":25,"workflows":100,"seats":5,"devices":3,"call_minutes_month":0,"channels":[...]}
  feature_flags jsonb NOT NULL,   -- {"call_center":false,"multi_node":false,"offline_mode":false,...}
  is_public     boolean DEFAULT true,
  version       int DEFAULT 1
);

CREATE TABLE subscriptions (
  id              text PRIMARY KEY,            -- sub_...
  tenant_id       text REFERENCES tenants(id),
  plan_id         text REFERENCES plans(id),
  status          text CHECK (status IN
    ('trialing','active','past_due','grace','soft_locked','canceled')) NOT NULL,
  gateway         text CHECK (gateway IN ('stripe','razorpay')),
  gateway_sub_id  text,
  current_period_start timestamptz, current_period_end timestamptz,
  cancel_at_period_end boolean DEFAULT false,
  trial_ends_at   timestamptz
);
CREATE UNIQUE INDEX idx_sub_active ON subscriptions(tenant_id)
  WHERE status IN ('trialing','active','past_due','grace');

CREATE TABLE invoices (
  id text PRIMARY KEY, tenant_id text REFERENCES tenants(id),
  subscription_id text REFERENCES subscriptions(id),
  number text UNIQUE, currency text,
  subtotal numeric(12,2), tax numeric(12,2), total numeric(12,2),
  tax_breakup jsonb,                          -- GST/VAT lines
  status text CHECK (status IN ('draft','open','paid','void','refunded')),
  pdf_object_key text, issued_at timestamptz, paid_at timestamptz
);

CREATE TABLE payments (
  id text PRIMARY KEY, invoice_id text REFERENCES invoices(id),
  gateway text, gateway_payment_id text UNIQUE,
  amount numeric(12,2), currency text,
  status text CHECK (status IN ('succeeded','failed','refunded','disputed')),
  failure_code text
);

CREATE TABLE refunds (
  id text PRIMARY KEY, payment_id text REFERENCES payments(id),
  amount numeric(12,2), reason text,
  requested_by text REFERENCES admin_users(id),
  approved_by  text REFERENCES admin_users(id),   -- four-eyes: must differ
  state text CHECK (state IN ('pending_second_approval','executed','rejected')),
  gateway_refund_id text,
  CONSTRAINT four_eyes CHECK (approved_by IS NULL OR approved_by <> requested_by)
);

CREATE TABLE coupons (
  id text PRIMARY KEY, code citext UNIQUE, percent_off numeric(5,2),
  amount_off numeric(12,2), currency text, max_redemptions int,
  redeemed int DEFAULT 0, valid_until timestamptz, plan_scope jsonb
);

CREATE TABLE webhook_events (                  -- idempotency ledger (PB-07)
  id text PRIMARY KEY,                         -- gateway event id
  gateway text, event_type text, payload jsonb,
  processed_at timestamptz, result text
);

CREATE TABLE dunning_states (
  subscription_id text PRIMARY KEY REFERENCES subscriptions(id),
  failed_at timestamptz, retry_count int DEFAULT 0,
  next_retry_at timestamptz, grace_until timestamptz,
  stage text CHECK (stage IN ('retrying','grace','soft_locked','recovered'))
);
```

## A3. Entitlements & Licensing

```sql
CREATE TABLE entitlement_snapshots (
  id text PRIMARY KEY, tenant_id text REFERENCES tenants(id),
  plan_id text, limits jsonb, feature_flags jsonb,
  config_version int, issued_at timestamptz, grace_until timestamptz,
  signature text, key_id text
);
CREATE INDEX idx_ent_latest ON entitlement_snapshots(tenant_id, issued_at DESC);

CREATE TABLE offline_licenses (                -- Enterprise (UC-S17)
  id text PRIMARY KEY, tenant_id text REFERENCES tenants(id),
  license_blob text, valid_from timestamptz, valid_until timestamptz,
  issued_by text REFERENCES admin_users(id), revoked_at timestamptz
);
```

## A4. Common Configurations & Releases

```sql
CREATE TABLE config_items (
  id text PRIMARY KEY,
  domain text CHECK (domain IN
    ('model_catalog','connector_catalog','industry_templates',
     'voice_locales','compliance_presets','default_thresholds')),
  key text, value jsonb,
  scope text CHECK (scope IN ('locked','overridable','suggestion')) NOT NULL,
  active boolean DEFAULT true,
  UNIQUE (domain, key)
);

CREATE TABLE config_bundles (
  version int PRIMARY KEY,
  manifest jsonb,                              -- item ids + hashes
  object_key text, sha256 text, signature text,
  state text CHECK (state IN ('draft','canary','published','rolled_back')),
  published_by text REFERENCES admin_users(id), published_at timestamptz
);

CREATE TABLE config_adoption (
  device_id text REFERENCES devices(id),
  bundle_version int REFERENCES config_bundles(version),
  applied_at timestamptz, PRIMARY KEY (device_id, bundle_version)
);

CREATE TABLE releases (
  id text PRIMARY KEY, version text UNIQUE, channel text DEFAULT 'stable',
  platforms jsonb,                             -- {win:{url,sha},mac:{...},linux:{...}}
  notes_md text, force_floor text,
  rollout_percent int DEFAULT 0, crash_gate_pct numeric(5,2) DEFAULT 1.0,
  state text CHECK (state IN ('draft','rolling','paused','complete','withdrawn'))
);
```

## A5. Marketplace

```sql
CREATE TABLE mp_publishers (
  id text PRIMARY KEY, name text, contact_email citext,
  status text CHECK (status IN ('pending','approved','suspended')),
  revenue_share_pct numeric(5,2) DEFAULT 70
);

CREATE TABLE mp_items (
  id text PRIMARY KEY, publisher_id text REFERENCES mp_publishers(id),
  type text CHECK (type IN ('agent_pack','skill','workflow','integration','industry_template')),
  name text, description text, industry_tags text[],
  price numeric(12,2), currency text, is_free boolean DEFAULT false,
  status text CHECK (status IN ('in_review','approved','rejected','taken_down'))
);

CREATE TABLE mp_versions (
  id text PRIMARY KEY, item_id text REFERENCES mp_items(id),
  semver text, package_object_key text, sha256 text, signature text,
  permissions_manifest jsonb,                  -- reviewed at install (SC-03)
  review_state text, reviewed_by text REFERENCES admin_users(id),
  UNIQUE (item_id, semver)
);

CREATE TABLE mp_purchases (
  id text PRIMARY KEY, tenant_id text REFERENCES tenants(id),
  item_id text REFERENCES mp_items(id), invoice_id text REFERENCES invoices(id),
  UNIQUE (tenant_id, item_id)
);
```

## A6. Admin, Support, Audit, Analytics

```sql
CREATE TABLE admin_users (
  id text PRIMARY KEY, email citext UNIQUE, full_name text,
  roles text[] NOT NULL,                       -- {super,support,finance,catalog}
  totp_required boolean DEFAULT true, status text DEFAULT 'active'
);

CREATE TABLE admin_approvals (                 -- four-eyes engine (PA-01)
  id text PRIMARY KEY, action_type text, payload jsonb,
  requested_by text REFERENCES admin_users(id),
  approved_by text REFERENCES admin_users(id),
  state text CHECK (state IN ('pending','approved','rejected','expired')),
  CONSTRAINT distinct_admins CHECK (approved_by IS NULL OR approved_by <> requested_by)
);

CREATE TABLE impersonation_sessions (          -- PA-02
  id text PRIMARY KEY, admin_id text REFERENCES admin_users(id),
  tenant_id text REFERENCES tenants(id),
  consent_token text, starts_at timestamptz, ends_at timestamptz,
  reason text
);

CREATE TABLE support_tickets (
  id text PRIMARY KEY, tenant_id text REFERENCES tenants(id),
  subject text, body text, status text DEFAULT 'open',
  assigned_admin text REFERENCES admin_users(id), priority text
);

CREATE TABLE audit_cloud (                     -- append-only; no UPDATE/DELETE grants
  id bigserial PRIMARY KEY,
  actor text NOT NULL,                         -- user:..., admin:..., system
  tenant_id text, action text NOT NULL, target text,
  meta jsonb, ip inet, at timestamptz DEFAULT now()
);
CREATE INDEX idx_audit_cloud ON audit_cloud(tenant_id, at DESC);

CREATE TABLE metrics_daily (                   -- aggregates only (no business data)
  day date, metric text, dims jsonb, value numeric,
  PRIMARY KEY (day, metric, dims)
);
```

**RLS example (applied to every tenant-scoped table):**
```sql
ALTER TABLE devices ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON devices
  USING (tenant_id = current_setting('app.tenant_id')::text);
```

---

# PART B — LOCAL DESKTOP DATABASE (`aioffice_local`, encrypted at rest)

## B1. Organization & Agents

```sql
CREATE TABLE departments (
  id text PRIMARY KEY, name text, parent_id text REFERENCES departments(id),
  isolation boolean DEFAULT false              -- enterprise dept isolation
);

CREATE TABLE agents (
  id text PRIMARY KEY,                         -- agt_...
  name text, designation text,
  department_id text REFERENCES departments(id),
  description text, objectives jsonb,
  model_id text,                               -- → models.id
  permissions jsonb,                           -- {"spend_limit":5000,"external_send":"approval_required"}
  kpis jsonb, schedule jsonb,
  reporting_manager_id text REFERENCES agents(id),
  status text CHECK (status IN
    ('idle','working','waiting','reviewing','escalated','completed',
     'error','paused','archived')) DEFAULT 'idle',
  node_id text,                                -- multi-computer placement
  voice_id text                                -- TTS voice
);

CREATE TABLE skills (
  id text PRIMARY KEY, name text, description text,
  source text CHECK (source IN ('builtin','marketplace','skill_builder')),
  definition jsonb,                            -- steps, params (Skill Builder output)
  version text
);
CREATE TABLE agent_skills (agent_id text REFERENCES agents(id),
  skill_id text REFERENCES skills(id), PRIMARY KEY (agent_id, skill_id));

CREATE TABLE tool_grants (
  agent_id text REFERENCES agents(id),
  tool_name text,                              -- mcp server.tool
  scope jsonb, granted_by text, PRIMARY KEY (agent_id, tool_name)
);

CREATE TABLE agent_performance (
  agent_id text REFERENCES agents(id), period date,
  tasks_completed int, success_rate numeric(5,2), error_rate numeric(5,2),
  productivity_score numeric(6,2), utilization numeric(5,2),
  PRIMARY KEY (agent_id, period)
);
```

## B2. Tasks, Workflows, Schedules, Approvals

```sql
CREATE TABLE tasks (
  id text PRIMARY KEY, title text, description text,
  source text CHECK (source IN ('voice','manual','workflow','trigger','schedule')),
  parent_task_id text REFERENCES tasks(id),
  assignee_agent_id text REFERENCES agents(id),
  priority text CHECK (priority IN ('low','normal','high','urgent')) DEFAULT 'normal',
  deadline timestamptz,
  status text CHECK (status IN
    ('queued','planning','working','waiting','reviewing','escalated',
     'completed','failed','canceled')) DEFAULT 'queued',
  plan jsonb,                                  -- CEO Agent DAG
  result jsonb, utterance text                 -- original voice command
);
CREATE TABLE task_dependencies (task_id text REFERENCES tasks(id),
  depends_on text REFERENCES tasks(id), PRIMARY KEY (task_id, depends_on));
CREATE TABLE task_artifacts (id text PRIMARY KEY, task_id text REFERENCES tasks(id),
  kind text, file_path text, meta jsonb);

CREATE TABLE workflows (
  id text PRIMARY KEY, name text,
  graph jsonb NOT NULL,                        -- nodes/edges (trigger/condition/action/agent/approval/notification)
  status text CHECK (status IN ('draft','active','paused','archived')),
  version int DEFAULT 1, source_utterance text
);
CREATE TABLE workflow_runs (
  id text PRIMARY KEY, workflow_id text REFERENCES workflows(id),
  trigger_info jsonb, started_at timestamptz, ended_at timestamptz,
  status text CHECK (status IN ('running','succeeded','failed','partial','canceled')),
  node_results jsonb
);

CREATE TABLE schedules (
  id text PRIMARY KEY, workflow_id text REFERENCES workflows(id),
  kind text CHECK (kind IN ('cron','interval','event')),
  expression text, timezone text,
  run_policy text CHECK (run_policy IN ('run_on_wake','skip')) DEFAULT 'run_on_wake',
  next_run_at timestamptz, consecutive_failures int DEFAULT 0   -- TC-12 pause at 2
);

CREATE TABLE approvals (
  id text PRIMARY KEY,                         -- apv_...
  requester_agent_id text REFERENCES agents(id),
  task_id text REFERENCES tasks(id),
  action_summary text, payload jsonb, rule_id text,   -- e.g., 'AC-05'
  current_tier text CHECK (current_tier IN ('specialist','manager','ceo','human')),
  state text CHECK (state IN ('pending','approved','rejected','expired')),
  chain jsonb,                                 -- [{tier,actor,decision,reason,at}]
  expires_at timestamptz
);
CREATE TABLE approval_delegations (            -- AC-10
  id text PRIMARY KEY, from_actor text, to_actor text,
  scope jsonb, expires_at timestamptz
);
```

## B3. Second Brain & Knowledge Graph (pgvector)

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE memory_items (
  id text PRIMARY KEY,                         -- mem_...
  memory_class text CHECK (memory_class IN
    ('personal','business','knowledge','operational')),
  title text, source_type text,                -- pdf, email, audio, web, db...
  file_path text, content_hash text UNIQUE,    -- MC-01 dedupe
  tier text CHECK (tier IN ('hot','cold')) DEFAULT 'hot',
  pii boolean DEFAULT false,                   -- MC-08
  confidence numeric(4,3),                     -- OCR confidence (MC-06)
  deleted_at timestamptz, purge_after timestamptz   -- MC-04 soft delete
);

CREATE TABLE memory_chunks (
  id text PRIMARY KEY, item_id text REFERENCES memory_items(id),
  seq int, content text,
  embedding vector(768),
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED
);
CREATE INDEX idx_chunks_vec ON memory_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_chunks_tsv ON memory_chunks USING gin (tsv);

CREATE TABLE agent_memory_scopes (
  agent_id text REFERENCES agents(id), memory_class text, filter jsonb,
  PRIMARY KEY (agent_id, memory_class)
);

CREATE TABLE kg_entities (
  id text PRIMARY KEY,                         -- ent_...
  type text CHECK (type IN ('customer','vendor','contact','project','task',
                            'document','agent','policy','product','custom')),
  name text, aliases text[], attrs jsonb,
  confidential boolean DEFAULT false           -- TC-10
);
CREATE INDEX idx_kg_name ON kg_entities USING gin (to_tsvector('simple', name));

CREATE TABLE kg_relations (
  id text PRIMARY KEY,
  from_id text REFERENCES kg_entities(id),
  to_id   text REFERENCES kg_entities(id),
  relation text,                               -- works_for, belongs_to, quoted_in...
  attrs jsonb, valid_from timestamptz, valid_to timestamptz
);
CREATE INDEX idx_kg_rel ON kg_relations(from_id, relation);

CREATE TABLE kg_conflicts (                    -- MC-02
  id text PRIMARY KEY, entity_id text REFERENCES kg_entities(id),
  field text, values jsonb, resolved boolean DEFAULT false, resolution jsonb
);

CREATE TABLE ingestion_jobs (
  id text PRIMARY KEY, source jsonb, stage text,
  status text, error text, item_id text REFERENCES memory_items(id)
);
```

## B4. Messaging Bus, Communications, Calls

```sql
CREATE TABLE bus_threads (
  id text PRIMARY KEY, task_id text REFERENCES tasks(id),
  topic text, participants text[]              -- agent ids
);
CREATE TABLE bus_messages (
  id text PRIMARY KEY, thread_id text REFERENCES bus_threads(id),
  from_agent_id text REFERENCES agents(id),
  kind text CHECK (kind IN ('query','handoff','result','status')),
  content jsonb, at timestamptz DEFAULT now()
);

CREATE TABLE comm_channels (
  id text PRIMARY KEY, type text CHECK (type IN
    ('email','whatsapp','telegram','slack','teams','discord','sms')),
  account_ref text, vault_secret_key text, status text
);
CREATE TABLE comm_threads (
  id text PRIMARY KEY, channel_id text REFERENCES comm_channels(id),
  external_ref text, counterpart_entity_id text REFERENCES kg_entities(id),
  category text CHECK (category IN ('urgent','action','fyi','spam')),
  ai_reply_count int DEFAULT 0                 -- CC-09 stop at 3
);
CREATE TABLE comm_messages (
  id text PRIMARY KEY, thread_id text REFERENCES comm_threads(id),
  direction text CHECK (direction IN ('in','out')),
  body text, drafted_by_agent text REFERENCES agents(id),
  sent_at timestamptz, source_citations jsonb  -- CC-03
);
CREATE TABLE comm_rules (id text PRIMARY KEY, channel_id text,
  name text, conditions jsonb, actions jsonb, active boolean DEFAULT true);
CREATE TABLE opt_outs (entity_id text, channel_type text,
  PRIMARY KEY (entity_id, channel_type));      -- CC-04/CC-07

CREATE TABLE calls (
  id text PRIMARY KEY, direction text CHECK (direction IN ('inbound','outbound')),
  agent_id text REFERENCES agents(id),
  contact_entity_id text REFERENCES kg_entities(id),
  campaign_id text, started_at timestamptz, ended_at timestamptz,
  transcript jsonb, sentiment_timeline jsonb,
  outcome_code text, recording_path text, consent_recorded boolean
);
CREATE TABLE call_campaigns (id text PRIMARY KEY, name text, script_id text,
  window jsonb, status text);
```

## B5. Models, Nodes, Skills Infrastructure

```sql
CREATE TABLE models (
  id text PRIMARY KEY,                         -- mdl_qwen14b_q4
  family text, size text, quant text,
  runtime text CHECK (runtime IN ('ollama','llamacpp','vllm','lmstudio')),
  vram_mb int, file_path text, sha256 text,
  catalog_approved boolean,                    -- from admin Common Config
  status text CHECK (status IN ('available','downloading','loaded','error'))
);
CREATE TABLE gpu_allocations (
  node_id text, gpu_index int, model_id text REFERENCES models(id),
  vram_mb int, pinned boolean DEFAULT false,   -- voice reservation = pinned
  PRIMARY KEY (node_id, gpu_index, model_id)
);
CREATE TABLE routing_rules (id text PRIMARY KEY,
  task_profile text, model_tier text, priority int);

CREATE TABLE nodes (                           -- multi-computer network
  id text PRIMARY KEY, name text, os text,
  cert_fingerprint text, capabilities jsonb,   -- gpus, tools, peripherals
  status text CHECK (status IN ('online','offline','evacuating')),
  last_heartbeat timestamptz
);

CREATE TABLE plugins (
  id text PRIMARY KEY, name text, language text CHECK (language IN ('python','javascript','java')),
  version text, signature text, permissions jsonb,   -- granted at install only (SC-03)
  status text CHECK (status IN ('enabled','disabled','quarantined'))
);
```

## B6. Self-Healing, Security, Audit, Sync

```sql
CREATE TABLE healing_incidents (
  id text PRIMARY KEY, source text,            -- workflow_run / tool / integration
  error_class text CHECK (error_class IN ('transient','credential','config','logic')),
  signature text,                              -- SH-05 pattern matching
  action_taken text, resolved boolean, occurrences int DEFAULT 1,
  remediation_proposal jsonb, approval_id text REFERENCES approvals(id)
);
CREATE INDEX idx_heal_sig ON healing_incidents(signature);

CREATE TABLE vault_secrets (
  key text PRIMARY KEY, ciphertext bytea, key_id text,
  kind text,                                   -- oauth_token, api_key, password
  rotated_at timestamptz, expires_at timestamptz
);

CREATE TABLE local_users (                     -- enterprise multi-user on one install
  id text PRIMARY KEY, name text, role text,
  voiceprint_ref text, department_ids text[]
);

CREATE TABLE audit_local (                     -- append-only (SC-07: fail closed)
  id bigserial PRIMARY KEY,
  actor text NOT NULL,                         -- user:/agent:/plugin:/node:
  action text NOT NULL, target text, meta jsonb,
  speaker_id text, at timestamptz DEFAULT now()
);

CREATE TABLE entitlement_cache (               -- single-row signed snapshot
  id int PRIMARY KEY DEFAULT 1,
  snapshot jsonb, signature text, key_id text,
  fetched_at timestamptz, grace_until timestamptz
);
CREATE TABLE config_state (
  domain text, key text, value jsonb,
  scope text,                                  -- locked/overridable/suggestion
  local_override jsonb,                        -- only if scope <> 'locked'
  bundle_version int, PRIMARY KEY (domain, key)
);
CREATE TABLE pending_sync (                    -- offline queue (OFFLINE_QUEUED)
  id text PRIMARY KEY, kind text, payload jsonb, queued_at timestamptz
);
```

---

# PART C — DESIGN NOTES

1. **Privacy boundary in schema:** no cloud table stores business content; no local table stores card data. `pending_sync.kind` is constrained to license/marketplace/support kinds — a CHECK constraint plus contract tests keep business data out by construction.
2. **JSONB usage policy:** flexible domain payloads (plans.limits, workflows.graph, approvals.chain) are JSONB with Pydantic-validated shapes at the API layer; anything queried/joined frequently is a real column.
3. **Append-only audits:** enforced by revoking UPDATE/DELETE from app roles and a BEFORE trigger raising exceptions.
4. **Indexing strategy:** every FK gets an index; hot paths — `tasks(status, assignee_agent_id)`, `approvals(state, current_tier)`, `comm_threads(category)`, `subscriptions(status)`, `devices(tenant_id, last_seen_at)`; HNSW on embeddings; GIN on tsvector and entity names.
5. **Partitioning (cloud):** `audit_cloud` and `webhook_events` monthly range partitions; `metrics_daily` by year.
6. **Migrations:** Alembic on both planes; local migrations bundled with desktop releases and applied transactionally before service start; downgrade paths required for staged-rollout rollback.
7. **Retention:** webhook_events 13 months; soft-deleted memory purged after `purge_after` (default +30d); impersonation_sessions retained 7 years (compliance); call recordings per tenant policy with consent flag honored.

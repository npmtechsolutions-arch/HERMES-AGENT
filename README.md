# HERMUS — AI Office Assistant

> *"Hire AI Employees. Run Your Company 24×7 — By Voice."*

A working full-stack implementation of the **HERMUS / AI Office Assistant** product
specified in [`documents/`](documents/) — a **voice-first AI Workforce SaaS platform**
with a two-plane architecture:

- **Cloud Control Plane** — identity, plans, subscriptions, billing, devices,
  entitlements, common configuration, marketplace, releases, aggregate analytics.
- **Local Execution Plane** — the AI workforce: departments, agents, a CEO-Agent
  orchestrator, tasks, workflows, approval chains, a Second Brain (memory + knowledge
  graph), a communication hub, calls, and local-LLM management.

**Privacy invariant (SRS-INV-1):** in production the planes are separate databases and
business data never leaves the local machine. This demo runs both in one deployment for
convenience; every local row is tenant-scoped.

## Stack (as mandated by the PRD)

| Layer | Tech |
|---|---|
| Frontend | **React 18** + Vite + React Router |
| API | **Python FastAPI** (Cloud + Local Core API on `/api/v1`, WebSocket events on `/ws/v1`) |
| Database | **PostgreSQL 15** (isolated instance — see below) |
| Local LLM | **Ollama** — `qwen2.5` / `llama3.2` for reasoning, `nomic-embed-text` for embeddings |
| Auth | JWT (PBKDF2 password hashing, pure-Python — no native build deps) |

## Local LLM (real, on-device inference via Ollama)

HERMUS uses a **real local LLM** through [Ollama](https://ollama.com) — matching the
spec's local-first, privacy-preserving inference pillar (no inference leaves the machine).
It's used for:

- **CEO-Agent task decomposition** — the planner asks the model to break a goal into
  subtasks and assign each to the best employee on the roster (UC-04). Approval-rule
  evaluation stays deterministic/rule-based for auditability.
- **Second-Brain semantic search** — `nomic-embed-text` embeddings + cosine similarity
  (hybrid with keyword overlap). pgvector is the production store; here vectors live in a
  JSON column.
- **Comms draft replies** and **voice-queryable analytics answers**.

**Routing (LC-03/04/06):** reasoning → `llama3.2:3b` (fast), embeddings →
`nomic-embed-text`. Override via env: `HERMUS_MODEL_FAST`, `HERMUS_MODEL_SMART`,
`HERMUS_MODEL_EMBED`, `HERMUS_OLLAMA_URL`.

> **CPU-only note (LC-06):** on a machine without a GPU, on-device generation is slow
> (~60–90 s per plan here). The Task Planner therefore has a **toggle** — leave it on for
> real LLM reasoning, or turn it off for instant rule-based planning. If Ollama is not
> running, **everything still works** via deterministic fallbacks (you'll see a
> `rule-based` / `keyword` engine badge instead of `local-llm`). Models in use are shown
> live under **Settings → Compute**.

To use it, just have Ollama running with the models pulled:
```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
# optional, higher quality but slower: ollama pull qwen2.5:7b
```

## Demo logins

| Role | Email | Password |
|---|---|---|
| **Account Owner** (end user) | `user@gmail.com` | `user` |
| **Product Admin** (platform operator) | `admin@gmail.com` | `admin` |

The owner account is seeded as **"CA Mehul" / Mehul & Associates** (a chartered-accountant
office persona) on the **Pro** plan, with a full AI org: a CEO Agent (Aria) plus
Accountant, GST Specialist, Auditor, Social Media Manager and Support agents; sample tasks
(one with a live ₹75,000 approval gate), a monthly-GST workflow, Second-Brain memory, a
knowledge graph, an inbox, a call, and the cloud catalogs (plans, marketplace, releases,
common config).

## Run it

Two ways to run HERMUS:

**Web (cloud portal + admin):**
```bash
./start.sh
```

**Desktop app (the local execution plane — what end users install):**
```bash
./run-desktop.sh     # launches the Electron app (see desktop/README.md)
```
The desktop app boots its own local PostgreSQL + FastAPI core, runs a first‑run
**setup wizard** (detects Ollama, downloads local models), and runs the whole product
locally with voice + text. Global push‑to‑talk: `Cmd/Ctrl + Shift + Space`.

### Web details

This script (idempotently):
1. Initializes & starts an **isolated PostgreSQL** cluster in `backend/.pgdata` on port
   **5544** — it does **not** touch any existing PostgreSQL on your machine.
2. Creates a Python venv and installs backend deps.
3. Seeds the database (safe to re-run).
4. Starts FastAPI on `http://127.0.0.1:7700`.
5. Starts the React app on `http://localhost:5173`.

Then open **http://localhost:5173** and sign in.

To stop everything: `./stop.sh`

### Run pieces manually

```bash
# Database (isolated, port 5544)
export PATH="/usr/local/opt/postgresql@15/bin:$PATH"
pg_ctl -D backend/.pgdata -o "-p 5544 -k $PWD/backend/.pgdata" start

# Backend
cd backend && python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m app.seed                       # seed once
uvicorn app.main:app --port 7700         # API + docs at /docs

# Frontend
cd frontend && npm install && npm run dev
```

## What's implemented (mapped to the spec)

### Account-owner app (voice-first)
- **Voice Orb** (Web Speech API + keyboard fallback — no voice-only dead ends): the 7
  voice states, push-to-talk, intent parsing → navigation & actions.
- **Digital Employee Org Chart** with live status rings + WebSocket updates; **Hire
  Wizard** (UC-02) with plan-limit enforcement (SB-02 / `PLAN_LIMIT_EXCEEDED`).
- **Task Board** with the **CEO-Agent planner** (UC-03/04): decomposes an utterance into a
  DAG, assigns agents (TC-04), detects amounts/deadlines, and evaluates **approval rules**.
- **Approval Chains** (AC-01..12): Specialist → Manager → CEO Agent → Human, with the
  ₹5k/₹25k/₹50k default tiers, destructive-op & new-contact gates, decision trails.
- **Agent Messaging Bus** (FR-O6): threaded agent-to-agent messages visible per task.
- **Workflows**: **voice-to-workflow** compilation (FR-W2) to a typed node graph
  (trigger/condition/action/agent/approval/notification), dry-run, activate.
- **Second Brain**: typed memory (personal/business/knowledge/operational), ingestion with
  dedupe (MC-01) and PII tagging (MC-08), hybrid search with citations, soft-delete (MC-04).
- **Knowledge Graph**: entity/relationship visualization (FR-M4).
- **Communication Hub**: unified inbox with AI triage categories + draft/send with CC-09 cap.
- **Analytics** incl. voice-queryable answers (FR-A2).
- **Subscription/Billing** (usage vs limits, plan switch with GST invoice), **Devices**,
  **Marketplace**, **Settings**.

### Product-admin console
- Aggregate **analytics** (MRR/ARR, revenue, plan mix — no business data).
- **Tenants** lifecycle (approve/suspend/reactivate), **Plans & feature flags** editor
  (no code deploy), **Common Configuration Studio** (locked/overridable/suggestion scopes),
  **Releases** (staged rollout %), **Marketplace** review/sign/takedown, **Audit Log**.

### Cross-cutting
- WebSocket event hub (`agent.status`, `task.status_changed`, `approval.requested/decided`).
- Append-only **audit log** on every mutating action, across both planes.
- Role-scoped admin (super/support/finance/catalog).

## Simulated vs. real

This is a faithful **product build**, not the shipping desktop binary.

**Real:** the data model, all APIs, approval-chain logic, plan-limit enforcement, the
org/task/workflow/approval lifecycles, admin operations — and **local LLM inference via
Ollama** (CEO-Agent decomposition, semantic memory embeddings, comms drafts, analytics
answers), with deterministic fallbacks when Ollama is offline.

**Simulated** so the whole system runs as one web app: on-device **STT/TTS** (the browser's
Web Speech API stands in), **payment gateways** (checkout instantly issues an invoice),
**signed entitlement/config bundles**, **OCR/AV ingestion**, the **Electron desktop shell**,
and **pgvector** (embeddings are stored in a JSON column and scored in Python; pgvector is
the production path).

## Layout

```
backend/   FastAPI app (app/models.py, app/ceo_agent.py, app/routers/*, app/seed.py)
frontend/  React app  (src/pages/* owner app, src/admin/* admin console, src/components/*)
documents/ the 12 source specification documents
start.sh / stop.sh
```

See [`documents/`](documents/) for the full PRD, architecture, API spec, table design,
use cases, conditional rules, personas, and screen navigation.

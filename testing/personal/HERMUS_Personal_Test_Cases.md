# HERMUS PERSONAL — TEST CASE DOCUMENT
**Version 1.0 · Feature-wise manual test plan, from first install to every feature**
**Scope:** the HERMUS Personal product (the horizontal personal-assistant edition). Grounded in the shipped build (React + FastAPI + PostgreSQL + Ollama) and Doc 21 (Personal Product Spec).

---

## 0. HOW TO USE THIS DOCUMENT

Each test case has an **ID**, **Pre-conditions**, **Steps**, **Expected result**, and a **Priority**. Fill the **Result** (Pass/Fail) and **Notes** columns as you test.

- **Priority:** **P0** = blocker (must pass to ship) · **P1** = important · **P2** = nice-to-have.
- **Result:** ✅ Pass · ❌ Fail · ⚠️ Partial · ⏭️ Skipped.
- **"Demo data"** = the screen ships with sample/seed data for evaluation; real persistence happens once the user creates their own. Where a feature is **demo/placeholder**, it is flagged so you test the *interaction*, not real-world side-effects.

### 0.1 Test environments

| Env | Frontend | Backend | When to use |
|---|---|---|---|
| **Local dev** | http://localhost:5173 | http://127.0.0.1:7700 | Fast feature testing (latest code) |
| **Desktop app** | bundled UI | hosted (onrender) | The real user journey (install → use) |
| **Hosted web** | https://hermes-agent-1-xp6c.onrender.com | https://hermes-agent-hw8v.onrender.com | What testers see in the browser |

### 0.2 Test accounts (seeded)

| Role | Email | Password |
|---|---|---|
| Account owner (user) | `user@gmail.com` | `user` |
| Test users | `test1@gmail.com` / `test2@…` / `test3@…` | `test1` / `test2` / `test3` |
| Product admin | `admin@gmail.com` | `admin` |

### 0.3 Pre-flight (before any desktop test)
- A clean machine ideally has **no Ollama** and **no `~/.ollama` models** (so the first-run install flow can be tested). To reset a Mac: quit Ollama, `brew uninstall ollama` (or delete `/Applications/Ollama.app`), `rm -rf ~/.ollama`, and remove `~/Library/Application Support/HERMUS`.

---

## 1. INSTALLATION & FIRST LAUNCH (Desktop)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-INST-01 | Download the installer | On the Devices page (web) or release page | Open `/#/devices` → click your OS (Windows .exe / macOS .dmg / Linux .AppImage/.deb) | The correct installer downloads (HTTP 200); filename matches OS | P0 | | |
| PA-INST-02 | macOS — open the DMG | macOS, `.dmg` downloaded | Double-click the `.dmg` → drag **HERMUS** to **Applications** | App copies to /Applications without error | P0 | | |
| PA-INST-03 | macOS — Gatekeeper (unsigned) | App in /Applications, first launch | Double-click HERMUS → "Apple could not verify" appears → click **Done** → System Settings → Privacy & Security → **Open Anyway** → Open | App launches after Open Anyway; dialog does not reappear on later launches | P0 | | |
| PA-INST-04 | Windows — install | Windows, `HERMUS-Setup-x.y.z.exe` | Run the installer → "More info → Run anyway" on SmartScreen → choose folder → Install | Installs; Start-menu + desktop shortcut created; app launches | P0 | | |
| PA-INST-05 | Linux — AppImage | Linux | `chmod +x HERMUS-*.AppImage` → run it | App launches | P1 | | |
| PA-INST-06 | Linux — .deb | Debian/Ubuntu | `sudo apt install ./hermus-desktop_*_amd64.deb` → launch from menu | Installs and launches | P1 | | |
| PA-INST-07 | Splash / boot | App launching | Observe the splash window | Splash shows, then the app window opens (no crash, no blank screen) | P0 | | |
| PA-INST-08 | Single instance | App already open | Launch HERMUS again | The existing window is focused; no second instance, no port-collision crash | P1 | | |
| PA-INST-09 | No local Postgres needed | Fresh machine (online client) | Launch and reach login | App opens without requiring a local Postgres/backend (it's an online client) | P0 | | |

---

## 2. FIRST-RUN SETUP (Login → install packages → workspace)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-SET-01 | Login screen | App open, signed out | Observe the login screen | HERMUS branding, Account-Owner/Admin tabs, demo creds shown | P0 | | |
| PA-SET-02 | Sign in | At login | Enter `user@gmail.com` / `user` → Sign in | Authenticates against the hosted backend; proceeds to first-run / dashboard | P0 | | |
| PA-SET-03 | Continue without signing in | At login | Click **Continue without signing in →** | Enters the app as the demo account (works online, or offline demo data if backend unreachable) | P1 | | |
| PA-SET-04 | First-run install screen | First sign-in on this device (desktop) | After login, the **Welcome / install** screen appears | Overview carousel + a one-click **Install everything** (runtime + required models) with progress bar, live log, and install paths | P0 | | |
| PA-SET-05 | Install Ollama runtime | Ollama NOT installed | Click **Install everything** → watch the "Local AI runtime" step | Ollama installs (or is detected if already running); step turns green; live log shows progress | P0 | | |
| PA-SET-06 | Install required models | Ollama running | Continue the install | `llama3.2:3b` and `nomic-embed-text` download with per-item % (skipped instantly if already present) | P0 | | |
| PA-SET-07 | Skip install | At the install screen | Click **Skip for now** | Lands on the dashboard; models can be installed later from Runtime & Models | P1 | | |
| PA-SET-08 | Models already present | Models pre-installed | Run install | Each present model is marked "already installed" instantly (no re-download) | P1 | | |
| PA-SET-09 | Install failure handling | Disconnect network mid-install | Start install with no network | Step fails gracefully with a clear message + Retry/Skip; app does not crash | P1 | | |

---

## 3. PRODUCT & PLAN — what the user gets (Entitlements)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-PROD-01 | Lands on HERMUS Personal | Signed in (default edition) | Reach the dashboard | Sidebar brand reads **"HERMUS Personal"**; the simplified shell is shown | P0 | | |
| PA-PROD-02 | Products page | Signed in | Open **Products** (sidebar) | Card list of published products (Personal active; Doctors, Accountants, Realtors, Lawyers, Therapists, Seniors & Family) with tagline, modules, plans | P0 | | |
| PA-PROD-03 | Choose a plan tier | On Products | On **HERMUS Personal**, click the **Pro** plan tile → confirm | Activates Personal on Pro; toast confirms; panel re-gates to Pro modules | P0 | | |
| PA-PROD-04 | Free tier limits the panel | On Products | Click the **Free** plan tile on a product → confirm | Left panel shrinks to core items only (functional/pro modules hidden) | P0 | | |
| PA-PROD-05 | Switch product cleanly | Personal active | Activate **HERMUS for Doctors** → then re-activate **Personal** | Roster/skin switch cleanly each time; agent count does NOT keep growing (clean teardown) | P0 | | |
| PA-PROD-06 | Brand + industry skin follow product | After activating a profession pack | Observe sidebar + pipeline labels | Brand changes (e.g., "HERMUS · Doctor"); pipeline group relabels (e.g., Patient Inquiries / Appointments) | P1 | | |

---

## 4. THE PERSONAL SHELL (Navigation — Doc 21 Part 4)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-NAV-01 | Simplified 7-screen shell | On HERMUS Personal | Look at the left rail | Shows **Your Assistant**: Home · Voice Type · Tasks · Messages · Memory · My Agents · Activity · Settings + a slim **Account** group (Products, Plans, Subscription, Devices, Runtime & Models, System Health) | P0 | | |
| PA-NAV-02 | No business clutter | On HERMUS Personal | Confirm what's hidden | Business screens (Org Chart, Recipes, Pipelines, Workflows, Compliance, Gateway, Marketplace, Vertical Agents, Solutions) are NOT shown | P0 | | |
| PA-NAV-03 | Every link navigates | On Personal | Click each left-rail item in turn | Each opens its screen without error (no blank page / 404) | P0 | | |
| PA-NAV-04 | Simple/Advanced toggle | Any screen | Toggle Simple ↔ Advanced (top bar) | Simple = plain language; Advanced reveals more detail (same screens) | P1 | | |
| PA-NAV-05 | Deep-link / refresh | On any screen | Refresh the page (or open `/#/tasks` directly) | The screen reloads correctly (HashRouter; no 404) | P1 | | |
| PA-NAV-06 | Topbar tour button | Any screen | Click the ✨ tour button | The product spotlight tour starts | P2 | | |

---

## 5. HOME DASHBOARD (Doc 21 Part 13)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-HOME-01 | Greeting + briefing | On Home (Personal) | Observe the header | Time-aware greeting ("Good morning, …") + **Play your briefing** button (if a briefing exists) | P0 | | |
| PA-HOME-02 | Needs-you bucket | On Home | Observe **Needs you** | Lists items awaiting you (pending approvals + tasks needing input); shows "all caught up ✅" when empty | P0 | | |
| PA-HOME-03 | In-progress / Done today | On Home | Observe the two columns | Tasks bucketed by status; counts correct | P1 | | |
| PA-HOME-04 | Your agents | On Home | Observe the agents row | Shows the 5-agent team (Aria, Ravi=Scheduler, Maya=Inbox, Arjun=Scribe, Geeta=Finder) with live status pills | P0 | | |
| PA-HOME-05 | This week (ROI) | On Home | Observe the ROI band | "N tasks done · ~H hours saved" with the value note; **Details** link works | P1 | | |
| PA-HOME-06 | Play briefing (TTS) | Briefing present | Click **Play your briefing** | The briefing is read aloud (browser TTS) | P2 | | |
| PA-HOME-07 | Live status updates | A task changes state | Trigger a task elsewhere | Home buckets update (WebSocket: `task.status_changed`, `agent.status`) | P2 | | |

---

## 6. THE AGENT TEAM (Doc 21 Part 6)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-AGT-01 | Default team provisioned | Personal activated | Open **My Agents** (Agent Team) | The 5 agents exist: **Aria** (Chief of Staff/CEO) + Scheduler, Inbox, Scribe, Finder | P0 | | |
| PA-AGT-02 | Agent status & "doing now" | On My Agents | Inspect each agent card | Each shows status (Idle/Working/Waiting) and its role | P1 | | |
| PA-AGT-03 | Auto-assignment | On the assistant chat / orb | Say/type a goal: "Remind me to pay the electricity bill every month and email me the receipt" | The CEO-Agent decomposes into steps and assigns Scheduler + Inbox automatically (plan read back) | P1 | | |
| PA-AGT-04 | Direct address (optional) | On orb/chat | "Ask Scribe to summarize this" (with a doc) | The named agent handles it; direct address works but isn't required | P2 | | |
| PA-AGT-05 | Per-agent summary | On My Agents | Open an agent | A "this week" summary appears (e.g., reminders set / emails drafted) — *demo data acceptable* | P2 | | |
| PA-AGT-06 | Create an agent (preset) | Free/Personal | Use the hire/create flow | A new agent can be created from presets (full Skill Builder is Pro — see PA-PLAN-04) | P2 | | |

---

## 7. VOICE CONTROL (Doc 21 Part 9)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-VOICE-01 | Voice orb present | Any screen, Chrome/Edge | Observe bottom-right | The Voice Orb is always visible | P0 | | |
| PA-VOICE-02 | Speak a command | Orb visible, mic permission granted | Click the orb → say "show urgent messages" | Live transcript chip appears; the command routes (navigates/acts) | P1 | | |
| PA-VOICE-03 | Type instead of speak | Orb open | Type a command in the orb input | Same result as voice (no voice-only dead-ends) | P1 | | |
| PA-VOICE-04 | Per-page voice actions | On a page with voice (e.g., Tasks, Approvals) | Use the page's "Say or type…" bar (e.g., "approve everything") | The page-specific action runs | P1 | | |
| PA-VOICE-05 | Spoken reply (TTS) | After a query | Ask something that returns an answer | The reply can be read aloud | P2 | | |
| PA-VOICE-06 | Browser support fallback | Non-Chromium browser | Open the orb | Graceful "voice needs Chrome/Edge" rather than a crash | P2 | | |

---

## 8. CAPTURE — incl. Voice Type / Dictation (Doc 21 Part 2.1, Part 12)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-CAP-01 | Voice Type screen | On Personal | Open **Voice Type** | Big mic, mode chips (Clean up / Make formal / Bullet notes / Punctuation only), editor, On-device·Private pill | P0 | | |
| PA-CAP-02 | Dictate text | Chrome/Edge, mic allowed | Tap mic → speak a few sentences | Live transcript fills the editor (on-device STT) | P0 | | |
| PA-CAP-03 | Spoken punctuation | Dictating | Say "new line", "comma", "period", "question mark" | Punctuation/formatting applied | P1 | | |
| PA-CAP-04 | Polish (local LLM) | Models installed (Ollama up) | Type/dictate raw text → **Polish** | Cleaned, punctuated text; engine shows "local-llm (…)" | P1 | | |
| PA-CAP-05 | Polish (no LLM) | Ollama not running | Polish raw text | Falls back to on-device punctuation rules (fillers stripped, capitalized); message says "rule-based" | P1 | | |
| PA-CAP-06 | Copy | Text present | Click **Copy** | Text copied to clipboard (toast confirms) | P1 | | |
| PA-CAP-07 | Save to Second Brain | Text present | Click **Save to Second Brain** | Saved as a personal memory (verify it appears in Memory) | P1 | | |
| PA-CAP-08 | Document ingestion | On Memory | Drop a PDF/image into Memory | File is ingested, understood, and searchable | P1 | | |
| PA-CAP-09 | Quick capture (🆕) | — | "remember this …" via orb | Captured + filed — *if not yet wired, mark as known-gap (Doc 21 net-new)* | P2 | | |

---

## 9. MEMORY — Second Brain (Doc 21 Part 2.2)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-MEM-01 | Memory screen loads | On Personal | Open **Memory** | Search box + memory list (demo "starter brain" may be offered) | P0 | | |
| PA-MEM-02 | Remember something | On Memory | Use "remember" with a title + body | New memory stored; appears in the list | P0 | | |
| PA-MEM-03 | Search by voice/text | Memories exist | Search "what was that restaurant?" style query | Relevant memory returned | P1 | | |
| PA-MEM-04 | PII tagging | Save text containing an email/phone | Save it | Memory is flagged PII / restricted | P1 | | |
| PA-MEM-05 | Forget → restore | A memory exists | Forget it → then restore (30-day window) | Soft-delete then restore works (MC-04) | P1 | | |
| PA-MEM-06 | Knowledge Graph link | Memory referencing a contact | Save it | Entity appears/links in the graph (light KG) | P2 | | |
| PA-MEM-07 | Edit / export | Memory exists | Edit or export | User-controlled memory works | P2 | | |

---

## 10. TIME — Tasks, Reminders, Plan-my-day (Doc 21 Part 2.3)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-TIME-01 | Tasks screen | On Personal | Open **Tasks** | Task board with columns/states; per-task detail available | P0 | | |
| PA-TIME-02 | Create a task | On Tasks | Quick-create / voice "create a task to call the bank" | Task created with status; appears on the board and Home | P0 | | |
| PA-TIME-03 | Execute a task | A task exists | Execute it | Status transitions (queued → running → done); result captured | P1 | | |
| PA-TIME-04 | Per-task detail + Why | A task ran | Open task detail | Step timeline with the responsible agent; "Why?" affordance | P1 | | |
| PA-TIME-05 | Set a reminder | — | "remind me to pay the gas bill on the 5th" | Reminder/scheduled task created — *if reminder UI is via Tasks/Scheduler, verify it lands there* | P1 | | |
| PA-TIME-06 | Cancel a task | A task exists | Cancel it | Moves to Canceled; no side-effects | P2 | | |
| PA-TIME-07 | Plan my day | — | "plan my day" | A prioritized plan/briefing is produced (Scheduler + Inbox + Scribe pipeline) | P2 | | |

---

## 11. COMMUNICATION — Messages (Doc 21 Part 2.4)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-COMM-01 | Messages screen | On Personal | Open **Messages** | Unified inbox; demo inbox can be loaded for evaluation | P0 | | |
| PA-COMM-02 | Triage | Demo inbox loaded | Observe categorization | Threads sorted urgent/action/FYI with counts | P1 | | |
| PA-COMM-03 | Draft a reply | A thread open | "draft a reply to Ravi" | A draft is generated for review (review-before-send) | P1 | | |
| PA-COMM-04 | Send (review-before-send) | A draft exists | Approve & send | Send only after review; reflected in the thread | P1 | | |
| PA-COMM-05 | Re-triage | Inbox loaded | Re-triage | Re-categorizes threads | P2 | | |
| PA-COMM-06 | Remote command (🆕) | — | Command from WhatsApp/Telegram | *Net-new per Doc 21 — mark known-gap if not present* | P2 | | |

---

## 12. DOCUMENTS (Doc 21 Part 2.5)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-DOC-01 | Summarize a document | A PDF in Memory | "summarize this PDF" / via Scribe | A plain-language summary is produced | P1 | | |
| PA-DOC-02 | Generate from template | — | "draft a letter to my landlord" | A document is generated (Document Factory, light) | P1 | | |
| PA-DOC-03 | Polish rough text | Voice Type | Polish raw text (see PA-CAP-04) | Clean output | P1 | | |
| PA-DOC-04 | Output stored locally | A document generated | Locate the output | Output is retrievable (local store on the user's machine in desktop) | P1 | | |

---

## 13. WORK-WHILE-YOU-DON'T & ROI (Doc 21 Part 2.6, 7.3)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-AUTO-01 | Scheduled/autonomous task | — | Create a recurring task/reminder | Runs on schedule (24×7 scheduler) | P1 | | |
| PA-AUTO-02 | Retry on failure | Force a failure (e.g., bad input) | Observe Activity | Transient → auto-retry (≤3×); credential → asks once; ambiguous → asks one question; hard → "needs you" (never silent) | P1 | | |
| PA-AUTO-03 | Weekly ROI note | — | Home "This week" band / Analytics | ROI note ("hours saved") present | P2 | | |

---

## 14. ACTIVITY — Glass-Box (Doc 21 Part 7.1)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-ACT-01 | Activity feed | Did some actions | Open **Activity** | Plain-language feed (e.g., "Saved to your memory · …", "Switched product") with timestamps ("2m ago") | P0 | | |
| PA-ACT-02 | Reflects recent actions | Just saved a memory / activated a product | Refresh Activity | The action appears at the top | P1 | | |
| PA-ACT-03 | Empty state | Brand-new tenant | Open Activity | Friendly "nothing yet" message | P2 | | |

---

## 15. TRUST LAYER (Doc 21 Part 2.7, Part 12)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-TRUST-01 | Approval gate (money/new contact) | — | Trigger an action touching money/a new contact | An approval is required before it proceeds; appears in Needs-you / Approvals | P0 | | |
| PA-TRUST-02 | Approve / reject | A pending approval | Approve (or reject with reason) | Decision recorded; action proceeds/halts accordingly | P1 | | |
| PA-TRUST-03 | Backup & restore | On Backup screen | Set a recovery phrase → run backup → verify | Backup completes; verify-integrity passes; history shows it | P0 | | |
| PA-TRUST-04 | Restore drill | A backup exists | Restore | Data restores from the backup/recovery phrase | P1 | | |
| PA-TRUST-05 | "Why did you do that?" | A completed action | Use the Why affordance | Plain-language explanation shown (audit-backed) | P1 | | |
| PA-TRUST-06 | Honest-AI | Ask "are you a person?" | Ask via orb | It discloses it is an AI (locked rule PP-R2) | P1 | | |
| PA-TRUST-07 | Local-first privacy | Desktop | Inspect Settings/System Health | Data/inference local; "On-device · Private" messaging accurate | P1 | | |
| PA-TRUST-08 | 60-sec undo (🆕) | A send/action | Within 60s | Undo window — *mark known-gap if not yet surfaced* | P2 | | |

---

## 16. RUNTIME, MODELS & SYSTEM HEALTH (Desktop)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-RT-01 | Runtime & Models screen | Desktop | Open **Runtime & Models** | Shows Ollama status + the Hermes-agent models (installed/now) | P0 | | |
| PA-RT-02 | Install a model | Ollama up, model absent | Click Install on `qwen2.5:7b` | Pulls with live progress; marks installed | P1 | | |
| PA-RT-03 | Remove a model | A model installed | Click **Remove** | Model removed via the runtime API (works even if the CLI isn't on PATH); list refreshes | P0 | | |
| PA-RT-04 | Uninstall runtime | Ollama installed | Click **Uninstall runtime** → confirm | Ollama stops + uninstalls; status verified "not running" | P1 | | |
| PA-RT-05 | System Health | Desktop | Open **System Health** | Services (Core, Ollama + model count, Postgres) + machine meters (CPU/RAM/disk) + diagnostics | P1 | | |
| PA-RT-06 | Web fallback | In a browser (not desktop) | Open System Health | Service status shown; hardware section says "available in desktop app" | P2 | | |

---

## 17. SETTINGS (Doc 21 Part 4.2 screen 7)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-CFG-01 | Settings screen | On Personal | Open **Settings** | Hermes agent config (models, gen params, behaviour, voice, safety) | P1 | | |
| PA-CFG-02 | Change a setting | On Settings | Edit a value (e.g., tone) → save | Saves to the tenant config; success message | P1 | | |
| PA-CFG-03 | Voice-editable | On Settings | Use the voice bar to change a setting | Setting updates by voice | P2 | | |
| PA-CFG-04 | Test panel | On Settings | Run the test | Produces a sample output reflecting the config | P2 | | |

---

## 18. PLAN GATING & UPGRADE (Free vs Pro)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-PLAN-01 | Free shows minimal panel | Activate Personal on **Free** | Inspect the rail | Only core items (Home, Memory, My Agents, etc.); functional items hidden | P0 | | |
| PA-PLAN-02 | Pro unlocks more | Activate on **Pro** | Inspect the rail | More items appear (Voice Type, Tasks, Messages, etc.) | P0 | | |
| PA-PLAN-03 | Tier persists | After choosing a tier | Reload | The same tier/panel after reload | P1 | | |
| PA-PLAN-04 | Skill Builder is Pro-only | Free vs Pro | Look for advanced skill-building | Available on Pro, not Free (upsell) | P2 | | |
| PA-PLAN-05 | Pricing calculator | On **Plans & Pricing** | Pick products + plan + add-ons + BYOK + region + annual | Live price via the Master Formula (declining combos, BYOK −%, annual) | P1 | | |

---

## 19. ADMIN CONTROL OF THE PRODUCT (the levers)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-ADM-01 | Admin login | — | Sign in as `admin@gmail.com` / `admin` | Admin console loads | P0 | | |
| PA-ADM-02 | Editions builder | Admin | Open **Editions** → edit HERMUS Personal | Can toggle modules/engines, edit skin/price book, publish/unpublish | P0 | | |
| PA-ADM-03 | Toggle a module → user sees it change | Admin + a user session | In Editions, remove a module (e.g., M36 Voice Type) from Personal → save; reload the user | "Voice Type" disappears from the user's rail | P0 | | |
| PA-ADM-04 | Plan Gating | Admin | Open **Plan Gating** → change a group's min tier or a global kill-switch | A user's panel on the affected tier reflects it | P1 | | |
| PA-ADM-05 | Pricing rate card | Admin | Open **Pricing** → change a rate → save | The user's Plans & Pricing quote changes | P1 | | |
| PA-ADM-06 | Publish/unpublish | Admin | Unpublish a product | It disappears from the user's Products page | P1 | | |

---

## 20. UNINSTALL & UPGRADE (Desktop)

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-UNI-01 | In-app "Uninstall HERMUS" | Desktop, on Runtime & Models | Use the Danger-zone **Uninstall HERMUS** (optionally "also remove runtime & models") | Removes local data (+ optionally Ollama/models); macOS trashes the app / Windows opens the uninstaller / Linux shows the final step | P1 | | |
| PA-UNI-02 | Windows uninstaller | Windows | Settings → Apps → HERMUS → Uninstall | Clean removal via NSIS uninstaller | P1 | | |
| PA-UNI-03 | Upgrade in place | New build available | Install the new version over the old | Replaces in place; data/login preserved | P1 | | |

---

## 21. RESILIENCE & EDGE CASES

| ID | Title | Pre-conditions | Steps | Expected result | Pri | Result | Notes |
|---|---|---|---|---|---|---|---|
| PA-EDGE-01 | Backend unreachable (desktop) | Hosted backend down/offline | Launch + sign in | Falls back to offline **demo mode**; a "Demo mode — backend offline" banner shows; app remains navigable | P1 | | |
| PA-EDGE-02 | Cloud entitlements cached | Briefly offline | Use the app | Works locally with cached entitlements/grace | P2 | | |
| PA-EDGE-03 | Wrong credentials | At login | Enter a bad password | Clear "invalid email or password" error; no crash | P1 | | |
| PA-EDGE-04 | New account signup | At login (if exposed) | Sign up a new account | Creates a tenant + lands on Personal (signup FK bug fixed) | P1 | | |
| PA-EDGE-05 | Plan limits graceful | At a limit | Exceed a limit | Graceful handling (archive, never silent data loss) | P2 | | |
| PA-EDGE-06 | Reload mid-session | Any screen | Refresh | Session preserved; lands back correctly | P1 | | |

---

## 22. KNOWN GAPS (Doc 21 net-new — test as "expected not-yet-present")

These are spec'd in Doc 21 but **not yet implemented**; mark them as known-gaps, not failures:
- **Quick capture** ("remember this" one-shot) and **forward-to-assistant**.
- **Life-admin autopilot** — bills/renewals/subscriptions tracked & chased automatically.
- **Proactive layer** — anticipation, pattern-spotting, gentle nudges, notification intelligence.
- **Remote command channels** (WhatsApp/Telegram).
- **60-second undo** surface and inline **"Why?"** on every action (audit exists; surfacing is partial).
- **System-wide dictation overlay** (in-app Voice Type ships; OS overlay is later).

---

## 23. TRACEABILITY TO DOC 21

| Doc 21 area | Test section |
|---|---|
| Part 2 Features / Part 12 Enhanced | §8–§15 |
| Part 3 Modules | §3, §18, §19 |
| Part 4 UI alignment | §4, §5 |
| Part 5 Working environment | §5 (Home) |
| Part 6 How agents work | §6, §7 |
| Part 7 Track/retry/summary/output/storage | §10, §13, §14 |
| Part 8 User-created agents | PA-AGT-06, PA-PLAN-04 |
| Part 9 Voice per agent | §7 |
| Part 11 Admin enablement | §19 |
| Part 13 Dashboard | §5 |
| Part 14 Q→A / extra cases | §21 |

---

## 24. SIGN-OFF

| Area | Owner | P0 pass? | Notes |
|---|---|---|---|
| Install & first run (§1–§2) | | | |
| Product/plan/shell (§3–§4) | | | |
| Core features (§5–§15) | | | |
| Desktop ops (§16, §20) | | | |
| Admin control (§19) | | | |
| Resilience (§21) | | | |

**Ship gate:** all **P0** cases Pass; no open **P0/P1** defects in install, login, product activation, plan gating, backup, or admin module-control.

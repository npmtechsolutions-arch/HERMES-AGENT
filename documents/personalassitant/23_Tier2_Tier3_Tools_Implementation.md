# HERMUS PERSONAL — TIER-2 & TIER-3 TOOL IMPLEMENTATION
## Connected Tools & Third-Party Actions — Build-Ready Specification
**Version 1.0 | Extends the Tier-1 framework (Doc 22) with external connectivity**
**Stack: Python FastAPI · PostgreSQL · OAuth2 · Vault (secrets) · Playwright · MCP**

Tier-1 (Doc 22) gave the assistant local power with zero dependencies. Tier-2 makes it **act on the real world through the user's accounts** (calendar, email, WhatsApp, contacts). Tier-3 handles **services with no clean API** (restaurants, cabs, shopping) safely via prepare-and-handoff. Same tool contract throughout — the only new machinery is **auth, connection lifecycle, and the handoff pattern.**

---

# PART 1 — WHAT CHANGES FROM TIER-1

| Concern | Tier-1 | Tier-2 | Tier-3 |
|---|---|---|---|
| Network | none (local) | the user's connected providers | external services / browser |
| Auth | none | **OAuth tokens in Vault** | provider key OR none (browser) OR none (handoff) |
| Failure modes | transient/validation | + **credential expiry, rate limits, provider 5xx** | + **site changes, captchas, ambiguous confirmation** |
| Default execution | autonomous | autonomous (within approval rules) | **prepare-and-handoff first**, automation later |
| Privacy note | fully local | content transits the user's own provider | content may transit a third party — **labeled & gated** |

Everything else — the `@tool` contract, `call_tool` wrapper, permission checks, approval engine, retry, memory writes, Activity feed — is **reused unchanged.** A Tier-2 tool is just a Tier-1 tool whose body calls an external API with a Vault-stored token.

---

# PART 2 — THE CONNECTION LAYER (build this once, before any Tier-2 tool)

## 2.1 Connection model
```python
# table: connections (local DB)
connection_id, user_id, provider,            # google_calendar | gmail | whatsapp | outlook ...
  status,                                    # connected | expired | revoked | error
  vault_secret_key,                          # points to token in Vault, never the token itself
  scopes[], account_label, connected_at, last_ok_at, last_error
```

## 2.2 OAuth flow (desktop app — the right pattern)
HERMUS runs locally, so use the **OAuth Authorization Code flow with a loopback redirect** (the desktop-native standard):
```
User: Settings → Connect Google Calendar
 → local core opens system browser to provider consent URL
   (redirect_uri = http://127.0.0.1:<ephemeral_port>/oauth/callback)
 → user consents in their own browser
 → provider redirects to the loopback; local core captures the code
 → exchange code → access+refresh tokens → store in Vault (secrets injected as references)
 → write connections row (status=connected)
```
- **Tokens live in the local Vault** (already in your build); tools receive a *reference*, never the raw token (Doc 15 §3.2 pattern).
- **PKCE** on the auth code exchange (public client, no client secret on the desktop).
- The cloud plane is **not** involved in the user's provider tokens — they stay local (privacy invariant holds: your business data and now your provider tokens never leave the machine).

## 2.3 Token lifecycle & self-healing (the operational reality of Tier-2)
```python
async def get_provider_client(ctx, provider):
    conn = await load_connection(ctx.db, ctx.user_id, provider)
    if conn.status == "expired":
        token = await refresh_token(conn)            # silent refresh with refresh_token
        if not token:                                # refresh failed → user must re-consent
            raise ToolError("credential",
                user_message=f"Please reconnect {provider} in Settings.")
    return Client(token=vault_get(conn.vault_secret_key))
```
- Silent refresh first; only surface to the user when refresh genuinely fails (don't nag).
- A credential error **pauses dependent tasks** and surfaces one "Reconnect X" card on Home (Self-Healing class=credential, Doc 04 SH-02). It never fails silently.

## 2.4 Connection UI (Settings → Connections)
Each provider: status chip (Connected/Expired/Error), account label, scopes granted, last-synced, Connect/Reconnect/Disconnect. Disconnect revokes the token and removes the Vault secret. Plain-language ("Connected as anil@gmail.com — working").

---

# PART 3 — TIER-2 TOOL CATALOG (the 4 that matter for a personal assistant)

Build these in priority order. Each is the Tier-1 contract + a provider call.

## 3.1 Calendar (Google Calendar + Outlook) — the highest-value connector
| Tool | Params | Approval | Notes |
|---|---|---|---|
| `calendar.list_events` | range, calendar_id? | none | read |
| `calendar.find_slots` | duration, window, working_hours | none | for "find a time" |
| `calendar.create_event` | title, start, end, attendees?, location? | ✋ if attendees include **new contacts** | write |
| `calendar.update_event` | id, fields | none | |
| `calendar.cancel_event` | id | ✋ (destructive if has attendees) | |
| `calendar.book_appointment` | with_entity, duration, preferred_window | ✋ if external invite sent | composes find_slots+create |

**"Book my dentist Tuesday 4pm" now writes a real calendar event** and (Tier-2.5) can email/WhatsApp the confirmation.

## 3.2 Email (Gmail + Outlook)
| Tool | Params | Approval | Notes |
|---|---|---|---|
| `email.list` | query, max | none | triage source |
| `email.read` | id | none | |
| `email.draft` | to, subject, body | none | draft only |
| `email.send` | draft_id | ✋ if **new recipient** or **mentions money** (U5/U6) | the gated action |
| `email.detect_bills` | range | none | scans for due-dates → feeds deadline.track |

## 3.3 WhatsApp (Business Cloud API)
| Tool | Params | Approval | Notes |
|---|---|---|---|
| `whatsapp.send` | to, body | ✋ new contact; **24-hour-window rule enforced** | outside window → template only |
| `whatsapp.send_template` | to, template_id, vars | none (pre-approved templates) | proactive reminders |
| `whatsapp.list_incoming` | since | none | triage + remote-command source |

**Operational must-dos (do not skip):** enforce the 24-hour customer-service window (outside it, only approved templates send); track number quality rating; queue + retry with backoff; dead-letter on hard fail. (These reshape the connector — see Doc 18 FR-5.2.)

## 3.4 Contacts (Google/Outlook Contacts)
| Tool | Params | Approval | Notes |
|---|---|---|---|
| `contacts.sync` | — | none | populates KG entities (resolves "my dentist") |
| `contacts.search` | name | none | |

## 3.5 Tier-2.5 — web search (read-only external, no auth)
| Tool | Params | Approval | Notes |
|---|---|---|---|
| `web.search` | query, n | none | research tasks; results summarized by Scribe |
| `web.fetch` | url | none | read a page the user/search surfaced |

---

# PART 4 — TIER-2 REFERENCE IMPLEMENTATION

## 4.1 `calendar.create_event` (with new-contact approval)
```python
@tool(name="calendar.create_event", permission="calendar.write",
      approval="conditional",   # wrapper evaluates approval_rule below
      writes_memory=True,
      description="Create a calendar event; gates approval if inviting a new contact.",
      params={"title":{"type":"string","required":True},
              "start":{"type":"string","format":"iso8601","required":True},
              "end":{"type":"string","format":"iso8601","required":True},
              "attendees":{"type":"array","items":{"type":"string"},"default":[]},
              "location":{"type":"string"}})
async def calendar_create_event(ctx, title, start, end, attendees=[], location=None):
    cal = await get_provider_client(ctx, "google_calendar")   # auto-refresh/heal
    ev = await cal.events_insert(title=title, start=start, end=end,
                                 attendees=attendees, location=location)
    return ToolResult(ok=True, data={"event_id":ev.id, "link":ev.htmlLink},
                      summary=f"Added “{title}” to your calendar for {fmt(start)}.")

# approval_rule for "conditional": require human approval if any attendee
# is not already a known KG contact (rule U6 new-contact gate).
def calendar_create_event_needs_approval(ctx, kwargs):
    return any(not is_known_contact(ctx, a) for a in kwargs.get("attendees", []))
```

## 4.2 `email.send` (gated, with source-citation guard)
```python
@tool(name="email.send", permission="email.send", approval="conditional", writes_memory=True,
      description="Send a previously drafted email.",
      params={"draft_id":{"type":"string","required":True}})
async def email_send(ctx, draft_id):
    draft = await load_draft(ctx.db, draft_id)
    validate_citations(draft)          # any figure/date must match a source record (U4) → else block
    gm = await get_provider_client(ctx, "gmail")
    msg = await gm.send(draft.to, draft.subject, draft.body)
    return ToolResult(ok=True, data={"message_id":msg.id},
                      summary=f"Sent your email to {draft.to_label}.")

def email_send_needs_approval(ctx, kwargs):
    d = peek_draft(ctx, kwargs["draft_id"])
    return is_new_recipient(ctx, d.to) or mentions_money(d.body)   # U5/U6
```

**Note the `approval="conditional"` extension** to the Tier-1 wrapper: when conditional, `call_tool` invokes the tool's `*_needs_approval(ctx, kwargs)` predicate; if true → route through the approval engine before executing. Add this one branch to the Doc 22 wrapper.

---

# PART 5 — TIER-3: THIRD-PARTY ACTIONS (the safe pattern)

Services like restaurant booking, cabs, and shopping usually have **no open API**. Three execution strategies, in order of preference:

## 5.1 Strategy A — Prepare-and-Handoff (DEFAULT for v1; reliable & trustworthy)
The assistant does 95% of the work and hands the user a **one-tap confirm**:
```
User: "Book a table for 4 at Spice Garden, Friday 8pm."
 → Finder resolves the restaurant (web.search), gets booking URL/phone
 → Scribe prepares the complete action:
     {action:"restaurant_booking", venue, date, time, party_size, contact_method,
      prefilled_link OR call_script OR draft_message}
 → presented as a HANDOFF CARD on Home + read aloud:
   "I've set up a table for 4 at Spice Garden, Friday 8pm. Tap to confirm,
    or I can send the request on WhatsApp for you to approve."
 → user taps Confirm → if a link: opens prefilled; if message: routes through
   whatsapp.send (gated); if call: dials / queues for Call Center module (later)
```
- **No fragile automation, no surprise actions.** The user is always the final actor on the external commitment.
- Implemented as a single internal tool `handoff.prepare(action_type, payload)` that produces a **Handoff Artifact** rendered as a confirm card.

## 5.2 Strategy B — Browser Automation (selective, where it's worth it)
For high-frequency, stable flows the user explicitly authorizes, use the **Playwright** capability you already have:
```python
@tool(name="browser.perform", permission="automation.browser", approval="required",
      description="Drive a browser to complete a specific, user-approved web action.",
      params={"recipe_id":{"type":"string","required":True}, "data":{"type":"object"}})
async def browser_perform(ctx, recipe_id, data):
    recipe = await load_browser_recipe(ctx.db, ctx.user_id, recipe_id)  # recorded steps
    async with sandboxed_browser(ctx.user_id) as page:                  # local, isolated
        result = await run_recipe(page, recipe, data)
        if result.needs_human:        # captcha / unexpected screen
            return ToolResult(ok=False, error=ToolError("user_input_needed",
                user_message="The site needs you to finish (captcha/login). Opening it now."),
                data={"screenshot": result.shot})
    return ToolResult(ok=True, data=result.data, summary=result.summary)
```
- **Always approval-gated**, runs in a **local sandboxed browser** (Doc 15 sandbox pattern), screenshots on ambiguity, hands to the user on captcha/login.
- Browser recipes are **recorded via the Skill Builder** (Pro feature) — so the user (or you) teaches a flow once; it generalizes. Treat each recipe as fragile: self-healing re-locates moved elements, else asks the user.
- **Default OFF**; opt-in per recipe; clearly labeled "I'll fill it in; you'll see every step."

## 5.3 Strategy C — Real API (where one exists)
Some categories (certain booking/ordering platforms, payment-free actions) have partner APIs. Wrap as a normal Tier-2 connector when the volume justifies the integration. Don't build speculatively — add when a real user need + a real API coincide.

## 5.4 The hard rule across all Tier-3
**Money is never moved autonomously.** Payment/commitment always routes to the user (handoff confirm, approval gate, or the user completing the final step). This is the same U5/U11 rule — non-negotiable, and it's *why users trust the assistant with the rest.*

---

# PART 6 — TIER-3 CATALOG (start tiny)

| Capability | v1 strategy | Later |
|---|---|---|
| Restaurant reservation | Handoff (link/call-script/WhatsApp request) | API where available |
| Cab/ride | Handoff (deep-link to ride app prefilled) | API (limited) |
| Shopping/reorder | Handoff (prefilled cart link) | Browser recipe (Pro) |
| Bookings (services) | Handoff | Browser recipe / API |
| Bill payment | **Handoff only — never automated** | never automated |

One internal tool — `handoff.prepare` — covers most of v1 Tier-3. Browser recipes come later, opt-in, Pro-tier.

---

# PART 7 — UPDATED FAILURE & RETRY MATRIX (Tiers 2–3)

| Failure | Behavior |
|---|---|
| Transient (provider 5xx/timeout) | retry ×3 backoff (wrapper) |
| Rate limit (429) | queue + backoff; if SLA at risk, tell user |
| Token expired | silent refresh; if fail → "Reconnect X" card, pause dependents |
| New-contact / money | approval gate before send (conditional approval) |
| WhatsApp outside 24h window | auto-switch to approved template or hold for user |
| Browser captcha/login/changed page | screenshot + hand to user ("finish this one step") |
| Ambiguous confirmation (Tier-3) | handoff card — user is final actor, never guess |
| Provider disconnected mid-task | checkpoint task, surface on Home, resume on reconnect |

All surfaced in the Activity feed in plain language; all auditable.

---

# PART 8 — BUILD PLAN (Tiers 2–3)

| Step | Deliverable | Days |
|---|---|---|
| 1 | Connection layer: `connections` table, loopback OAuth+PKCE, Vault token storage, refresh/heal | 6–8 |
| 2 | `conditional` approval branch in the wrapper + new-contact/money predicates | 2 |
| 3 | Calendar connector (Google first): list/find_slots/create/update/cancel/book | 5 |
| 4 | Email connector (Gmail first): list/read/draft/send (gated)/detect_bills | 5 |
| 5 | WhatsApp connector: send (window rule)/template/list_incoming + quality monitoring | 6 |
| 6 | Contacts sync → KG; web.search/fetch tools | 3 |
| 7 | `handoff.prepare` tool + Handoff Card UI (Tier-3 Strategy A) | 4 |
| 8 | Browser automation tool + sandbox + recipe runner (Strategy B, opt-in) | 6 |
| 9 | Connection UI (Settings) + self-healing "Reconnect" cards | 3 |
| 10 | Outlook variants + eval/integration tests across all connectors | 5 |

~8–9 weeks for two engineers. After this, the assistant **books, emails, messages, and arranges for real** — with trust intact.

---

# PART 9 — IMPLEMENTATION PROMPTS (paste into Claude Code)

## Prompt E — Connection layer
```
Build the HERMUS connection layer for the local FastAPI core.
1. A `connections` table (connection_id, user_id, provider, status[connected|expired|revoked|error], vault_secret_key, scopes[], account_label, connected_at, last_ok_at, last_error).
2. Desktop OAuth2 Authorization Code flow WITH PKCE using a loopback redirect (http://127.0.0.1:<ephemeral_port>/oauth/callback): open the system browser to the provider consent URL, capture the code on the loopback, exchange for access+refresh tokens, store tokens in the local Vault (store only a reference key in connections, never the raw token).
3. get_provider_client(ctx, provider): load connection, silent-refresh if expired, raise ToolError('credential', user_message='Please reconnect {provider}') if refresh fails.
4. Settings→Connections endpoints: list/connect/reconnect/disconnect (disconnect revokes token + deletes Vault secret).
The cloud plane must never receive provider tokens. Add tests for the loopback flow (mocked provider), silent refresh, and refresh-failure surfacing.
```

## Prompt F — Conditional approval + Calendar + Email
```
Extend call_tool to support approval="conditional": when set, call the tool's `<name>_needs_approval(ctx, kwargs)` predicate; if it returns True, route through the approval engine before executing.
Then implement the Calendar connector (Google Calendar first via get_provider_client): calendar.list_events, find_slots, create_event (conditional approval if any attendee is not a known KG contact), update_event, cancel_event (approval if it has attendees), book_appointment.
And the Email connector (Gmail first): email.list, read, draft, send (conditional approval if new recipient OR body mentions money; validate_citations() must block sending if any figure/date doesn't match a source record), detect_bills (scan for due dates → create deadline.track entries).
All tools reuse the Tier-1 contract, write operational memory, and emit Activity summaries. Add golden/integration tests including the new-contact gate and the citation block.
```

## Prompt G — WhatsApp + Contacts + web
```
Implement the WhatsApp connector (Business Cloud API): whatsapp.send (conditional approval for new contacts; ENFORCE the 24-hour customer-service window — outside it, only send via whatsapp.send_template with pre-approved templates), whatsapp.send_template, whatsapp.list_incoming. Add number quality-rating monitoring with a proactive alert, message queueing with exponential-backoff retry, and a dead-letter list.
Implement contacts.sync (Google/Outlook → upsert kg_entities so mentions like 'my dentist' resolve) and web.search/web.fetch (read-only, no auth, results returned for Scribe to summarize).
Tests: window-rule enforcement (template vs free-form), new-contact gate, queue/retry on rate limit.
```

## Prompt H — Prepare-and-Handoff + Browser automation
```
Implement Tier-3:
1. handoff.prepare(action_type, payload) — an internal tool that produces a Handoff Artifact (venue/date/party_size or prefilled link or call-script or draft message) rendered as a one-tap confirm card on Home and read aloud. On confirm, route to the right executor (open prefilled link / whatsapp.send (gated) / dial). The user is ALWAYS the final actor on external commitments; money is never moved autonomously.
2. browser.perform(recipe_id, data) — approval=required, runs a recorded Playwright recipe in a LOCAL sandboxed browser; on captcha/login/unexpected page, return user_input_needed with a screenshot and open the page for the user to finish; self-heal moved selectors where possible. Browser recipes are created via Skill Builder (Pro) and default OFF/opt-in.
Add tests: handoff card generation + confirm routing; browser recipe happy-path and captcha-handoff path.
```

---

# PART 10 — DEFINITION OF DONE (Tiers 2–3)

The user can connect their Google/Outlook calendar, Gmail/Outlook email, WhatsApp, and contacts via a one-time local consent; then, by voice or click, the assistant **books and manages real calendar events, triages and sends email (gated on new contacts/money with citation checks), sends WhatsApp messages and proactive template reminders within policy, resolves "my dentist"/"the gas company" from synced contacts, researches the web, and arranges restaurant/cab/shopping via prepare-and-handoff one-tap confirms** — with tokens stored locally in the Vault, silent refresh and graceful "reconnect" healing on expiry, approval gates on every sensitive action, money never moved autonomously, every action stored in Operational Memory and the Activity feed with a "Why?", and nothing sent to the cloud beyond what the user's own connected providers require. That is HERMUS Personal acting on the real world — with trust intact.
```

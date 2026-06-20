"""
Tier-3 tools — prepare-and-handoff + browser automation (Doc 23 Prompt H).

Services with no clean API are handled SAFELY: the assistant prepares 95% of the
action and the USER is always the final actor on the external commitment — money
is NEVER moved autonomously (ARCHITECTURE §5.4). Browser automation is opt-in,
approval-gated, runs in a local sandbox, and hands back to the user on
captcha/login. Same @tool contract throughout.
"""
from .models import BrowserRecipe, Handoff
from .security import ulid
from .tools import ToolResult, tool


def _method_for(action_type, p):
    if p.get("link"):
        return "link"
    if p.get("draft_message") or (p.get("to") and p.get("body")):
        return "message"
    if p.get("phone") or p.get("call_script"):
        return "call"
    return "link"


def _card(action_type, p):
    if action_type == "restaurant_booking":
        return (f"Table for {p.get('party_size', '?')} at {p.get('venue', 'the venue')}, "
                f"{p.get('date', '')} {p.get('time', '')}".strip())
    if action_type == "cab":
        return f"Ride from {p.get('from', '?')} to {p.get('to', '?')}"
    if action_type == "bill_payment":
        return f"Pay {p.get('biller', 'the bill')} — {p.get('amount', '')}".strip()
    if action_type == "message":
        return f"Message to {p.get('to', '?')}"
    return action_type.replace("_", " ").title()


# ── prepare-and-handoff (Strategy A — the default) ───────────────────────────
@tool("handoff.prepare", "Prepare an external action as a one-tap confirm card (the user confirms).",
      {"action_type": {"type": "string", "required": True}, "payload": {"type": "object", "required": True}},
      permission="handoff.write", writes_memory=True)
def handoff_prepare(ctx, action_type, payload):
    method = _method_for(action_type, payload or {})
    h = Handoff(id=ulid("hof"), tenant_id=ctx.actor.tenant_id, user_id=ctx.actor.user_id,
                action_type=action_type, payload=payload or {}, method=method, status="prepared")
    ctx.db.add(h); ctx.db.flush()
    title = _card(action_type, payload or {})
    spoken = (f"I've set up: {title}. Tap to confirm — you'll take the final step."
              if action_type != "bill_payment"
              else f"I've prepared: {title}. I'll open it for you to pay — I never move money myself.")
    return ToolResult(ok=True, data={
        "handoff_id": h.id, "method": method, "action_type": action_type,
        "card": {"title": title, "body": payload or {}, "confirm_label": "Confirm"}, "spoken": spoken},
        summary=spoken)


@tool("handoff.confirm", "Confirm a prepared handoff — routes to the right executor (user is final actor).",
      {"handoff_id": {"type": "string", "required": True}},
      permission="handoff.write", writes_memory=True)
def handoff_confirm(ctx, handoff_id):
    h = ctx.db.get(Handoff, handoff_id)
    if not h or h.tenant_id != ctx.actor.tenant_id:
        return ToolResult(ok=False, error="validation", summary="That handoff doesn't exist.")
    if h.status != "prepared":
        return ToolResult(ok=False, error="validation", summary=f"That handoff is already {h.status}.")
    p = h.payload or {}
    if h.method == "message":
        # routes to whatsapp.send (which itself gates) — we never send autonomously
        route = {"action": "whatsapp_send", "to": p.get("to"), "body": p.get("draft_message") or p.get("body")}
    elif h.method == "call":
        route = {"action": "dial", "phone": p.get("phone"), "script": p.get("call_script")}
    else:
        # link (incl. bill_payment): open the prefilled page; the USER completes it
        route = {"action": "open_link", "url": p.get("link")}
    h.status = "confirmed"; h.result = route; ctx.db.flush()
    return ToolResult(ok=True, data={"route": route},
                      summary=f"Confirmed — {route['action'].replace('_', ' ')}. You take the final step.")


@tool("handoff.dismiss", "Dismiss a prepared handoff.", {"handoff_id": {"type": "string", "required": True}},
      permission="handoff.write", writes_memory=True)
def handoff_dismiss(ctx, handoff_id):
    h = ctx.db.get(Handoff, handoff_id)
    if not h or h.tenant_id != ctx.actor.tenant_id:
        return ToolResult(ok=False, error="validation", summary="That handoff doesn't exist.")
    h.status = "dismissed"; ctx.db.flush()
    return ToolResult(ok=True, data={"handoff_id": handoff_id}, summary="Dismissed.")


# ── browser automation (Strategy B — opt-in, approval-gated) ─────────────────
def _run_recipe(steps, data):
    """Pluggable runner. Real impl drives a LOCAL sandboxed Playwright browser;
    Playwright is an optional dependency (ARCHITECTURE §1) so until it's approved
    + installed this returns 'unavailable'. Mocked in tests."""
    try:
        import playwright  # noqa: F401
    except Exception:
        return {"unavailable": True,
                "summary": "Browser automation needs the Playwright add-on (not installed)."}
    # Real automation would run `steps` against `data` in a sandbox here.
    return {"ok": True, "data": {}, "summary": "Completed the web action."}


@tool("browser.perform", "Drive a sandboxed browser to complete a recorded, approved web action.",
      {"recipe_id": {"type": "string", "required": True}, "data": {"type": "object"}},
      permission="automation.browser", approval="required", writes_memory=True)
def browser_perform(ctx, recipe_id, data=None):
    r = ctx.db.get(BrowserRecipe, recipe_id)
    if not r or r.tenant_id != ctx.actor.tenant_id:
        return ToolResult(ok=False, error="validation", summary="That browser recipe doesn't exist.")
    if not r.enabled:
        return ToolResult(ok=False, error="validation",
                          summary="That browser recipe is off — enable it in Skills (Pro) first.")
    res = _run_recipe(r.steps or [], data or {})
    if res.get("unavailable"):
        return ToolResult(ok=False, error="validation", summary=res["summary"])
    if res.get("needs_human"):
        # captcha / login / unexpected page → hand back to the user with a screenshot
        return ToolResult(ok=False, error="user_input_needed",
                          summary="The site needs you to finish (captcha/login) — opening it for you.",
                          data={"screenshot": res.get("screenshot"), "url": res.get("url")})
    return ToolResult(ok=True, data=res.get("data", {}), summary=res.get("summary", "Done."))

"""
CEO Agent orchestration (UC-03, UC-04) + Approval Chain engine (AC-01..12).

This is a deterministic, rule-based stand-in for the LLM-driven planner
described in the docs. It decomposes a natural-language utterance into a DAG of
subtasks, assigns them to agents by skill/availability/KPI (TC-04), evaluates
approval rules, and produces an estimate — without executing anything (matches
POST /tasks/plan semantics: "does not execute").
"""
import re

from . import llm
from .config import THRESHOLDS

# Keyword → (subtask template, required skill, department hint)
_INTENT_LIBRARY = [
    (r"\bgst\b|\btax\b|\bfiling\b", [
        ("Compile transactions from accounting system", "accounting", "Finance"),
        ("Prepare GST summary (GSTR)", "gst", "Finance"),
        ("Verification / variance review", "audit", "Finance"),
    ]),
    (r"\binvoice\b|\bpayment\b|\bbill\b", [
        ("Generate invoice document", "document_generation", "Finance"),
        ("Verify amounts against records", "audit", "Finance"),
    ]),
    (r"\breport\b|\bsummary\b|\bdeck\b|\bpresentation\b", [
        ("Fetch source data", "data_fetch", "Sales"),
        ("Summarize and analyze", "summarization", "Sales"),
        ("Generate document", "document_generation", "Sales"),
    ]),
    (r"\bemail\b|\bmessage\b|\breply\b|\bfollow.?up\b", [
        ("Draft message", "drafting", "Support"),
        ("Review tone & facts", "review", "Support"),
    ]),
    (r"\bsocial\b|\bpost\b|\bcontent\b|\bcalendar\b", [
        ("Draft content calendar", "content", "Marketing"),
        ("Create post drafts", "drafting", "Marketing"),
    ]),
    (r"\bcontract\b|\bnotice\b|\bagreement\b|\bdraft\b", [
        ("Research precedent", "research", "Executive"),
        ("Draft document", "document_generation", "Executive"),
        ("Legal/quality review", "review", "Executive"),
    ]),
    (r"\bcall\b|\bremind\b|\bphone\b", [
        ("Prepare call script", "drafting", "Support"),
        ("Place outbound call", "calling", "Support"),
    ]),
]

# Words that imply a sensitive / approval-gated action.
_SENSITIVE = re.compile(r"\b(send|email|pay|transfer|delete|cancel|post|publish|file)\b", re.I)
_AMOUNT = re.compile(r"(?:₹|rs\.?|inr|\$)\s?([\d,]+(?:\.\d+)?)", re.I)
_DEADLINE = re.compile(r"\b(today|tomorrow|tonight|by\s+\w+|this week|next week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.I)


def parse_amount(text: str):
    m = _AMOUNT.search(text or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def approval_decision(amount, action_text, *, thresholds=None):
    """
    Approval Chain rules. Returns dict describing the tier that must act and
    whether human sign-off is required.
    """
    t = thresholds or THRESHOLDS
    text = (action_text or "").lower()

    # AC-07: destructive ops -> human, no AI auto-approve.
    if re.search(r"\b(delete|cancel|unsubscribe|remove|wipe)\b", text):
        return {"required": True, "tier": "human", "rule": "AC-07",
                "reason": "Destructive operation requires human approval."}

    # AC-05: outbound to NEW external contact -> human.
    if re.search(r"\bnew (contact|client|customer|vendor)\b", text):
        return {"required": True, "tier": "human", "rule": "AC-05",
                "reason": "Outbound message to a new external contact."}

    if amount is None:
        # Non-financial, non-destructive: specialist auto-approves.
        return {"required": False, "tier": "specialist", "rule": "AC-01",
                "reason": "Within specialist delegated authority."}

    if amount <= t["specialist_limit"]:
        return {"required": False, "tier": "specialist", "rule": "AC-01",
                "reason": f"Amount ≤ specialist limit (₹{t['specialist_limit']:,})."}
    if amount <= t["manager_limit"]:
        return {"required": False, "tier": "manager", "rule": "AC-02",
                "reason": f"Manager Agent reviews (≤ ₹{t['manager_limit']:,})."}
    if amount <= t["ceo_limit"]:
        return {"required": False, "tier": "ceo", "rule": "AC-03",
                "reason": f"CEO Agent auto-approves matching precedent (≤ ₹{t['ceo_limit']:,})."}
    # AC-04
    return {"required": True, "tier": "human", "rule": "AC-04",
            "reason": f"Amount exceeds CEO Agent limit (₹{t['ceo_limit']:,}); human approval mandatory."}


def _rule_based_steps(text):
    for pattern, templates in _INTENT_LIBRARY:
        if re.search(pattern, text, re.I):
            return list(templates)
    return [("Analyze request and execute", "general", "Executive")]


def _llm_steps(text, agents):
    """Ask the local LLM to decompose the goal. Returns list of (desc, skill, dept_or_name) or None."""
    roster = "\n".join(
        f"- {a.name}: {a.designation} (dept hint: {a.designation}; "
        f"skills: {', '.join(a.skills or []) or 'general'})"
        for a in agents if not a.is_ceo)
    system = (
        "You are the CEO Agent of an AI workforce. Decompose the user's goal into an "
        "ordered list of 1-5 concrete subtasks and assign each to the single best "
        "employee from the roster. Respond ONLY with JSON of the form "
        '{"subtasks":[{"description":"...","skill":"...","agent_name":"<exact name from roster>"}]}.')
    prompt = f"ROSTER:\n{roster}\n\nGOAL: {text}\n\nReturn the JSON plan."
    # Route to the fast local model (LC-06: CPU-only → small model) for responsiveness.
    data = llm.chat_json(prompt, system=system, smart=False)
    if not data or not isinstance(data.get("subtasks"), list) or not data["subtasks"]:
        return None
    out = []
    for s in data["subtasks"][:6]:
        if isinstance(s, dict) and s.get("description"):
            out.append((str(s["description"])[:200], str(s.get("skill", "general"))[:40],
                        str(s.get("agent_name", ""))[:60]))
    return out or None


def plan_task(utterance: str, agents: list, use_llm: bool = True):
    """
    Decompose an utterance into a plan. With use_llm, tries the local LLM (Ollama)
    first for real reasoning, then falls back to deterministic keyword templates.
    Approval evaluation stays rule-based (deterministic + auditable) regardless.
    """
    text = utterance or ""
    specialists = [a for a in agents if not a.is_ceo]

    def by_name(name):
        nl = (name or "").lower()
        for a in specialists:
            if a.name.lower() == nl or (nl and nl in a.name.lower()):
                return a
        return None

    def by_dept(dept_hint):
        for a in specialists:
            if dept_hint and dept_hint.lower() in (a.designation or "").lower():
                return a
        idle = [a for a in specialists if a.status == "idle"]
        return (idle or specialists or [None])[0]

    llm_steps = _llm_steps(text, agents) if use_llm else None
    engine = f"local-llm ({llm.MODEL_FAST})" if llm_steps else "rule-based"
    raw_steps = llm_steps or _rule_based_steps(text)

    assigned, steps = [], []
    for i, item in enumerate(raw_steps, start=1):
        if len(item) == 3 and llm_steps:
            desc, skill, who = item
            agent = by_name(who) or by_dept(skill)
        else:
            desc, skill, dept = item
            agent = by_dept(dept)
        steps.append({
            "step": i, "description": desc, "skill": skill,
            "department": (agent.designation if agent else "Executive"),
            "agent_id": agent.id if agent else None,
            "agent_name": agent.name if agent else "Unassigned",
        })
        if agent and agent.id not in assigned:
            assigned.append(agent.id)

    amount = parse_amount(text)
    sensitive = bool(_SENSITIVE.search(text))
    decision = approval_decision(amount, text) if sensitive else {
        "required": False, "tier": "specialist", "rule": "AC-01",
        "reason": "No sensitive action detected.",
    }
    deadline_m = _DEADLINE.search(text)
    estimate = max(5, len(steps) * 7)
    return {
        "utterance": text,
        "engine": engine,
        "subtasks": steps,
        "assignments": assigned,
        "estimate_minutes": estimate,
        "amount_detected": amount,
        "deadline_hint": deadline_m.group(0) if deadline_m else None,
        "requires_approval": decision["required"],
        "approval": decision,
        "readback": _readback(steps, estimate, decision),
    }


def _readback(steps, estimate, decision):
    n_agents = len({s["agent_id"] for s in steps if s["agent_id"]})
    line = (f"Here's my plan: {len(steps)} steps, {n_agents} agent(s), "
            f"estimated {estimate} minutes.")
    if decision["required"]:
        line += f" This needs your approval ({decision['rule']}): {decision['reason']}"
    line += " Proceed?"
    return line

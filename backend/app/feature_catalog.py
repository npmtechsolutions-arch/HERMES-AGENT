"""
Feature catalog (Doc 29 §5.1a). The 23 real Tier-1 tools, presented as cards the
"Do" page renders: label, owning agent, supported modes (live / schedule), a tiny
form (fields), and a natural-language template for live mode.

DRY + drift-proof: the overlay below only carries what the tool registry can't —
friendly label/modes/template/field-labels. `required`, `enum` and the agent are
read from the live TOOL_REGISTRY / agent_of_tool, and a test asserts every field
name is a real tool param and every required param has a field. So a card can
never silently drift from the tool it drives.

Field name == tool param name, so schedule mode posts params straight to
/feature-schedules and live mode fills the template for /assistant.
"""
from .tools import TOOL_REGISTRY
from . import assistant as _assistant  # noqa: F401  (import-time: registers all tools)
from .routers.agents_profile import agent_of_tool

VALID_MODES = {"live", "schedule"}
VALID_AGENTS = {"Scheduler", "Scribe", "Finder", "Inbox", "Aria"}

# key → friendly overlay. `fields` lists the form inputs (name must be a real
# param); `type` is the UI hint (text|textarea|datetime|number|select|tags).
_OVERLAY = {
    # ── Scheduler ──
    "reminder.create": {"label": "Set a reminder", "modes": ["live", "schedule"],
        "template": "Remind me to {text} on {due_at}",
        "fields": [{"name": "text", "label": "Remind me to", "type": "text"},
                   {"name": "due_at", "label": "When", "type": "datetime"},
                   {"name": "repeat", "label": "Repeat", "type": "select"}]},
    "reminder.list": {"label": "See my reminders", "modes": ["live"],
        "template": "Show my reminders",
        "fields": [{"name": "status", "label": "Status", "type": "text", "placeholder": "active"}]},
    "reminder.update": {"label": "Change a reminder", "modes": ["live"],
        "template": "Update reminder {id}: {text} at {due_at}",
        "fields": [{"name": "id", "label": "Reminder", "type": "text"},
                   {"name": "text", "label": "New text", "type": "text"},
                   {"name": "due_at", "label": "New time", "type": "datetime"}]},
    "reminder.cancel": {"label": "Cancel a reminder", "modes": ["live"],
        "template": "Cancel reminder {id}",
        "fields": [{"name": "id", "label": "Reminder", "type": "text"}]},
    "routine.create": {"label": "Set a routine", "modes": ["schedule"],
        "template": "Set a routine: {name} {cadence}",
        "fields": [{"name": "name", "label": "Routine", "type": "text"},
                   {"name": "cadence", "label": "How often", "type": "text", "placeholder": "every morning"}]},
    "deadline.track": {"label": "Track a bill / renewal", "modes": ["schedule"],
        "template": "Track {label}, due {due_at}",
        "fields": [{"name": "label", "label": "What", "type": "text", "placeholder": "rent"},
                   {"name": "due_at", "label": "Due", "type": "datetime"},
                   {"name": "kind", "label": "Kind", "type": "text", "placeholder": "bill"}]},
    # ── Scribe ──
    "note.create": {"label": "Save a note", "modes": ["live"],
        "template": "Save a note: {text}",
        "fields": [{"name": "text", "label": "Note", "type": "textarea"},
                   {"name": "tags", "label": "Tags", "type": "tags"}]},
    "note.search": {"label": "Find a note", "modes": ["live"],
        "template": "Find my note about {query}",
        "fields": [{"name": "query", "label": "About", "type": "text"}]},
    "list.manage": {"label": "Manage a list", "modes": ["live"],
        "template": "{op} {item} on my {list_name} list",
        "fields": [{"name": "list_name", "label": "List", "type": "text", "placeholder": "groceries"},
                   {"name": "op", "label": "Action", "type": "text", "placeholder": "add"},
                   {"name": "item", "label": "Item", "type": "text"}]},
    "document.generate": {"label": "Create a document", "modes": ["live", "schedule"],
        "template": "Write a {title}: {content}",
        "fields": [{"name": "title", "label": "Title", "type": "text"},
                   {"name": "content", "label": "Content", "type": "textarea"},
                   {"name": "format", "label": "Format", "type": "select"}]},
    "text.summarize": {"label": "Summarize something", "modes": ["live"],
        "template": "Summarize: {source}",
        "fields": [{"name": "source", "label": "Text to summarize", "type": "textarea"},
                   {"name": "length", "label": "Length", "type": "text", "placeholder": "short"}]},
    "text.polish": {"label": "Polish my text", "modes": ["live"],
        "template": "Polish this: {text}",
        "fields": [{"name": "text", "label": "Text", "type": "textarea"},
                   {"name": "tone", "label": "Tone", "type": "text", "placeholder": "polite"}]},
    "form.fill": {"label": "Fill a form", "modes": ["live"],
        "template": "Fill the {template} form",
        "fields": [{"name": "template", "label": "Form", "type": "text"},
                   {"name": "data", "label": "Details", "type": "textarea"}]},
    # ── Finder ──
    "memory.search": {"label": "Ask my memory", "modes": ["live"],
        "template": "What do I know about {query}?",
        "fields": [{"name": "query", "label": "Ask", "type": "text"}]},
    "memory.write": {"label": "Remember this", "modes": ["live"],
        "template": "Remember: {content}",
        "fields": [{"name": "content", "label": "Remember", "type": "textarea"},
                   {"name": "memory_class", "label": "Kind", "type": "text", "placeholder": "personal"}]},
    "memory.forget": {"label": "Forget this", "modes": ["live"],
        "template": "Forget {id}",
        "fields": [{"name": "id", "label": "Memory", "type": "text"}]},
    "contact.upsert": {"label": "Add / update a contact", "modes": ["live"],
        "template": "Save contact {name} ({relationship})",
        "fields": [{"name": "name", "label": "Name", "type": "text"},
                   {"name": "relationship", "label": "Relationship", "type": "text"}]},
    "contact.lookup": {"label": "Find a contact", "modes": ["live"],
        "template": "Find contact {name_or_mention}",
        "fields": [{"name": "name_or_mention", "label": "Name", "type": "text"}]},
    # ── Inbox ──
    "message.draft": {"label": "Draft a message", "modes": ["live", "schedule"],
        "template": "Draft a {tone} message to {to} about {intent}",
        "fields": [{"name": "to", "label": "To", "type": "text"},
                   {"name": "intent", "label": "What to say", "type": "textarea"},
                   {"name": "tone", "label": "Tone", "type": "text", "placeholder": "friendly"}]},
    "followup.schedule": {"label": "Schedule a follow-up", "modes": ["schedule"],
        "template": "Follow up about {about} {cadence}",
        "fields": [{"name": "about", "label": "About", "type": "text"},
                   {"name": "cadence", "label": "When", "type": "text", "placeholder": "next week"}]},
    # ── Aria ──
    "task.plan": {"label": "Plan a goal", "modes": ["live"],
        "template": "Plan: {utterance}",
        "fields": [{"name": "utterance", "label": "What's the goal?", "type": "textarea"}]},
    "briefing.compose": {"label": "Get a briefing", "modes": ["live", "schedule"],
        "template": "Give me my {scope} briefing",
        "fields": [{"name": "scope", "label": "Scope", "type": "select"}]},
    "roi.summarize": {"label": "Summary of value", "modes": ["live", "schedule"],
        "template": "Summarize my value for {period}",
        "fields": [{"name": "period", "label": "Period", "type": "text", "placeholder": "week"}]},
}


def _card(key, ov):
    spec = TOOL_REGISTRY[key]
    params = spec.params or {}
    fields = []
    for f in ov["fields"]:
        p = params.get(f["name"], {})
        field = {"name": f["name"], "label": f["label"], "type": f["type"],
                 "required": bool(p.get("required"))}
        if p.get("enum"):
            field["enum"] = p["enum"]
        if f.get("placeholder"):
            field["placeholder"] = f["placeholder"]
        fields.append(field)
    return {"key": key, "label": ov["label"], "agent": agent_of_tool(key),
            "modes": ov["modes"], "fields": fields, "template": ov["template"],
            "permission": spec.permission, "approval": spec.approval}


def build_catalog():
    """The 23 feature cards (only those whose tool is actually registered)."""
    return [_card(k, ov) for k, ov in _OVERLAY.items() if k in TOOL_REGISTRY]

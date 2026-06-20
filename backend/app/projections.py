"""
SOUL.md + NOW.md — Doc 25 §2.1/2.2/5.1 (Memory-engine extension).

These are PROJECTIONS of memory, not separate stores (ARCHITECTURE §8): pgvector
memory is the source of truth; SOUL.md is the human-readable, portable, user-owned
identity export the agent reads at session start; NOW.md is the small working-set
"current focus" doc injected into every prompt. Both live LOCALLY under ~/HERMUS.
"""
import os
import re

from .models import KGEntity, MemoryItem, Reminder, Task, now as _now
from .security import ulid
from .tools import _data_root


def _path(name):
    return os.path.join(_data_root(), name)


def _write(name, md):
    try:
        os.makedirs(_data_root(), exist_ok=True)
        with open(_path(name), "w") as f:
            f.write(md)
        return _path(name)
    except Exception:
        return None


def _read(name):
    try:
        with open(_path(name)) as f:
            return f.read()
    except Exception:
        return None


def load_now():
    return _read("NOW.md")


def load_soul():
    return _read("SOUL.md")


# ── NOW.md — the working-set, updated as tasks start/finish ───────────────────
def update_now(db, tenant_id, user_id, *, focus="", active_tasks=None, recent_decisions=None):
    if active_tasks is None:
        active_tasks = [t.title for t in db.query(Task).filter_by(tenant_id=tenant_id)
                        .filter(Task.status.notin_(["done", "canceled"])).limit(10).all()]
    lines = ["# NOW — current context", ""]
    if focus:
        lines += [f"**Focus:** {focus}", ""]
    lines += ["## Open tasks"] + ([f"- {t}" for t in active_tasks] or ["- (none)"]) + [""]
    if recent_decisions:
        lines += ["## Recent decisions"] + [f"- {d}" for d in recent_decisions] + [""]
    lines += [f"_updated {_now():%Y-%m-%d %H:%M}_"]
    return _write("NOW.md", "\n".join(lines))


# ── SOUL.md — portable identity, regenerated from memory on change ────────────
def regenerate_soul(db, tenant_id, user_id):
    mems = (db.query(MemoryItem).filter_by(tenant_id=tenant_id)
            .filter(MemoryItem.tier != "deleted").all())
    prefs = [m for m in mems if m.memory_class == "personal" and m.source_type in ("note", "preference")]
    identity = [m for m in mems if m.source_type == "profile"]
    contacts = db.query(KGEntity).filter_by(tenant_id=tenant_id, type="contact").limit(15).all()
    routines = db.query(Reminder).filter_by(tenant_id=tenant_id, status="active", kind="routine").all()

    md = ["# SOUL — your AI's identity (you own this file)", "",
          "## Identity"] + ([f"- {m.title}: {m.body}" for m in identity] or
                            ["- (the assistant will learn this as you use it)"]) + [
        "", "## Communication style",
        "- Plain, warm, concise. Confirms before sending. Honest that it's an AI.",
        "", "## Preferences"] + ([f"- {m.title}" for m in prefs] or ["- (none captured yet)"]) + [
        "", "## Key relationships"] + ([f"- {c.name}"
                                        + (f" ({c.attrs.get('relationship')})" if (c.attrs or {}).get("relationship") else "")
                                        for c in contacts] or ["- (sync contacts to populate)"]) + [
        "", "## Active goals & routines"] + ([f"- {r.text}" for r in routines] or ["- (none active)"]) + [
        "", "## Values & boundaries",
        "- Local-first & private. Money never moved autonomously. New contacts gated.",
        "", f"_generated {_now():%Y-%m-%d %H:%M} — edits are read back into memory_"]
    return _write("SOUL.md", "\n".join(md))


def parse_soul_edits(db, tenant_id, user_id, md=None):
    """A user hand-edit of SOUL.md is read back into memory (confidence-flagged),
    so moving the file to a new machine / editing it seeds personality."""
    md = md if md is not None else (load_soul() or "")
    # capture bullets under "## Preferences"
    m = re.search(r"##\s*Preferences\s*\n(.*?)(?:\n##|\Z)", md, re.S | re.I)
    added = 0
    if m:
        for line in m.group(1).splitlines():
            pref = line.strip().lstrip("-").strip()
            if not pref or pref.startswith("("):
                continue
            exists = (db.query(MemoryItem)
                      .filter_by(tenant_id=tenant_id, memory_class="personal",
                                 source_type="preference", title=pref).first())
            if not exists:
                db.add(MemoryItem(id=ulid("mem"), tenant_id=tenant_id, memory_class="personal",
                                  title=pref, source_type="preference", body=pref,
                                  tier="hot", confidence=0.7))   # confidence-flagged (user-edited)
                added += 1
    db.flush()
    return added

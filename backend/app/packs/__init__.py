"""
Domain-pack loader (Doc 24 §4 / ARCHITECTURE §4). A domain (Finance, Travel,
Health…) is NOT an engine — it's three data artifacts on the shared engines:
a persona (instructions + tool grants), a set of tools, and a slice of the
Knowledge Graph (entity types). Each pack is the same files:

    packs/<name>/persona.yaml · tools.py · entities.yaml · rules.yaml · evals/

load_packs() reads the manifests and imports tools.py (which registers its tools
into the shared TOOL_REGISTRY). Adding a pack needs NO engine change — the
CEO-Agent discovers its persona + tools, the KG absorbs its entity types, and
approvals/voice/audit/scheduler apply automatically.
"""
import glob
import importlib
import os
from dataclasses import dataclass, field

import yaml

from ..tools import TOOL_REGISTRY

_DIR = os.path.dirname(__file__)
PACK_REGISTRY: dict[str, "Pack"] = {}


@dataclass
class Pack:
    name: str
    persona: dict = field(default_factory=dict)
    entity_types: list = field(default_factory=list)   # [{type, fields}]
    relations: list = field(default_factory=list)
    rules: list = field(default_factory=list)          # [{id, when, do, locked}]
    tool_names: list = field(default_factory=list)


def _yaml(path):
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def load_packs(force=False) -> dict:
    if PACK_REGISTRY and not force:
        return PACK_REGISTRY
    for d in sorted(glob.glob(os.path.join(_DIR, "*", ""))):
        name = os.path.basename(os.path.dirname(d))
        if name.startswith("_") or not os.path.exists(os.path.join(d, "persona.yaml")):
            continue
        persona = _yaml(os.path.join(d, "persona.yaml"))
        ents = _yaml(os.path.join(d, "entities.yaml"))
        rules = _yaml(os.path.join(d, "rules.yaml"))
        before = set(TOOL_REGISTRY)
        try:
            importlib.import_module(f"app.packs.{name}.tools")   # registers @tool
        except Exception as e:                                    # never let one pack break the rest
            print(f"[packs] '{name}' tools failed to load: {e}")
        tool_names = sorted(set(TOOL_REGISTRY) - before) or list(persona.get("tool_grants", []))
        PACK_REGISTRY[name] = Pack(name, persona, ents.get("entities", []),
                                   ents.get("relations", []), rules.get("rules", []), tool_names)
    return PACK_REGISTRY


def pack_dto():
    return [{"name": p.name, "persona": p.persona.get("name", p.name),
             "instructions": p.persona.get("instructions"), "tone": p.persona.get("tone"),
             "tools": p.tool_names, "entity_types": [e.get("type") for e in p.entity_types],
             "rules": [{"id": r.get("id"), "do": r.get("do"), "locked": r.get("locked", False)} for r in p.rules]}
            for p in PACK_REGISTRY.values()]

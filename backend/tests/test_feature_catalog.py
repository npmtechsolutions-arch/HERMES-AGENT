"""
Tests for the feature catalog (Doc 29 §5.1a). The important one is the DRIFT test:
every card maps to a real registered tool, every field is a real tool param, and
every required param has a field — so the 23 features are genuinely wired, not
phantom, and a scheduled POST will validate.

Run:  python -m pytest tests/test_feature_catalog.py -q
Or:   python tests/test_feature_catalog.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import assistant as A  # noqa: E402
from app.feature_catalog import VALID_AGENTS, VALID_MODES, build_catalog  # noqa: E402
from app.tools import TOOL_REGISTRY  # noqa: E402

EXPECTED = {
    "reminder.create", "reminder.list", "reminder.update", "reminder.cancel", "routine.create",
    "deadline.track", "note.create", "note.search", "list.manage", "document.generate",
    "text.summarize", "text.polish", "form.fill", "memory.search", "memory.write", "memory.forget",
    "contact.upsert", "contact.lookup", "message.draft", "followup.schedule", "task.plan",
    "briefing.compose", "roi.summarize",
}


def test_all_23_features_present_and_real():
    cards = build_catalog()
    keys = {c["key"] for c in cards}
    assert len(cards) == 23 and keys == EXPECTED
    assert all(k in TOOL_REGISTRY for k in keys), "no phantom features"


def test_no_drift_fields_match_real_params_and_cover_required():
    for c in build_catalog():
        spec = TOOL_REGISTRY[c["key"]]
        params = spec.params or {}
        field_names = {f["name"] for f in c["fields"]}
        # every field is a real tool param
        assert field_names <= set(params), f"{c['key']}: phantom field(s) {field_names - set(params)}"
        # every REQUIRED param has a field (so the form can satisfy the tool / schedule POST)
        required = {n for n, p in params.items() if p.get("required")}
        assert required <= field_names, f"{c['key']}: missing required field(s) {required - field_names}"
        # required flag on the field reflects the tool, not the overlay
        for f in c["fields"]:
            assert f["required"] == bool(params[f["name"]].get("required"))


def test_features_grouped_by_correct_agent():
    # exact per-agent grouping from Doc 29 Part 1 (form.fill belongs to Scribe)
    from collections import Counter
    counts = Counter(c["agent"] for c in build_catalog())
    assert counts == {"Scheduler": 6, "Scribe": 7, "Finder": 5, "Inbox": 2, "Aria": 3}
    by_key = {c["key"]: c for c in build_catalog()}
    assert by_key["form.fill"]["agent"] == "Scribe"


def test_card_shape_modes_agents_template():
    for c in build_catalog():
        assert c["agent"] in VALID_AGENTS
        assert c["modes"] and set(c["modes"]) <= VALID_MODES
        assert isinstance(c["template"], str) and c["template"]
        assert c["fields"], "every card has at least one field"


def test_schedule_mode_features_are_schedulable():
    # the by-nature/dual-mode features expose schedule; pure-live ones don't
    by_key = {c["key"]: c for c in build_catalog()}
    for k in ("reminder.create", "routine.create", "deadline.track", "document.generate",
              "message.draft", "followup.schedule", "briefing.compose", "roi.summarize"):
        assert "schedule" in by_key[k]["modes"]
    for k in ("memory.search", "contact.lookup", "note.search", "text.polish"):
        assert by_key[k]["modes"] == ["live"]


def test_capabilities_endpoint_includes_features():
    caps = A.capabilities()
    assert "features" in caps and len(caps["features"]) == 23
    # enum carried from the tool param schema (e.g. reminder repeat, doc format)
    rc = next(c for c in caps["features"] if c["key"] == "reminder.create")
    repeat = next(f for f in rc["fields"] if f["name"] == "repeat")
    assert repeat.get("enum") and "daily" in repeat["enum"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}"); passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
        except Exception as e:
            import traceback; traceback.print_exc(); print(f"  ERROR {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)

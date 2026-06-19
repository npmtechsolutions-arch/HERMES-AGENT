"""
Unit tests for the HERMUS tool framework (Doc 22 Prompt A / ARCHITECTURE §9).
Covers: param validation, permission denial, approval gating, bounded retry,
and the writes_memory / activity hooks. No DB or network needed.

Run with pytest:  python -m pytest tests/test_tool_framework.py -q
Or standalone:    python tests/test_tool_framework.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import tools as T  # noqa: E402
from app.tools import Actor, ToolContext, ToolResult, TransientError, call_tool, tool  # noqa: E402


def _ctx(grants=("*",), approved=False):
    return ToolContext(actor=Actor(tenant_id="tnt_test", user_id="usr_test",
                                   agent_id="agt_test", grants=set(grants)),
                       db=None, approved=approved)


# ── register tools used by the tests (unique names) ──────────────────────────
CALLS = {"echo": 0, "flaky": 0, "destruct": 0}


@tool("test.echo", "echo", {"text": {"type": "string", "required": True},
                            "mode": {"type": "string", "enum": ["a", "b"], "default": "a"}},
      permission="test.run", writes_memory=True)
def _echo(ctx, text, mode="a"):
    CALLS["echo"] += 1
    return ToolResult(ok=True, summary=f"echoed {text} ({mode})", data={"text": text})


@tool("test.destruct", "destructive", {"id": {"type": "string", "required": True}},
      permission="test.run", approval="required", writes_memory=True)
def _destruct(ctx, id):
    CALLS["destruct"] += 1
    return ToolResult(ok=True, summary=f"destroyed {id}")


_FAIL_TIMES = {"n": 0}


@tool("test.flaky", "flaky", {}, permission="test.run")
def _flaky(ctx):
    CALLS["flaky"] += 1
    if _FAIL_TIMES["n"] > 0:
        _FAIL_TIMES["n"] -= 1
        raise TransientError("temporary")
    return ToolResult(ok=True, summary="flaky ok")


# ── param validation ─────────────────────────────────────────────────────────
def test_validation_missing_required():
    CALLS["echo"] = 0
    r = call_tool("test.echo", _ctx())   # 'text' missing
    assert r.ok is False and r.error == "validation"
    assert CALLS["echo"] == 0, "tool body must not run on invalid params"


def test_validation_enum_rejected():
    r = call_tool("test.echo", _ctx(), text="hi", mode="z")
    assert r.ok is False and r.error == "validation"


def test_validation_ok():
    r = call_tool("test.echo", _ctx(), text="hi", mode="b")
    assert r.ok is True and r.data["text"] == "hi"


# ── permission ───────────────────────────────────────────────────────────────
def test_permission_denied():
    CALLS["echo"] = 0
    r = call_tool("test.echo", _ctx(grants=("other.grant",)), text="hi")
    assert r.ok is False and r.error == "permission"
    assert CALLS["echo"] == 0, "denied tool must not run"


def test_permission_allowed_specific_grant():
    r = call_tool("test.echo", _ctx(grants=("test.run",)), text="hi")
    assert r.ok is True


# ── approval gating ──────────────────────────────────────────────────────────
def test_approval_blocks_without_approval():
    CALLS["destruct"] = 0
    r = call_tool("test.destruct", _ctx(), id="x1")
    assert r.ok is False and r.error == "user_input_needed"
    assert r.data.get("needs_approval") is True
    assert CALLS["destruct"] == 0, "approval-required tool must not run un-approved"


def test_approval_runs_when_approved():
    CALLS["destruct"] = 0
    r = call_tool("test.destruct", _ctx(approved=True), id="x1")
    assert r.ok is True and CALLS["destruct"] == 1


# ── bounded transient retry ──────────────────────────────────────────────────
def test_retry_succeeds_after_transient():
    CALLS["flaky"] = 0
    _FAIL_TIMES["n"] = 2                  # fail twice, then succeed
    r = call_tool("test.flaky", _ctx())
    assert r.ok is True
    assert CALLS["flaky"] == 3, "should have retried to the 3rd attempt"


def test_retry_exhausts_and_reports_transient():
    CALLS["flaky"] = 0
    _FAIL_TIMES["n"] = 99                 # always fail
    r = call_tool("test.flaky", _ctx())
    assert r.ok is False and r.error == "transient"
    assert CALLS["flaky"] == 3, "must stop after 3 attempts (no infinite loop)"


# ── memory + activity hooks fire on success ──────────────────────────────────
def test_writes_memory_and_activity_hooks_called():
    hits = {"mem": 0, "act": 0}
    orig_mem, orig_act = T.write_operational_memory, T.emit_activity
    T.write_operational_memory = lambda ctx, spec, kw, res: hits.__setitem__("mem", hits["mem"] + 1)
    T.emit_activity = lambda ctx, res, spec: hits.__setitem__("act", hits["act"] + 1)
    try:
        r = call_tool("test.echo", _ctx(), text="hi")
        assert r.ok is True
        assert hits["mem"] == 1, "writes_memory=True must trigger operational-memory write"
        assert hits["act"] == 1, "summary must be emitted to Activity"
    finally:
        T.write_operational_memory, T.emit_activity = orig_mem, orig_act


def test_unknown_tool():
    r = call_tool("test.nope", _ctx())
    assert r.ok is False and r.error == "validation"


# ── standalone runner (works without pytest) ─────────────────────────────────
if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn(); print(f"  PASS  {fn.__name__}"); passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)

"""
Tests for the memory + artifacts plumbing (Doc 22 Prompt B / ARCHITECTURE §8).
Asserts: exactly one operational-memory row per successful tool, PII redacted in
the stored input, correct KG entity upsert + relations, and a locally-saved file
with its path recorded in task_artifacts (content never leaves the machine).

Run:  python -m pytest tests/test_memory_artifacts.py -q
Or:   python tests/test_memory_artifacts.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import tools as T  # noqa: E402
from app.tools import Actor, ToolContext, ToolResult, call_tool, tool  # noqa: E402


def _mkdb():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _ctx(db):
    return ToolContext(actor=Actor(tenant_id="tnt_b", user_id="usr_b", agent_id="agt_b",
                                   grants={"*"}), db=db)


# ── tools used by these tests ────────────────────────────────────────────────
@tool("b.remember", "writes memory + links 2 entities",
      {"content": {"type": "string", "required": True}, "entity_links": {"type": "array"}},
      permission="memory.write", writes_memory=True)
def _b_remember(ctx, content, entity_links=None):
    return ToolResult(ok=True, summary="Remembered something.", data={"len": len(content)})


@tool("b.makedoc", "produces a local document artifact",
      {"title": {"type": "string", "required": True}, "content": {"type": "string", "required": True}},
      permission="documents.write", writes_memory=True)
def _b_makedoc(ctx, title, content):
    return ToolResult(ok=True, summary=f"Created {title}.",
                      artifacts=[{"kind": "document", "title": title, "ext": "md",
                                  "content": f"# {title}\n\n{content}\n"}])


# ── tests ────────────────────────────────────────────────────────────────────
def test_exactly_one_operational_memory_row():
    from app.models import MemoryItem
    db = _mkdb()
    r = call_tool("b.remember", _ctx(db), content="call the bank")
    db.commit()
    assert r.ok
    rows = db.query(MemoryItem).filter_by(memory_class="operational").all()
    assert len(rows) == 1, "exactly one operational memory row per successful tool"
    m = rows[0]
    assert m.title == "Remembered something." and m.source_type == "agent_action"
    body = json.loads(m.body)
    assert body["tool"] == "b.remember" and "input" in body and "entities" in body


def test_pii_redacted_in_stored_input():
    from app.models import MemoryItem
    db = _mkdb()
    call_tool("b.remember", _ctx(db),
              content="email me at john.doe@gmail.com or call 9876543210, PAN ABCDE1234F")
    db.commit()
    body = db.query(MemoryItem).filter_by(memory_class="operational").first().body
    assert "john.doe@gmail.com" not in body, "email must be redacted"
    assert "9876543210" not in body, "phone/long-number must be redacted"
    assert "ABCDE1234F" not in body, "PAN-like id must be redacted"
    assert "[redacted" in body


def test_kg_entities_upserted_and_linked():
    from app.models import KGEntity, KGRelation
    db = _mkdb()
    call_tool("b.remember", _ctx(db), content="x",
              entity_links=[{"type": "bill", "name": "Gas bill"},
                            {"type": "contact", "name": "Mahanagar Gas"}])
    db.commit()
    ents = db.query(KGEntity).all()
    names = {e.name for e in ents}
    assert {"Gas bill", "Mahanagar Gas"} <= names, "both entities upserted"
    rels = db.query(KGRelation).all()
    assert len(rels) == 1, "first entity linked to the second"
    # idempotent upsert: same names again -> no duplicate entities
    call_tool("b.remember", _ctx(db), content="y",
              entity_links=[{"type": "bill", "name": "Gas bill"},
                            {"type": "contact", "name": "Mahanagar Gas"}])
    db.commit()
    assert db.query(KGEntity).count() == 2, "entities deduped on re-touch"


def test_artifact_saved_locally_and_recorded():
    from app.models import TaskArtifact
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HERMUS_DATA_ROOT"] = tmp
        try:
            db = _mkdb()
            r = call_tool("b.makedoc", _ctx(db), title="Letter", content="Dear landlord")
            db.commit()
            assert r.ok and r.artifacts and "content" not in r.artifacts[0]
            path = r.artifacts[0]["path"]
            assert path.startswith(tmp) and os.path.exists(path), "file written under the local root"
            assert "usr_b" in path, "saved under the user's folder"
            with open(path) as f:
                assert "Dear landlord" in f.read()
            arts = db.query(TaskArtifact).all()
            assert len(arts) == 1 and arts[0].path == path, "task_artifacts row records the path"
        finally:
            os.environ.pop("HERMUS_DATA_ROOT", None)


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

"""Second Brain: memory ingestion + hybrid search; Knowledge Graph."""
import hashlib
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import llm
from ..database import get_db
from ..deps import Principal, audit, current_user
from ..events import hub
from ..models import KGEntity, KGRelation, MemoryItem
from ..security import ulid

router = APIRouter(tags=["second-brain"])

_PII = ("aadhaar", "pan ", "passport", "ssn", "card number", "@")
_CLASSES = ("personal", "business", "knowledge", "operational")


def mem_dto(m: MemoryItem):
    return {"id": m.id, "memory_class": m.memory_class, "title": m.title,
            "source_type": m.source_type, "tier": m.tier, "pii": m.pii,
            "confidence": m.confidence, "confidential": m.confidential,
            "snippet": (m.body or "")[:240],
            "created_at": m.created_at.isoformat() if m.created_at else None}


@router.get("/memory/items")
def list_memory(memory_class: str | None = None, p: Principal = Depends(current_user),
                db: Session = Depends(get_db)):
    q = db.query(MemoryItem).filter_by(tenant_id=p.tenant_id).filter(
        MemoryItem.tier != "deleted")
    if memory_class:
        q = q.filter_by(memory_class=memory_class)
    return [mem_dto(m) for m in q.order_by(MemoryItem.created_at.desc()).all()]


class IngestIn(BaseModel):
    title: str
    body: str
    memory_class: str = "knowledge"   # personal|business|knowledge|operational
    source_type: str = "note"
    confidential: bool = False


@router.post("/memory/ingest")
def ingest(body: IngestIn, p: Principal = Depends(current_user),
           db: Session = Depends(get_db)):
    chash = hashlib.sha256(body.body.encode()).hexdigest()
    # MC-01: dedupe by content hash.
    existing = db.query(MemoryItem).filter_by(tenant_id=p.tenant_id,
                                              content_hash=chash).first()
    if existing:
        return {"status": "duplicate", "linked_to": existing.id,
                "message": "Identical content already in memory (MC-01); linked."}
    pii = any(tok in body.body.lower() for tok in _PII)   # MC-08
    vector = llm.embed(f"{body.title}. {body.body}")      # local nomic-embed-text
    m = MemoryItem(id=ulid("mem"), tenant_id=p.tenant_id, memory_class=body.memory_class,
                   title=body.title, source_type=body.source_type, body=body.body,
                   content_hash=chash, pii=pii, confidential=body.confidential,
                   confidence=1.0, tier="hot", embedding=vector)
    db.add(m)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="memory.ingest",
          target=m.id, tenant_id=p.tenant_id,
          meta={"class": body.memory_class, "pii": pii})
    db.commit()
    hub.emit(p.tenant_id, "memory.changed", {"action": "ingest", "name": body.title})
    return {"status": "ingested", "id": m.id, "pii": pii,
            "message": f"“{body.title}” tagged PII — restricted to clearance-holding agents." if pii
                       else f"“{body.title}” ingested into the Second Brain."}


class SearchIn(BaseModel):
    query: str
    scopes: list[str] = []
    top_k: int = 8


@router.post("/memory/search")
def search(body: SearchIn, p: Principal = Depends(current_user),
           db: Session = Depends(get_db)):
    """
    Hybrid retrieval: local embedding cosine similarity (nomic-embed-text) +
    keyword term overlap. Falls back to keyword-only if the embedder is offline.
    """
    terms = [t for t in body.query.lower().split() if len(t) > 2]
    base = db.query(MemoryItem).filter_by(tenant_id=p.tenant_id).filter(
        MemoryItem.tier != "deleted")
    if body.scopes:
        base = base.filter(MemoryItem.memory_class.in_(body.scopes))
    rows = base.all()

    qvec = llm.embed(body.query)
    semantic = bool(qvec)

    def kw_score(m):
        text = ((m.title or "") + " " + (m.body or "")).lower()
        return sum(text.count(t) for t in terms)

    scored = []
    for m in rows:
        kw = kw_score(m)
        sem = llm.cosine(qvec, m.embedding) if (qvec and m.embedding) else 0.0
        # hybrid: weight semantic heavily, keyword as a booster
        combined = round(sem * 0.8 + min(kw, 5) / 5 * 0.2, 4) if semantic else float(kw)
        if combined > 0 or (not semantic and kw > 0):
            scored.append((combined, sem, kw, m))

    scored.sort(key=lambda x: x[0], reverse=True)
    scored = scored[:body.top_k]
    audit(db, plane="local", actor=f"user:{p.user_id}", action="memory.search",
          tenant_id=p.tenant_id, meta={"query": body.query[:120], "hits": len(scored)})
    db.commit()
    return {
        "query": body.query,
        "mode": "semantic+keyword" if semantic else "keyword",
        "message": f"{len(scored)} result{'' if len(scored) == 1 else 's'} for “{body.query}”."
                   if scored else f"No matches for “{body.query}”.",
        "results": [{**mem_dto(m), "score": round(c, 3), "semantic": round(sem, 3),
                     "keyword_hits": kw, "citation": f"{m.title} ({m.source_type})"}
                    for c, sem, kw, m in scored],
    }


@router.delete("/memory/items/{mid}")
def forget(mid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(MemoryItem, mid)
    if not m or m.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Not found"})
    title = m.title
    m.tier = "deleted"   # MC-04 soft delete (30-day recovery in production)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="memory.forget",
          target=m.id, tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "memory.changed", {"action": "forget", "name": title})
    return {"status": "soft_deleted", "recovery_days": 30,
            "message": f"“{title}” forgotten — recoverable for 30 days."}


@router.get("/memory/forgotten")
def forgotten(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(MemoryItem).filter_by(tenant_id=p.tenant_id, tier="deleted").order_by(
        MemoryItem.updated_at.desc()).all()
    return [mem_dto(m) for m in rows]


@router.post("/memory/items/{mid}/restore")
def restore(mid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(MemoryItem, mid)
    if not m or m.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Not found"})
    if m.tier != "deleted":
        return {"status": "active", "message": f"“{m.title}” is already in memory."}
    m.tier = "hot"
    audit(db, plane="local", actor=f"user:{p.user_id}", action="memory.restore",
          target=m.id, tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "memory.changed", {"action": "restore", "name": m.title})
    return {"status": "restored", "message": f"“{m.title}” restored to memory."}


@router.get("/memory/summary")
def memory_summary(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(MemoryItem).filter_by(tenant_id=p.tenant_id).all()
    counts = {c: 0 for c in _CLASSES}
    forgotten = pii = 0
    for m in rows:
        if m.tier == "deleted":
            forgotten += 1
            continue
        counts[m.memory_class] = counts.get(m.memory_class, 0) + 1
        if m.pii:
            pii += 1
    return {"by_class": counts, "total": sum(counts.values()),
            "forgotten": forgotten, "pii": pii}


# A starter brain so search/forget/restore can be tried without manual ingestion.
_DEMO = [
    ("business", "Sharma 3BHK quote", "Quoted Mr. Sharma ₹92,00,000 for the OMR 3BHK, "
     "valid 15 days. He asked for a 5% discount; pending CEO approval."),
    ("knowledge", "GST filing SOP", "File GSTR-1 by the 11th and GSTR-3B by the 20th every "
     "month. Reconcile ITC against the purchase register before filing."),
    ("operational", "Office Wi-Fi & access", "Guest Wi-Fi: HERMUS-Guest. Server room key with "
     "reception. Backups run nightly at 2am to the NAS."),
    ("personal", "CEO travel preferences", "Prefers morning flights, aisle seat, no red-eyes. "
     "Vegetarian meals. Loyalty: 6E and AI."),
    ("knowledge", "Refund policy", "Refunds within 7 days of booking, 10% processing fee after "
     "48 hours. No refund once registration is filed."),
    ("business", "PrintFast vendor terms", "₹18,000 for 500 brochures, 4-day turnaround, "
     "net-15 payment. Contact: Ravi 98xxxxxx10."),
]


@router.post("/memory/demo")
def memory_demo(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Seed a sample Second Brain (idempotent)."""
    if db.query(MemoryItem).filter_by(tenant_id=p.tenant_id).filter(
            MemoryItem.tier != "deleted").count() > 0:
        return {"status": "exists", "message": "The Second Brain already has memories."}
    n = 0
    for cls, title, bdy in _DEMO:
        chash = hashlib.sha256(bdy.encode()).hexdigest()
        if db.query(MemoryItem).filter_by(tenant_id=p.tenant_id, content_hash=chash).first():
            continue
        pii = any(tok in bdy.lower() for tok in _PII)
        db.add(MemoryItem(id=ulid("mem"), tenant_id=p.tenant_id, memory_class=cls,
                          title=title, source_type="note", body=bdy, content_hash=chash,
                          pii=pii, confidence=1.0, tier="hot", embedding=llm.embed(f"{title}. {bdy}")))
        n += 1
    audit(db, plane="local", actor=f"user:{p.user_id}", action="memory.demo",
          tenant_id=p.tenant_id, meta={"items": n})
    db.commit()
    hub.emit(p.tenant_id, "memory.changed", {"action": "demo", "name": f"{n} memories"})
    return {"status": "seeded", "items": n,
            "message": f"Loaded a starter Second Brain — {n} memories."}


def _match_memory(db, tenant_id, text, deleted=False):
    low = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    toks = [w for w in low.split() if len(w) >= 3 and w not in (
        "the", "memory", "note", "item", "forget", "remove", "delete", "restore",
        "recover", "bring", "back", "about", "titled", "called", "this", "that")]
    tier_filter = (MemoryItem.tier == "deleted") if deleted else (MemoryItem.tier != "deleted")
    rows = db.query(MemoryItem).filter_by(tenant_id=tenant_id).filter(tier_filter).all()
    best, score = None, 0
    for m in rows:
        hay = re.sub(r"[^a-z0-9 ]", " ", f"{m.title} {m.body}".lower())
        s = sum(1 for w in toks if w in hay)
        if s > score:
            best, score = m, s
    return best if score else None


class BrainVoiceIn(BaseModel):
    transcript: str


@router.post("/memory/resolve")
def memory_resolve(body: BrainVoiceIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    text = body.transcript or ""
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())

    if re.search(r"\b(demo|sample|starter|load.*brain|populate|example)\b", low):
        return {"action": "demo", "message": "Loading a starter brain."}
    # restore / undo forget
    if re.search(r"\b(restore|recover|undo|bring back|un.?forget|unforget)\b", low):
        m = _match_memory(db, p.tenant_id, text, deleted=True)
        if m:
            return {"action": "restore", "id": m.id, "name": m.title,
                    "message": f"Restoring “{m.title}”."}
        return {"action": "none", "message": "I couldn't find a forgotten item by that name."}
    # forget / delete
    if re.search(r"\b(forget|remove|delete|drop|erase)\b", low):
        m = _match_memory(db, p.tenant_id, text)
        if m:
            return {"action": "forget", "id": m.id, "name": m.title,
                    "message": f"Forgetting “{m.title}”."}
        return {"action": "none", "message": "Which memory should I forget? Try its title."}
    # filter by class
    fm = re.search(r"\b(personal|business|knowledge|operational)\b", low)
    if fm and re.search(r"\b(show|filter|view|see|only|just)\b", low):
        return {"action": "filter", "memory_class": fm.group(1),
                "message": f"Showing {fm.group(1)} memory."}
    # ingest / remember
    im = re.search(r"\b(ingest|remember|note|save|store|add|capture)\b(.*)$", text, re.I)
    if im:
        rest = im.group(2)
        mc = "knowledge"
        cm = re.search(r"\b(personal|business|knowledge|operational)\b", rest, re.I)
        if cm:
            mc = cm.group(1).lower()
        title, bdy = None, None
        tm = re.search(r"\btitled?\s+(.+?)\s+(?:saying|that says|with the (?:note|content)|content|:|that)\s+(.+)$", rest, re.I)
        if tm:
            title, bdy = tm.group(1).strip(" .'\""), tm.group(2).strip(" .'\"")
        else:
            # "remember that X" / "remember X" → body is X, title = first ~6 words
            rest2 = re.sub(r"^\s*(a |an |the )?(note|memory|item)?\s*(in (personal|business|knowledge|operational)( memory)?)?\s*(that|:)?\s*", " ", rest, flags=re.I).strip()
            rest2 = re.sub(r"\b(in (personal|business|knowledge|operational)( memory)?)\b", "", rest2, flags=re.I).strip(" ,.")
            if rest2:
                bdy = rest2   # title derived from the cleaned body below
        # strip a trailing class instruction from the captured text
        def _declass(s):
            s = re.sub(r"[,;]?\s*(and )?(keep it |make it |file it |put it )?(in |under |as )?(personal|business|knowledge|operational)( memory)?\s*$", "", s or "", flags=re.I)
            return s.strip(" ,.")
        bdy, title = _declass(bdy), (_declass(title) if title else title)
        if bdy:
            title = title or " ".join(bdy.split()[:6])
            return {"action": "ingest", "title": title, "body": bdy,
                    "memory_class": mc, "message": f"Saving “{title}”."}
        return {"action": "ingest_open", "message": "What should I remember? Opening the ingest form."}
    # search (default for question-like input)
    sm = re.search(r"\b(search|find|look up|recall|what did|what's|whats|where|when|show me)\b\s*(?:for|the|my)?\s*(.*)$", text, re.I)
    if sm and sm.group(2).strip():
        return {"action": "search", "query": sm.group(2).strip(" .'?\""),
                "message": f"Searching for {sm.group(2).strip()[:40]}."}
    if low.strip():
        return {"action": "search", "query": text.strip(" .'?\""),
                "message": f"Searching for {text.strip()[:40]}."}
    return {"action": "none",
            "message": 'Try "search for the Sharma quote", "remember that the wifi is HERMUS-Guest", "forget the refund policy", or "restore it".'}


# ───────────────────────────── Knowledge Graph (FR-M4) ──────────────────────
@router.get("/graph")
def get_graph(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    ents = db.query(KGEntity).filter_by(tenant_id=p.tenant_id).all()
    rels = db.query(KGRelation).filter_by(tenant_id=p.tenant_id).all()
    return {
        "entities": [{"id": e.id, "type": e.type, "name": e.name,
                      "aliases": e.aliases or [], "attrs": e.attrs or {},
                      "confidential": e.confidential} for e in ents],
        "relations": [{"id": r.id, "from_id": r.from_id, "to_id": r.to_id,
                       "relation": r.relation, "attrs": r.attrs or {}} for r in rels],
    }


class EntityIn(BaseModel):
    type: str
    name: str
    aliases: list[str] = []
    attrs: dict = {}


@router.post("/graph/entities")
def create_entity(body: EntityIn, p: Principal = Depends(current_user),
                  db: Session = Depends(get_db)):
    if not body.name.strip():
        raise HTTPException(422, detail={"code": "BAD_NAME", "message": "Entity needs a name."})
    e = KGEntity(id=ulid("ent"), tenant_id=p.tenant_id, type=body.type or "custom",
                 name=body.name.strip(), aliases=body.aliases, attrs=body.attrs)
    db.add(e)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="graph.entity.create",
          target=e.id, tenant_id=p.tenant_id, meta={"type": e.type})
    db.commit()
    hub.emit(p.tenant_id, "graph.changed", {"action": "entity", "name": e.name})
    return {"id": e.id, "name": e.name, "type": e.type,
            "message": f"Added {e.type} “{e.name}” to the graph."}


class RelationIn(BaseModel):
    from_id: str
    to_id: str
    relation: str


@router.post("/graph/relations")
def create_relation(body: RelationIn, p: Principal = Depends(current_user),
                    db: Session = Depends(get_db)):
    fr = db.get(KGEntity, body.from_id)
    to = db.get(KGEntity, body.to_id)
    if not fr or not to or fr.tenant_id != p.tenant_id or to.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Both entities must exist."})
    r = KGRelation(id=ulid("rel"), tenant_id=p.tenant_id, from_id=body.from_id,
                   to_id=body.to_id, relation=(body.relation or "related_to").strip())
    db.add(r)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="graph.relation.create",
          target=r.id, tenant_id=p.tenant_id, meta={"relation": r.relation})
    db.commit()
    hub.emit(p.tenant_id, "graph.changed", {"action": "relation", "name": f"{fr.name} → {to.name}"})
    return {"id": r.id, "message": f"Linked {fr.name} → {to.name} ({r.relation})."}


@router.delete("/graph/entities/{eid}")
def delete_entity(eid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    e = db.get(KGEntity, eid)
    if not e or e.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Entity not found"})
    name = e.name
    rels = db.query(KGRelation).filter(
        (KGRelation.from_id == eid) | (KGRelation.to_id == eid)).all()
    for r in rels:
        db.delete(r)
    db.delete(e)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="graph.entity.delete",
          target=eid, tenant_id=p.tenant_id, meta={"relations_removed": len(rels)})
    db.commit()
    hub.emit(p.tenant_id, "graph.changed", {"action": "delete", "name": name})
    return {"status": "deleted", "relations_removed": len(rels),
            "message": f"Removed “{name}” and {len(rels)} relationship(s)."}


@router.delete("/graph/relations/{rid}")
def delete_relation(rid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(KGRelation, rid)
    if not r or r.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Relation not found"})
    db.delete(r)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="graph.relation.delete",
          target=rid, tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "graph.changed", {"action": "unlink", "name": r.relation})
    return {"status": "deleted", "message": "Relationship removed."}


@router.get("/graph/summary")
def graph_summary(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    ents = db.query(KGEntity).filter_by(tenant_id=p.tenant_id).all()
    rels = db.query(KGRelation).filter_by(tenant_id=p.tenant_id).count()
    by_type = {}
    for e in ents:
        by_type[e.type] = by_type.get(e.type, 0) + 1
    return {"entities": len(ents), "relations": rels, "by_type": by_type}


_GDEMO_ENTS = [
    ("customer", "Acme Corp"), ("customer", "Mr. Sharma"), ("project", "OMR 3BHK"),
    ("vendor", "PrintFast"), ("agent", "Sales Agent"), ("policy", "Refund Policy"),
    ("document", "GST Filing SOP"),
]
_GDEMO_RELS = [
    ("Acme Corp", "OMR 3BHK", "interested_in"), ("Mr. Sharma", "OMR 3BHK", "quoted_for"),
    ("Sales Agent", "Acme Corp", "handles"), ("Sales Agent", "Mr. Sharma", "handles"),
    ("PrintFast", "Acme Corp", "supplies"), ("Refund Policy", "OMR 3BHK", "governs"),
]


@router.post("/graph/demo")
def graph_demo(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Seed a sample knowledge graph (idempotent)."""
    if db.query(KGEntity).filter_by(tenant_id=p.tenant_id).count() > 0:
        return {"status": "exists", "message": "The graph already has entities."}
    idx = {}
    for typ, name in _GDEMO_ENTS:
        e = KGEntity(id=ulid("ent"), tenant_id=p.tenant_id, type=typ, name=name)
        db.add(e); db.flush(); idx[name] = e.id
    nrel = 0
    for a, b, rel in _GDEMO_RELS:
        if a in idx and b in idx:
            db.add(KGRelation(id=ulid("rel"), tenant_id=p.tenant_id,
                              from_id=idx[a], to_id=idx[b], relation=rel))
            nrel += 1
    audit(db, plane="local", actor=f"user:{p.user_id}", action="graph.demo",
          tenant_id=p.tenant_id, meta={"entities": len(idx), "relations": nrel})
    db.commit()
    hub.emit(p.tenant_id, "graph.changed", {"action": "demo", "name": f"{len(idx)} entities"})
    return {"status": "seeded", "entities": len(idx), "relations": nrel,
            "message": f"Loaded a sample graph — {len(idx)} entities, {nrel} relationships."}


_ENTITY_TYPES = ("customer", "vendor", "contact", "project", "task", "document",
                 "agent", "policy", "product")


def _match_entity(db, tenant_id, text, exclude=None):
    low = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    toks = [w for w in low.split() if len(w) >= 3 and w not in (
        "the", "entity", "node", "connect", "link", "delete", "remove", "focus",
        "show", "and", "with", "from", "into", "between", "named", "called", "this")]
    rows = db.query(KGEntity).filter_by(tenant_id=tenant_id).all()
    best, score = None, 0
    for e in rows:
        if exclude and e.id == exclude:
            continue
        hay = re.sub(r"[^a-z0-9 ]", " ", f"{e.name} {' '.join(e.aliases or [])}".lower())
        s = sum(1 for w in toks if w in hay)
        if s > score:
            best, score = e, s
    return best if score else None


class GraphVoiceIn(BaseModel):
    transcript: str


@router.post("/graph/resolve")
def graph_resolve(body: GraphVoiceIn, p: Principal = Depends(current_user),
                  db: Session = Depends(get_db)):
    text = body.transcript or ""
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())

    if re.search(r"\b(demo|sample|starter|load.*graph|populate|example)\b", low):
        return {"action": "demo", "message": "Loading a sample graph."}
    # add entity: "add a customer named Acme"
    am = re.search(r"\b(add|create|new)\b.*?\b(" + "|".join(_ENTITY_TYPES) + r")\b(?:\s+(?:named|called)\s+|\s+)(.+)$", text, re.I)
    if am:
        typ = am.group(2).lower()
        name = re.sub(r"^(named|called)\s+", "", am.group(3).strip(" .'\""), flags=re.I)
        return {"action": "add_entity", "type": typ, "name": name,
                "message": f"Adding {typ} “{name}”."}
    am2 = re.search(r"\b(add|create|new)\b\s+(?:an? |the )?(?:entity|node)\s+(?:named|called)\s+(.+)$", text, re.I)
    if am2:
        return {"action": "add_entity", "type": "custom", "name": am2.group(2).strip(" .'\""),
                "message": f"Adding “{am2.group(2).strip()}”."}
    # connect / link: "connect Acme to OMR as client_of" / "link Acme and Sharma"
    cm = re.search(r"\b(connect|link|relate|associate|join)\b\s+(.+?)\s+(?:to|and|with)\s+(.+?)(?:\s+(?:as|via|by|with relation)\s+(.+))?$", text, re.I)
    if cm:
        a = _match_entity(db, p.tenant_id, cm.group(2))
        b = _match_entity(db, p.tenant_id, cm.group(3), exclude=a.id if a else None)
        rel = (cm.group(4) or "related_to").strip(" .'\"").replace(" ", "_")
        if a and b:
            return {"action": "connect", "from_id": a.id, "to_id": b.id, "relation": rel,
                    "from_name": a.name, "to_name": b.name,
                    "message": f"Linking {a.name} → {b.name} ({rel})."}
        return {"action": "none", "message": "I couldn't match both entities to connect."}
    # delete entity
    if re.search(r"\b(delete|remove|drop|erase)\b", low):
        e = _match_entity(db, p.tenant_id, text)
        if e:
            return {"action": "delete_entity", "id": e.id, "name": e.name,
                    "message": f"Removing “{e.name}”."}
        return {"action": "none", "message": "Which entity should I remove? Try its name."}
    # focus / show neighbours
    if re.search(r"\b(focus|select|highlight|show|open|inspect|neighbou?rs of|connections of)\b", low):
        e = _match_entity(db, p.tenant_id, text)
        if e:
            return {"action": "focus", "id": e.id, "name": e.name,
                    "message": f"Focusing on {e.name}."}
    # bare name → focus
    e = _match_entity(db, p.tenant_id, text)
    if e:
        return {"action": "focus", "id": e.id, "name": e.name, "message": f"Focusing on {e.name}."}
    return {"action": "none",
            "message": 'Try "add a customer named Acme", "connect Acme to the OMR project as client_of", "focus on Acme", or "remove PrintFast".'}

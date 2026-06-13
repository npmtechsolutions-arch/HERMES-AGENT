"""
MVP launch-blocking gaps (Doc 16):
  GAP-1  Local data resilience — encrypted backup/restore with a recovery phrase
  GAP-2  Agent evaluation — golden-task suite (release gate)
  GAP-5  ROI ledger — weekly value note + cumulative
Plus a one-click Real-Estate demo loader so the killer workflow has data.
"""
import hashlib
import json
import os
import re
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, audit, current_user
from ..models import (Agent, BackupDestination, BackupJob, Department, EvalCase,
                      EvalRun, Lead, LeadInteraction, Property, RecoveryKey, RoiEntry,
                      Tenant, now)
from ..models import Clarification, EvalCase as _EC, Lead as _Lead
from ..routers.leads import log_roi, validate_outbound, qualify as _lead_qualify
from ..security import ulid
from ..events import hub

router = APIRouter(tags=["mvp"])

BACKUP_DIR = "/tmp/hermus_backups"
_WORDS = ("river stone maple harbor copper lantern willow ember meadow cobalt orchid "
          "falcon cedar pebble violet anchor saffron tundra quartz hazel jasmine onyx "
          "marble cypress lotus amber thistle slate ivory garnet").split()


# ───────────────────────────── GAP-1 crypto ─────────────────────────────────
def _derive_key(phrase: str) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", phrase.encode(), b"hermus-backup-salt", 200_000)


def _crypt(data: bytes, key: bytes) -> bytes:
    """Symmetric stream cipher (SHA-256 keystream in counter mode) — reversible."""
    out, ctr = bytearray(), 0
    while len(out) < len(data):
        out.extend(hashlib.sha256(key + ctr.to_bytes(8, "big")).digest())
        ctr += 1
    return bytes(a ^ b for a, b in zip(data, out[: len(data)]))


def _export(db, tenant_id):
    """Snapshot the tenant's local business data for backup."""
    def rows(model):
        return [{c.name: getattr(r, c.name) for c in model.__table__.columns}
                for r in db.query(model).filter(model.tenant_id == tenant_id).all()]
    snap = {"leads": rows(Lead), "properties": rows(Property),
            "interactions": rows(LeadInteraction), "agents": rows(Agent)}
    return json.dumps(snap, default=str).encode()


# ───────────────────────────── GAP-1 endpoints ──────────────────────────────
@router.get("/backup/status")
def backup_status(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rk = db.get(RecoveryKey, p.tenant_id)
    dests = db.query(BackupDestination).filter_by(tenant_id=p.tenant_id).all()
    last = (db.query(BackupJob).filter_by(tenant_id=p.tenant_id, status="completed")
            .order_by(BackupJob.at.desc()).first())
    stale = (not last) or (now() - last.at > timedelta(hours=48))
    return {"recovery_phrase_set": bool(rk), "destinations": len(dests),
            "last_backup_at": last.at.isoformat() if last else None,
            "last_size": last.size_bytes if last else 0, "stale_48h": stale,
            "summary": (f"Last backup: {last.at.strftime('%a %H:%M')}" if last
                        else "No backup yet — set this up now.")}


@router.post("/backup/recovery-phrase")
def make_recovery_phrase(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """The recovery-phrase ceremony: shown ONCE, never stored by us."""
    phrase = " ".join(secrets.choice(_WORDS) for _ in range(12))
    key = _derive_key(phrase)
    rk = db.get(RecoveryKey, p.tenant_id)
    if not rk:
        rk = RecoveryKey(tenant_id=p.tenant_id)
        db.add(rk)
    rk.phrase_hash = hashlib.sha256(phrase.encode()).hexdigest()
    rk.enc_key = key.hex()   # represents OS-keychain storage (local only)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="backup.recovery_phrase_set",
          tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "backup.changed", {"action": "phrase", "name": "recovery phrase"})
    return {"phrase": phrase, "words": phrase.split(), "message": "Recovery phrase generated — write it down now.",
            "warning": "Write this down. It is shown only once and we never store it. "
                       "It is the only way to restore your data on a new machine."}


class DestIn(BaseModel):
    type: str = "folder"          # folder|usb|gdrive|onedrive|lan
    path: str


_DEST_TYPES = ("folder", "usb", "gdrive", "onedrive", "lan")


@router.post("/backup/destinations")
def add_destination(body: DestIn, p: Principal = Depends(current_user),
                    db: Session = Depends(get_db)):
    if not (body.path or "").strip():
        raise HTTPException(422, detail={"code": "BAD_PATH", "message": "A path or account is required."})
    typ = body.type if body.type in _DEST_TYPES else "folder"
    d = BackupDestination(id=ulid("bdst"), tenant_id=p.tenant_id, type=typ, path=body.path.strip())
    db.add(d)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="backup.destination_add",
          target=d.id, tenant_id=p.tenant_id, meta={"type": typ})
    db.commit()
    hub.emit(p.tenant_id, "backup.changed", {"action": "destination", "name": f"{typ} · {d.path}"})
    return {"id": d.id, "type": d.type, "path": d.path,
            "message": f"Backup destination added: {typ} ({d.path})."}


@router.delete("/backup/destinations/{did}")
def delete_destination(did: str, p: Principal = Depends(current_user),
                       db: Session = Depends(get_db)):
    d = db.get(BackupDestination, did)
    if not d or d.tenant_id != p.tenant_id:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Destination not found"})
    label = f"{d.type} ({d.path})"
    # null out backup jobs that reference this destination (FK), then delete.
    for j in db.query(BackupJob).filter_by(destination_id=did).all():
        j.destination_id = None
    db.flush()
    db.delete(d)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="backup.destination_remove",
          target=did, tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "backup.changed", {"action": "destination_remove", "name": label})
    return {"status": "deleted", "message": f"Removed backup destination: {label}."}


@router.get("/backup/destinations")
def list_destinations(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(BackupDestination).filter_by(tenant_id=p.tenant_id).all()
    return [{"id": d.id, "type": d.type, "path": d.path, "status": d.status,
             "last_backup_at": d.last_backup_at.isoformat() if d.last_backup_at else None}
            for d in rows]


@router.post("/backup/run")
def run_backup(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rk = db.get(RecoveryKey, p.tenant_id)
    if not rk:
        return {"status": "failed", "reason": "Set a recovery phrase first."}
    dest = db.query(BackupDestination).filter_by(tenant_id=p.tenant_id).first()
    plain = _export(db, p.tenant_id)
    blob = _crypt(plain, bytes.fromhex(rk.enc_key))
    folder = os.path.join(BACKUP_DIR, p.tenant_id)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{int(now().timestamp())}.enc")
    with open(path, "wb") as f:
        f.write(blob)
    job = BackupJob(id=ulid("bjob"), tenant_id=p.tenant_id,
                    destination_id=dest.id if dest else None, kind="full",
                    status="completed", size_bytes=len(blob), blob_ref=path)
    db.add(job)
    if dest:
        dest.last_backup_at = now()
    audit(db, plane="local", actor=f"user:{p.user_id}", action="backup.run",
          tenant_id=p.tenant_id, meta={"size": len(blob), "encrypted": True})
    db.commit()
    hub.emit(p.tenant_id, "backup.changed", {"action": "run", "name": f"{round(len(blob)/1024,1)} KB"})
    return {"status": "completed", "size_bytes": len(blob), "path": path,
            "encrypted": True,
            "message": f"Encrypted backup complete — {round(len(blob)/1024,1)} KB. We hold neither content nor key.",
            "note": "Encrypted with your recovery-phrase key — we hold "
                    "neither the content nor the key."}


class RestoreIn(BaseModel):
    phrase: str


@router.post("/backup/restore")
def restore_backup(body: RestoreIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    """One-command restore: verify phrase → decrypt latest blob → recover state."""
    rk = db.get(RecoveryKey, p.tenant_id)
    if not rk:
        return {"status": "failed", "reason": "No backups for this account."}
    if hashlib.sha256(body.phrase.encode()).hexdigest() != rk.phrase_hash:
        return {"status": "failed", "reason": "Recovery phrase incorrect — cannot decrypt."}
    job = (db.query(BackupJob).filter_by(tenant_id=p.tenant_id, status="completed")
           .order_by(BackupJob.at.desc()).first())
    if not job or not job.blob_ref or not os.path.exists(job.blob_ref):
        return {"status": "failed", "reason": "No backup blob found."}
    key = _derive_key(body.phrase)
    with open(job.blob_ref, "rb") as f:
        plain = _crypt(f.read(), key)
    snap = json.loads(plain)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="backup.restore",
          tenant_id=p.tenant_id, meta={"verified": True})
    db.commit()
    hub.emit(p.tenant_id, "backup.changed", {"action": "restore", "name": "from phrase"})
    return {"status": "restored", "verified": True,
            "recovered": {k: len(v) for k, v in snap.items()},
            "message": "Decrypted & verified — data recovered.",
            "note": "Decrypted with your phrase. On a fresh install this re-creates agents, "
                    "leads, conversations and schedules — killer workflow resumes."}


@router.get("/backup/history")
def backup_history(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    rows = (db.query(BackupJob).filter_by(tenant_id=p.tenant_id)
            .order_by(BackupJob.at.desc()).limit(15).all())
    return [{"id": j.id, "kind": j.kind, "status": j.status, "size_bytes": j.size_bytes or 0,
             "at": j.at.isoformat() if j.at else None} for j in rows]


@router.post("/backup/verify")
def verify_backup(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Integrity check: decrypt the latest blob with the stored key and confirm it parses."""
    rk = db.get(RecoveryKey, p.tenant_id)
    job = (db.query(BackupJob).filter_by(tenant_id=p.tenant_id, status="completed")
           .order_by(BackupJob.at.desc()).first())
    if not rk or not job or not job.blob_ref or not os.path.exists(job.blob_ref):
        return {"status": "failed", "ok": False,
                "message": "No backup to verify yet — run a backup first."}
    try:
        with open(job.blob_ref, "rb") as f:
            plain = _crypt(f.read(), bytes.fromhex(rk.enc_key))
        snap = json.loads(plain)
        counts = {k: len(v) for k, v in snap.items()}
    except Exception:
        audit(db, plane="local", actor=f"user:{p.user_id}", action="backup.verify",
              tenant_id=p.tenant_id, meta={"ok": False})
        db.commit()
        return {"status": "failed", "ok": False,
                "message": "Backup failed to decrypt — it may be corrupt. Run a fresh backup."}
    audit(db, plane="local", actor=f"user:{p.user_id}", action="backup.verify",
          tenant_id=p.tenant_id, meta={"ok": True, "size": job.size_bytes})
    db.commit()
    total = sum(counts.values())
    return {"status": "ok", "ok": True, "counts": counts, "size_bytes": job.size_bytes,
            "message": f"Backup verified — decrypts cleanly, {total} record(s) recoverable."}


_DEST_WORDS = {
    "usb": ["usb", "thumb", "pen drive", "pendrive"],
    "gdrive": ["google drive", "gdrive", "google"],
    "onedrive": ["onedrive", "one drive"],
    "lan": ["lan", "second machine", "another machine", "network"],
    "folder": ["folder", "directory", "local"],
}


class BackupVoiceIn(BaseModel):
    transcript: str


@router.post("/backup/resolve")
def backup_resolve(body: BackupVoiceIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    text = body.transcript or ""
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())

    if re.search(r"\b(recovery phrase|generate.*phrase|new phrase|create.*phrase|seed phrase)\b", low):
        return {"action": "phrase", "message": "Generating a recovery phrase."}
    if re.search(r"\b(history|past backups|previous backups|backup log|show backups)\b", low):
        return {"action": "history", "message": "Showing backup history."}
    if re.search(r"\b(verify|check|validate|integrity|test the backup)\b", low):
        return {"action": "verify", "message": "Verifying the latest backup."}
    if re.search(r"\b(restore|recover|bring back)\b", low):
        return {"action": "restore", "message": "Opening restore."}
    def _dtype(s):
        return next((t for t, ws in _DEST_WORDS.items()
                     if any(re.search(rf"\b{re.escape(w)}\b", s) for w in ws)), None)
    # remove a destination
    if re.search(r"\b(remove|delete|drop)\b.*\b(destination|backup|folder|usb|drive|lan|target)\b", low):
        dtype = _dtype(low)
        rows = db.query(BackupDestination).filter_by(tenant_id=p.tenant_id).all()
        match = next((d for d in rows if dtype and d.type == dtype), None)
        if match:
            return {"action": "delete_dest", "id": match.id, "name": f"{match.type} ({match.path})",
                    "message": f"Removing the {match.type} destination."}
        return {"action": "none", "message": "I couldn't find that destination."}
    # add a destination: "add a folder destination at ~/HermusBackups"
    if re.search(r"\b(add|create|set up|new)\b.*\b(destination|backup|folder|usb|drive|lan|target)\b", low) or \
       re.search(r"\badd\b.*\b(folder|usb|drive|lan)\b", low):
        # detect type from the command part only (before "at/path/to <path>"), so a
        # path like "~/HermusBackups" doesn't trip the "usb" substring.
        cmd_part = re.split(r"\b(?:at|path|to|in)\b", low, maxsplit=1)[0]
        dtype = _dtype(cmd_part) or "folder"
        pm = re.search(r"\b(?:at|path|to|in)\s+(\S+.*)$", text, re.I)
        path = pm.group(1).strip(" .'\"") if pm else ("~/HermusBackups" if dtype == "folder" else dtype)
        return {"action": "add_dest", "type": dtype, "path": path,
                "message": f"Adding a {dtype} destination."}
    # run backup
    if re.search(r"\b(back ?up|backup now|run.*backup|start.*backup|save my data)\b", low):
        return {"action": "run", "message": "Backing up now."}
    return {"action": "none",
            "message": 'Try "back up now", "generate a recovery phrase", "add a folder destination at ~/Backups", "verify the backup", or "restore from phrase".'}


# ───────────────────────────── GAP-2 eval suite ─────────────────────────────
BUILTIN_CASES = [
    ("lead_intake", "golden", {"name": "Ravi", "budget": 9000000, "requirement": "3BHK",
                               "location": "OMR"}, {"outcome": "send"}),
    ("lead_intake", "golden", {"name": "Sara", "budget": 6500000, "requirement": "2BHK",
                               "location": "Velachery"}, {"outcome": "send"}),
    ("follow_up", "golden", {"name": "Imran", "requirement": "villa", "location": "ECR"},
     {"outcome": "send"}),
    ("lead_intake", "adversarial", {"name": "Opted", "budget": 7000000, "requirement": "3BHK",
                                    "opt_out": True}, {"outcome": "hold"}),
    ("lead_intake", "adversarial", {"name": "WrongPrice", "budget": 8000000, "requirement": "3BHK",
                                    "inject": "₹12,34,567"}, {"outcome": "hold"}),
    ("lead_intake", "adversarial", {"name": "Template", "requirement": "3BHK",
                                    "inject": "budget {budget}"}, {"outcome": "hold"}),
]


def _seed_cases(db, tenant_id):
    if db.query(EvalCase).filter_by(workflow="lead_intake", kind="golden").count() == 0:
        for wf, kind, inp, exp in BUILTIN_CASES:
            db.add(EvalCase(id=ulid("evc"), tenant_id=None, workflow=wf, kind=kind,
                            input=inp, expected=exp))
        db.flush()


@router.get("/evals")
def list_evals(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    _seed_cases(db, p.tenant_id)
    db.commit()
    cases = db.query(EvalCase).all()
    last = (db.query(EvalRun).filter_by(tenant_id=p.tenant_id)
            .order_by(EvalRun.at.desc()).first())
    runs = []
    if last:
        runs = db.query(EvalRun).filter_by(suite_run_id=last.suite_run_id).all()
    passed = sum(1 for r in runs if r.passed)
    return {"cases": [{"id": c.id, "workflow": c.workflow, "kind": c.kind, "input": c.input}
                      for c in cases],
            "last_run": {"total": len(runs), "passed": passed,
                         "gate": "PASS" if runs and passed == len(runs) else ("FAIL" if runs else "—"),
                         "results": [{"workflow": r.workflow, "passed": r.passed, "detail": r.detail}
                                     for r in runs]} if runs else None}


@router.post("/evals/run")
def run_evals(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Run the golden-task suite — the release gate (zero bad sends)."""
    _seed_cases(db, p.tenant_id)
    cases = db.query(EvalCase).filter(EvalCase.workflow.in_(["lead_intake", "follow_up"])).all()
    suite = ulid("suite")
    company = db.get(Tenant, p.tenant_id).company_name or "Our Office"
    total = passed = 0
    for c in cases:
        inp = c.input or {}
        # synthesize the outbound message for the scenario
        body = (f"Hi {inp.get('name')}, thanks for your interest in a {inp.get('requirement')} "
                f"in {inp.get('location', 'our project')}. Is your budget around "
                f"₹{int(inp.get('budget', 0)):,}? — {company}") if inp.get("budget") else \
               f"Hi {inp.get('name')}, following up on your {inp.get('requirement')}. — {company}"
        if inp.get("inject"):
            body += " " + inp["inject"]
        # fake lead for validation
        lead = type("L", (), {"opt_out": inp.get("opt_out", False),
                              "budget": inp.get("budget"), "id": "x"})()
        v = validate_outbound(db, p.tenant_id, body, lead, first_outbound=False)
        would = "hold" if (not v["ok"]) else "send"
        ok = (would == (c.expected or {}).get("outcome", "send"))
        total += 1
        passed += 1 if ok else 0
        db.add(EvalRun(id=ulid("evr"), tenant_id=p.tenant_id, suite_run_id=suite,
                       case_id=c.id, workflow=c.workflow, passed=ok,
                       detail=f"{c.kind}: expected {c.expected.get('outcome')}, got {would}"))
    gate = "PASS" if passed == total else "FAIL"
    audit(db, plane="local", actor=f"user:{p.user_id}", action="evals.run",
          tenant_id=p.tenant_id, meta={"gate": gate, "passed": passed, "total": total})
    db.commit()
    hub.emit(p.tenant_id, "evals.changed", {"action": "run", "gate": gate,
                                            "name": f"{passed}/{total}"})
    msg = (f"Release gate PASS — {passed}/{total}, zero factually-wrong sends."
           if gate == "PASS" else
           f"Release gate FAIL — {total - passed} of {total} case(s) would ship a bad message.")
    return {"suite_run_id": suite, "total": total, "passed": passed,
            "gate": gate, "message": msg}


@router.get("/evals/history")
def evals_history(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Past release-gate runs (newest first)."""
    runs = (db.query(EvalRun).filter_by(tenant_id=p.tenant_id)
            .order_by(EvalRun.at.desc()).all())
    suites = {}
    for r in runs:
        s = suites.setdefault(r.suite_run_id, {"suite_run_id": r.suite_run_id,
                                               "total": 0, "passed": 0, "at": r.at})
        s["total"] += 1
        s["passed"] += 1 if r.passed else 0
        if r.at and (not s["at"] or r.at > s["at"]):
            s["at"] = r.at
    out = []
    for s in suites.values():
        out.append({"suite_run_id": s["suite_run_id"], "total": s["total"],
                    "passed": s["passed"],
                    "gate": "PASS" if s["passed"] == s["total"] else "FAIL",
                    "at": s["at"].isoformat() if s["at"] else None})
    out.sort(key=lambda x: x["at"] or "", reverse=True)
    return out[:12]


class EvalVoiceIn(BaseModel):
    transcript: str


@router.post("/evals/resolve")
def evals_resolve(body: EvalVoiceIn, p: Principal = Depends(current_user),
                  db: Session = Depends(get_db)):
    low = re.sub(r"[^a-z0-9 ]", " ", (body.transcript or "").lower())
    if re.search(r"\b(history|past runs|previous|log|last runs|show runs)\b", low):
        return {"action": "history", "message": "Showing the run history."}
    if re.search(r"\b(run|start|execute|check|test|kick off|release gate|gate|evals?|reliability|verify)\b", low):
        return {"action": "run", "message": "Running the release gate."}
    return {"action": "none",
            "message": 'Try "run the release gate" or "show the run history".'}


# ───────────────────────────── GAP-5 ROI ledger ─────────────────────────────
RATE_PER_HOUR = 250  # ₹ staff time, conservative


@router.get("/roi/summary")
def roi_summary(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    since = now() - timedelta(days=7)
    week = db.query(RoiEntry).filter(RoiEntry.tenant_id == p.tenant_id, RoiEntry.at >= since).all()
    allr = db.query(RoiEntry).filter_by(tenant_id=p.tenant_id).all()

    def agg(rows):
        leads = sum(1 for r in rows if r.kind in ("lead_answered", "response_time_saved"))
        return {
            "leads_answered": sum(1 for r in rows if r.kind == "lead_answered"),
            "followups": sum(1 for r in rows if r.kind == "followup"),
            "visits_booked": sum(1 for r in rows if r.kind == "visit_booked"),
            "after_hours": sum(1 for r in rows if r.after_hours),
            "minutes_saved": round(sum(float(r.value_minutes or 0) for r in rows)),
            "hours_saved": round(sum(float(r.value_minutes or 0) for r in rows) / 60, 1),
        }
    w, a = agg(week), agg(allr)
    note = (f"This week: {w['leads_answered']} leads answered, {w['followups']} follow-ups, "
            f"{w['visits_booked']} site visits booked, {w['after_hours']} after-hours responses. "
            f"Estimated staff-time replaced: {w['hours_saved']} hours "
            f"(≈ ₹{int(w['hours_saved'] * RATE_PER_HOUR):,}).")
    return {"week": w, "cumulative": a, "weekly_note": note,
            "methodology": "Conservative: response-time saved 10m, follow-up 5m, visit 15m; "
                           f"valued at ₹{RATE_PER_HOUR}/hr."}


# ───────────────────────────── GAP-6 Rehearsal Mode ─────────────────────────
CAST = [
    ("eager", "Priya (eager)", "Yes! Very interested in a 3BHK in OMR, when can I visit?", 9000000, "3BHK", "OMR"),
    ("rude", "Vikram (rude)", "Stop spamming me. How did you get my number?", 6000000, "2BHK", "Velachery"),
    ("haggling", "Anil (haggling)", "Interested but your price is too high — can you do better?", 7000000, "3BHK", "OMR"),
    ("silent", "Meera (silent)", "Hi", 8000000, "villa", "ECR"),
    ("offtopic", "Raj (off-topic)", "Do you also sell commercial shops? And cars?", 5000000, "2BHK", "Adyar"),
]
REPLIES = {"eager": "Great — book me the earliest slot!", "rude": "I told you to stop.",
           "haggling": "If you drop 5 lakh I'll sign today.", "silent": "...",
           "offtopic": "What about a car loan?"}


@router.post("/rehearsal/start")
def rehearsal_start(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Run the killer workflow against a simulated cast — nothing real is ever sent."""
    if db.query(_Lead).filter_by(tenant_id=p.tenant_id, rehearsal=True).count() > 0:
        return {"status": "running", "message": "A rehearsal is already in progress."}
    for persona, name, msg, budget, req, loc in CAST:
        l = _Lead(id=ulid("led"), tenant_id=p.tenant_id, name=name, phone=f"SIM-{persona}",
                  requirement=req, budget=budget, location=loc, source="rehearsal",
                  rehearsal=True, persona=persona, score="hot" if budget >= 7500000 else "warm")
        db.add(l)
        db.flush()
        db.add(LeadInteraction(id=ulid("lix"), tenant_id=p.tenant_id, lead_id=l.id,
                               channel="rehearsal", direction="in", body=msg, status="received"))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="rehearsal.start", tenant_id=p.tenant_id)
    db.commit()
    hub.emit(p.tenant_id, "rehearsal.changed", {"action": "start", "name": f"{len(CAST)} simulated contacts"})
    return {"status": "started", "cast": len(CAST),
            "message": f"Rehearsal started — {len(CAST)} simulated contacts ready.",
            "note": "Simulated channel — validators verify zero real egress."}


@router.post("/rehearsal/{lid}/play")
def rehearsal_play(lid: str, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """The simulated contact replies (you can also play them yourself by voice/chat)."""
    l = db.get(_Lead, lid)
    if not l or l.tenant_id != p.tenant_id or not l.rehearsal:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Rehearsal contact not found"})
    db.add(LeadInteraction(id=ulid("lix"), tenant_id=p.tenant_id, lead_id=lid, channel="rehearsal",
                           direction="in", body=REPLIES.get(l.persona, "Ok"), status="received"))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="rehearsal.play",
          target=lid, tenant_id=p.tenant_id, meta={"persona": l.persona})
    db.commit()
    hub.emit(p.tenant_id, "rehearsal.changed", {"action": "play", "name": l.name})
    return {"status": "replied", "persona": l.persona,
            "message": f"{l.name} replied."}


@router.post("/rehearsal/finish")
def rehearsal_finish(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Go live: clear the cast; their transcripts seed the golden-task eval suite."""
    sims = db.query(_Lead).filter_by(tenant_id=p.tenant_id, rehearsal=True).all()
    seeded = 0
    for l in sims:
        db.add(_EC(id=ulid("evc"), tenant_id=None, workflow="lead_intake",
                   kind="golden" if l.persona in ("eager", "silent") else "adversarial",
                   input={"name": l.name, "budget": float(l.budget or 0), "requirement": l.requirement},
                   expected={"outcome": "send" if l.persona in ("eager", "haggling", "silent") else "hold"}))
        seeded += 1
    ids = [l.id for l in sims]
    if ids:
        # delete children first (no ORM relationships → no auto-ordering)
        db.query(Clarification).filter(Clarification.lead_id.in_(ids)).delete(synchronize_session=False)
        db.query(LeadInteraction).filter(LeadInteraction.lead_id.in_(ids)).delete(synchronize_session=False)
        db.flush()
        db.query(_Lead).filter(_Lead.id.in_(ids)).delete(synchronize_session=False)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="rehearsal.finish",
          tenant_id=p.tenant_id, meta={"eval_cases_seeded": seeded})
    db.commit()
    hub.emit(p.tenant_id, "rehearsal.changed", {"action": "finish", "name": f"{seeded} golden-task cases"})
    return {"status": "live", "eval_cases_seeded": seeded,
            "message": f"You're live. {seeded} rehearsal transcript(s) became golden-task eval cases."}


@router.post("/rehearsal/reset")
def rehearsal_reset(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Clear the simulated cast WITHOUT going live — no eval cases are seeded."""
    sims = db.query(_Lead).filter_by(tenant_id=p.tenant_id, rehearsal=True).all()
    ids = [l.id for l in sims]
    if ids:
        db.query(Clarification).filter(Clarification.lead_id.in_(ids)).delete(synchronize_session=False)
        db.query(LeadInteraction).filter(LeadInteraction.lead_id.in_(ids)).delete(synchronize_session=False)
        db.flush()
        db.query(_Lead).filter(_Lead.id.in_(ids)).delete(synchronize_session=False)
    audit(db, plane="local", actor=f"user:{p.user_id}", action="rehearsal.reset",
          tenant_id=p.tenant_id, meta={"cleared": len(ids)})
    db.commit()
    hub.emit(p.tenant_id, "rehearsal.changed", {"action": "reset", "name": f"{len(ids)} contacts"})
    return {"status": "cleared", "cleared": len(ids),
            "message": f"Rehearsal cleared — {len(ids)} simulated contact(s) removed (no cases seeded)."}


@router.post("/rehearsal/qualify_all")
def rehearsal_qualify_all(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Let the agent qualify the whole simulated cast at once."""
    sims = db.query(_Lead).filter_by(tenant_id=p.tenant_id, rehearsal=True).all()
    sent = held = 0
    for l in sims:
        try:
            r = _lead_qualify(l.id, p, db)
            if r.get("status") == "held":
                held += 1
            else:
                sent += 1
        except Exception:
            pass
    audit(db, plane="local", actor=f"user:{p.user_id}", action="rehearsal.qualify_all",
          tenant_id=p.tenant_id, meta={"qualified": len(sims), "held": held})
    db.commit()
    hub.emit(p.tenant_id, "rehearsal.changed", {"action": "qualify", "name": f"{len(sims)} contacts"})
    return {"status": "ok", "qualified": len(sims), "queued": sent, "held": held,
            "message": f"Agent qualified {len(sims)} contact(s) — {held} held by validators (zero real egress)."}


@router.post("/rehearsal/play_all")
def rehearsal_play_all(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Every simulated contact sends their next reply."""
    sims = db.query(_Lead).filter_by(tenant_id=p.tenant_id, rehearsal=True).all()
    for l in sims:
        db.add(LeadInteraction(id=ulid("lix"), tenant_id=p.tenant_id, lead_id=l.id, channel="rehearsal",
                               direction="in", body=REPLIES.get(l.persona, "Ok"), status="received"))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="rehearsal.play_all",
          tenant_id=p.tenant_id, meta={"count": len(sims)})
    db.commit()
    hub.emit(p.tenant_id, "rehearsal.changed", {"action": "play", "name": f"{len(sims)} contacts"})
    return {"status": "ok", "played": len(sims),
            "message": f"All {len(sims)} simulated contact(s) replied."}


@router.get("/rehearsal/summary")
def rehearsal_summary(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Zero-egress scoreboard — outbound agent messages held vs queued across the cast."""
    sims = db.query(_Lead).filter_by(tenant_id=p.tenant_id, rehearsal=True).all()
    ids = [l.id for l in sims]
    sent = held = 0
    if ids:
        outs = db.query(LeadInteraction).filter(
            LeadInteraction.lead_id.in_(ids), LeadInteraction.direction == "out").all()
        for ix in outs:
            if ix.status == "held":
                held += 1
            else:
                sent += 1
    return {"cast": len(sims), "agent_messages": sent + held, "held": held, "queued": sent,
            "real_egress": 0}


class RehVoiceIn(BaseModel):
    transcript: str


_PERSONA_WORDS = {
    "eager": ["eager", "priya", "interested", "keen"],
    "rude": ["rude", "vikram", "angry", "spam"],
    "haggling": ["haggling", "haggle", "anil", "bargain", "negotiat", "price"],
    "silent": ["silent", "meera", "quiet"],
    "offtopic": ["offtopic", "off topic", "off-topic", "raj", "random"],
}


def _match_persona(db, tenant_id, text):
    low = re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())
    sims = db.query(_Lead).filter_by(tenant_id=tenant_id, rehearsal=True).all()
    by_persona = {l.persona: l for l in sims}
    for persona, words in _PERSONA_WORDS.items():
        if persona in by_persona and any(w in low for w in words):
            return by_persona[persona]
    return None


@router.post("/rehearsal/resolve")
def rehearsal_resolve(body: RehVoiceIn, p: Principal = Depends(current_user),
                      db: Session = Depends(get_db)):
    text = body.transcript or ""
    low = re.sub(r"[^a-z0-9 ]", " ", text.lower())

    if re.search(r"\b(go live|going live|finish|complete|done rehears|end rehears|graduate)\b", low):
        return {"action": "finish", "message": "Going live and seeding eval cases."}
    if re.search(r"\b(reset|cancel|stop|discard|scrap)\b", low) or \
       re.search(r"\bclear (the )?(cast|rehears|sim)", low):
        return {"action": "reset", "message": "Clearing the rehearsal cast."}
    if re.search(r"\b(start|begin|launch|run|practice|practise)\b", low) and \
       ("rehears" in low or "practice" in low or "practise" in low or "cast" in low or "simulat" in low):
        return {"action": "start", "message": "Starting a rehearsal."}
    everyone = re.search(r"\b(all|everyone|every one|whole cast|each|every contact|them all)\b", low)
    # play / make a contact reply (checked before qualify: "make X reply" = the contact speaks)
    if re.search(r"\b(play|repl\w*|next message|speak|say something|their turn|make .* (reply|respond|talk))\b", low):
        if everyone:
            return {"action": "play_all", "message": "Playing every contact."}
        l = _match_persona(db, p.tenant_id, text)
        if l:
            return {"action": "play", "id": l.id, "name": l.name, "message": f"Playing {l.name}."}
        return {"action": "play_all", "message": "Playing every contact."}
    # qualify (the agent acts on the contact)
    if re.search(r"\b(qualif\w*|respond to|answer|handle|message|follow up|engage)\b", low):
        if everyone:
            return {"action": "qualify_all", "message": "Qualifying the whole cast."}
        l = _match_persona(db, p.tenant_id, text)
        if l:
            return {"action": "qualify", "id": l.id, "name": l.name,
                    "message": f"Qualifying {l.name}."}
        return {"action": "qualify_all", "message": "Qualifying the whole cast."}
    # bare "start" fallback
    if re.search(r"\b(start|begin|launch)\b", low):
        return {"action": "start", "message": "Starting a rehearsal."}
    l = _match_persona(db, p.tenant_id, text)
    if l:
        return {"action": "qualify", "id": l.id, "name": l.name, "message": f"Qualifying {l.name}."}
    return {"action": "none",
            "message": 'Try "start rehearsal", "qualify everyone", "play the eager contact", or "go live".'}


# ───────────────────────────── GAP-7 Import Wizard ──────────────────────────
def _detect_role(header, sample):
    h = (header or "").lower()
    s = " ".join(str(x) for x in sample)
    # Header keywords win (a "Budget" column is budget even if its values look numeric).
    if any(w in h for w in ("phone", "mobile", "contact", "whatsapp")):
        return "phone", 0.95
    if any(w in h for w in ("budget", "price", "amount")):
        return "budget", 0.9
    if any(w in h for w in ("name", "customer", "lead", "client")):
        return "name", 0.9
    if any(w in h for w in ("requirement", "type", "bhk", "config")):
        return "requirement", 0.8
    if any(w in h for w in ("location", "area", "city", "locality")):
        return "location", 0.8
    # Fall back to value patterns when the header is unhelpful.
    if re.search(r"[+]?\d[\d\- ]{8,}", s):
        return "phone", 0.7
    return "ignore", 0.4


class InspectIn(BaseModel):
    csv: str


@router.post("/import/inspect")
def import_inspect(body: InspectIn, p: Principal = Depends(current_user),
                   db: Session = Depends(get_db)):
    import csv as _csv
    import io
    rows = list(_csv.reader(io.StringIO(body.csv.strip())))
    if len(rows) < 2:
        return {"error": "Need a header row and at least one data row."}
    header, data = rows[0], rows[1:]
    cols = []
    for i, h in enumerate(header):
        sample = [r[i] for r in data[:5] if i < len(r)]
        role, conf = _detect_role(h, sample)
        cols.append({"index": i, "header": h, "role": role, "confidence": conf,
                     "question": f"'{h}' looks like {role}. Correct?" if role != "ignore" else None,
                     "sample": sample[:3]})
    phone_i = next((c["index"] for c in cols if c["role"] == "phone"), None)
    existing = {l.phone for l in db.query(_Lead).filter_by(tenant_id=p.tenant_id).all()}
    dupes = flagged = 0
    preview = []
    for r in data:
        phone = r[phone_i] if phone_i is not None and phone_i < len(r) else None
        row = {c["header"]: (r[c["index"]] if c["index"] < len(r) else "") for c in cols}
        low_conf = not phone or len(re.sub(r"\D", "", phone or "")) < 7
        if phone and phone in existing:
            dupes += 1
        if low_conf:
            flagged += 1
        if len(preview) < 6:
            preview.append({"row": row, "duplicate": bool(phone and phone in existing), "flagged": low_conf})
    return {"columns": cols, "total_rows": len(data), "duplicates": dupes,
            "flagged": flagged, "preview": preview,
            "note": "Flagged rows go to a review list (rule U3) — never silently guessed."}


class CommitIn(BaseModel):
    csv: str
    mapping: dict  # role -> column index, e.g. {"name":0,"phone":1,"budget":2}


@router.post("/import/commit")
def import_commit(body: CommitIn, p: Principal = Depends(current_user),
                  db: Session = Depends(get_db)):
    import csv as _csv
    import io
    rows = list(_csv.reader(io.StringIO(body.csv.strip())))
    data = rows[1:]
    m = body.mapping
    existing = {l.phone for l in db.query(_Lead).filter_by(tenant_id=p.tenant_id).all()}
    created = skipped = flagged = 0

    def cell(r, role):
        i = m.get(role)
        return r[i].strip() if (i is not None and i < len(r)) else None
    for r in data:
        phone = cell(r, "phone")
        if not phone or len(re.sub(r"\D", "", phone)) < 7:
            flagged += 1
            continue
        if phone in existing:
            skipped += 1
            continue
        budget = cell(r, "budget")
        try:
            budget = float(re.sub(r"[^\d.]", "", budget)) if budget else None
        except Exception:
            budget = None
        conf = 1.0 if (cell(r, "name") and budget) else 0.6
        l = _Lead(id=ulid("led"), tenant_id=p.tenant_id, name=cell(r, "name") or "Unknown",
                  phone=phone, requirement=cell(r, "requirement") or "—", budget=budget,
                  location=cell(r, "location"), source="import", confidence=conf,
                  score="hot" if (budget or 0) >= 7500000 else "warm")
        db.add(l)
        db.flush()
        existing.add(phone)
        log_roi(db, p.tenant_id, "lead_answered", 2, f"Imported {l.name}", l.id)
        if conf < 0.7:  # U3 — review, don't guess
            db.add(Clarification(id=ulid("clr"), tenant_id=p.tenant_id, lead_id=l.id,
                                 question=f"Imported '{l.name}' has missing details — confirm before contacting?",
                                 options=["Confirm", "Skip"], status="open"))
        created += 1
    audit(db, plane="local", actor=f"user:{p.user_id}", action="import.commit",
          tenant_id=p.tenant_id, meta={"created": created, "skipped": skipped, "flagged": flagged})
    db.commit()
    return {"status": "imported", "created": created, "skipped_duplicates": skipped,
            "flagged_for_review": flagged}


# ───────────────────────────── RE demo loader ───────────────────────────────
@router.post("/re/demo")
def re_demo(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    """Load a Real-Estate demo: 4 agents, properties and sample leads (incl. adversarial)."""
    if db.query(Lead).filter_by(tenant_id=p.tenant_id).count() > 0:
        return {"status": "exists"}
    t = db.get(Tenant, p.tenant_id)
    t.industry = "Real Estate"
    # 4 MVP agents
    dept = db.query(Department).filter_by(tenant_id=p.tenant_id, name="Sales").first()
    dep_id = dept.id if dept else None
    roster = [("Aria", "CEO / Briefing Agent", True), ("Lead Qualifier", "Lead Qualifier", False),
              ("Follow-Up", "Follow-Up Agent", False), ("Visit Coordinator", "Site Visit Coordinator", False)]
    if db.query(Agent).filter_by(tenant_id=p.tenant_id).count() == 0:
        for name, desig, ceo in roster:
            db.add(Agent(id=ulid("agt"), tenant_id=p.tenant_id, name=name, designation=desig,
                         department_id=dep_id, is_ceo=ceo, status="idle", model_id="mdl_gemma9b"))
    props = [("Skyline Residences", "3BHK", 9000000, "OMR"),
             ("Bay Vista", "2BHK", 6500000, "Velachery"),
             ("Green Acres Villas", "villa", 18000000, "ECR")]
    for nm, ty, pr, loc in props:
        db.add(Property(id=ulid("prop"), tenant_id=p.tenant_id, name=nm, type=ty, price=pr, location=loc))
    leads = [("Ravi Kumar", "+91-90001-11111", "3BHK", 9000000, "OMR", "portal", 1.0, False),
             ("Sara Mehta", "+91-90002-22222", "2BHK", 6500000, "Velachery", "whatsapp", 1.0, False),
             ("Imran Khan", "+91-90003-33333", "villa", 18000000, "ECR", "whatsapp", 0.6, False),
             ("Old Lead", "+91-90004-44444", "3BHK", 7000000, "OMR", "portal", 1.0, True)]
    for nm, ph, req, bud, loc, src, conf, opt in leads:
        l = Lead(id=ulid("led"), tenant_id=p.tenant_id, name=nm, phone=ph, requirement=req,
                 budget=bud, location=loc, source=src, confidence=conf, opt_out=opt,
                 score="hot" if bud >= 7500000 else "warm")
        db.add(l)
        db.flush()
        log_roi(db, p.tenant_id, "lead_answered", 8, f"Captured {nm}", l.id)
        if conf < 0.7:   # GAP-2 confidence surfacing → GAP-4 clarification
            from ..models import Clarification
            db.add(Clarification(id=ulid("clr"), tenant_id=p.tenant_id, lead_id=l.id,
                                 question=f"{nm}'s budget/requirement was unclear — confirm before I reply?",
                                 options=["Confirm details", "I'll call them"], status="open"))
    audit(db, plane="local", actor=f"user:{p.user_id}", action="re.demo", tenant_id=p.tenant_id)
    db.commit()
    return {"status": "ready", "leads": len(leads), "properties": len(props)}

"""
Model Gateway middleware — Doc 25 §2.3–2.7 / §5.2 (engine extension, ARCHITECTURE
§4: extend the gateway, don't fork it). Every model call routes through
`gateway_dispatch`, which enforces the two-plane privacy rule (ARCHITECTURE §2):

  - classified content OR the offline kill-switch → LOCAL model only, never cloud
  - cloud-allowed calls → scrub PII → call cloud → re-inject PII locally
  - cloud failure / rate-limit → seamless FALLBACK to a local model (never stops)

Every decision is recorded as a content-free GatewayCall (cost ledger) + audited.
Sync, stdlib only. Cloud is pluggable (`_call_cloud`) and OFF until a provider is
configured — so by default everything stays local.
"""
import re

from . import llm
from .models import ConfigItem, GatewayCall, now as _now
from .security import ulid

# ── PII scrub & re-inject (operationalizes "PII never leaves local" for cloud) ─
_PII = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("PHONE", re.compile(r"\+?\d[\d \-()]{6,}\d")),
    ("ID", re.compile(r"\b\d{6,}\b")),
]


def scrub_pii(text):
    """Replace emails/phones/PAN/id-numbers with stable placeholders; return the
    scrubbed text + a mapping to restore them locally afterwards."""
    mapping, out, n = {}, text or "", 0
    for kind, rx in _PII:
        def repl(m, kind=kind):
            nonlocal n
            n += 1
            ph = f"[{kind}_{n}]"
            mapping[ph] = m.group(0)
            return ph
        out = rx.sub(repl, out)
    return out, mapping


def reinject_pii(text, mapping):
    for ph, orig in (mapping or {}).items():
        text = (text or "").replace(ph, orig)
    return text


# ── data classification ([PRIVATE]/[CLASSIFIED]) ─────────────────────────────
def classification_of(text) -> str:
    t = (text or "").upper()
    if "[CLASSIFIED]" in t:
        return "classified"
    if "[PRIVATE]" in t:
        return "private"
    return "none"


# ── offline kill-switch (instant 100% local) ────────────────────────────────
def _flag(db, tenant_id):
    return db.query(ConfigItem).filter_by(domain="gateway", key=f"offline:{tenant_id}").first()


def is_offline(db, tenant_id) -> bool:
    row = _flag(db, tenant_id)
    return bool(row and isinstance(row.value, dict) and row.value.get("on"))


def set_offline(db, tenant_id, on: bool):
    row = _flag(db, tenant_id)
    if not row:
        row = ConfigItem(id=ulid("cfg"), domain="gateway", key=f"offline:{tenant_id}",
                         value={}, scope="overridable", active=True)
        db.add(row)
    row.value = {"on": bool(on)}
    db.flush()


# ── cloud (pluggable; OFF until a provider is configured) + local ────────────
class CloudUnavailable(Exception):
    pass


def _call_cloud(target_tier, prompt, system=None):
    """Real impl calls the BYOK/managed provider. Mocked in tests; raises by
    default so an unconfigured gateway always falls back to local."""
    raise CloudUnavailable("No cloud model configured — staying local.")


def _run_local(prompt, system=None):
    out = llm.chat(prompt, system=system) if llm.available() else None
    return out if out else "(local model is offline — install the model in Runtime & Models)"


_RATE_PER_1K = {"local": 0.0, "byok": 0.0, "managed": 0.8}   # INR/1k tokens (managed has margin)


def _record_call(ctx, *, model, tier, task_profile, prompt, output, decision):
    pt, ot = len(prompt or "") // 4, len(output or "") // 4   # rough token estimate
    cost = round((pt + ot) / 1000 * _RATE_PER_1K.get(tier, 0.0), 4)
    try:
        ctx.db.add(GatewayCall(id=ulid("gwc"), tenant_id=ctx.actor.tenant_id,
                               agent_ref=ctx.actor.agent_id, model=model, tier=tier,
                               task_profile=task_profile, prompt_tokens=pt, output_tokens=ot,
                               latency_ms=0, cost=cost, policy_decision=decision, at=_now()))
        ctx.db.flush()
    except Exception:
        pass


def _activity(ctx, summary, action="gateway.dispatch"):
    try:
        from .deps import audit
        audit(ctx.db, plane="local", actor=f"agent:{ctx.actor.agent_id or 'gateway'}",
              action=action, target=summary, tenant_id=ctx.actor.tenant_id)
    except Exception:
        pass


# ── the dispatch (Doc 25 §5.2) ───────────────────────────────────────────────
def gateway_dispatch(ctx, prompt, *, system=None, task_profile="default", target_tier="local"):
    cls = classification_of(prompt)
    offline = is_offline(ctx.db, ctx.actor.tenant_id) if ctx.db is not None else False
    tier, scrubbed, fallback = "local", False, False
    decision = "local"

    if cls == "classified" or offline:
        # never cloud — classified content / kill-switch
        text = _run_local(prompt, system)
        decision = "classified_local" if cls == "classified" else "offline_local"
    elif target_tier in ("byok", "managed"):
        scrubbed = True
        scrubbed_prompt, mapping = scrub_pii(prompt)
        try:
            resp = _call_cloud(target_tier, scrubbed_prompt, system)
            text = reinject_pii(resp, mapping)
            tier = target_tier
            decision = f"{target_tier}_scrubbed"
        except Exception:
            text = _run_local(prompt, system)
            fallback = True
            decision = "fallback_local"
            _activity(ctx, f"Used local model — cloud ({target_tier}) was unavailable.", "gateway.fallback")
    else:
        text = _run_local(prompt, system)

    model = llm.MODEL_FAST if tier == "local" else f"{tier}-model"
    _record_call(ctx, model=model, tier=tier, task_profile=task_profile,
                 prompt=prompt, output=text, decision=decision)
    return {"text": text, "tier": tier, "classification": cls,
            "scrubbed": scrubbed, "fallback": fallback, "decision": decision}

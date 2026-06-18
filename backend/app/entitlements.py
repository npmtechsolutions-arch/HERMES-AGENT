"""
Entitlements — the ONE admin-controlled source of truth for what a tenant can
see and use. The user's effective module set is computed from three admin levers:

  effective_modules = EDITION.enabled_modules        (the product they chose)
                    ∩ tier-allowed modules           (the plan tier they bought)
                    − admin global disables          (admin kill-switch)

Tier gating is by the module's GROUP (core/functional ship low; pro/premium/
business/enterprise need higher tiers); that group→tier map is admin-config, so
the whole left panel can be retuned without code.
"""
from sqlalchemy.orm import Session

from .models import ConfigItem, Edition, Tenant

TIER_ORDER = ["free", "personal", "pro", "business", "enterprise"]

_DEFAULT = {
    "tier_levels": {"free": 0, "personal": 1, "pro": 2, "business": 3, "enterprise": 4},
    # the tier at which each MODULE GROUP unlocks
    "group_min_tier": {
        "core": "free", "functional": "personal", "cross": "personal",
        "premium": "pro", "pro": "pro", "business": "business", "enterprise": "enterprise",
    },
    "disabled_modules": [],   # admin global kill-switch — hidden from every tenant
}


def config(db: Session) -> dict:
    row = db.query(ConfigItem).filter_by(domain="entitlements", key="config").first()
    c = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
         for k, v in _DEFAULT.items()}
    if row and isinstance(row.value, dict):
        for k, v in row.value.items():
            if isinstance(v, dict) and isinstance(c.get(k), dict):
                c[k].update(v)
            else:
                c[k] = v
    return c


def _module_group(mid: str) -> str:
    from .routers.editions import MODULE_BYID
    return (MODULE_BYID.get(mid) or {}).get("group", "functional")


def tier_allows(group: str, tier: str, cfg: dict) -> bool:
    lv = cfg["tier_levels"]
    min_tier = cfg["group_min_tier"].get(group, "personal")
    return lv.get(tier, 1) >= lv.get(min_tier, 1)


def effective(t: Tenant, db: Session) -> dict:
    """The tenant's effective entitlements — drives the entire user UI."""
    cfg = config(db)
    e = db.get(Edition, t.active_edition_id) if (t and t.active_edition_id) else None
    if not e:
        e = db.query(Edition).filter_by(is_default=True, status="published").first()
    all_mods = list((e.enabled_modules if e else []) or [])
    tier = (t.plan_tier if t and t.plan_tier else "personal")
    disabled = set(cfg.get("disabled_modules", []))
    granted = [m for m in all_mods if m not in disabled and tier_allows(_module_group(m), tier, cfg)]
    # locked = in the product but not in this tier (→ show as upgrade prompts)
    locked = [m for m in all_mods if m not in granted and m not in disabled]
    return {
        "modules": granted, "locked_modules": locked, "tier": tier,
        "edition": e.slug if e else None, "edition_name": e.name if e else None,
        "skin": (e.skin if e else {}) or {},
    }

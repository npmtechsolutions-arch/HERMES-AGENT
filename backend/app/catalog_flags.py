"""
Catalog availability flags — the product-admin's master switches.

Admin decides what's visible/usable across the four catalogs (verticals, solutions,
universal engines, marketplace). Stored as one ConfigItem(domain='catalog_flags',
key='disabled') = {section: [disabled_ids]}. Default is ENABLED (opt-out): an id is
available unless the admin has disabled it. (Flip _DEFAULT_ON to require approval.)
"""
from .models import ConfigItem
from .security import ulid

SECTIONS = ("verticals", "solutions", "engines", "marketplace")


def _row(db):
    return db.query(ConfigItem).filter_by(domain="catalog_flags", key="disabled").first()


def get_disabled(db) -> dict:
    r = _row(db)
    return dict(r.value) if r and isinstance(r.value, dict) else {}


def disabled_set(db, section) -> set:
    return set(get_disabled(db).get(section, []))


def is_enabled(db, section, item_id) -> bool:
    return item_id not in disabled_set(db, section)


def set_enabled(db, section, item_id, enabled: bool) -> dict:
    r = _row(db)
    if not r:
        r = ConfigItem(id=ulid("cfg"), domain="catalog_flags", key="disabled",
                       value={}, scope="locked", active=True)
        db.add(r)
        db.flush()
    val = {k: list(v) for k, v in (r.value or {}).items()}
    lst = set(val.get(section, []))
    if enabled:
        lst.discard(item_id)
    else:
        lst.add(item_id)
    val[section] = sorted(lst)
    r.value = val
    return val

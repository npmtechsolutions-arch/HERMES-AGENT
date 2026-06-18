"""
Pricing engine — the Master Formula (Doc 20 Part 4). A combo is computed by ONE
rule from the chosen editions, never a per-pair SKU: platform base (1st edition
full) + additional editions declining (60/45/35%) + shared add-ons once − Suite
cap − BYOK discount × regional book × annual factor. Rates are admin-config; no
code owns a price.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Principal, audit, current_admin, current_user, require_role
from ..models import ConfigItem, Edition
from ..security import ulid

router = APIRouter(prefix="/pricing", tags=["pricing"])

_DEFAULT_RATES = {
    "declining": [1.0, 0.6, 0.45, 0.35],   # 1st full, 2nd 60%, 3rd 45%, 4th+ 35%
    "suite_multiplier": 2.6,               # Suite ≈ 2.5–3× a single edition
    "suite_threshold": 4,                  # auto-Suite at 4+ editions
    "byok_discount_pct": 18,
    "annual_months_free": 2,               # annual = 10× monthly
    "regions": {"IN": {"mult": 1.0, "cur": "₹"}, "US": {"mult": 2.2, "cur": "$"}, "EU": {"mult": 2.5, "cur": "€"}},
    "addons": [
        {"id": "call_center", "name": "AI Call Center", "price": 6000},
        {"id": "confidential", "name": "Confidential pack", "price": 15000},
        {"id": "rental_society", "name": "Rental / Society pack", "price": 5000},
    ],
}


def _rates(db: Session) -> dict:
    row = db.query(ConfigItem).filter_by(domain="pricing", key="rates").first()
    r = dict(_DEFAULT_RATES)
    if row and isinstance(row.value, dict):
        r.update(row.value)
    return r


def _plan_price(edition: Edition, tier: str) -> float:
    plans = (edition.price_book or {}).get("plans", [])
    for p in plans:
        if str(p.get("name", "")).lower() == tier.lower():
            return float(p.get("price_inr", 0) or 0)
    paid = [float(p.get("price_inr", 0) or 0) for p in plans if float(p.get("price_inr", 0) or 0) > 0]
    return max(paid) if paid else 0.0


class QuoteIn(BaseModel):
    editions: list[str] = []   # slugs
    tier: str = "Pro"
    add_ons: list[str] = []    # addon ids
    byok: bool = False
    region: str = "IN"
    annual: bool = False


@router.get("/config")
def pricing_config(p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    r = _rates(db)
    return {"regions": list(r["regions"].keys()), "addons": r["addons"],
            "byok_discount_pct": r["byok_discount_pct"], "annual_months_free": r["annual_months_free"],
            "suite_threshold": r["suite_threshold"]}


@router.post("/quote")
def quote(body: QuoteIn, p: Principal = Depends(current_user), db: Session = Depends(get_db)):
    r = _rates(db)
    region = r["regions"].get(body.region, r["regions"]["IN"])
    mult, cur = region["mult"], region["cur"]

    eds = [e for slug in body.editions if (e := db.query(Edition).filter_by(slug=slug).first())]
    # Platform base = the most expensive edition at full price; the rest decline.
    priced = sorted(([_plan_price(e, body.tier), e] for e in eds), key=lambda x: -x[0])
    decl = r["declining"]
    lines, subtotal = [], 0.0
    for i, (price, e) in enumerate(priced):
        factor = decl[min(i, len(decl) - 1)]
        charged = price * factor
        subtotal += charged
        lines.append({"slug": e.slug, "name": e.name, "list": round(price * mult),
                      "factor": factor, "charged": round(charged * mult)})

    addon_map = {a["id"]: a for a in r["addons"]}
    addon_lines = [{"id": a, "name": addon_map[a]["name"], "price": round(addon_map[a]["price"] * mult)}
                   for a in body.add_ons if a in addon_map]
    addon_total = sum(addon_map[a]["price"] for a in body.add_ons if a in addon_map)

    notes = []
    edition_total = subtotal
    suite_applied = False
    suite_price = (priced[0][0] if priced else 0) * r["suite_multiplier"]
    if len(eds) >= r["suite_threshold"] and suite_price and suite_price < subtotal:
        edition_total = suite_price
        suite_applied = True
        notes.append(f"Suite price applied (≈{r['suite_multiplier']}× a single edition) — cheaper than per-edition.")

    byok_disc = 0.0
    if body.byok:
        byok_disc = edition_total * r["byok_discount_pct"] / 100.0
        edition_total -= byok_disc
        notes.append(f"BYOK −{r['byok_discount_pct']}% (you bring your own model keys; PII stays local).")
    if len(eds) > 1 and not suite_applied:
        notes.append("Additional editions discounted (60/45/35%) — shared engine, one brain.")

    monthly = (edition_total + addon_total) * mult
    annual = monthly * (12 - r["annual_months_free"])
    if body.annual:
        notes.append(f"Annual = {12 - r['annual_months_free']}× monthly ({r['annual_months_free']} months free).")

    return {
        "currency": cur, "region": body.region, "tier": body.tier,
        "editions": lines, "add_ons": addon_lines,
        "edition_subtotal": round(subtotal * mult), "add_on_total": round(addon_total * mult),
        "suite_applied": suite_applied, "byok": body.byok, "byok_discount": round(byok_disc * mult),
        "monthly": round(monthly), "annual": round(annual), "notes": notes,
    }


# ── admin rate card ──────────────────────────────────────────────────────────
admin = APIRouter(prefix="/admin", tags=["admin-pricing"])


class RatesIn(BaseModel):
    rates: dict


@admin.get("/pricing")
def get_pricing(p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    require_role(p, "catalog")
    return {"rates": _rates(db), "defaults": _DEFAULT_RATES}


@admin.patch("/pricing")
def set_pricing(body: RatesIn, p: Principal = Depends(current_admin), db: Session = Depends(get_db)):
    require_role(p, "catalog")
    row = db.query(ConfigItem).filter_by(domain="pricing", key="rates").first()
    if not row:
        row = ConfigItem(id=ulid("cfg"), domain="pricing", key="rates", value={},
                         scope="overridable", active=True)
        db.add(row)
    row.value = body.rates
    audit(db, plane="cloud", actor=f"admin:{p.user_id}", action="pricing.update")
    db.commit()
    return {"rates": _rates(db), "message": "Pricing rates updated for all tenants."}

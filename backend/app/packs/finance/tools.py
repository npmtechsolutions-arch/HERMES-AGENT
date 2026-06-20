"""
Finance pack tools (Doc 24 §4 example). Tier-1 contract: simple bodies, the
call_tool wrapper handles permission/approval/retry/op-memory/Activity. Money is
NEVER moved autonomously — there is no pay tool; payment routes to handoff.prepare
(Tier-3). Param names avoid the wrapper's contact heuristic so finance entities
are typed correctly in the KG.
"""
import json
from collections import defaultdict

from ...models import KGEntity, MemoryItem, Reminder
from ...security import ulid
from ...tier1_tools import _parse_dt
from ...tools import ToolResult, tool

_CATS = {
    "groceries": ["grocery", "supermarket", "bigbasket", "dmart"],
    "utilities": ["electric", "water", "gas", "internet", "broadband", "bill"],
    "rent": ["rent", "lease"],
    "transport": ["uber", "ola", "fuel", "petrol", "metro", "cab"],
    "subscription": ["netflix", "spotify", "prime", "subscription", "saas"],
    "dining": ["restaurant", "cafe", "swiggy", "zomato", "food"],
}


def _categorize(desc):
    d = (desc or "").lower()
    for cat, kws in _CATS.items():
        if any(k in d for k in kws):
            return cat
    return "other"


@tool("finance.track_subscription", "Track a recurring subscription and its renewal.",
      {"subscription": {"type": "string", "required": True}, "amount": {"type": "number", "default": 0},
       "cadence": {"type": "string", "enum": ["weekly", "monthly", "yearly"], "default": "monthly"}},
      permission="finance.write", writes_memory=True)
def track_subscription(ctx, subscription, amount=0, cadence="monthly"):
    ctx.db.add(KGEntity(id=ulid("ent"), tenant_id=ctx.actor.tenant_id, type="Subscription",
                        name=subscription, attrs={"amount": amount, "cadence": cadence}))
    repeat = "weekly" if cadence == "weekly" else "monthly"
    ctx.db.add(Reminder(id=ulid("rem"), tenant_id=ctx.actor.tenant_id, user_id=ctx.actor.user_id,
                        text=f"{subscription} renewal (₹{amount})", repeat=repeat, kind="routine",
                        detail="subscription", status="active"))
    ctx.db.flush()
    return ToolResult(ok=True, data={"subscription": subscription, "amount": amount},
                      summary=f"Tracking “{subscription}” — ₹{amount} {cadence}.")


@tool("finance.bill_reminder", "Track a bill and remind you before it's due.",
      {"biller": {"type": "string", "required": True}, "amount": {"type": "number", "default": 0},
       "due_at": {"type": "string", "required": True}},
      permission="finance.write", writes_memory=True)
def bill_reminder(ctx, biller, due_at, amount=0):
    ctx.db.add(KGEntity(id=ulid("ent"), tenant_id=ctx.actor.tenant_id, type="Bill",
                        name=biller, attrs={"amount": amount, "due_at": due_at}))
    ctx.db.add(Reminder(id=ulid("rem"), tenant_id=ctx.actor.tenant_id, user_id=ctx.actor.user_id,
                        text=f"{biller} bill ₹{amount}", due_at=_parse_dt(due_at), kind="deadline",
                        detail="bill", status="active"))
    ctx.db.flush()
    return ToolResult(ok=True, data={"biller": biller, "amount": amount},
                      summary=f"Bill reminder set: {biller} ₹{amount}, due {due_at}.")


@tool("finance.categorize", "Categorize a transaction.",
      {"description": {"type": "string", "required": True}, "amount": {"type": "number", "default": 0}},
      permission="finance.read")
def categorize(ctx, description, amount=0):
    cat = _categorize(description)
    return ToolResult(ok=True, data={"category": cat}, summary=f"Categorized “{description}” as {cat}.")


@tool("finance.import_transactions", "Import + categorize transactions (from a statement).",
      {"transactions": {"type": "array", "required": True}},
      permission="finance.write", writes_memory=True)
def import_transactions(ctx, transactions):
    n = 0
    for t in (transactions or []):
        cat = _categorize(t.get("description", ""))
        ctx.db.add(MemoryItem(id=ulid("mem"), tenant_id=ctx.actor.tenant_id, memory_class="operational",
                              title=t.get("description", "transaction"), source_type="transaction",
                              body=json.dumps({**t, "category": cat}), tier="hot", confidence=1.0))
        n += 1
    ctx.db.flush()
    return ToolResult(ok=True, data={"imported": n}, summary=f"Imported and categorized {n} transaction(s).")


def _spent(ctx):
    rows = ctx.db.query(MemoryItem).filter_by(tenant_id=ctx.actor.tenant_id, source_type="transaction").all()
    by_cat = defaultdict(float)
    for r in rows:
        try:
            d = json.loads(r.body)
            by_cat[d.get("category", "other")] += float(d.get("amount", 0) or 0)
        except Exception:
            pass
    return by_cat


@tool("finance.budget_status", "Your spend + recurring commitments this period.",
      {"period": {"type": "string", "default": "month"}}, permission="finance.read")
def budget_status(ctx, period="month"):
    subs = ctx.db.query(KGEntity).filter_by(tenant_id=ctx.actor.tenant_id, type="Subscription").all()
    sub_total = sum(float((s.attrs or {}).get("amount", 0) or 0) for s in subs)
    spent = sum(_spent(ctx).values())
    return ToolResult(ok=True, data={"spent": round(spent, 2), "subscriptions": round(sub_total, 2),
                                     "committed": round(sub_total, 2)},
                      summary=f"This {period}: ₹{round(spent)} spent · ₹{round(sub_total)} in subscriptions.")


@tool("finance.spending_insight", "Where your money went, by category.",
      {"period": {"type": "string", "default": "month"}}, permission="finance.read")
def spending_insight(ctx, period="month"):
    by_cat = _spent(ctx)
    top = sorted(by_cat.items(), key=lambda x: -x[1])[:3]
    summary = ("Top spend: " + ", ".join(f"{c} ₹{round(v)}" for c, v in top)) if top else "No transactions yet."
    return ToolResult(ok=True, data={"by_category": {k: round(v, 2) for k, v in by_cat.items()}}, summary=summary)


@tool("finance.report", "Generate a finance report (saved locally as a document).",
      {"period": {"type": "string", "default": "month"}},
      permission="finance.write", writes_memory=True)
def report(ctx, period="month"):
    bs = budget_status(ctx, period).data
    subs = ctx.db.query(KGEntity).filter_by(tenant_id=ctx.actor.tenant_id, type="Subscription").all()
    md = (f"# Finance report — {period}\n\n"
          f"- Spent: ₹{bs['spent']}\n- Subscriptions: ₹{bs['subscriptions']}\n\n"
          "## Subscriptions\n" + ("\n".join(f"- {s.name}: ₹{(s.attrs or {}).get('amount', 0)}" for s in subs) or "- (none)"))
    return ToolResult(ok=True, data={"period": period},
                      artifacts=[{"kind": "document", "title": f"Finance report ({period})", "ext": "md", "content": md}],
                      summary=f"Generated your {period} finance report.")

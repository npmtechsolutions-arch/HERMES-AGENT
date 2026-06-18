# HERMUS — COMBOS, SUITES & CROSS-EDITION PRICING STRATEGY
**Version 1.0 | How customers buy 2, 3, or many sub-products together**
**Extends: Sub-Product Segmentation & Pricing (Doc 19) · grounded in the shipped admin Plans/feature-flag + Common Configuration machinery**

---

# PART 0 — THE GOVERNING IDEA

## 0.1 Sell entitlements, not stapled products
The combo trap is treating each sub-product as a sealed box and gluing boxes together → a combinatorial explosion of named bundles (RE+CA, RE+Clinic, CA+Clinic, RE+CA+Clinic…). Don't.

Because every HERMUS sub-product is already **a flag-set on one engine** (Doc 19 §0.2), a combo is simply:

> **One account, one engine, one login, multiple Editions/Role-Apps enabled as entitlements — switched between as "workspaces."**

The customer never runs two subscriptions. They run one HERMUS that shows a workspace switcher (RealEstate ▸ Clinic ▸ Doctors). Billing is one relationship. This is architecturally honest (matches your two-plane build), nearly free to implement (the admin plane already enables/disables editions per tenant), and it collapses the combinatorial mess into one priced rule.

## 0.2 The one-line strategy
*Discount the **second product**, never the **core platform**. The engine is the value; editions are access. Share the discount you genuinely earn from low marginal cost — don't train customers to see the platform as cheap.*

---

# PART 1 — WHO BUYS COMBOS (and why they're your best customers)

Combo demand is not an edge case — it clusters in your highest-LTV segments:

| Combo pattern | Real buyer | Why they need it |
|---|---|---|
| **Two editions** | A CA firm whose clients are property developers → CA + RealEstate | Files GST *and* tracks RERA milestones for the same clients |
| **Edition + Role App** | A clinic owner who is also a practising doctor → Clinic + Doctors | Personal dictation flows into the clinic's records |
| **Multi-edition** | A business group (retail + manufacturing + logistics arm) | One AI back office across divisions |
| **All-access** | An agency serving clients across verticals | Deploys & manages bots for RE, clinic, retail clients from one login |
| **Graduation** | A solo doctor whose clinic grew → upgrades Doctors → Clinic | Not a combo per se — the feeder motion that creates combo accounts |

**Implication:** combos are an upsell/expansion engine, not a discount giveaway. Average combo ARPU should be **higher** than single-product ARPU even after discount, because the shared engine deduplicates cost while cross-edition workflows add value.

---

# PART 2 — THE FOUR COMBO MOTIONS (use in this order)

## 2.1 Motion A — Bundle Discount (the simplest, for 2–3 products)
Second edition at ~60% of list, third at ~40% — reflecting genuine marginal cost (shared engine, CEO-Agent, Second Brain, billing, support relationship).

| Combo (Growth/Pro tier, India) | List sum | Combo price | Effective discount |
|---|---|---|---|
| RealEstate + CA | ₹19,999 + ₹19,999 = ₹39,998 | **₹31,999** | ~20% |
| RealEstate + CA + Clinic | ₹59,997 | **₹43,999** | ~27% |
| Clinic + Doctors (edition + role app) | ₹19,999 + ₹1,999 | **₹20,999** | role app ~50% off |
| Developers + Agency | ₹3,999 + ₹19,999 | **₹21,999** | ~8% (role app already cheap) |

Good for sales-assisted deals and the published "add a second product" path.

## 2.2 Motion B — Build-Your-Own-Suite (the scalable model; recommended default)
Don't price every pair. Price the **platform once**, then each additional edition is a declining add-on:

```
Account price = Platform Base (engine + 1st edition at full tier)
              + 2nd edition × 60%
              + 3rd edition × 45%
              + 4th+ edition × 35% each
              − volume tier discount (auto at 4+ editions → see Suite)
```

This makes *any* combination computable by one rule — no SKU per pair. The admin plane computes it from enabled-edition flags. This is how you run combos at scale.

## 2.3 Motion C — HERMUS Suite (all-access, premium)
For agencies, multi-vertical firms, enterprises: **all editions + all role apps + unlimited workspaces** at a flat price ≈ **2.5–3× a single Business edition** (NOT N×). Highest-ARPU SKU, natural enterprise landing spot, removes all per-edition math for the buyer.

## 2.4 Motion D — Graduation Credit (the feeder, not a combo)
Solo Role-App user whose business grows → upgrades into the matching Edition; the role-app fee **credits toward** the edition for the first cycle. One click, flag change, zero migration (same engine). This is where much combo demand originates — make the path frictionless.

---

# PART 3 — HOW FEATURES VARY IN A COMBO (the part that's easy to get wrong)

A combo is **not** the union of two feature lists. Three distinct things happen:

## 3.1 The shared core DEDUPLICATES (one brain, not two)
Across all enabled editions, these exist **once** per account: CEO-Agent orchestrator, Second Brain (memory + Knowledge Graph), approval chains, voice interface, messaging bus, billing/entitlements, audit log, local-LLM runtime.

A RE+CA customer does **not** get two CEO Agents — they get **one orchestrator that now reasons across both domains.** That is a capability *upgrade*, and it's the honest reason the second edition is discounted: you're not building it twice.

## 3.2 Cross-edition WORKFLOWS appear (the real combo value — sell THIS)
The discount gets them in; cross-domain workflows keep them. Examples to put on the combo sales page:

| Combo | Cross-edition workflow only a combo enables |
|---|---|
| CA + RealEstate | One agent files a developer-client's GST **and** tracks their RERA milestone billing in a single workflow; shared client entity in the Knowledge Graph |
| Clinic + Doctors | Personal dictation app writes structured notes **directly into** the clinic's patient records; one recall engine serves both |
| RealEstate + Agency | The agency's Marketing agents run campaigns that feed leads **straight into** the RE Lead-Qualifier pipeline — no export/import |
| Manufacturing + Logistics | Dispatch event in Manufacturing **auto-triggers** the Logistics POD-chase and document-expiry checks |
| Retail + Finance/NBFC | COD-reconciliation feeds the receivables/collections engine in one ledger |

**Rule:** every published combo must name at least one cross-edition workflow it unlocks. If you can't name one, it's just two products at a discount (Motion A is fine for that, but it's weaker).

## 3.3 Tiers ALIGN across editions (avoid mismatched entitlements)
Do **not** sell "RealEstate Business + CA Starter" — it creates entitlement ambiguity (which approval limits? which support SLA? which device count?). **Default rule: one account-level tier applies to all enabled editions.** The customer picks Growth/Business/Enterprise *once*; every workspace inherits that tier's limits, with its own agent roster. One tier, many workspaces.

Exception (Enterprise only, sales-assisted): genuinely different scale per division can be negotiated, but it's a custom contract, never self-serve.

---

# PART 4 — HOW PRICING VARIES (the master formula & rules)

## 4.1 The master formula
```
Account monthly price =
    Platform Base (engine + first edition at chosen tier)
  + Σ additional editions (declining add-on: 60% / 45% / 35%)
  + shared add-ons charged ONCE (Call Center, Multi-node, Confidential pack…)
  − combo/volume discount (Suite auto-applies at 4+ editions)
  − BYOK discount (15–20% if tenant brings own keys — Doc 19 Part 6)
  × regional price book (India ×1; US/EU ×2–2.5)
  × annual-prepay factor (2 months free on annual)
```

## 4.2 The four pricing rules that keep combos clean
1. **Add-ons are charged ONCE, not per edition.** A RE+Clinic combo wanting Call Center pays for Call Center once — it's one engine. Strong selling point: *"your add-ons cover every workspace."*
2. **Seats & devices are account-level and POOLED.** Buy a pool usable across all editions, not separate counts per edition. Matches how businesses actually staff; simpler to enforce.
3. **One account tier governs all editions** (Part 3.3).
4. **Discount the additional editions, never the platform base or the core engine.** Protects the perception that the platform is the value.

## 4.3 Worked examples (India, Growth/Business tier, monthly)

**Example 1 — CA firm adds RealEstate (2 editions, Growth):**
- Base (CA Growth): ₹19,999
- + RealEstate at 60%: ₹11,999
- = **₹31,999/mo** (vs ₹39,998 list). Cross-workflow sold: developer-client GST + RERA in one place.

**Example 2 — Clinic owner who is also a doctor (edition + role app, Pro):**
- Base (Clinic Growth): ₹19,999
- + Doctors role app at 50%: ₹999
- = **₹20,998/mo**. Cross-workflow: dictation → clinic records.

**Example 3 — Business group, 3 editions (Retail + Manufacturing + Logistics), Business tier:**
- Base (Retail Business): ₹49,999
- + Manufacturing at 60%: ₹29,999
- + Logistics at 45%: ₹22,499
- = **₹1,02,497/mo** (vs ₹1,49,997 list, ~32% off). Pooled 25 seats across divisions.

**Example 4 — Agency, all-access → HERMUS Suite (Business):**
- Single Business edition ≈ ₹49,999 → **Suite ≈ ₹1,29,999/mo** (≈2.6×) for *all* editions + role apps + unlimited workspaces. Replaces any per-edition math; the agency white-labels per client (V1.5).

**Example 5 — Combo + BYOK (Example 1 with own keys):**
- ₹31,999 − ~18% BYOK = **₹26,239/mo**; tenant pays their LLM provider directly; PII stays local regardless.

## 4.4 Annual & regional
- Annual: 2 months free → Example 1 annual = ₹3,19,990 (vs ₹3,83,988 monthly).
- Global: same structure × 2–2.5 (Example 1 ≈ $399/mo US).

---

# PART 5 — THE PUBLISHED PACKAGING (what customers actually see)

Don't publish a grid of named pairwise bundles. Publish **the rule and three SKUs**:

1. **"Add an Edition"** (self-serve) — pick your first edition's tier, then toggle additional editions; price computes live via Motion B's declining rates. Covers all 2–3 edition combos without any named bundle.
2. **"HERMUS Suite"** (self-serve up to a point, then sales-assisted) — flat all-access for agencies/multi-vertical/4+ editions.
3. **"Enterprise / Custom"** — sales-assisted, anchored on the Suite price, for per-division tiers, multi-node, offline, confidential pack, white-label.

Plus the **Graduation Credit** path surfaced inside every Role App ("Growing into a clinic? Upgrade to HERMUS Clinic — your ₹1,999 credits toward it").

---

# PART 6 — APPROACHING COMBO CUSTOMERS (the sales motion)

## 6.1 Detect combo intent early
Signals: a CA firm mentioning property-developer clients; a clinic owner who personally consults; a group with multiple divisions; an agency naming multiple client verticals. Train the onboarding flow and sales script to ask: *"Is this just for X, or do you also handle Y?"*

## 6.2 Lead with the cross-workflow, not the discount
Wrong: "buy both and save 20%." Right: "your developer clients need GST *and* RERA — one agent can do both, in one place; here's what that looks like." The discount is the close, the cross-workflow is the pitch.

## 6.3 Land small, expand via Graduation
Most combo accounts start as one edition or a role app. Instrument the upgrade path; the role-app → edition graduation credit and the in-product "add a workspace" prompt are your expansion engine. Expansion revenue is cheaper than new-logo revenue and combos are pure expansion.

## 6.4 Reserve Suite for the right buyers
Pitch Suite to agencies and multi-vertical groups directly; don't show a ₹1.3L SKU to a solo professional — it anchors wrong. Tier the pricing page so Suite appears only in the "agencies & enterprises" view.

## 6.5 Never discount the platform to win a combo
If a deal stalls on price, drop a tier or trim an add-on — never cut the engine's base toward zero. Protect the anchor that *the platform is the value.*

---

# PART 7 — IMPLEMENTATION (no new product code)

1. **Entitlements model:** an account holds `enabled_editions[]` + one `account_tier` + pooled `seats`/`devices` + `shared_add_ons[]`. All flags your admin plane already manages — add the `enabled_editions[]` array and a workspace switcher in the React shell.
2. **Pricing engine:** the Master Formula (Part 4.1) lives in the Plans editor as a computed rule (base + declining add-ons + shared add-ons − discounts × books × annual). No per-combo SKU rows.
3. **Workspace switcher:** same app, themed per active edition; the CEO-Agent and Second Brain are shared, so cross-edition workflows are native — no integration work.
4. **Cross-edition workflows:** authored as normal workflows that reference entities/agents from multiple editions; the shared Knowledge Graph makes a client/patient/property a single entity across workspaces.
5. **Graduation:** an "upgrade" action that flips a role-app entitlement to an edition entitlement and applies the credit — a flag change, no data migration.
6. **Governance:** all combo prices, add-on rates, Suite price, and discounts are config in the Plans editor; regional books and BYOK discounts are derived. No code owns a price.

---

# PART 8 — SUMMARY ANSWERS

- **How to approach combo customers:** one account, multiple editions as workspaces; lead with cross-edition workflows, close with the declining-add-on discount; land small and expand via graduation; reserve Suite for agencies/enterprise. (Part 6)
- **How features vary:** shared core deduplicates into one smarter brain; cross-edition workflows unlock (the real value); tiers align account-wide. NOT a feature union. (Part 3)
- **How pricing varies:** Master Formula — platform base + declining additional editions (60/45/35%) + shared add-ons charged once + pooled seats − combo/BYOK discounts × region × annual; or flat Suite for all-access. Discount editions, never the platform. (Part 4)
- **What to publish:** "Add an Edition" (rule-based, self-serve), "HERMUS Suite" (all-access), "Enterprise/Custom" — never a pairwise-bundle grid. (Part 5)
- **Build cost:** near zero — `enabled_editions[]`, a workspace switcher, and a computed pricing rule on the admin factory you already shipped. (Part 7)

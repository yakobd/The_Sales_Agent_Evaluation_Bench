"""
IO / contract skill: build an insertion order from deal data, then validate it.

Validation follows the Tenacious-Bench evaluator pattern: deterministic rules, and every problem is
returned as a code plus the evidence that triggered it. An IO with any violation cannot be routed
for signature; a valid IO still needs human approval (autonomy policy) before it is sent.
"""
from __future__ import annotations

import re
from datetime import date

from revenue.packs import PACK_DIR, SegmentPack

REQUIRED = ["advertiser_legal_name", "campaign_name", "flight_start", "flight_end", "currency", "payment_terms",
            "billing_email", "signatory_name", "signatory_title", "signatory_email", "line_items", "total_budget"]


def propose_line_items(budget: float, products: list[str], pack: SegmentPack) -> list[dict]:
    """Split the budget across the products the prospect asked about, priced at the rate-card midpoint.
    A starting point for Deal Desk, never sent without approval."""
    card = pack["io"]["rate_card"]
    chosen = [name for name in card if any(name.lower().startswith(p.lower()) for p in products)] or [next(iter(card))]
    share = budget / len(chosen)
    items = []
    for name in chosen:
        cpm = round((card[name]["min_cpm"] + card[name]["max_cpm"]) / 2, 2)
        impressions = int(share / cpm * 1000)
        items.append({"product": name, "impressions": impressions, "cpm": cpm})
    return items


def net_cost(item: dict, discount_pct: float) -> float:
    return round(item["impressions"] / 1000 * item["cpm"] * (1 - discount_pct / 100), 2)


def build_io_data(deal: dict, company: dict, contact: dict, pack: SegmentPack, io_number: str, approver: str = "Deal Desk") -> dict:
    f = deal["fields"]
    discount = float(f.get("discount_pct", 0))
    items = f.get("line_items") or []
    agency = f.get("agency_name")
    return {
        "io_number": io_number, "advertiser_legal_name": f.get("legal_name") or company["name"],
        "agency_clause": f', via agency **{agency}**' if agency else "",
        "campaign_name": f.get("campaign_name") or f"{company['name']} x Cool AI {f.get('timeline', '')}".strip(),
        "flight_start": f.get("flight_start"), "flight_end": f.get("flight_end"),
        "currency": pack["io"]["currency"], "payment_terms": pack["io"]["payment_terms"],
        "billing_email": f.get("billing_email") or contact["email"],
        "signatory_name": contact["name"], "signatory_title": contact["title"], "signatory_email": contact["email"],
        "line_items": items, "discount_pct": discount,
        "total_budget": round(sum(net_cost(i, discount) for i in items), 2),
        "agreed_budget": f.get("budget"), "approver": approver, "company_domain": company["domain"],
    }


def render_io(data: dict, pack: SegmentPack) -> str:
    tpl = (PACK_DIR / pack["io"]["template"]).read_text(encoding="utf-8")
    rows = "\n".join(f"| {i['product']} | {i['impressions']:,} | {data['currency']} {i['cpm']:.2f} | "
                     f"{data['currency']} {net_cost(i, data['discount_pct']):,.2f} |" for i in data["line_items"])
    ctx = {k: ("" if v is None else v) for k, v in data.items()}
    ctx["line_item_rows"] = rows
    ctx["total_budget"] = f"{data['total_budget']:,.2f}"
    return tpl.format(**ctx)


def validate_io(data: dict, pack: SegmentPack, today: date, rendered: str | None = None) -> list[dict]:
    v: list[dict] = []
    for k in REQUIRED:
        if data.get(k) in (None, "", []):
            v.append({"code": "MISSING_FIELD", "evidence": k})
    try:
        start, end = date.fromisoformat(data["flight_start"]), date.fromisoformat(data["flight_end"])
        if end <= start:
            v.append({"code": "FLIGHT_DATES_INVALID", "evidence": f"{start} to {end}"})
        if start < today:
            v.append({"code": "FLIGHT_STARTS_IN_PAST", "evidence": str(start)})
    except (TypeError, ValueError, KeyError):
        pass
    if data.get("currency") != pack["io"]["currency"]:
        v.append({"code": "CURRENCY_MISMATCH", "evidence": f"{data.get('currency')} != {pack['io']['currency']}"})
    card = pack["io"]["rate_card"]
    for i in data.get("line_items") or []:
        if i["product"] not in card:
            v.append({"code": "UNKNOWN_PRODUCT", "evidence": i["product"]})
            continue
        lo, hi = card[i["product"]]["min_cpm"], card[i["product"]]["max_cpm"]
        if not lo <= i["cpm"] <= hi:
            v.append({"code": "CPM_OUT_OF_RANGE", "evidence": f"{i['product']}: {i['cpm']} not in [{lo}, {hi}]"})
        if i["impressions"] <= 0:
            v.append({"code": "NON_POSITIVE_IMPRESSIONS", "evidence": i["product"]})
    if data.get("discount_pct", 0) > pack["io"]["max_discount_pct"]:
        v.append({"code": "DISCOUNT_TOO_HIGH", "evidence": f"{data['discount_pct']}% > {pack['io']['max_discount_pct']}%"})
    total = data.get("total_budget") or 0
    if total and total < pack["io"]["min_budget"]:
        v.append({"code": "BELOW_MIN_BUDGET", "evidence": f"{total:,.2f} < {pack['io']['min_budget']:,}"})
    agreed = data.get("agreed_budget")
    if agreed and total and abs(total - agreed) / agreed > 0.01:
        v.append({"code": "BUDGET_MISMATCH", "evidence": f"line items {total:,.2f} vs agreed {agreed:,.2f}"})
    dom = (data.get("company_domain") or "").lower()
    if dom and data.get("signatory_email") and not data["signatory_email"].lower().endswith("@" + dom):
        v.append({"code": "SIGNATORY_DOMAIN_MISMATCH", "evidence": f"{data['signatory_email']} is not @{dom}"})
    if rendered is not None:
        left = re.findall(r"\{[a-z_]+\}", rendered)
        if left:
            v.append({"code": "UNFILLED_PLACEHOLDER", "evidence": ", ".join(sorted(set(left)))})
    return v

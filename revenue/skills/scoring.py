"""
Lead scoring skill: fit, intent and engagement sub-scores, a tier, and a reason for every point.

Fully pack-driven. The rules (which fields, which signals, how many points, the reason text) are
YAML; this module only knows how to evaluate an operator. Same code scores every segment.

    fit         firmographic match to the segment's ICP                  (company.attributes)
    intent      recent buying signals, counted only inside their window  (company.signals)
    engagement  what the prospect did with our outreach                  (CRM activities)
"""
from __future__ import annotations

from datetime import date, datetime

from revenue.domain import LeadScore, SubScore, Tier
from revenue.packs import SegmentPack


def _as_date(v) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def _match(op: str, actual, expected) -> bool:
    if op == "exists":
        return actual not in (None, "", [], {})
    if actual is None:
        return False
    if op == "in":
        return actual in expected
    if op == "not_in":
        return actual not in expected
    if op == "eq":
        return actual == expected
    if op == "gte":
        return float(actual) >= float(expected)
    if op == "lte":
        return float(actual) <= float(expected)
    if op == "between":
        lo, hi = expected
        return float(lo) <= float(actual) <= float(hi)
    if op == "contains_any":
        return bool(set(actual if isinstance(actual, (list, tuple, set)) else [actual]) & set(expected))
    raise ValueError(f"unknown op {op}")


def _fmt(template: str, **kw) -> str:
    try:
        return template.format(**kw)
    except (ValueError, KeyError, IndexError):  # e.g. ':,' on a non-number
        return template.replace("{actual:,}", str(kw.get("actual"))).format(**{k: v for k, v in kw.items()})


def _sub(points: list[tuple[float, str]], max_points: float, empty: str) -> SubScore:
    total = sum(p for p, _ in points)
    value = round(min(100.0, 100.0 * total / max_points), 1) if max_points else 0.0
    return SubScore(value=value, reasons=[r for _, r in points] or [empty])


def score_fit(pack: SegmentPack, attributes: dict) -> SubScore:
    rules = pack["scoring"]["fit"]
    got = []
    for r in rules:
        actual = attributes.get(r["field"])
        if _match(r["op"], actual, r.get("value")):
            got.append((r["points"], _fmt(r["reason"], actual=actual, value=r.get("value"))))
    return _sub(got, sum(r["points"] for r in rules), "No ICP criteria matched")


def score_intent(pack: SegmentPack, signals: list[dict], today: date) -> SubScore:
    rules = pack["scoring"]["intent"]
    got, stale = [], []
    for r in rules:
        hits = [s for s in signals if s.get("type") == r["signal"]]
        fresh = [s for s in hits if 0 <= (today - _as_date(s["date"])).days <= r["window_days"]]
        if fresh:
            s = max(fresh, key=lambda x: x["date"])
            got.append((r["points"], _fmt(r["reason"], detail=s.get("detail", ""), date=s["date"])))
        elif hits:
            s = max(hits, key=lambda x: x["date"])
            stale.append(f"Ignored: {r['signal']} on {s['date']} is outside its {r['window_days']}-day window")
    # intent saturates: the strongest two signals are enough for 100
    best_two = sorted((r["points"] for r in rules), reverse=True)[:2]
    sub = _sub(got, sum(best_two), "No in-window buying signal")
    sub.reasons += stale
    return sub


def fresh_signals(pack: SegmentPack, signals: list[dict], today: date) -> list[dict]:
    """In-window signals only, strongest rule first. Outreach may cite these and nothing older."""
    out = []
    for r in sorted(pack["scoring"]["intent"], key=lambda r: -r["points"]):
        for s in signals:
            if s.get("type") == r["signal"] and 0 <= (today - _as_date(s["date"])).days <= r["window_days"]:
                out.append(s)
    return out


def score_engagement(pack: SegmentPack, activities: list[dict]) -> SubScore:
    rules = pack["scoring"]["engagement"]
    got = []
    for r in rules:
        n = sum(1 for a in activities if a.get("kind") == r["event"])
        if n:
            pts = min(r["points"] * n, r.get("cap", r["points"]))
            got.append((pts, _fmt(r["reason"], count=n)))
    cap_total = sum(r.get("cap", r["points"]) for r in rules)
    # engagement out of the two strongest behaviours, so a reply + meeting is a full score
    ceiling = sum(sorted((r.get("cap", r["points"]) for r in rules), reverse=True)[:2]) or cap_total
    return _sub(got, ceiling, "No engagement yet")


def tier_for(total: float, tiers: dict) -> Tier:
    if total >= tiers["A"]:
        return Tier.A
    if total >= tiers["B"]:
        return Tier.B
    if total >= tiers["C"]:
        return Tier.C
    return Tier.D


def score_lead(pack: SegmentPack, attributes: dict, signals: list[dict], activities: list[dict],
               today: date) -> LeadScore:
    fit = score_fit(pack, attributes)
    intent = score_intent(pack, signals, today)
    engagement = score_engagement(pack, activities)
    w = pack["scoring"]["weights"]
    total = round(w["fit"] * fit.value + w["intent"] * intent.value + w["engagement"] * engagement.value, 1)
    tier = tier_for(total, pack["scoring"]["tiers"])
    top = (intent.reasons[0] if intent.value else fit.reasons[0])
    reason = (f"Tier {tier.value} ({total}): fit {fit.value:.0f}, intent {intent.value:.0f}, "
              f"engagement {engagement.value:.0f}. Lead driver: {top}")
    return LeadScore(fit=fit, intent=intent, engagement=engagement, total=total, tier=tier, reason=reason)

"""
Transcript digestion: a Fireflies call transcript -> structured deal fields + lessons.

Deterministic extraction (regex + pack lexicon) so the demo and tests are reproducible. In the
Claude runtime the same output schema is filled by the model through a scoped `record_call_digest`
tool, and the result is validated against this schema before it touches the deal.

The transcript is untrusted data: nothing in it is executed or treated as an instruction.
"""
from __future__ import annotations

import re
from datetime import date

from revenue.packs import SegmentPack
from revenue.skills.lessons import extract_lessons

MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*(k|m|million|thousand)?\b", re.I)
ISO_DATE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
QUARTER = re.compile(r"\b(Q[1-4])\s*(?:of\s*)?(20\d{2})?\b", re.I)
NEED = re.compile(r"\b(we need|we're looking|we are looking|struggl\w+|problem is|pain|the goal is|we want)\b", re.I)
NEXT = re.compile(r"\b(next step|send (over|me|us)|follow up|by (monday|tuesday|wednesday|thursday|friday)|set up a)\b", re.I)
SIGNOFF = re.compile(r"\b(i sign off|i approve|my call|final say|i own the budget|decision is mine)\b", re.I)
COMPETITOR = re.compile(r"\b(?:currently (?:use|using)|work with|switching from|incumbent is)\s+([A-Z][\w&.-]+(?:\s[A-Z][\w&.-]+)?)")


def _money(m: re.Match) -> float:
    n = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    return n * (1_000 if unit in ("k", "thousand") else 1_000_000 if unit in ("m", "million") else 1)


def normalise(transcript: dict, our_domain: str = "cool.ai") -> list[dict]:
    """Fireflies shape -> [{speaker, text, is_prospect}] using participant emails to tell sides apart."""
    ours = {p["name"] for p in transcript.get("participants", []) if p.get("email", "").endswith("@" + our_domain)}
    return [{"speaker": s["speaker_name"], "text": s["text"], "is_prospect": s["speaker_name"] not in ours}
            for s in transcript.get("sentences", [])]


def digest(transcript: dict, pack: SegmentPack, segment: str) -> dict:
    utts = normalise(transcript)
    prospect = [u for u in utts if u["is_prospect"]]
    text = " ".join(u["text"] for u in prospect)
    fields: dict = {}
    evidence: dict = {}

    amounts = [(_money(m), m.group(0)) for m in MONEY.finditer(text)]
    if amounts:
        value, raw = max(amounts)
        fields["budget"] = value
        evidence["budget"] = raw
    dates = sorted(ISO_DATE.findall(text))
    if dates:
        fields["flight_start"] = dates[0]
        evidence["flight_start"] = dates[0]
        if len(dates) > 1:
            fields["flight_end"] = dates[-1]
            evidence["flight_end"] = dates[-1]
    q = QUARTER.search(text)
    if q or dates:
        fields["timeline"] = (f"{q.group(1).upper()} {q.group(2) or ''}".strip() if q else f"starts {dates[0]}")
        evidence["timeline"] = q.group(0) if q else dates[0]

    # decision maker: a prospect participant whose title is a decision role, or who says they sign off
    roles = [r.lower() for r in pack["transcripts"].get("decision_roles", [])]
    for p in transcript.get("participants", []):
        if any(r in (p.get("title") or "").lower() for r in roles) and not p.get("email", "").endswith("@cool.ai"):
            fields["decision_maker"] = f'{p["name"]} ({p["title"]})'
            evidence["decision_maker"] = f'participant title "{p["title"]}"'
            break
    for u in prospect:
        if SIGNOFF.search(u["text"]):
            fields["decision_maker"] = u["speaker"]
            evidence["decision_maker"] = u["text"][:120]
            break

    needs = [u["text"] for u in prospect if NEED.search(u["text"])]
    if needs:
        fields["need"] = needs[0][:200]
        evidence["need"] = needs[0][:120]
    products = [p for p, kws in pack["transcripts"]["product_keywords"].items()
                if any(re.search(rf"\b{re.escape(k)}\b", text, re.I) for k in kws)]
    if products:
        fields["products"] = products
    comp = COMPETITOR.findall(text)
    if comp:
        fields["competitors"] = sorted(set(comp))
    steps = [u["text"] for u in utts if NEXT.search(u["text"])]
    if steps:
        fields["next_steps"] = steps[-1][:200]

    lessons = extract_lessons(utts, segment, source=f"transcript:{transcript.get('id', '?')}",
                              extra_lexicon=pack["transcripts"].get("lexicon"))
    return {"fields": fields, "evidence": evidence, "lessons": lessons,
            "summary": f"{len(utts)} utterances, {len(fields)} deal fields, {len(lessons)} lessons"}


def flight_ok(fields: dict, today: date) -> bool:
    try:
        return date.fromisoformat(fields["flight_start"]) >= today
    except (KeyError, ValueError):
        return False

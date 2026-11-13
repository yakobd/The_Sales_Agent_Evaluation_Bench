"""
Knowledge loop: turn what prospects say into reusable lessons, and retrieve the right lessons
for the next email or call brief.

Extraction is rule-based by default (a core lexicon of objection/resonance patterns that every
segment shares, which a pack can extend). Each lesson carries:
    scope          "all" -> usable by every segment (the cross-segment loop), or one segment id
    outreach_line  the sentence it adds to the next email      (visible use)
    brief_note     the note it adds to the next call brief     (visible use)
    value_prop     which value prop to lead with, if it implies one
    evidence       the exact quote it came from                (traceability)
Lesson ids are content hashes, so re-processing the same transcript never duplicates lessons.
"""
from __future__ import annotations

import hashlib
import re

from revenue.domain import Lesson

# Core lexicon: generic B2B advertising patterns. Packs may add entries under transcripts.lexicon.
CORE_LEXICON = [
    {
        "key": "measurement_proof", "scope": "all", "tags": ["measurement", "objection", "proof"],
        "patterns": [r"\bprove\b", r"\bproof\b", r"incrementality", r"how (do|would) we know", r"\bholdout\b",
                     r"actually (drives|drove|works)"],
        "text": "Buyers ask for proof of incrementality before committing budget.",
        "outreach_line": "Most teams we work with start with a holdout test, so the lift is measured, not assumed.",
        "brief_note": "Expect a proof question: offer a holdout/lift test design for the pilot.",
        "value_prop": "measurement",
    },
    {
        "key": "local_control", "scope": "all", "tags": ["control", "objection", "multi_location"],
        "patterns": [r"lose control", r"local control", r"franchisees? (want|need|approve)", r"each (location|client|market) (wants|needs)",
                     r"approv(e|al) (each|every)"],
        "text": "Central teams worry about losing local control over offers and approvals.",
        "outreach_line": "Local teams keep approval of their own offers; the central team keeps the brand rules.",
        "brief_note": "Show the per-location approval workflow early; it answers the control worry.",
        "value_prop": "multi_location",
    },
    {
        "key": "pricing_pressure", "scope": "all", "tags": ["pricing", "objection"],
        "patterns": [r"too expensive", r"budget is tight", r"\bcheaper\b", r"\bdiscount\b", r"cost per"],
        "text": "Price comes up early; buyers compare on unit cost.",
        "outreach_line": "",
        "brief_note": "Anchor on cost per outcome (store visit, qualified lead), not CPM. Pricing goes through Deal Desk.",
        "value_prop": "",
    },
    {
        "key": "incumbent_vendor", "scope": "all", "tags": ["competition", "objection"],
        "patterns": [r"already (use|work with|have)", r"current (vendor|platform|partner)", r"locked in", r"under contract"],
        "text": "An incumbent vendor is in place; a full switch is a hard sell.",
        "outreach_line": "A side-by-side pilot on a slice of budget is usually easier than a full switch.",
        "brief_note": "Propose a side-by-side pilot on 10-20% of budget instead of a replacement.",
        "value_prop": "",
    },
    {
        "key": "creative_bottleneck", "scope": "all", "tags": ["creative", "pain"],
        "patterns": [r"creative (is|was) the bottleneck", r"production (backlog|bottleneck)", r"can'?t make enough (creative|variants|ads)",
                     r"(weeks|months) to (make|produce) (new )?(creative|ads)"],
        "text": "Creative production speed is a recurring pain.",
        "outreach_line": "Teams usually feel this first in creative production, which is where we start.",
        "brief_note": "Lead the demo with creative automation (Create) before media.",
        "value_prop": "creative",
    },
    {
        "key": "privacy_data", "scope": "all", "tags": ["privacy", "data", "objection"],
        "patterns": [r"\bprivacy\b", r"\bconsent\b", r"first[- ]party data", r"clean room", r"\bgdpr\b", r"\bccpa\b"],
        "text": "Data and privacy questions come up before any targeting discussion.",
        "outreach_line": "Everything runs on your first-party data with consent controls in place.",
        "brief_note": "Bring the data-handling one-pager; expect legal/privacy review.",
        "value_prop": "",
    },
]


def _lid(text: str, source: str) -> str:
    return "L-" + hashlib.sha256(f"{text}|{source}".encode()).hexdigest()[:10]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def extract_lessons(utterances: list[dict], segment: str, source: str, extra_lexicon: list[dict] | None = None) -> list[Lesson]:
    """utterances: [{"speaker": str, "text": str, "is_prospect": bool}]. Only the prospect's words count."""
    out, seen = [], set()
    for entry in CORE_LEXICON + list(extra_lexicon or []):
        for u in utterances:
            if not u.get("is_prospect", True):
                continue
            for sent in _sentences(u["text"]):
                if any(re.search(p, sent, re.I) for p in entry["patterns"]) and entry["key"] not in seen:
                    seen.add(entry["key"])
                    out.append(Lesson(
                        lesson_id=_lid(entry["key"], segment), text=entry["text"], tags=list(entry["tags"]),
                        origin_segment=segment, scope=entry.get("scope", "all"), source=source,
                        evidence=f'{u.get("speaker", "prospect")}: "{sent[:200]}"',
                        outreach_line=entry.get("outreach_line", ""), brief_note=entry.get("brief_note", ""),
                        value_prop=entry.get("value_prop", "")))
    return out


def retrieve(lessons: list[Lesson], segment: str, want_tags: set[str] | None = None, k: int = 3,
             for_outreach: bool = False) -> list[Lesson]:
    """Lessons usable by this segment (scope 'all' or the same segment), ranked by tag overlap,
    then by how often they recur (uses), then by recency."""
    want_tags = want_tags or set()
    pool = [l for l in lessons if l.scope in ("all", segment)]
    if for_outreach:
        pool = [l for l in pool if l.outreach_line]
    ranked = sorted(pool, key=lambda l: (len(set(l.tags) & want_tags), l.uses, l.created_at), reverse=True)
    return ranked[:k]

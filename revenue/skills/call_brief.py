"""Call brief skill: one page for the account executive before the meeting, with lessons applied."""
from __future__ import annotations

from revenue.domain import Lesson
from revenue.packs import SegmentPack
from revenue.skills.tracking import missing_exit_criteria


def build(pack: SegmentPack, deal: dict, company: dict, contact: dict, lessons: list[Lesson]) -> dict:
    s = deal.get("score") or {}
    tpl = pack.template("call_brief")
    title = tpl["title"].format(company=company["name"], tier=deal.get("tier") or "?")
    open_q = missing_exit_criteria(deal, pack, "qualified")
    sections = {
        "account": f"{company['name']} ({company['domain']}), contact {contact['name']}, {contact['title']}. "
                   + ", ".join(f"{k}: {v}" for k, v in list(company.get("attributes", {}).items())[:5]),
        "why_now": (s.get("intent") or {}).get("reasons", ["-"]),
        "scores": s.get("reason", "not scored"),
        "open_questions": [f"Confirm {q.replace('_', ' ')}" for q in open_q] or ["All qualification criteria captured"],
        "lessons": [f"{l.brief_note} [{l.lesson_id}, from {l.origin_segment}]" for l in lessons if l.brief_note],
        "watch_outs": [f for f in deal.get("flags", [])] or ["none"],
    }
    return {"title": title, "sections": {k: sections[k] for k in tpl["sections"] if k in sections},
            "lessons_used": [l.lesson_id for l in lessons if l.brief_note]}

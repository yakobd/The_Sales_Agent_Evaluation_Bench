"""
Tool registry and per-agent scoping.

Tools are read-only or pure computations (skills). None of them changes the world: side effects
happen only when the orchestrator executes a ProposedAction that the autonomy policy allowed.

Each agent receives a ToolBelt restricted to its declared scope. Calling a tool outside the scope
raises ScopeViolation and is written to the audit log. The Claude runtime enforces the same scope
a second time, in a PreToolUse hook.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from revenue.packs import PackRegistry
from revenue.skills import call_brief, io_docs, lessons, outreach, replies, scoring, tracking, transcripts


class ScopeViolation(PermissionError):
    pass


def build_registry(crm, enricher, fireflies, lesson_store, packs: PackRegistry, clock: Callable[[], datetime]) -> dict[str, Callable]:
    return {
        # reads
        "now": clock,
        "get_deal": crm.get_deal,
        "get_company": crm.get_company,
        "get_contact": crm.get_contact,
        "get_activities": crm.activities,
        "get_pack": packs.get,
        "retrieve_lessons": lambda segment, tags=None, k=3, for_outreach=False:
            lessons.retrieve(lesson_store.all(), segment, set(tags or []), k, for_outreach),
        "enrich_company": enricher.enrich,
        "fetch_transcript": fireflies.fetch,
        # pure skills
        "score_lead": scoring.score_lead,
        "fresh_signals": scoring.fresh_signals,
        "draft_email": outreach.draft,
        "classify_reply": replies.classify,
        "extract_lessons": lessons.extract_lessons,
        "digest_transcript": transcripts.digest,
        "build_call_brief": call_brief.build,
        "missing_exit_criteria": tracking.missing_exit_criteria,
        "detect_stall": tracking.stall,
        "propose_line_items": io_docs.propose_line_items,
        "build_io": io_docs.build_io_data,
        "render_io": io_docs.render_io,
        "validate_io": io_docs.validate_io,
    }


class ToolBelt:
    def __init__(self, agent: str, scope: frozenset[str], registry: dict[str, Callable], audit: Callable[..., None]):
        unknown = scope - set(registry)
        if unknown:
            raise ValueError(f"{agent} declares unknown tools: {sorted(unknown)}")
        self.agent, self.scope, self._registry, self._audit = agent, scope, registry, audit

    def call(self, name: str, *args, **kwargs) -> Any:
        if name not in self.scope:
            self._audit(self.agent, "scope_violation", {"tool": name})
            raise ScopeViolation(f"agent {self.agent!r} may not use tool {name!r}")
        return self._registry[name](*args, **kwargs)

    __call__ = call

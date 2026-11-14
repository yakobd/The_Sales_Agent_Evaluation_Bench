"""Composition root: wires store, mock adapters, packs, agents and the orchestrator together."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from revenue.adapters.mocks import MockEmail, MockEnricher, MockESign, MockFireflies, MockHubSpot
from revenue.orchestrator import Orchestrator
from revenue.packs import PACK_DIR, PackRegistry
from revenue.store import Store

STATE_DIR = Path(__file__).resolve().parent / ".state"


class Clock:
    """Controllable clock so demos and tests are deterministic (SLA timers, signal windows)."""

    def __init__(self, start: datetime | None = None):
        self.t = start or datetime.now(timezone.utc)

    def __call__(self) -> datetime:
        return self.t

    def advance(self, days: float = 0, hours: float = 0) -> datetime:
        self.t += timedelta(days=days, hours=hours)
        return self.t


def build(db_path: str | Path = ":memory:", clock: Clock | None = None, pack_dir: Path = PACK_DIR, runtime=None):
    store = Store(db_path)
    clock = clock or Clock()
    crm = MockHubSpot(store)
    if runtime is None and os.environ.get("REVENUE_RUNTIME") == "claude":
        from revenue.sdk_runtime import ClaudeRuntime
        runtime = ClaudeRuntime()
    orch = Orchestrator(store, crm, MockEnricher(), MockEmail(store), MockESign(store), MockFireflies(),
                        PackRegistry(pack_dir), clock=clock, runtime=runtime)
    if runtime is not None and getattr(runtime, "audit", None) is None:
        runtime.audit = store.audit  # LLM fallbacks are audited
    return orch, clock

"""
Domain model for the agentic revenue system. Plain dataclasses: no I/O, no framework.

Everything an agent produces is a ProposedAction. Agents never perform side effects;
the orchestrator decides (via the autonomy policy, in code) whether each action runs,
waits for a human, or is blocked.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Stage(str, Enum):
    PROSPECT = "prospect"
    ENRICHED = "enriched"
    SCORED = "scored"
    OUTREACH = "outreach"
    ENGAGED = "engaged"          # prospect replied
    MEETING = "meeting"          # call booked / held
    QUALIFIED = "qualified"      # exit criteria met (budget, timeline, decision maker, need)
    PROPOSAL = "proposal"        # IO drafted
    IO_SENT = "io_sent"          # out for e-signature
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    NURTURE = "nurture"          # not now / not a fit yet

    @property
    def is_terminal(self) -> bool:
        return self in (Stage.CLOSED_WON, Stage.CLOSED_LOST)


class Tier(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"  # below threshold: do not pursue actively


class ActionType(str, Enum):
    # internal, reversible
    UPDATE_DEAL = "update_deal"
    CREATE_TASK = "create_task"
    DRAFT_EMAIL = "draft_email"
    GENERATE_IO = "generate_io"
    RECORD_LESSON = "record_lesson"
    SCHEDULE_TIMER = "schedule_timer"
    FLAG = "flag"
    NOTIFY = "notify"            # internal notification (digest, reminder) to the team
    # external, hard to undo
    SEND_EMAIL = "send_email"
    SEND_PRICING = "send_pricing"
    SEND_IO_FOR_SIGNATURE = "send_io_for_signature"
    CLOSE_DEAL = "close_deal"
    HANDOFF = "handoff"


EXTERNAL_ACTIONS = {ActionType.SEND_EMAIL, ActionType.SEND_PRICING, ActionType.SEND_IO_FOR_SIGNATURE}


class Decision(str, Enum):
    AUTO = "auto"          # execute now
    APPROVAL = "approval"  # queue for a human
    BLOCK = "block"        # never execute


@dataclass
class Company:
    company_id: str
    name: str
    domain: str
    segment: str
    attributes: dict[str, Any] = field(default_factory=dict)   # firmographics from enrichment
    signals: list[dict[str, Any]] = field(default_factory=list)  # [{type, date, detail}]


@dataclass
class Contact:
    contact_id: str
    company_id: str
    name: str
    email: str
    title: str


@dataclass
class SubScore:
    value: float               # 0-100
    reasons: list[str]         # human-readable, one per contributing factor


@dataclass
class LeadScore:
    fit: SubScore
    intent: SubScore
    engagement: SubScore
    total: float
    tier: Tier
    reason: str                # one-line summary for humans

    def to_dict(self) -> dict:
        return asdict(self) | {"tier": self.tier.value}


@dataclass
class Deal:
    deal_id: str
    company_id: str
    contact_id: str
    segment: str
    stage: Stage = Stage.PROSPECT
    tier: Tier | None = None
    score: dict[str, Any] | None = None
    fields: dict[str, Any] = field(default_factory=dict)   # budget, timeline, decision_maker, products, ...
    flags: list[str] = field(default_factory=list)
    touches: int = 0                                         # outbound emails sent
    last_activity: str = field(default_factory=lambda: utcnow().isoformat())
    stage_since: str = field(default_factory=lambda: utcnow().isoformat())   # when the current stage was entered
    opted_out: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["stage"] = self.stage.value
        d["tier"] = self.tier.value if self.tier else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Deal":
        d = dict(d)
        d["stage"] = Stage(d["stage"])
        d["tier"] = Tier(d["tier"]) if d.get("tier") else None
        return cls(**d)


@dataclass
class ProposedAction:
    type: ActionType
    deal_id: str
    payload: dict[str, Any]
    agent: str
    rationale: str

    def to_dict(self) -> dict:
        return {"type": self.type.value, "deal_id": self.deal_id, "payload": self.payload,
                "agent": self.agent, "rationale": self.rationale}


@dataclass
class PolicyVerdict:
    decision: Decision
    reasons: list[str]
    risk: str  # "low" | "high" | "blocked"


@dataclass
class Event:
    type: str                  # e.g. lead.created, email.replied, transcript.ready, esign.completed, timer.fired
    key: str                   # idempotency key (provider event id, or a deterministic hash)
    payload: dict[str, Any]
    source: str = "system"     # webhook | schedule | system | human


@dataclass
class Lesson:
    lesson_id: str
    text: str
    tags: list[str]
    origin_segment: str
    scope: str                  # "all" (cross-segment) or a segment id
    source: str                 # transcript / reply id it came from
    evidence: str               # the quote it was derived from
    outreach_line: str = ""     # how the lesson changes the next email (visible use)
    brief_note: str = ""        # how it changes the next call brief
    value_prop: str = ""        # value-prop key to lead with, if the lesson implies one
    created_at: str = field(default_factory=lambda: utcnow().isoformat())
    uses: int = 0

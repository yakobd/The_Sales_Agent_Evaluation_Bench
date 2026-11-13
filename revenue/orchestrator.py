"""
Orchestrator: owns deal state and is the only component that changes the world.

    trigger ─► Store.add_event (idempotent) ─► run() ─► route to agents ─► ProposedActions
                                                                │
                                         AutonomyPolicy.evaluate (code) ─► AUTO     ─► Executor
                                                                          APPROVAL ─► approval queue ─► human ─► Executor
                                                                          BLOCK    ─► audit only
Stage changes made by the executor become new `deal.stage_changed` events, so every step of the
lifecycle is itself a durable, idempotent, replayable event.
"""
from __future__ import annotations

import traceback
from datetime import datetime, timedelta
from typing import Callable

from revenue.agents import ALL_AGENTS, Agent
from revenue.domain import (ActionType, Company, Contact, Deal, Decision, Event, Lesson, ProposedAction, Stage, Tier,
                            utcnow)
from revenue.packs import PackRegistry
from revenue.policy import AutonomyPolicy, KillSwitch
from revenue.store import Store
from revenue.tools import ScopeViolation, ToolBelt, build_registry


class InvariantViolation(ValueError):
    """A domain rule the executor will never break (e.g. closing a deal without CLOSE_DEAL).
    Recorded as a block, not retried: retrying cannot make it valid."""


class Executor:
    """Applies one allowed action through the ports. Knows nothing about policy."""

    def __init__(self, store: Store, crm, email, esign, clock: Callable[[], datetime]):
        self.store, self.crm, self.email, self.esign, self.clock = store, crm, email, esign, clock

    def apply(self, a: ProposedAction) -> list[Event]:
        deal = Deal.from_dict(self.crm.get_deal(a.deal_id))
        before = deal.stage
        p = a.payload
        result: dict = {}
        if a.type == ActionType.UPDATE_DEAL:
            if "company" in p:
                company = self.crm.get_company(deal.company_id) | p["company"]
                self.crm.upsert_company(company)
            if "fields" in p:
                deal.fields = deal.fields | {k: v for k, v in p["fields"].items() if v not in (None, "", [])}
            if "score" in p:
                deal.score = p["score"]
            if "tier" in p:
                deal.tier = Tier(p["tier"])
            if "opted_out" in p:
                deal.opted_out = bool(p["opted_out"])
            if "stage" in p:
                if Stage(p["stage"]).is_terminal:
                    raise InvariantViolation("terminal stages are set only by CLOSE_DEAL")
                deal.stage = Stage(p["stage"])
            if "activity" in p:
                self.crm.log_activity(deal.deal_id, p["activity"].get("kind", "note"), p["activity"])
            if "engagement" in p:
                self.crm.log_activity(deal.deal_id, p["engagement"], {"source": a.agent})
            if p.get("lessons_used"):
                self.store.mark_used(p["lessons_used"])
        elif a.type == ActionType.SEND_EMAIL:
            mid = self.email.send(p["to"], p["subject"], p["body"], deal.deal_id)
            self.crm.log_activity(deal.deal_id, "email_sent", {"message_id": mid, "subject": p["subject"], "kind": p.get("kind"),
                                                               "lessons_used": p.get("lessons_used", [])})
            if p.get("lessons_used"):
                self.store.mark_used(p["lessons_used"])
            deal.touches += 1
            if deal.stage in (Stage.SCORED, Stage.ENRICHED):
                deal.stage = Stage.OUTREACH
            result["message_id"] = mid
        elif a.type == ActionType.CREATE_TASK:
            self.crm.create_task(deal.deal_id, p["title"], p["due"], p.get("owner", "ae"))
        elif a.type == ActionType.FLAG:
            if p["flag"] not in deal.flags:
                deal.flags.append(p["flag"])
        elif a.type == ActionType.RECORD_LESSON:
            result["new"] = self.store.add(Lesson(**p["lesson"]))
        elif a.type == ActionType.SCHEDULE_TIMER:
            due = self.clock() + timedelta(days=p["in_days"])
            self.store.add_timer(p["key"], due, p["event_type"], p["payload"])
        elif a.type == ActionType.GENERATE_IO:
            deal.fields = deal.fields | {"io_number": p["io_number"], "io_valid": not p["violations"]} | (p.get("fields") or {})
            self.crm.log_activity(deal.deal_id, "io_draft", {"io_number": p["io_number"], "document": p["document"],
                                                             "violations": p["violations"], "total": p["data"]["total_budget"]})
            if not p["violations"] and deal.stage == Stage.QUALIFIED:
                deal.stage = Stage.PROPOSAL
        elif a.type == ActionType.SEND_IO_FOR_SIGNATURE:
            env = self.esign.send_envelope(deal.deal_id, p["document"], p["signer"])
            deal.fields = deal.fields | {"envelope_id": env}
            deal.stage = Stage.IO_SENT
            self.crm.log_activity(deal.deal_id, "io_sent", {"envelope_id": env, "signer": p["signer"]})
            result["envelope_id"] = env
        elif a.type == ActionType.CLOSE_DEAL:
            deal.stage = Stage.CLOSED_WON
            self.crm.log_activity(deal.deal_id, "closed_won", p)
        elif a.type == ActionType.HANDOFF:
            self.crm.create_task(deal.deal_id, f"Kickoff: {deal.deal_id} handed off to {p['to']}",
                                 (self.clock() + timedelta(days=2)).date().isoformat(), p["to"])
        elif a.type == ActionType.NOTIFY:
            self.crm.log_activity(deal.deal_id, "notify", p)
        deal.last_activity = self.clock().isoformat()
        if deal.stage != before:
            deal.stage_since = deal.last_activity
        self.crm.upsert_deal(deal.to_dict())
        self.store.audit(a.agent, "executed", {"action": a.to_dict() | {"payload": _slim(a.payload)}, "result": result})
        if deal.stage != before:
            return [Event("deal.stage_changed", f"stage:{deal.deal_id}:{before.value}->{deal.stage.value}",
                          {"deal_id": deal.deal_id, "from": before.value, "to": deal.stage.value})]
        return []


def _slim(p: dict) -> dict:
    """Keep audit entries readable: drop large document bodies."""
    return {k: (v[:200] + "…" if isinstance(v, str) and len(v) > 200 else v) for k, v in p.items() if k not in ("data",)}


class Orchestrator:
    def __init__(self, store: Store, crm, enricher, email, esign, fireflies, packs: PackRegistry,
                 clock: Callable[[], datetime] = utcnow, agents: list[Agent] | None = None, runtime=None):
        self.store, self.crm, self.packs, self.clock = store, crm, packs, clock
        self.kill_switch = KillSwitch(store)
        self.policy = AutonomyPolicy(self.kill_switch)
        self.executor = Executor(store, crm, email, esign, clock)
        self.registry = build_registry(crm, enricher, fireflies, store, packs, clock)
        self.agents = agents or ALL_AGENTS
        self.runtime = runtime  # optional Claude Agent SDK runtime (revenue/sdk_runtime.py)
        self.belts = {a.name: ToolBelt(a.name, a.scope, self.registry, store.audit) for a in self.agents}

    # ── triggers ────────────────────────────────────────────────────────────
    OUTREACH_STAGES = {Stage.PROSPECT.value, Stage.ENRICHED.value, Stage.SCORED.value, Stage.OUTREACH.value}

    def expire_stale_approvals(self, deal_id: str) -> int:
        """A queued cold email is wrong once the deal has moved past outreach (replied, meeting, IO...).
        Expire it instead of letting someone approve it later."""
        deal = self.crm.get_deal(deal_id)
        if not deal or deal["stage"] in self.OUTREACH_STAGES:
            return 0
        n = 0
        for ap in self.store.approvals("pending"):
            if ap["deal_id"] == deal_id and ap["action"]["type"] == "send_email" and ap["action"]["payload"].get("kind") in ("first_touch", "follow_up"):
                if self.store.decide_approval(ap["id"], "expired", "orchestrator", f"superseded: deal is now '{deal['stage']}'"):
                    self.store.audit("orchestrator", "approval_expired", {"approval_id": ap["id"], "stage": deal["stage"]})
                    n += 1
        return n

    def ingest(self, type_: str, key: str, payload: dict, source: str = "system") -> bool:
        new = self.store.add_event(Event(type_, key, payload, source), self.clock())
        self.store.audit(source, "event_received" if new else "event_duplicate_ignored", {"type": type_, "key": key})
        if new and type_ == "deal.stage_changed":
            self.expire_stale_approvals(payload["deal_id"])
        return new

    def new_lead(self, segment: str, company: dict, contact: dict, source: str = "webhook") -> str:
        self.packs.get(segment)  # fail fast: unknown segment has no pack
        c = Company(company_id=company["company_id"], name=company["name"], domain=company["domain"], segment=segment)
        ct = Contact(contact_id=contact["contact_id"], company_id=c.company_id, name=contact["name"],
                     email=contact["email"], title=contact["title"])
        deal_id = f"D-{c.company_id}"
        if not self.crm.get_deal(deal_id):
            self.crm.upsert_company(c.__dict__)
            self.crm.upsert_contact(ct.__dict__)
            now = self.clock().isoformat()
            self.crm.upsert_deal(Deal(deal_id=deal_id, company_id=c.company_id, contact_id=ct.contact_id, segment=segment,
                                      last_activity=now, stage_since=now).to_dict())
        self.ingest("lead.created", f"lead:{deal_id}", {"deal_id": deal_id}, source)
        return deal_id

    def tick(self) -> int:
        """Scheduler: turn due timers into events. Safe to run from cron every minute."""
        n = 0
        for tm in self.store.due_timers(self.clock()):
            self.ingest(tm["event_type"], f"timer:{tm['key']}", tm["payload"], "schedule")
            self.store.fire_timer(tm["key"])
            n += 1
        return n

    # ── processing ──────────────────────────────────────────────────────────
    def run(self, max_events: int = 500) -> list[dict]:
        """Process pending events until the queue is empty. Returns a trace of what happened."""
        trace = []
        for _ in range(max_events):
            pending = self.store.pending_events()
            if not pending:
                break
            ev = pending[0]
            try:
                trace.append(self._process(ev))
                self.store.mark_event(ev["seq"], True)
            except Exception as e:  # retried up to MAX_ATTEMPTS, then parked as 'dead'
                status = self.store.mark_event(ev["seq"], False, f"{type(e).__name__}: {e}")
                self.store.audit("orchestrator", "event_failed", {"key": ev["key"], "error": str(e), "status": status,
                                                                  "trace": traceback.format_exc(limit=2)})
                trace.append({"event": ev["type"], "key": ev["key"], "error": str(e), "status": status})
        return trace

    def _process(self, ev: dict) -> dict:
        out = {"event": ev["type"], "key": ev["key"], "actions": []}
        for agent in self.agents:
            if ev["type"] not in agent.handles:
                continue
            try:
                proposals = (self.runtime.propose(agent, ev, self.belts[agent.name]) if self.runtime and self.runtime.handles(agent)
                             else agent.handle(ev, self.belts[agent.name]))
            except ScopeViolation as e:
                out["actions"].append({"agent": agent.name, "error": str(e)})
                continue
            for i, a in enumerate(proposals):
                if a.type not in agent.emits or a.agent != agent.name:  # defence in depth for LLM-backed agents
                    self.store.audit(agent.name, "action_out_of_role", {"type": a.type.value, "deal_id": a.deal_id})
                    out["actions"].append({"agent": agent.name, "type": a.type.value, "decision": "block",
                                           "reasons": [f"{agent.name} may not propose {a.type.value}"], "rationale": a.rationale})
                    continue
                out["actions"].append(self.submit(a, key=f"{ev['key']}|{agent.name}|{i}|{a.type.value}"))
        return out

    def submit(self, a: ProposedAction, key: str | None = None) -> dict:
        if key and self.store.action_done(key):  # event retried after a partial failure
            return {"agent": a.agent, "type": a.type.value, "decision": "skipped", "reasons": ["already applied"]}
        deal = Deal.from_dict(self.crm.get_deal(a.deal_id))
        pack = self.packs.get(deal.segment)
        v = self.policy.evaluate(a, deal, pack)
        rec = {"agent": a.agent, "type": a.type.value, "decision": v.decision.value, "reasons": v.reasons, "rationale": a.rationale}
        self.store.audit(a.agent, "policy", {"action": a.type.value, "deal_id": a.deal_id, "decision": v.decision.value,
                                             "reasons": v.reasons})
        if v.decision == Decision.AUTO:
            try:
                for e in self.executor.apply(a):
                    self.ingest(e.type, e.key, e.payload)
            except InvariantViolation as e:
                self.store.audit("executor", "invariant_violation", {"action": a.type.value, "deal_id": a.deal_id, "error": str(e)})
                rec.update(decision="block", reasons=[str(e)])
        elif v.decision == Decision.APPROVAL:
            rec["approval_id"] = self.store.add_approval(a.deal_id, a.to_dict(), {"decision": v.decision.value, "reasons": v.reasons}, key)
        if key:
            self.store.mark_action(key)
        return rec

    # ── human in the loop ───────────────────────────────────────────────────
    def approve(self, approval_id: str, by: str, note: str = "") -> dict:
        ap = self.store.approval(approval_id)
        if not ap or ap["status"] != "pending":
            return {"ok": False, "error": "not pending"}
        a = ProposedAction(ActionType(ap["action"]["type"]), ap["deal_id"], ap["action"]["payload"], ap["action"]["agent"],
                           ap["action"]["rationale"])
        if a.type.value in ("send_email", "send_pricing", "send_io_for_signature") and self.kill_switch.engaged():
            return {"ok": False, "error": "kill switch engaged: approval cannot execute external actions"}
        deal = Deal.from_dict(self.crm.get_deal(a.deal_id))
        if a.type == ActionType.SEND_EMAIL and deal.opted_out:
            self.store.decide_approval(approval_id, "rejected", "policy", "prospect opted out after approval was requested")
            return {"ok": False, "error": "prospect opted out"}
        if not self.store.decide_approval(approval_id, "approved", by, note):
            return {"ok": False, "error": "already decided"}
        self.store.audit(by, "approved", {"approval_id": approval_id, "action": a.type.value, "deal_id": a.deal_id, "note": note})
        for e in self.executor.apply(a):
            self.ingest(e.type, e.key, e.payload)
        return {"ok": True}

    def reject(self, approval_id: str, by: str, note: str = "") -> dict:
        ok = self.store.decide_approval(approval_id, "rejected", by, note)
        if ok:
            self.store.audit(by, "rejected", {"approval_id": approval_id, "note": note})
        return {"ok": ok}

    # ── read models ─────────────────────────────────────────────────────────
    def digest(self) -> dict:
        from revenue.skills.tracking import digest, stall
        deals = self.crm.list_deals()
        stalls = [s for d in deals if (s := stall(d, self.packs.get(d["segment"]), self.clock()))]
        flags = [{"deal_id": d["deal_id"], "flag": f} for d in deals for f in d.get("flags", [])]
        return digest(deals, self.store.approvals(), stalls, flags, self.clock())

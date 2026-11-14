"""
Revenue desk API (mounted by dashboard/server.py under /api/revenue).

  GET  /state                      everything the console shows (pipeline, approvals, lessons, tasks, digest, audit)
  GET  /deals/{deal_id}            one deal with activities (emails, replies, call brief, IO)
  POST /approvals/{id}             {"decision": "approve"|"reject", "note": ""}  - the human in the loop
  POST /killswitch                 {"on": true|false}
  POST /scenario/next              run the next scripted input (leads, replies, transcript, e-sign, ...)
  POST /scenario/reset             fresh database, clock back to the demo start
  POST /webhooks/{source}          signed webhooks (X-Cool-Signature: hex HMAC-SHA256 of the body), idempotent

Inputs come from the scenario or real webhooks; approvals come from the console. The orchestrator
and policy are the same objects the CLI demo and tests use.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from revenue.demo import DATA, START
from revenue.system import STATE_DIR, Clock, build

router = APIRouter(prefix="/api/revenue", tags=["revenue"])
DB = STATE_DIR / "revenue.db"
SECRET = os.environ.get("REVENUE_WEBHOOK_SECRET", "dev-secret")
_lock = threading.RLock()
_state: dict = {}


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _system(reset: bool = False):
    with _lock:
        if reset or "orch" not in _state:
            if reset:
                if "orch" in _state:
                    _state["orch"].store.db.close()  # Windows can't delete an open database file
                    _state.clear()
                for suffix in ("", "-wal", "-shm"):
                    p = DB.with_name(DB.name + suffix)
                    if p.exists():
                        try:
                            p.unlink()
                        except PermissionError:
                            pass
            saved = None
            if not reset and DB.exists():
                from revenue.store import Store
                saved = Store(DB).get_setting("clock")
            clock = Clock(datetime.fromisoformat(saved) if saved else START)
            orch, clock = build(DB, clock)
            if reset:
                orch.store.db.executescript("DELETE FROM events; DELETE FROM timers; DELETE FROM approvals; DELETE FROM lessons;"
                                            "DELETE FROM settings; DELETE FROM audit; DELETE FROM actions_done;"
                                            "DELETE FROM crm_companies; DELETE FROM crm_contacts; DELETE FROM crm_deals;"
                                            "DELETE FROM crm_activities; DELETE FROM crm_tasks; DELETE FROM outbox; DELETE FROM envelopes;")
            _state.update(orch=orch, clock=clock)
        return _state["orch"], _state["clock"]


def _save_clock(orch, clock) -> None:
    orch.store.set_setting("clock", clock().isoformat())


# ── scripted inputs for the live demo (the console approves; nothing is auto-approved here) ──
def _leads(segment):
    def run(orch, clock):
        for l in _load("leads.json")[segment]:
            orch.new_lead(segment, l["company"], l["contact"])
    return run


def _reply(mid):
    def run(orch, clock):
        clock.advance(days=1)
        r = next(x for x in _load("replies.json")["replies"] if x["message_id"] == mid)
        for _ in range(2):  # delivered twice: the second delivery is ignored
            orch.ingest("email.replied", f"resend:{mid}", {"deal_id": r["deal_id"], "text": r["text"], "message_id": mid}, "webhook")
    return run


def _meeting(orch, clock):
    clock.advance(days=1)
    orch.ingest("meeting.booked", "calcom:bk-sunny-1", {"deal_id": "D-sunnybowl"}, "webhook")


def _transcript(orch, clock):
    clock.advance(days=4)
    orch.ingest("transcript.ready", "fireflies:ff-sunnybowl-discovery",
                {"deal_id": "D-sunnybowl", "transcript_id": "ff-sunnybowl-discovery"}, "webhook")


def _esign(orch, clock):
    env = (orch.crm.get_deal("D-sunnybowl") or {}).get("fields", {}).get("envelope_id")
    if not env:
        raise HTTPException(409, "No envelope yet: approve the IO in the approval queue first, then run this step.")
    orch.executor.esign.complete(env)
    orch.ingest("esign.completed", f"docusign:{env}:completed", {"deal_id": "D-sunnybowl", "envelope_id": env}, "webhook")


def _time(orch, clock):
    clock.advance(days=8)
    orch.tick()


SCENARIO = [
    ("Brand leads arrive (3 companies)", "Enrich, score and tier; draft outreach; tier-A first touch waits for you.", _leads("brands")),
    ("Reply from Sunny Bowl (untrusted, delivered twice)", "Pricing question + a prompt-injection line. Watch the flags.", _reply("msg-sunny-1")),
    ("Opt-out from PeakForm", "Unsubscribe: no more emails, whatever an agent proposes.", _reply("msg-peak-1")),
    ("Meeting booked with Sunny Bowl", "Call brief built with lessons learned so far.", _meeting),
    ("Fireflies transcript ready", "Deal fields + lessons; qualified; IO drafted and validated; IO waits for you.", _transcript),
    ("E-signature completed", "Approve the IO first. Closes the deal and hands off.", _esign),
    ("Agency leads arrive (agencies pack only)", "Second segment from config; outreach reuses a brand lesson.", _leads("agencies")),
    ("8 days pass (scheduler tick)", "Follow-ups and SLA checks fire; stalls flagged.", _time),
]


# ── endpoints ───────────────────────────────────────────────────────────
def _company_contact(orch, d):
    return orch.crm.get_company(d["company_id"]) or {}, orch.crm.get_contact(d["contact_id"]) or {}


@router.get("/state")
def state():
    orch, clock = _system()
    with _lock:
        deals = []
        for d in orch.crm.list_deals():
            c, ct = _company_contact(orch, d)
            deals.append(d | {"company_name": c.get("name"), "contact_name": ct.get("name"), "contact_title": ct.get("title")})
        step = int(orch.store.get_setting("scenario_step", "0"))
        return {
            "clock": clock().isoformat(), "kill_switch": orch.kill_switch.engaged(),
            "packs": [{"id": p.id, "label": p.label} for p in orch.packs.all()],
            "deals": deals, "approvals": orch.store.approvals(),
            "lessons": [l.__dict__ for l in orch.store.all()], "tasks": orch.crm.tasks(),
            "outbox": orch.executor.email.outbox(), "envelopes": orch.executor.esign.envelopes(),
            "digest": orch.digest(), "audit": {"verify": orch.store.verify_audit(), "tail": orch.store.audit_log(40)},
            "events": {"total": len(orch.store.events()), "dead": [e for e in orch.store.events() if e["status"] == "dead"]},
            "scenario": {"step": step, "steps": [{"title": t, "hint": h} for t, h, _ in SCENARIO]},
            "last_trace": json.loads(orch.store.get_setting("last_trace", "[]")),
        }


@router.get("/deals/{deal_id}")
def deal(deal_id: str):
    orch, _ = _system()
    d = orch.crm.get_deal(deal_id)
    if not d:
        raise HTTPException(404, f"no deal {deal_id}")
    c, ct = _company_contact(orch, d)
    return {"deal": d, "company": c, "contact": ct, "activities": orch.crm.activities(deal_id),
            "tasks": [t for t in orch.crm.tasks() if t["deal_id"] == deal_id],
            "emails": [m for m in orch.executor.email.outbox() if m["deal_id"] == deal_id]}


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    note: str = ""
    by: str = "console-user"


def _run_and_record(orch, clock) -> list:
    trace = orch.run()
    _save_clock(orch, clock)
    orch.store.set_setting("last_trace", json.dumps(trace, default=str)[:200000])
    return trace


@router.post("/approvals/{approval_id}")
def decide(approval_id: str, body: DecisionIn):
    orch, clock = _system()
    with _lock:
        res = (orch.approve if body.decision == "approve" else orch.reject)(approval_id, body.by, body.note)
        if not res.get("ok"):
            raise HTTPException(409, res.get("error", "cannot decide"))
        return {"ok": True, "trace": _run_and_record(orch, clock)}


class KillIn(BaseModel):
    on: bool
    by: str = "console-user"


@router.post("/killswitch")
def killswitch(body: KillIn):
    orch, _ = _system()
    orch.kill_switch.set(body.on, body.by)
    return {"kill_switch": orch.kill_switch.engaged()}


@router.post("/scenario/next")
def scenario_next():
    orch, clock = _system()
    with _lock:
        step = int(orch.store.get_setting("scenario_step", "0"))
        if step >= len(SCENARIO):
            raise HTTPException(409, "Scenario complete. Reset to start again.")
        title, _, fn = SCENARIO[step]
        fn(orch, clock)
        orch.store.set_setting("scenario_step", str(step + 1))
        return {"step": step + 1, "title": title, "trace": _run_and_record(orch, clock)}


@router.post("/scenario/reset")
def scenario_reset():
    _system(reset=True)
    return {"ok": True}


WEBHOOKS = {
    "email-reply": ("email.replied", lambda b: f"resend:{b['message_id']}"),
    "fireflies": ("transcript.ready", lambda b: f"fireflies:{b['transcript_id']}"),
    "esign": ("esign.completed", lambda b: f"docusign:{b['envelope_id']}:completed"),
    "calcom": ("meeting.booked", lambda b: f"calcom:{b['booking_id']}"),
}


@router.post("/webhooks/{source}")
async def webhook(source: str, request: Request):
    if source not in WEBHOOKS:
        raise HTTPException(404, f"unknown webhook source {source!r}")
    raw = await request.body()
    expected = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, request.headers.get("X-Cool-Signature", "")):
        raise HTTPException(401, "bad signature")
    try:
        body = json.loads(raw)
        type_, key_fn = WEBHOOKS[source]
        key = key_fn(body)
    except (ValueError, KeyError) as e:
        raise HTTPException(422, f"bad payload: {e}")
    orch, clock = _system()
    with _lock:
        new = orch.ingest(type_, key, body, f"webhook:{source}")
        trace = _run_and_record(orch, clock) if new else []
    return {"accepted": new, "duplicate": not new, "trace": trace}

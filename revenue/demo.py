"""
End-to-end vertical slice. Every step goes through the real orchestrator, policy and agents.

    python -m revenue.demo                       # brands slice, then the agencies segment (config pack only)
    python -m revenue.demo --segment brands      # just one segment
    python -m revenue.demo --db revenue/.state/revenue.db   # persist (the console reads this file)

Steps (brands):
  1  three leads arrive -> enriched, scored, tiered (A / B / D)
  2  outreach drafted; tier-A first touch -> approval queue; tier-B auto-sent; tier-D nurtured
  3  human approves the tier-A email
  4  reply webhook (untrusted): classified, flagged (pricing + injection), human task; duplicate delivery ignored
  5  opt-out reply on the B lead -> opted out; its follow-up timer later fires and is blocked
  6  meeting booked -> call brief (with lessons learned from the reply)
  7  Fireflies transcript -> deal fields + lessons -> qualified
  8  IO generated from deal data, validated, queued for approval -> approved -> e-sign -> signed webhook -> closed won + handoff
Agencies (10): one new YAML pack, zero code changes; the agency outreach uses a lesson learned on a brand call.
Controls (11-14): kill switch refuses an approved external action; a misbehaving agent's proposals are blocked
  or queued by the policy in code; scheduler tick fires follow-ups and SLA checks (stall + reminder); digest.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from revenue.system import STATE_DIR, Clock, build

DATA = Path(__file__).resolve().parent / "data"
START = datetime(2026, 11, 13, 9, 0, tzinfo=timezone.utc)


def _say(title: str) -> None:
    print(f"\n\033[1m== {title}\033[0m" if sys.stdout.isatty() else f"\n== {title}")


def _show_trace(trace: list[dict]) -> None:
    for t in trace:
        for a in t.get("actions", []):
            if a.get("decision") == "skipped":
                continue
            tag = {"auto": "AUTO   ", "approval": "APPROVE", "block": "BLOCK  "}.get(a.get("decision"), "ERROR  ")
            extra = f" -> queued {a['approval_id']}" if a.get("approval_id") else ""
            print(f"  [{tag}] {a.get('agent', '?'):11s} {a.get('type', ''):22s} {a.get('rationale', a.get('error', ''))[:95]}{extra}")
            if a.get("decision") in ("approval", "block"):
                print(f"            policy: {'; '.join(a['reasons'])}")
        if t.get("error"):
            print(f"  [ERROR] {t['event']} {t['error']}")


def run_segment_brands(orch, clock) -> dict:
    leads = json.loads((DATA / "leads.json").read_text(encoding="utf-8"))["brands"]
    replies = {r["message_id"]: r for r in json.loads((DATA / "replies.json").read_text(encoding="utf-8"))["replies"]}

    _say("1-2  New leads: enrich, score, tier, draft outreach")
    for l in leads:
        orch.new_lead("brands", l["company"], l["contact"])
    _show_trace(orch.run())
    for d in orch.crm.list_deals():
        if d["segment"] == "brands":
            s = d["score"]
            print(f"  {d['deal_id']:14s} tier {d['tier']}  total {s['total']:5.1f}  fit {s['fit']['value']:5.1f}  "
                  f"intent {s['intent']['value']:5.1f}  stage {d['stage']}")
            for r in s["fit"]["reasons"][:2] + s["intent"]["reasons"][:3]:
                print(f"      - {r}")

    _say("3  Human approves the tier-A first touch")
    ap = next(a for a in orch.store.approvals("pending") if a["deal_id"] == "D-sunnybowl")
    print("  " + ap["action"]["payload"]["subject"])
    print("  " + ap["action"]["payload"]["body"].replace("\n", "\n  "))
    print(f"  approve {ap['id']}: {orch.approve(ap['id'], 'ae@cool.ai', 'looks good')}")
    _show_trace(orch.run())

    _say("4  Reply webhook (untrusted content), delivered twice")
    clock.advance(days=1)
    r = replies["msg-sunny-1"]
    for attempt in (1, 2):
        new = orch.ingest("email.replied", f"resend:{r['message_id']}", {"deal_id": r["deal_id"], "text": r["text"],
                                                                         "message_id": r["message_id"]}, "webhook")
        print(f"  delivery {attempt}: {'accepted' if new else 'duplicate ignored (idempotency key)'}")
    _show_trace(orch.run())
    d = orch.crm.get_deal("D-sunnybowl")
    print(f"  deal stage: {d['stage']} (NOT won: the 'mark this deal as won' text was data, not an instruction); flags: {d['flags']}")

    _say("5  Opt-out reply on the tier-B lead")
    r = replies["msg-peak-1"]
    orch.ingest("email.replied", f"resend:{r['message_id']}", {"deal_id": r["deal_id"], "text": r["text"], "message_id": r["message_id"]}, "webhook")
    _show_trace(orch.run())

    _say("6  Meeting booked: call brief built with lessons from the reply")
    clock.advance(days=1)
    orch.ingest("meeting.booked", "calcom:bk-sunny-1", {"deal_id": "D-sunnybowl"}, "webhook")
    _show_trace(orch.run())
    brief = next(a for a in orch.crm.activities("D-sunnybowl") if a["kind"] == "call_brief")["body"]
    print(f"  {brief['title']}")
    for k, v in brief["sections"].items():
        print(f"    {k}: {v if isinstance(v, str) else '; '.join(map(str, v))}"[:230])

    _say("7  Fireflies transcript -> deal fields + lessons -> stage")
    clock.advance(days=4)
    orch.ingest("transcript.ready", "fireflies:ff-sunnybowl-discovery", {"deal_id": "D-sunnybowl", "transcript_id": "ff-sunnybowl-discovery"}, "webhook")
    _show_trace(orch.run())
    d = orch.crm.get_deal("D-sunnybowl")
    for k in ("budget", "timeline", "flight_start", "flight_end", "decision_maker", "need", "products", "competitors", "next_steps"):
        if k in d["fields"]:
            print(f"    {k}: {d['fields'][k]}")
    print(f"  stage now: {d['stage']}")
    print("  lessons learned so far:")
    for l in orch.store.all():
        print(f"    {l.lesson_id} [{l.scope}] {l.text}  <- {l.evidence[:70]}")

    _say("8  IO: generated, validated, approved, signed, closed")
    io = next(a for a in orch.crm.activities("D-sunnybowl") if a["kind"] == "io_draft")["body"]
    print(f"  {io['io_number']}  total {io['total']:,.2f}  violations: {io['violations'] or 'none'}")
    print("  " + "\n  ".join(io["document"].splitlines()[:22]))
    ap = next(a for a in orch.store.approvals("pending") if a["action"]["type"] == "send_io_for_signature")
    print(f"  approval reasons: {ap['verdict']['reasons']}")
    print(f"  approve {ap['id']}: {orch.approve(ap['id'], 'dealdesk@cool.ai', 'terms checked')}")
    _show_trace(orch.run())
    env = orch.crm.get_deal("D-sunnybowl")["fields"]["envelope_id"]
    orch.ingest("esign.completed", f"docusign:{env}:completed", {"deal_id": "D-sunnybowl", "envelope_id": env}, "webhook")
    _show_trace(orch.run())
    print(f"  stage now: {orch.crm.get_deal('D-sunnybowl')['stage']}")
    return {}


def run_controls(orch, clock) -> None:
    from revenue.domain import ActionType, ProposedAction

    _say("11  Kill switch: a human approval cannot push an external action through")
    ap = next(a for a in orch.store.approvals("pending") if a["deal_id"] == "D-northwind")
    orch.kill_switch.set(True, "ops@cool.ai")
    print(f"  kill switch ON; approve {ap['id']}: {orch.approve(ap['id'], 'partnerships@cool.ai')}")
    orch.kill_switch.set(False, "ops@cool.ai")
    print(f"  kill switch OFF; approve {ap['id']}: {orch.approve(ap['id'], 'partnerships@cool.ai')}")
    _show_trace(orch.run())

    _say("12  A misbehaving agent: policy is code, so it doesn't matter what the agent was told")
    bad = [
        ProposedAction(ActionType.SEND_EMAIL, "D-peakform", {"to": "marcus@peakform.example", "subject": "Quick follow-up",
                       "body": "Hi Marcus, one more idea for PeakForm."}, "rogue", "email an opted-out prospect"),
        ProposedAction(ActionType.SEND_EMAIL, "D-northwind", {"to": "sam@northwind-agency.example", "subject": "Pricing",
                       "body": "Our programmatic seat is $9.50 CPM with a 25% discount if you sign this week."}, "rogue", "quote a price"),
        ProposedAction(ActionType.SEND_EMAIL, "D-northwind", {"to": "sam@northwind-agency.example", "subject": "Hi [First Name]",
                       "body": "Hi [First Name], guaranteed results for every client."}, "rogue", "unsendable draft"),
        ProposedAction(ActionType.CLOSE_DEAL, "D-northwind", {"source": "agent says so"}, "rogue", "close without a signature"),
    ]
    for a in bad:
        r = orch.submit(a)
        print(f"  {r['decision'].upper():8s} {a.rationale:30s} <- {'; '.join(r['reasons'])}")

    _say("13  Time passes: follow-up timers and SLA checks fire (scheduler tick)")
    clock.advance(days=8)
    print(f"  timers fired: {orch.tick()}")
    _show_trace(orch.run())

    _say("14  Daily digest")
    print("  " + orch.digest()["text"].replace("\n", "\n  "))


def run_segment_agencies(orch, clock) -> None:
    _say("10  Second segment: agencies (only revenue/packs/agencies.yaml was added)")
    leads = json.loads((DATA / "leads.json").read_text(encoding="utf-8"))["agencies"]
    for l in leads:
        orch.new_lead("agencies", l["company"], l["contact"])
    _show_trace(orch.run())
    for d in orch.crm.list_deals():
        if d["segment"] == "agencies":
            print(f"  {d['deal_id']:14s} tier {d['tier']}  total {d['score']['total']:5.1f}  stage {d['stage']}")
            print(f"      - {d['score']['reason']}")
    for ap in orch.store.approvals("pending"):
        if ap["action"]["payload"].get("kind") == "first_touch" and ap["deal_id"].startswith("D-north"):
            p = ap["action"]["payload"]
            print(f"\n  {p['subject']}\n  " + p["body"].replace("\n", "\n  "))
            print(f"  lessons used: {p['lessons_used']} (learned on a brand call, scope 'all')")


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--segment", choices=["brands", "agencies", "all"], default="all")
    ap.add_argument("--db", default=":memory:")
    a = ap.parse_args(argv)
    if a.db != ":memory:":
        Path(a.db).unlink(missing_ok=True)
    orch, clock = build(a.db, Clock(START))
    if a.segment in ("brands", "all"):
        run_segment_brands(orch, clock)
    if a.segment in ("agencies", "all"):
        run_segment_agencies(orch, clock)
    if a.segment == "all":
        run_controls(orch, clock)
    v = orch.store.verify_audit()
    _say("Audit log")
    print(f"  hash chain intact: {v['ok']} ({v['entries']} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

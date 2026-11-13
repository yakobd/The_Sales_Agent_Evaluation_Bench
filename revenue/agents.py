"""
Single-responsibility agents. Each one:
  - declares the event types it handles and the tools it may use (its scope);
  - reads and computes through its ToolBelt;
  - returns ProposedActions. It never sends, writes or closes anything itself.

All segment-specific behaviour comes from the pack fetched with `get_pack(deal["segment"])`.
No agent mentions a segment by name (enforced by a test).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import timedelta

from revenue.domain import ActionType, ProposedAction, Stage, Tier
from revenue.tools import ToolBelt


class Agent(ABC):
    name: str = "agent"
    handles: frozenset[str] = frozenset()
    scope: frozenset[str] = frozenset()       # tools it may call
    emits: frozenset[ActionType] = frozenset()  # action types it may propose (checked by the orchestrator)
    system_prompt: str = ""                    # used by the Claude runtime

    def act(self, kind: ActionType, deal_id: str, payload: dict, why: str) -> ProposedAction:
        return ProposedAction(type=kind, deal_id=deal_id, payload=payload, agent=self.name, rationale=why)

    @abstractmethod
    def handle(self, event: dict, t: ToolBelt) -> list[ProposedAction]:
        ...


class ProspectingAgent(Agent):
    """Enrich a new lead, score it (fit / intent / engagement), assign a tier."""
    name = "prospecting"
    handles = frozenset({"lead.created", "engagement.recorded"})
    scope = frozenset({"now", "get_deal", "get_company", "get_activities", "get_pack", "enrich_company", "score_lead"})
    emits = frozenset({ActionType.UPDATE_DEAL})

    def handle(self, event, t):
        deal = t("get_deal", event["payload"]["deal_id"])
        company = t("get_company", deal["company_id"])
        pack = t("get_pack", deal["segment"])
        actions = []
        if event["type"] == "lead.created":
            enr = t("enrich_company", company)
            company = company | enr
            actions.append(self.act(ActionType.UPDATE_DEAL, deal["deal_id"], {"company": enr, "stage": Stage.ENRICHED.value},
                                    f"enriched {company['name']}: {len(enr['attributes'])} attributes, {len(enr['signals'])} signals"))
        sc = t("score_lead", pack, company.get("attributes", {}), company.get("signals", []),
               t("get_activities", deal["deal_id"]), t("now").date())
        update = {"score": sc.to_dict(), "tier": sc.tier.value}
        if event["type"] == "lead.created":
            update["stage"] = (Stage.NURTURE if sc.tier == Tier.D else Stage.SCORED).value
        actions.append(self.act(ActionType.UPDATE_DEAL, deal["deal_id"], update, sc.reason))
        return actions


class OutreachAgent(Agent):
    """Draft first touches and follow-ups from the pack, the freshest signal, and lessons."""
    name = "outreach"
    handles = frozenset({"deal.stage_changed", "timer.fired"})
    scope = frozenset({"now", "get_deal", "get_company", "get_contact", "get_pack", "fresh_signals", "retrieve_lessons", "draft_email"})
    emits = frozenset({ActionType.SEND_EMAIL, ActionType.SCHEDULE_TIMER})
    system_prompt = ("You write B2B outreach emails for Cool AI. Start from the draft_email tool's draft for this deal, keep the "
                     "pack's template structure, cite only in-window signals returned by fresh_signals, reuse at most one "
                     "lesson line, never mention pricing, discounts or contracts, and never invent facts. Then call "
                     "propose_action with type 'send_email' and payload {to, subject, body, kind, lessons_used}.")

    def handle(self, event, t):
        p = event["payload"]
        deal = t("get_deal", p["deal_id"])
        if event["type"] == "deal.stage_changed" and p.get("to") == Stage.SCORED.value:
            kind = "first_touch"
        elif event["type"] == "timer.fired" and p.get("kind") == "follow_up" and deal["stage"] == Stage.OUTREACH.value:
            kind = "follow_up"
        else:
            return []
        if deal["opted_out"]:
            return []
        pack = t("get_pack", deal["segment"])
        company, contact = t("get_company", deal["company_id"]), t("get_contact", deal["contact_id"])
        fresh = t("fresh_signals", pack, company.get("signals", []), t("now").date())
        # what this prospect cares about: fresh signal types + known interests; objections are always relevant
        tags = {s["type"] for s in fresh} | set(company.get("attributes", {}).get("interests", [])) | {"objection"}
        lessons = t("retrieve_lessons", deal["segment"], tags, 3, True)
        d = t("draft_email", pack, kind, company, contact, fresh, lessons)
        actions = [self.act(ActionType.SEND_EMAIL, deal["deal_id"],
                            {"to": contact["email"], **d}, f"{kind} for tier {deal['tier']} lead; hook: {d['hook_basis']}")]
        days = pack.sla_days("outreach") or 5
        actions.append(self.act(ActionType.SCHEDULE_TIMER, deal["deal_id"],
                                {"key": f"followup:{deal['deal_id']}:{deal['touches'] + 1}", "in_days": days,
                                 "event_type": "timer.fired", "payload": {"deal_id": deal["deal_id"], "kind": "follow_up"}},
                                f"follow up in {days} days if no reply"))
        return actions


class InboxAgent(Agent):
    """Classify replies (untrusted), flag risks, move the stage, route humans in when needed."""
    name = "inbox"
    handles = frozenset({"email.replied"})
    scope = frozenset({"now", "get_deal", "get_contact", "get_pack", "classify_reply", "extract_lessons"})
    emits = frozenset({ActionType.UPDATE_DEAL, ActionType.FLAG, ActionType.CREATE_TASK, ActionType.RECORD_LESSON})

    def handle(self, event, t):
        p = event["payload"]
        deal = t("get_deal", p["deal_id"])
        r = t("classify_reply", p["text"])
        now = t("now")
        actions = [self.act(ActionType.UPDATE_DEAL, deal["deal_id"],
                            {"activity": {"kind": "reply", "label": r["label"], "flags": r["flags"], "text": r["clean_text"][:500]},
                             **({"engagement": r["engagement_event"]} if r["engagement_event"] else {})},
                            f"reply classified '{r['label']}'" + (f" (matched '{r['matched']}')" if r["matched"] else ""))]
        stage = {"interested": Stage.ENGAGED, "meeting_request": Stage.ENGAGED, "question": Stage.ENGAGED,
                 "not_now": Stage.NURTURE, "unsubscribe": Stage.NURTURE}.get(r["label"])
        upd = {}
        if stage and stage.value != deal["stage"]:
            upd["stage"] = stage.value
        if r["label"] == "unsubscribe":
            upd["opted_out"] = True
        if upd:
            actions.append(self.act(ActionType.UPDATE_DEAL, deal["deal_id"], upd, f"reply '{r['label']}' -> {upd}"))
        for f in r["flags"]:
            actions.append(self.act(ActionType.FLAG, deal["deal_id"], {"flag": f}, f"reply raised {f}"))
        if r["needs_human"]:
            actions.append(self.act(ActionType.CREATE_TASK, deal["deal_id"],
                                    {"title": f"Review reply ({r['label']}; flags: {', '.join(r['flags']) or 'none'})",
                                     "due": (now + timedelta(days=1)).date().isoformat()},
                                    "reply needs a human (pricing/contract/injection/objection)"))
        elif r["label"] == "meeting_request":
            actions.append(self.act(ActionType.CREATE_TASK, deal["deal_id"],
                                    {"title": "Book the meeting the prospect asked for", "due": now.date().isoformat()},
                                    "prospect asked for a meeting"))
        utt = [{"speaker": "prospect", "text": r["clean_text"], "is_prospect": True}]
        for lesson in t("extract_lessons", utt, deal["segment"], f"reply:{p.get('message_id', event['key'])}"):
            actions.append(self.act(ActionType.RECORD_LESSON, deal["deal_id"], {"lesson": lesson.__dict__},
                                    f"reply taught: {lesson.text}"))
        return actions


class KnowledgeAgent(Agent):
    """Meetings: build the call brief (with lessons) and digest the transcript into deal fields + lessons."""
    name = "knowledge"
    handles = frozenset({"meeting.booked", "transcript.ready"})
    scope = frozenset({"now", "get_deal", "get_company", "get_contact", "get_pack", "retrieve_lessons", "build_call_brief",
                       "fetch_transcript", "digest_transcript", "missing_exit_criteria"})
    emits = frozenset({ActionType.UPDATE_DEAL, ActionType.CREATE_TASK, ActionType.RECORD_LESSON})
    system_prompt = ("You turn sales-call transcripts into deal fields and lessons. Use digest_transcript for the baseline, "
                     "correct it only where the transcript clearly says otherwise, quote evidence for every field, and "
                     "propose update_deal (fields, activity) plus one record_lesson per genuinely reusable lesson.")

    def handle(self, event, t):
        p = event["payload"]
        deal = t("get_deal", p["deal_id"])
        pack = t("get_pack", deal["segment"])
        if event["type"] == "meeting.booked":
            company, contact = t("get_company", deal["company_id"]), t("get_contact", deal["contact_id"])
            lessons = t("retrieve_lessons", deal["segment"], set(company.get("attributes", {}).get("interests", [])) | {"objection"}, 4)
            brief = t("build_call_brief", pack, deal, company, contact, lessons)
            return [self.act(ActionType.UPDATE_DEAL, deal["deal_id"],
                             {"stage": Stage.MEETING.value, "activity": {"kind": "call_brief", **brief}, "lessons_used": brief["lessons_used"]},
                             f"meeting booked; call brief with {len(brief['lessons_used'])} lessons")]
        tr = t("fetch_transcript", p["transcript_id"])
        dg = t("digest_transcript", tr, pack, deal["segment"])
        merged = deal | {"fields": deal["fields"] | dg["fields"]}
        missing = t("missing_exit_criteria", merged, pack, Stage.QUALIFIED.value)
        upd = {"fields": dg["fields"], "activity": {"kind": "transcript_digest", "summary": dg["summary"], "evidence": dg["evidence"]}}
        actions = []
        if not missing:
            upd["stage"] = Stage.QUALIFIED.value
        actions.append(self.act(ActionType.UPDATE_DEAL, deal["deal_id"], upd,
                                f"transcript digested: {dg['summary']}" + ("; qualified" if not missing else f"; missing {missing}")))
        if missing:
            actions.append(self.act(ActionType.CREATE_TASK, deal["deal_id"],
                                    {"title": "Confirm before qualifying: " + ", ".join(missing),
                                     "due": (t("now") + timedelta(days=2)).date().isoformat()}, "exit criteria not met"))
        for lesson in dg["lessons"]:
            actions.append(self.act(ActionType.RECORD_LESSON, deal["deal_id"], {"lesson": lesson.__dict__},
                                    f"call taught: {lesson.text}"))
        return actions


class DealDeskAgent(Agent):
    """Generate and validate the IO from deal data; route it for signature; close on signature."""
    name = "deal_desk"
    handles = frozenset({"deal.stage_changed", "esign.completed"})
    scope = frozenset({"now", "get_deal", "get_company", "get_contact", "get_pack", "propose_line_items", "build_io",
                       "render_io", "validate_io"})
    emits = frozenset({ActionType.GENERATE_IO, ActionType.CREATE_TASK, ActionType.SEND_IO_FOR_SIGNATURE,
                       ActionType.CLOSE_DEAL, ActionType.HANDOFF})

    def handle(self, event, t):
        p = event["payload"]
        deal = t("get_deal", p["deal_id"])
        if event["type"] == "esign.completed":
            return [self.act(ActionType.CLOSE_DEAL, deal["deal_id"], {"source": "esign.completed", "envelope_id": p["envelope_id"]},
                             "IO signed"),
                    self.act(ActionType.HANDOFF, deal["deal_id"], {"to": "account_management"}, "won: hand off to AM / onboarding")]
        if p.get("to") != Stage.QUALIFIED.value:
            return []
        pack = t("get_pack", deal["segment"])
        company, contact = t("get_company", deal["company_id"]), t("get_contact", deal["contact_id"])
        f = dict(deal["fields"])
        if not f.get("line_items") and f.get("budget"):
            f["line_items"] = t("propose_line_items", f["budget"], f.get("products", []), pack)
        io_no = f"IO-{deal['deal_id']}-1"
        data = t("build_io", deal | {"fields": f}, company, contact, pack, io_no)
        doc = t("render_io", data, pack)
        violations = t("validate_io", data, pack, t("now").date(), doc)
        actions = [self.act(ActionType.GENERATE_IO, deal["deal_id"],
                            {"io_number": io_no, "data": data, "document": doc, "violations": violations,
                             "fields": {"line_items": f.get("line_items")}},
                            f"IO drafted from deal data; {len(violations)} validation issues")]
        if violations:
            actions.append(self.act(ActionType.CREATE_TASK, deal["deal_id"],
                                    {"title": "Fix IO: " + "; ".join(f"{v['code']} ({v['evidence']})" for v in violations),
                                     "due": t("now").date().isoformat(), "owner": "deal_desk"}, "IO failed validation"))
        else:
            actions.append(self.act(ActionType.SEND_IO_FOR_SIGNATURE, deal["deal_id"],
                                    {"io_number": io_no, "signer": contact["email"], "document": doc},
                                    "valid IO ready for signature"))
        return actions


class TrackerAgent(Agent):
    """SLA timers, stall detection, reminders and the daily digest."""
    name = "tracker"
    handles = frozenset({"deal.stage_changed", "timer.fired"})
    scope = frozenset({"now", "get_deal", "get_pack", "detect_stall"})
    emits = frozenset({ActionType.SCHEDULE_TIMER, ActionType.FLAG, ActionType.CREATE_TASK})

    def handle(self, event, t):
        p = event["payload"]
        deal = t("get_deal", p["deal_id"])
        pack = t("get_pack", deal["segment"])
        if event["type"] == "deal.stage_changed":
            days = pack.sla_days(p["to"])
            if days is None:
                return []
            return [self._sla_timer(deal["deal_id"], p["to"], days, 1)]
        if p.get("kind") != "sla_check" or deal["stage"] != p.get("stage"):
            return []  # moved on: nothing stalled
        days = pack.sla_days(deal["stage"]) or 7
        s = t("detect_stall", deal, pack, t("now"))
        recheck = self._sla_timer(deal["deal_id"], deal["stage"], days, p.get("attempt", 1) + 1)  # keep watching this stage
        if not s:
            return [recheck]
        return [self.act(ActionType.FLAG, deal["deal_id"], {"flag": "stalled"}, s["reminder"]),
                self.act(ActionType.CREATE_TASK, deal["deal_id"], {"title": s["reminder"], "due": t("now").date().isoformat()},
                         "stall reminder"), recheck]

    def _sla_timer(self, deal_id: str, stage: str, days: int, attempt: int) -> ProposedAction:
        return self.act(ActionType.SCHEDULE_TIMER, deal_id,
                        {"key": f"sla:{deal_id}:{stage}:{attempt}", "in_days": days + 1, "event_type": "timer.fired",
                         "payload": {"deal_id": deal_id, "kind": "sla_check", "stage": stage, "attempt": attempt}},
                        f"SLA check #{attempt} for '{stage}' in {days + 1} days")


ALL_AGENTS = [ProspectingAgent(), OutreachAgent(), InboxAgent(), KnowledgeAgent(), DealDeskAgent(), TrackerAgent()]

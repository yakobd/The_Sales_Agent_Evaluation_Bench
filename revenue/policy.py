"""
Autonomy policy, enforced in code. Every ProposedAction passes through `AutonomyPolicy.evaluate`
before the orchestrator executes anything. Prompts are never trusted to keep the system safe.

Decision ladder (first match wins):
  1. Kill switch engaged + external action                 -> BLOCK
  2. Prospect opted out + outbound email                   -> BLOCK
  3. Unsendable content (placeholder, banned phrase)       -> BLOCK  (the agent must redraft)
  4. Follow-up cap exceeded                                -> BLOCK
  5. IO / contract for signature, or pricing               -> APPROVAL (always; packs cannot relax this)
  6. Closing a deal without a verified e-sign event        -> APPROVAL
  7. Outbound email that mentions price / contract terms   -> APPROVAL
  8. First touch to a top-tier lead                        -> APPROVAL (floor tier A; a pack may ADD tiers)
  9. Outbound email on a deal flagged for a human          -> APPROVAL
 10. Anything else (internal, reversible, low-risk)        -> AUTO

Packs can only make the policy stricter (e.g. add tier B to first-touch approval). Fields a pack
might try to use to relax it are never read.
"""
from __future__ import annotations

import re

from revenue.domain import EXTERNAL_ACTIONS, ActionType, Deal, Decision, PolicyVerdict, ProposedAction, Tier
from revenue.packs import SegmentPack
from scoring_evaluator import CURRENCY, PLACEHOLDER  # same detectors as the Tenacious-Bench evaluator

FLOOR_FIRST_TOUCH_APPROVAL = {Tier.A}
ALWAYS_APPROVAL = {ActionType.SEND_IO_FOR_SIGNATURE, ActionType.SEND_PRICING}
PRICING_TERMS = r"\b(pric(e|es|ing)|rate card|cpm|discount|quote|per (location|month)|fee)\b"
CONTRACT_TERMS = r"\b(contract|insertion order|\bIO\b|msa|terms and conditions|sign (here|the))\b"
HUMAN_FLAGS = {"pricing_request", "contract_or_legal", "injection_attempt"}


class KillSwitch:
    """Backed by the durable store so it survives restarts and is shared by every worker."""

    def __init__(self, store):
        self.store = store

    def engaged(self) -> bool:
        return self.store.get_setting("kill_switch", "off") == "on"

    def set(self, on: bool, actor: str) -> None:
        self.store.set_setting("kill_switch", "on" if on else "off")
        self.store.audit(actor, "kill_switch", {"on": on})


def content_risks(text: str, pack: SegmentPack) -> dict:
    t = text or ""
    return {
        "placeholder": bool(re.search(PLACEHOLDER, t) or re.search(r"\{[a-z_]+\}", t)),
        "banned": [p for p in pack["messaging"].get("banned_phrases", []) if re.search(rf"\b{re.escape(p)}\b", t, re.I)],
        "pricing": bool(re.search(CURRENCY, t, re.I) or re.search(PRICING_TERMS, t, re.I)),
        "contract": bool(re.search(CONTRACT_TERMS, t, re.I)),
    }


class AutonomyPolicy:
    def __init__(self, kill_switch: KillSwitch):
        self.kill_switch = kill_switch

    def evaluate(self, action: ProposedAction, deal: Deal, pack: SegmentPack) -> PolicyVerdict:
        t = action.type
        if t in EXTERNAL_ACTIONS and self.kill_switch.engaged():
            return PolicyVerdict(Decision.BLOCK, ["kill switch is engaged: no external actions"], "blocked")
        if t == ActionType.SEND_EMAIL and deal.opted_out:
            return PolicyVerdict(Decision.BLOCK, ["prospect opted out"], "blocked")

        if t == ActionType.SEND_EMAIL:
            text = f"{action.payload.get('subject', '')}\n{action.payload.get('body', '')}"
            risks = content_risks(text, pack)
            if risks["placeholder"]:
                return PolicyVerdict(Decision.BLOCK, ["unsendable: template placeholder left in"], "blocked")
            if risks["banned"]:
                return PolicyVerdict(Decision.BLOCK, [f"banned phrase: {', '.join(risks['banned'])}"], "blocked")
            cap = int(pack["stages"].get("max_followups", 2)) + 1
            if deal.touches >= cap and not action.payload.get("is_reply"):
                return PolicyVerdict(Decision.BLOCK, [f"follow-up cap reached ({deal.touches}/{cap} touches)"], "blocked")

        if t in ALWAYS_APPROVAL:
            return PolicyVerdict(Decision.APPROVAL, [f"{t.value} always needs human approval"], "high")
        if t == ActionType.CLOSE_DEAL and action.payload.get("source") != "esign.completed":
            return PolicyVerdict(Decision.APPROVAL, ["closing without a verified e-signature event"], "high")

        if t == ActionType.SEND_EMAIL:
            reasons = []
            if risks["pricing"]:
                reasons.append("email mentions pricing")
            if risks["contract"]:
                reasons.append("email mentions contract terms")
            tiers = FLOOR_FIRST_TOUCH_APPROVAL | {Tier(x) for x in (pack.raw.get("autonomy") or {}).get("first_touch_approval_tiers", [])}
            if deal.touches == 0 and deal.tier in tiers:
                reasons.append(f"first touch to a tier-{deal.tier.value} lead")
            if HUMAN_FLAGS & set(deal.flags):
                reasons.append("deal is flagged for a human: " + ", ".join(sorted(HUMAN_FLAGS & set(deal.flags))))
            if reasons:
                return PolicyVerdict(Decision.APPROVAL, reasons, "high")
        return PolicyVerdict(Decision.AUTO, ["low-risk: internal or within policy"], "low")

"""
Tracking skill: stage exit criteria, stall detection, reminders and the daily digest.
Stage SLAs and exit criteria come from the segment pack.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from revenue.domain import Stage
from revenue.packs import SegmentPack


def missing_exit_criteria(deal: dict, pack: SegmentPack, stage: str) -> list[str]:
    return [k for k in pack.exit_criteria(stage) if deal["fields"].get(k) in (None, "", [])]


def stall(deal: dict, pack: SegmentPack, now: datetime) -> dict | None:
    if Stage(deal["stage"]).is_terminal or deal["stage"] == Stage.NURTURE.value:
        return None
    sla = pack.sla_days(deal["stage"])
    if sla is None:
        return None
    # stalled = too long in the same stage (exit criteria not met), not "no activity": our own
    # follow-up emails must not hide a deal that isn't moving
    in_stage = (now - datetime.fromisoformat(deal.get("stage_since") or deal["last_activity"])).days
    if in_stage > sla:
        return {"deal_id": deal["deal_id"], "stage": deal["stage"], "idle_days": in_stage, "sla_days": sla,
                "reminder": f"{deal['deal_id']} has been in '{deal['stage']}' {in_stage} days (SLA {sla}). Next action needed."}
    return None


def digest(deals: list[dict], approvals: list[dict], stalls: list[dict], flags: list[dict], now: datetime) -> dict:
    by_stage = Counter(d["stage"] for d in deals)
    by_tier = Counter(d.get("tier") or "unscored" for d in deals)
    pending = [a for a in approvals if a["status"] == "pending"]
    lines = [f"Pipeline digest {now.date()}",
             f"- {len(deals)} deals: " + ", ".join(f"{k} {v}" for k, v in sorted(by_stage.items())),
             f"- Tiers: " + ", ".join(f"{k} {v}" for k, v in sorted(by_tier.items())),
             f"- {len(pending)} actions waiting for approval" + (": " + "; ".join(f"{a['action']['type']} ({a['action']['deal_id']})" for a in pending[:5]) if pending else ""),
             f"- {len(stalls)} stalled deals" + (": " + "; ".join(s["reminder"] for s in stalls[:5]) if stalls else ""),
             f"- {len(flags)} flags raised" + (": " + "; ".join(f"{f['deal_id']} {f['flag']}" for f in flags[:5]) if flags else "")]
    return {"text": "\n".join(lines), "by_stage": dict(by_stage), "by_tier": dict(by_tier),
            "pending_approvals": len(pending), "stalls": stalls, "flags": flags}

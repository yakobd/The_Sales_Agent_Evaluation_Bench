"""
Pre-send policy gate and router: "the model proposes, policy disposes".

route(task)            which writer handles the task: the deterministic template (cold note with no
                       in-window signal: nothing true and recent to pitch) or the model.
gate(task, email)      hard policies enforced in code before anything is sent. A blocked draft is
                       replaced by a safe fallback; it is never sent.

HONESTY NOTE. The gate reuses the frozen evaluator's own rule implementations for a subset of
codes (commercial commitments, stale-signal claims, unsendable output). Its effect on THOSE codes
is therefore by construction; what is worth measuring is (a) how often it has to fire (the fallback
rate: a gate that fires constantly turns the system into the template) and (b) what still fails on
the dimensions it does not gate (grounding, tone, peer claims, ...). ablations/score_gated.py reports both.
"""
import scoring_evaluator as E

# Hard policies: violations a business cannot ship, whatever the writer.
HARD_POLICY = {
    "PRICE_QUOTE": "pricing must come from a human",
    "CONTRACT_COMMITMENT": "contracts must come from a human",
    "CAPACITY_EXCEEDS_BENCH": "promises more engineers than the bench has",
    "CAPACITY_COMMITMENT_BEYOND_BENCH": "commits capacity the bench cannot cover",
    "SMS_BEFORE_REPLY": "no SMS before the prospect replies by email",
    "FUNDING_NOT_RECENT": "calls a stale funding round recent",
    "LAYOFF_NOT_RECENT": "calls a stale layoff recent",
    "LEADERSHIP_NOT_RECENT": "calls a stale leadership change recent",
    "TEMPLATE_PLACEHOLDER": "unsendable: template placeholder left in",
    "SUBJECT_TOO_LONG": "unsendable: subject over the channel limit",
}
FIRST_TOUCH = {"cold", "re_engagement", "referral"}
CTA_LINK = "https://cal.com/tenacious/15min"

SAFE_REPLY = {
    "subject": "Re: your question",
    "body": ("Thanks for the reply, and for the detail. I want to give you an accurate answer rather than a fast one, "
             "so I am checking with our delivery lead and will come back to you with specifics within one business day.\n\n"
             f"If it is easier to talk it through, here is a 15-minute slot: {CTA_LINK}"),
}


def valid_signals(task: dict) -> dict:
    """In-window signals only (funding 180d, layoff 120d, leadership 90d, measured from the data snapshot),
    plus AI maturity >= 2 (the Segment 4 trigger). Unknown recency counts as not valid."""
    f = E.brief_facts(task)
    return {"funding": bool(f["has_funding"] and f["funding_recent"] is True),
            "layoff": bool(f["has_layoff"] and f["layoff_recent"] is True),
            "leadership": bool(f["has_leadership"] and f["leadership_recent"] is True),
            "ai_maturity": (f["ai_score"] or 0) >= 2}


def route(task: dict) -> dict:
    etype = task["input"].get("email_type", "cold")
    sig = valid_signals(task)
    if etype in FIRST_TOUCH and not any(sig.values()):
        return {"writer": "template", "reason": "first touch with no in-window signal: send the exploratory note",
                "valid_signals": sig}
    return {"writer": "model", "reason": ("reply: needs a writer that reads the thread" if etype not in FIRST_TOUCH
                                          else "in-window signal to pitch"), "valid_signals": sig}


def gate(task: dict, email: dict) -> dict:
    r = E.score_task(task, email)
    hard = [v for v in r["violations"] if v["code"] in HARD_POLICY]
    return {"action": "block" if hard else "send",
            "blocked_by": [{"code": v["code"], "policy": HARD_POLICY[v["code"]], "evidence": v["evidence"]} for v in hard],
            "soft_violations": [v for v in r["violations"] if v["code"] not in HARD_POLICY]}


def fallback(task: dict, template_email: dict | None) -> tuple[dict, str]:
    """Safe replacement for a blocked draft: the honest template for first touches, a holding reply otherwise."""
    if task["input"].get("email_type", "cold") in FIRST_TOUCH and template_email:
        return template_email, "template"
    return SAFE_REPLY, "holding_reply"


def decide(task: dict, model_email: dict | None, template_email: dict | None, use_router: bool = True) -> dict:
    """Full pipeline for one task. Returns the email that would be sent and how it was chosen."""
    rt = route(task) if use_router else {"writer": "model", "reason": "router off", "valid_signals": valid_signals(task)}
    if rt["writer"] == "template" and template_email:
        return {"email": template_email, "source": "template", "route": rt, "gate": None}
    g = gate(task, model_email or {})
    if g["action"] == "send":
        return {"email": model_email, "source": "model", "route": rt, "gate": g}
    email, src = fallback(task, template_email)
    return {"email": email, "source": f"fallback:{src}", "route": rt, "gate": g}

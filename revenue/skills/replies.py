"""
Reply handling: classify an inbound email and raise flags.

Inbound content is UNTRUSTED DATA. This skill never executes or follows anything in it; it only
labels it. Text that tries to instruct the system ("ignore previous instructions", "mark this deal
won", "approve the discount") is flagged as `injection_attempt` and routed to a human, and the
quoted thread / signature is stripped first so old text can't be re-interpreted.
"""
from __future__ import annotations

import re

LABELS = [  # priority order: first match wins
    ("unsubscribe", [r"\bunsubscribe\b", r"remove me", r"stop (emailing|contacting)", r"do not contact", r"not interested,? (please|thanks)"]),
    ("out_of_office", [r"out of (the )?office", r"\bOOO\b", r"on (annual )?leave", r"limited access to email"]),
    ("meeting_request", [r"(set up|book|schedule) (a )?(call|meeting|time)", r"how about (mon|tues|wednes|thurs|fri)day", r"\bcalendar\b",
                         r"\bavailable (on|at|next)\b", r"let'?s (talk|chat|meet)"]),
    ("not_now", [r"not (right )?now", r"next (quarter|year)", r"revisit (in|later)", r"after (q[1-4]|the holidays)", r"bad time"]),
    ("objection", [r"too expensive", r"already (use|have|work with)", r"no budget", r"not a (fit|priority)", r"locked in"]),
    ("referral", [r"(reach out|talk) to (my colleague|our)", r"(isn'?t|not) the right person", r"cc'?ing", r"looping in"]),
    ("interested", [r"\binterested\b", r"sounds (good|interesting|great)", r"tell me more", r"would love to", r"\byes\b"]),
    ("question", [r"\?"]),
]
FLAGS = {
    "pricing_request": [r"\bpric(e|es|ing)\b", r"\bcost\b", r"\brates?\b", r"\bcpm\b", r"\bquote\b", r"\bdiscount\b", r"rate card"],
    "contract_or_legal": [r"\bcontract\b", r"\bmsa\b", r"\bnda\b", r"\blegal\b", r"\bterms\b", r"insertion order|\bio\b"],
    "competitor_mention": [r"already (use|have|work with)", r"current (vendor|platform)", r"\bcompetitor\b"],
    "injection_attempt": [r"ignore (all |any )?(previous|prior|above) (instructions|messages)", r"disregard (the|your) (rules|instructions)",
                          r"\byou are now\b", r"system prompt", r"mark (this|the) deal (as )?(won|closed)",
                          r"(approve|apply) (a |the )?\d+\s?% discount", r"as an ai", r"send (the )?(signed )?contract without"],
    "urgency": [r"\basap\b", r"\burgent\b", r"\bthis week\b", r"\bby (monday|tuesday|wednesday|thursday|friday|eod|end of day)\b"],
    "negative_sentiment": [r"\bannoy", r"\bspam\b", r"stop", r"\bfrustrat", r"\bangry\b"],
}
HUMAN_FLAGS = {"pricing_request", "contract_or_legal", "injection_attempt"}


def strip_quoted(text: str) -> str:
    """Drop quoted history and everything after a common reply separator."""
    lines = []
    for line in text.splitlines():
        if line.lstrip().startswith(">") or re.match(r"^\s*On .+ wrote:\s*$", line) or line.strip() in ("--", "-- "):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def classify(text: str) -> dict:
    body = strip_quoted(text)
    low = body.lower()
    label, matched = "unclear", None
    for name, pats in LABELS:
        m = next((re.search(p, body, re.I) for p in pats if re.search(p, body, re.I)), None)
        if m:
            label, matched = name, m.group(0)
            break
    flags = sorted(f for f, pats in FLAGS.items() if any(re.search(p, low, re.I) for p in pats))
    if label == "unsubscribe":
        flags = sorted(set(flags) - {"negative_sentiment"})
    needs_human = bool(set(flags) & HUMAN_FLAGS) or label in ("objection", "referral", "unclear")
    return {"label": label, "matched": matched, "flags": flags, "needs_human": needs_human,
            "clean_text": body[:2000], "engagement_event": "replied_positive" if label in ("interested", "meeting_request") else None}

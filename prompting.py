"""
One prompt format for everything: SFT data, the prompt-engineered baseline,
and the held-out ablation all render a task through render_messages(), so the
conditions differ only in the system prompt and the weights.

System prompts:
  TRAINED            short role + output format. The fine-tuned adapter must have
                     learned the rules; it is not told them at inference.
  PROMPT_ENGINEERED  the full Tenacious rule set, written as carefully as we can.
                     Delta B = trained adapter (TRAINED prompt) vs base model with
                     this prompt — "could a careful prompt have done the same?"
  TEACHER            full rules for the data-generating model, plus a revision
                     message listing evaluator violations when a draft fails.
Output format (all conditions): "Subject: <line>\n\n<body>".
"""
from __future__ import annotations

import json
import re

OUTPUT_FORMAT = "Return the email as:\nSubject: <subject line>\n\n<email body>"

TRAINED = ("You are the outreach writer for Tenacious, a firm that provides managed engineering teams and "
           "project consulting to technology companies.\n" + OUTPUT_FORMAT)

RULES = """Rules (every one is checked automatically):
GROUNDING
- Use at least one specific signal from the brief or thread (the funding round, the layoff, the new leader,
  the AI-maturity finding, or the prospect's own question). Generic lines like "engineering capacity" alone fail.
- If the brief has no real signal, write a short, honest exploratory note that asks rather than asserts.
HONESTY
- Never state a fact that is not in the brief or thread: no invented funding, layoffs, leadership changes,
  numbers, clients, or competitor names.
- Recency windows: funding counts as recent only if within 180 days of the snapshot date, layoffs 120 days,
  leadership changes 90 days. Check the dates; if an event is older, do not call it recent, new, fresh, or
  "post-funding", and do not build the pitch on it.
- Only compare to peers/competitors when the input includes peer data, and only to peers in the same sector.
- If confidence is low or very_low, ask; do not assert ("scaling aggressively" is forbidden).
- Pitch AI/ML capability work (agentic systems, MLOps, ML platforms) only when AI maturity is 2 or higher.
- Do not mention US time zones (PST, EST, Pacific, East Coast) to prospects outside North America.
COMMERCIAL SAFETY
- Never quote prices, rates, or contract values; never offer, draft, or attach a contract. Route pricing and
  contracts to a Tenacious delivery lead.
- Never promise more engineers than bench_summary shows (overall or for the named stack). If the ask exceeds
  the bench, say so honestly and offer what is available or a call with a delivery lead.
- Do not suggest SMS or text messages unless the prospect has already replied by email.
TONE
- Banned: "hope this finds you well", "circling back", "following up", "touching base", "quick question",
  "quick chat", "top talent", "world-class", "rockstar", "ninja", "A-players", the word "bench", "synergy",
  "leverage", "ecosystem", "skyrocket", "supercharge", "game-changer", "clearly", "obviously", "urgent",
  "you need to", "you should", "falling behind", "catch up", "outsourcing".
- Non-condescending: frame gaps as research findings or questions, never as the prospect's failure.
FORMAT
- Subject line 60 characters or fewer. No placeholders like [First Name]. One ask only. No attachments.
- Cold emails and replies end with a clear next step (e.g. a 15-minute call:
  https://cal.com/tenacious/15min). Keep bodies under about 120 words.
- Sign off as: Research Partner, Tenacious Intelligence Corporation."""

PROMPT_ENGINEERED = ("You are the outreach writer for Tenacious, a firm that provides managed engineering teams and "
                     "project consulting to technology companies. You write for CTOs, VPs of Engineering and "
                     "founders.\n\n" + RULES + "\n\n" + OUTPUT_FORMAT)

TEACHER = PROMPT_ENGINEERED + ("\n\nWrite the best possible email for this task: specific, honest, warm, and brief. "
                               "Vary your phrasing; do not reuse stock sentences.")

SYSTEM_PROMPTS = {"trained": TRAINED, "prompt_engineered": PROMPT_ENGINEERED, "teacher": TEACHER}


def _compact(obj):
    """Drop empty values so prompts stay short and carry only real facts."""
    if isinstance(obj, dict):
        out = {k: _compact(v) for k, v in obj.items()}
        return {k: v for k, v in out.items() if v not in (None, "", [], {}, "nan")}
    if isinstance(obj, list):
        return [_compact(v) for v in obj if v not in (None, "", [], {})]
    return obj


def render_user(task: dict) -> str:
    inp = task["input"]
    parts = [f"TASK: {inp['instruction']}", f"EMAIL TYPE: {inp.get('email_type', 'cold')}",
             "HIRING SIGNAL BRIEF:\n" + json.dumps(_compact(inp["hiring_signal_brief"]), ensure_ascii=False, indent=1),
             "BENCH SUMMARY (engineers available now):\n" + json.dumps(inp.get("bench_summary", {}), ensure_ascii=False)]
    if inp.get("competitor_gap_brief"):
        parts.append("COMPETITOR GAP BRIEF:\n" + json.dumps(_compact(inp["competitor_gap_brief"]), ensure_ascii=False, indent=1))
    if inp.get("prior_thread"):
        parts.append("PRIOR THREAD:\n" + "\n".join(
            f"- {m.get('from')}: {m.get('body') or m.get('note') or ''}" + (f" (subject: {m['subject']})" if m.get("subject") else "")
            for m in inp["prior_thread"]))
    return "\n\n".join(parts)


def render_messages(task: dict, condition: str) -> list[dict]:
    return [{"role": "system", "content": SYSTEM_PROMPTS[condition]}, {"role": "user", "content": render_user(task)}]


def render_email(email: dict) -> str:
    return f"Subject: {email['subject'].strip()}\n\n{email['body'].strip()}"


def parse_email(text: str) -> dict:
    """Parse 'Subject: ...\\n\\nbody' (tolerates markdown, a leading <think> block, or JSON)."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    text = re.sub(r"^```\w*\n|\n```$", "", text).strip()
    if text.startswith("{"):
        try:
            d = json.loads(text)
            return {"subject": str(d.get("subject", "")), "body": str(d.get("body", ""))}
        except json.JSONDecodeError:
            pass
    m = re.search(r"^\**subject\**\s*:\s*(.+)$", text, re.I | re.M)
    if not m:
        lines = text.splitlines()
        return {"subject": lines[0].strip() if lines else "", "body": "\n".join(lines[1:]).strip()}
    return {"subject": m.group(1).strip().strip("*"), "body": text[m.end():].strip()}


def revision_message(violations: list[dict]) -> str:
    items = "\n".join(f"- {v['code']}: {v['evidence']}" for v in violations)
    return ("Your draft failed these automatic checks:\n" + items +
            "\nRewrite the email so it passes every rule. Return only the corrected email in the same format.")

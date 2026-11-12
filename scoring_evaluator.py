"""
Tenacious-Bench Scoring Evaluator v0.2

Scores one outreach email (subject + body) against one Tenacious-Bench task.
Deterministic by default: same task + same email -> same score, no network.

Five deterministic dimensions (all must pass for overall_score = 1.0):

  grounding          the email references at least one *task-specific* signal
                     from the brief (generic words like "engineering" don't count)
  honesty            no claim the brief cannot support: funding / layoff /
                     leadership claims, numbers absent from the inputs, sector-peer
                     comparisons without a competitor brief, assertive language on
                     weak signals, US time zones sent to non-US prospects
  commercial_safety  no price / TCV quotes, no contract commitments, no engineer
                     counts above what the bench summary shows
  tone               no Tenacious style-guide banned phrase (word-boundary match)
  format             subject <= 60 chars, no template placeholders, CTA present
                     when the task requires one, optional body word limit

Optional sixth dimension (off by default, costs money, non-deterministic):

  tone_judge         an LLM scores the 5 Tenacious tone markers 1-5; pass if the
                     mean >= 4.0. Enable with --judge or score_task(..., judge=...).
                     It is reported separately and only gates overall_score when
                     require_judge=True. Use a model family different from the
                     generator under test (preference-leakage rule, Li et al. 2025).

Every failure is recorded as a violation {dimension, code, evidence} so a score
can always be traced to the exact text that caused it.

v0.1 (the scorer used for the original Week 11 results) is preserved unchanged
in scoring_evaluator_v01.py for comparison.

Usage:
    python scoring_evaluator.py --task path/to/task.json [--output email.json] [--judge]
    python scoring_evaluator.py --dataset tenacious_bench_v0.1/dev
    python scoring_evaluator.py --demo
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

VERSION = "0.2"
DIMENSIONS = ("grounding", "honesty", "commercial_safety", "tone", "format")

# ─────────────────────────────────────────────────────────────────────────────
# Lexicons
# ─────────────────────────────────────────────────────────────────────────────

# Banned phrases. Core list = the Tenacious style guide v2 list (as embedded in
# the SFT system prompt). Extras were added in Week 11 from probe evidence.
# "cheaper" was removed in v0.2: it appears in a Tenacious-labelled GOOD draft
# (TB-SG10), so it is not a style-guide ban.
BANNED_PHRASES = [
    # style guide v2
    "just circling back", "hope this finds you well", "just following up",
    "per my last email", "top talent", "world-class", "rockstar", "a-players",
    "ninja", "wizard", "bench", "aggressive hiring", "skyrocket", "supercharge",
    "synergize", "synergy", "game-changer", "disruptor", "you are missing",
    "falling behind", "behind the curve", "catch up", "quick question",
    "quick chat", "obviously", "clearly", "touching base", "following up", "as per",
    # Week 11 extras (probe-derived)
    "hope you're doing well", "i hope this email finds you", "per my last",
    "guru", "10x", "paradigm shift", "leverage", "ecosystem",
    "you are falling behind", "your competitors have", "fell behind",
    "you need to", "you should", "you'll regret", "don't miss out",
    "last chance", "urgent", "our proprietary", "our ai-powered",
    "struggling", "outsourcing", "cost effective", "cost-effective",
]
# Regex variants of generic openers that slip past exact phrases.
BANNED_PATTERNS = [
    (r"\bhope (this|the) (message|email|note) finds you\b", "generic opener"),
    (r"\bi hope you('| a)re (doing )?well\b", "generic opener"),
]

# required_signals entries that appear in almost every email and therefore
# prove nothing about grounding (245/293 v0.1 tasks relied on one of these).
GENERIC_SIGNALS = {
    "engineering", "new", "team", "growth", "cost", "company", "capacity",
    "hiring", "roles", "delivery", "may", "appears", "public", "profile",
    "based", "platform", "gap", "capability", "vendor", "mix", "data",
    "restructure",
}

# Fallback signal words per brief fact, used when a task lists no specific signal.
SIGNAL_WORDS = {
    "layoff": [r"layoffs?", r"laid off", r"restructur\w*", r"contracted by", r"headcount"],
    "leadership": [r"new (cto|vp|head|chief)\w*", r"leadership", r"appoint\w*"],
    "funding": [r"series [a-f]", r"raised", r"funding", r"round", r"seed"],
    "ai": [r"ai", r"ml", r"machine learning", r"mlops", r"llm", r"agentic"],
}

CLAIM_PATTERNS = {
    "funding": r"\bseries [a-f]\b|\braised\b|\bfunding round\b|\bpost-funding\b|"
               r"\bfresh(ly)? funded\b|\bnew funding\b|\bfundrais\w*|"
               r"\bclosed (your|a|the|its) \$?\d",
    "layoff": r"\blayoffs?\b|\blaid off\b|\brestructur\w*|\bcontracted by\b|"
              r"\breduction in force\b|\bheadcount reduction\b",
    "leadership": r"\bnew (cto|vp|head of|chief)\b|\bleadership (changes?|appointments?|transitions?)\b|"
                  r"\b(recently|just) (appointed|brought in|hired) (a |an |your )?(new )?"
                  r"(cto|vp|chief|head|engineering leader)|\bcongrat\w* on (the|your) "
                  r"(new )?(role|appointment|leadership)",
}
PEER_CLAIM = (r"\b(companies|peers|competitors|teams|players) (adjacent|in your (sector|space|"
              r"category|industry|segment)|like yours|at your stage in)|\btop[- ]quartile\b|"
              r"\byour (competitors|peers)\b|\bin your sector\b|\bsector peers\b|"
              r"\bpeer companies\b|\bmost (of your )?peers\b")
# Segment-4 (specialized capability) pitch language. Only allowed at AI maturity >= 2 (probe P03).
SEGMENT4_PITCH = (r"\bagentic[- ]systems?\b|\bmlops\b|\bml platform\b|\bcapability[- ]gap squads?\b|"
                  r"\bllm[- ]orchestrat\w*|\bai capability gap\b")
ASSERTIVE = (r"\baggressive(ly)?\b|\brapidly (scaling|growing|hiring)\b|\bscaling fast\b|"
             r"\bhypergrowth\b|\byou are scaling\b|\byour team is (growing|scaling)\b|"
             r"\bgrowing (its|your) engineering team\b|\bscaling (its|your) engineering\b")
US_TIME = (r"\b(pst|pdt|est|edt|cst|pacific( time)?|eastern time|us east coast|"
           r"east coast|west coast|us (business )?hours|us time ?zones?)\b")
NON_US_REGION_HINTS = {
    "eu": ["europe", "european", "emea", " eu ", "cet", "cest", "germany", "german",
           "munich", "berlin", "netherlands", "amsterdam", "france", "paris", "london",
           "uk", "united kingdom", "spain", "sweden", "stockholm", "dublin", "ireland",
           "deu", "nld", "fra", "gbr", "esp", "swe", "irl"],
    "africa": ["africa", "kenya", "nairobi", "ethiopia", "addis", "nigeria", "lagos",
               " eat ", "ken", "eth", "nga"],
}
# ISO country codes (2- and 3-letter) by Tenacious delivery region.
EUROPE_CODES = {"AT", "BE", "CH", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GB", "UK", "GR", "HU", "IE", "IT",
                "LT", "LU", "LV", "NL", "NO", "PL", "PT", "RO", "SE", "SI", "SK", "UA",
                "AUT", "BEL", "CHE", "CZE", "DEU", "DNK", "EST", "ESP", "FIN", "FRA", "GBR", "GRC", "HUN", "IRL",
                "ITA", "LTU", "LUX", "LVA", "NLD", "NOR", "POL", "PRT", "ROU", "SWE", "SVN", "SVK", "UKR"}
AFRICA_CODES = {"ET", "KE", "NG", "ZA", "EG", "GH", "RW", "UG", "TZ", "MA", "SN",
                "ETH", "KEN", "NGA", "ZAF", "EGY", "GHA", "RWA", "UGA", "TZA", "MAR", "SEN"}
US_CODES = {"US", "USA", "CA", "CAN", "MX", "MEX"}  # North American time zones
# Claims that a layoff / leadership change is recent (windows: layoff 120 days, leadership 90).
RECENT_LAYOFF_CLAIM = (r"\brecent(ly)? (restructur\w*|layoffs?|reductions?|downsiz\w*)|"
                       r"\bjust (restructured|laid off|downsized)\b|\bgone through a recent\b")
RECENT_LEADERSHIP_CLAIM = (r"\b(recent|new) (leadership|cto|cio|cpo|vp|head|chief)\b|\bfirst 90 days\b|"
                           r"\brecently (appointed|brought in|hired|named)\b|\bcongrat\w* on the recent\b|"
                           r"\brecent \w+ (appointment|hire)\b")
# Claims that funding is recent. Segment 1 = round in the last 180 days.
RECENT_FUNDING_CLAIM = (r"\b(recent(ly)?|just|newly|fresh(ly)?) (raised|closed|funded|announced)\b|"
                        r"\bpost-funding\b|\bfresh (budget|capital|funding)\b|\brecent (funding|round|raise)\b|"
                        r"\bclosed your .{0,25}(last|this) (month|quarter|week)\b")
PRICE_CONTEXT = (r"\b(cost|costs|price|pricing|priced|quote|quoted|rate|rates|fee|fees|"
                 r"total|tcv|contract value|per month|/month|monthly|installments?|invoice|budget)\b")
CONTRACT_COMMIT = (r"\b(attached|drafted|draft|send over|sending) (the |a |our )?contract\b|"
                   r"\bsign and return\b|\bbegin onboarding\b|\bcontract outline\b")
CAPACITY = r"\b(\d{1,3})\s+(?:senior\s+|dedicated\s+|full-time\s+)?(\w+\s+)?(engineers|developers|devs)\b"
CURRENCY = r"[$€£]\s?\d[\d,]*(?:\.\d+)?\s*(?:k|m|million)?|\b\d[\d,]*(?:\.\d+)?\s?(?:usd|eur|gbp|dollars|euros)\b"
# A reply that agrees to (or implies) a request the bench cannot cover, without declining or routing to a human.
COMMIT_PHRASE = (r"\bwe can (assemble|provide|deliver|staff|place|plug|ramp|scale|get you|have)\b|\bcan likely fulfill\b|"
                 r"\babsolutely\b|\bno problem\b|\bwe('ll| will) (have|get|assemble|provide)\b")
DECLINE_PHRASE = (r"\bcannot\b|\bcan't\b|\bcan not\b|\bnot able\b|\bunable\b|\bat the edge\b|\brefer you\b|"
                  r"\bwould rather\b|\bhonest(ly)?\b|\bonly have\b|\bdelivery lead\b|\bconfirm (with|after)\b")
PLACEHOLDER = (r"\[[^\]\n]{2,60}\]|\{\{[^}\n]+\}\}|<(first[_ ]?name|company|name)[^>]*>|"
               r"\byour (company|full name|position|contact information)\b(?=\s*\])")
# Style guide: "ends with a calendar link OR an explicit next-step offer".
# Tenacious-labelled good drafts use soft offers ("I can share two case studies",
# "Want me to send the PDF?"), so offers count as a CTA.
CTA = (r"https?://|cal\.com|\bcalendar\b|\b(15|20|30)[- ]minutes?\b|\bbook\b|\bschedule\b|\bcall\b|"
       r"\bworth (a )?\d+|\breply\b|\bnext step\b|\bwalk through\b|"
       r"\bhappy to (send|share|introduce|walk|talk)\b|\bwant me to\b|\bi can (share|send)\b|"
       r"\b(would|could) (it|that|this) be useful\b|\byour call\b|\blet me know\b")
# Channel policy (probe P25): SMS only after the prospect has replied by email.
SMS_MENTION = r"\bsms\b|\btext message\b|\btext us\b|\bwhatsapp\b"
# A list of 2+ capitalised names after a peer claim, e.g. "including Intercom, Zendesk, and Drift".
NAMED_LIST = (r"(?:including|such as|like|—|:)\s+((?:[A-Z][\w.&'-]+(?:\s[A-Z][\w.&'-]+)*)"
              r"(?:,\s*(?:and\s+)?[A-Z][\w.&'-]+(?:\s[A-Z][\w.&'-]+)*)+)")
# Style guide: one ask per email; no attachments in first-touch email.
ENUMERATED_ASKS = r"\b(first|second|third|fourth|fifth)(ly)?\b[,:]"
ATTACHMENT = r"(?<!strings )\battach(ed|ment|ing)\b"  # but not the idiom "no strings attached"
FIRST_TOUCH_TYPES = {"cold", "re_engagement", "referral"}
NUMBER_UNITS_IGNORED =r"(minutes?|mins?|hours?|hrs?|days?|weeks?|months?|years?|yrs?|am|pm|x)\b"
SIGNATURE_LINES = {"research partner", "tenacious intelligence corporation",
                   "gettenacious.com", "best,", "best", "thanks,", "regards,"}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _flatten(obj) -> list[str]:
    """All string / number leaves of a nested JSON object."""
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _flatten(v)]
    if isinstance(obj, list):
        return [s for v in obj for s in _flatten(v)]
    if obj is None or isinstance(obj, bool):
        return []
    return [str(obj)]


def input_text(task: dict) -> str:
    """Everything the writer was allowed to know, lowercased."""
    inp = task.get("input", {})
    parts = _flatten({k: v for k, v in inp.items() if k != "instruction"})
    return " ".join(parts).lower()


def brief_facts(task: dict) -> dict:
    """Boolean facts about the prospect, read from the structured brief."""
    inp = task.get("input", {})
    brief = inp.get("hiring_signal_brief", {}) or {}
    text = " ".join(_flatten(brief)).lower()
    firmo = brief.get("firmographics", {}) or {}
    funding_list = str(firmo.get("funding_rounds_list", "") or "")
    funding = brief.get("funding") or {}
    has_funding = bool(funding) or funding_list not in ("", "[]", "None", "nan") or bool(
        re.search(r"\bseries [a-f]\b|\bseed round\b|\braised\b|\bfunding (round|event)\b|\bclosed .{0,20}\bround\b", text))
    layoff = brief.get("layoff_signal", {}) or {}
    lead = brief.get("leadership_signal", {}) or {}
    # icp_classification.reasons are written by the W10 pipeline from the same
    # signals, so they count as evidence; authoring meta-notes do not.
    reasons = " ".join(r for r in (brief.get("icp_classification", {}) or {}).get("reasons", [])
                       if not re.match(r"(hand-authored scenario|style guide labeled|adversarial)", str(r).lower())).lower()
    reason_layoff = bool(re.search(r"\blayoffs?\b|\blaid off\b|\brestructur", reasons))
    reason_lead = bool(re.search(r"\bnew (cto|vp|head|chief)|\bleadership (change|hire)|\bappointed\b", reasons))
    # a peer/competitor summary in the reasons is competitor-gap evidence (W10 competitor_gap output)
    reason_peers = bool(re.search(r"\b(peers?|peer companies|adjacent compan\w*|competitors?|sector peers)\b", reasons))
    region_text = " " + " ".join(_flatten({
        "firmo": {k: firmo.get(k) for k in ("country_code", "country", "location", "region", "hq", "timezone")},
        "brief_region": brief.get("region"), "tz": brief.get("timezone"),
    })).lower() + " "
    code = str(firmo.get("country_code") or "").strip().upper()
    region = ("eu" if code in EUROPE_CODES else "africa" if code in AFRICA_CODES else "us" if code in US_CODES
              else "other" if re.fullmatch(r"[A-Z]{2,3}", code) and code != "NAN" else None)
    if region is None:
        for name, hints in NON_US_REGION_HINTS.items():
            if any(h in region_text for h in hints):
                region = name
    if region is None and re.search(r"\b(usa?|united states|us-|america|new york|san francisco|california)\b", region_text):
        region = "us"
    funding_recent = funding.get("recent") if isinstance(funding, dict) else None
    return {
        "has_funding": has_funding,
        "has_layoff": bool(layoff.get("layoff_detected")) or reason_layoff,
        "has_leadership": bool(lead.get("leadership_change_detected")) or reason_lead,
        "confidence": str((brief.get("icp_classification", {}) or {}).get("confidence", "")).lower(),
        "ai_score": (brief.get("ai_maturity", {}) or {}).get("ai_maturity_score") or 0,
        "has_competitor_brief": bool(inp.get("competitor_gap_brief") or brief.get("competitor_gap")) or reason_peers,
        "region": region,
        "funding_recent": funding_recent,  # None = unknown; False = round older than 180 days
        "layoff_recent": layoff.get("within_window"),        # None = unknown; False = older than 120 days
        "leadership_recent": lead.get("within_window"),      # None = unknown; False = older than 90 days
    }


def _norm_number(tok: str) -> str:
    return tok.replace(",", "").rstrip(".").lstrip("$").lower()


def _numbers_in(text: str) -> set[str]:
    return {_norm_number(m) for m in re.findall(r"\$?\d[\d,]*(?:\.\d+)?", text)}


URL = r"https?://\S+|\b[\w.-]+\.(?:com|io|ai|dev|org|net)(?:/\S*)?|localhost:\d+\S*"
DATE_NUMBER = r"\b(19|20)\d{2}\b|\b\d{1,2}(st|nd|rd|th)\b"


def _claim_text(text: str) -> str:
    """Text with URLs and dates blanked out, so '3000' in localhost:3000 or the
    year 2026 is never mistaken for a factual claim about the prospect."""
    return re.sub(DATE_NUMBER, " ", re.sub(URL, " ", text))


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _v(violations, dim, code, evidence):
    violations.append({"dimension": dim, "code": code, "evidence": evidence[:160]})


# ─────────────────────────────────────────────────────────────────────────────
# Dimension checks. Each returns a list of violations (empty list = pass).
# ─────────────────────────────────────────────────────────────────────────────

def _brief_signal_patterns(task: dict) -> list[str]:
    """Signal patterns implied by the brief's own facts (and its literal titles/names)."""
    brief = task.get("input", {}).get("hiring_signal_brief", {}) or {}
    f = brief_facts(task)
    pats: list[str] = []
    if f["has_layoff"]:
        pats += SIGNAL_WORDS["layoff"]
    if f["has_leadership"]:
        lead = brief.get("leadership_signal", {}) or {}
        pats += SIGNAL_WORDS["leadership"] + [r"(cto|vp engineering|vp of engineering|head of engineering|chief \w+ officer)"]
        pats += [re.escape(str(lead[k]).lower()) for k in ("leader_title", "leader_name") if lead.get(k)]
    if f["has_funding"]:
        pats += SIGNAL_WORDS["funding"]
    if f["ai_score"] >= 2:
        pats += SIGNAL_WORDS["ai"]
    return pats


def check_grounding(email: dict, task: dict) -> tuple[list, dict]:
    """
    Pass if the email (subject or body) references at least one specific signal:
    either a non-generic entry of ground_truth.required_signals, or a signal
    pattern implied by the brief's facts (e.g. "Series B" when funding is known).
    """
    text = (email.get("subject", "") + "\n" + email.get("body", "")).lower()
    gt = task.get("ground_truth", {})
    specific = [s.lower() for s in gt.get("required_signals", []) if s.lower() not in GENERIC_SIGNALS]
    patterns = [re.escape(s) for s in specific] + _brief_signal_patterns(task)
    # A reply is grounded if it answers the prospect's latest message: its numbers or distinctive words.
    asks = [m for m in (task.get("input", {}).get("prior_thread") or [])
            if isinstance(m, dict) and m.get("from") == "prospect"]
    if asks:
        last = str(asks[-1].get("body", "")).lower()
        stop = {"thanks", "reaching", "would", "could", "about", "there", "their", "these", "which", "within",
                "please", "currently", "happy", "already", "really", "maybe", "think", "right", "where", "provide"}
        patterns += [re.escape(w) for w in set(re.findall(r"\b\d+\b|\b[a-z]{5,}\b", last)) if w not in stop]
    found = [p for p in patterns if re.search(rf"(?<!\w){p}(?!\w)", text)]
    info = {"candidates": len(patterns), "found": found[:5]}
    if not patterns:
        return [], {**info, "note": "brief has no specific signal; grounding not applicable"}
    if not found:
        return [{"dimension": "grounding", "code": "NO_SPECIFIC_SIGNAL",
                 "evidence": f"none of {specific or 'the brief-derived signals'} referenced"}], info
    return [], info


def check_honesty(email: dict, task: dict) -> tuple[list, dict]:
    body = email.get("body", "")
    low = _claim_text((email.get("subject", "") + "\n" + body).lower())
    f = brief_facts(task)
    known = input_text(task)
    known_numbers = _numbers_in(known)
    out: list = []

    for claim, fact in (("funding", "has_funding"), ("layoff", "has_layoff"), ("leadership", "has_leadership")):
        m = re.search(CLAIM_PATTERNS[claim], low)
        if m and not f[fact]:
            _v(out, "honesty", f"{claim.upper()}_UNSUPPORTED", m.group(0))

    for claim_re, fact, recent, code, window in (
            (RECENT_FUNDING_CLAIM, "has_funding", "funding_recent", "FUNDING_NOT_RECENT", 180),
            (RECENT_LAYOFF_CLAIM, "has_layoff", "layoff_recent", "LAYOFF_NOT_RECENT", 120),
            (RECENT_LEADERSHIP_CLAIM, "has_leadership", "leadership_recent", "LEADERSHIP_NOT_RECENT", 90)):
        m = re.search(claim_re, low)
        if m and f[fact] and f[recent] is False:
            _v(out, "honesty", code, f"{m.group(0)} (brief: event older than {window} days)")

    # Numbers about the prospect (money, %, headcounts) must appear in the inputs.
    # Offer terms (minutes, days, months...) and engineer counts are excluded here;
    # engineer counts are a capacity commitment, checked under commercial_safety.
    for m in re.finditer(r"\$?\d[\d,]*(?:\.\d+)?(\s*(%|percent|[mk]\b|million|billion|bn\b))?(\s*\w+)?", low):
        token, tail = m.group(0), (m.group(3) or "").strip()
        num = _norm_number(re.match(r"\$?\d[\d,]*(?:\.\d+)?", token).group(0))
        after = low[m.end(): m.end() + 12]
        if re.match(NUMBER_UNITS_IGNORED, tail) or re.match(r"\s*" + NUMBER_UNITS_IGNORED, after if not tail else ""):
            continue
        if re.match(r"(engineers|developers|devs|senior|dedicated)\b", tail):
            continue
        if re.search(r"[-–]\s*$", low[max(0, m.start() - 2): m.start()]) or re.match(r"\s*[-–]\s*\d", low[m.end(): m.end() + 3]):
            continue  # ranges like "3-5 hours", "7–14 days" are offer terms
        if num in {"15", "20", "30"} and re.match(r"[- ]?min", low[m.end(): m.end() + 5]):
            continue
        if num in known_numbers:
            continue
        if "$" in token:
            sent = next((s for s in _sentences(low) if token.strip() in s), "")
            if re.search(PRICE_CONTEXT, sent):
                continue  # a price, not a prospect fact: judged once, under commercial_safety
        if len(num) <= 1 and "$" not in token and "%" not in token:
            continue  # single digits like "3 companies" — too noisy to call fabrication
        _v(out, "honesty", "NUMBER_NOT_IN_INPUTS", token.strip())

    m = re.search(PEER_CLAIM, low)
    if m and not f["has_competitor_brief"]:
        _v(out, "honesty", "PEER_CLAIM_UNSUPPORTED", m.group(0))
    out += _check_named_peers(body, task)

    m = re.search(ASSERTIVE, low)
    if m and f["confidence"] in ("low", "very_low"):
        _v(out, "honesty", "ASSERTIVE_ON_WEAK_SIGNAL", f"{m.group(0)} (confidence={f['confidence']})")

    m = re.search(SEGMENT4_PITCH, low)
    if m and f["ai_score"] < 2:
        _v(out, "honesty", "SEGMENT4_PITCH_LOW_AI_MATURITY", f"{m.group(0)} (ai_maturity={f['ai_score']})")

    m = re.search(US_TIME, low)
    if m and f["region"] in ("eu", "africa", "other"):
        _v(out, "honesty", "REGION_TIMEZONE_MISMATCH", f"{m.group(0)} for {f['region']} prospect")

    return out, {"facts": f}


def _sector_words(s: str) -> set[str]:
    stop = {"and", "or", "the", "of", "a", "platform", "platforms", "company", "companies", "services", "tech"}
    return {w for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 2 and w not in stop}


def _check_named_peers(body: str, task: dict) -> list:
    """
    Named peer companies must (1) appear in the inputs and (2) be in the
    prospect's sector when the competitor brief records sectors (probe P33:
    the W10 random fallback compared an AI company to dental practices).
    """
    out: list = []
    inp = task.get("input", {})
    brief = inp.get("hiring_signal_brief", {}) or {}
    prospect = str(brief.get("prospect", "")).lower()
    known = input_text(task)
    gap = inp.get("competitor_gap_brief") or {}
    peers = {str(p.get("name", "")).lower(): p for p in gap.get("peers", []) if isinstance(p, dict)}
    prospect_sector = _sector_words(str(gap.get("prospect_sector", "")))
    for sent in _sentences(body):
        if not re.search(PEER_CLAIM, sent.lower()):
            continue
        for lst in re.findall(NAMED_LIST, sent):
            for name in re.split(r",\s*(?:and\s+)?|\s+and\s+", lst):
                n = name.strip().lower()
                if not n or n == prospect:
                    continue
                if n not in known:
                    _v(out, "honesty", "PEER_NOT_IN_BRIEF", name.strip())
                elif n in peers and prospect_sector:
                    if not (_sector_words(str(peers[n].get("sector", ""))) & prospect_sector):
                        _v(out, "honesty", "PEER_SECTOR_MISMATCH",
                           f"{name.strip()} ({peers[n].get('sector')}) vs prospect sector {gap.get('prospect_sector')}")
    return out


def check_commercial_safety(email: dict, task: dict) -> tuple[list, dict]:
    low = _claim_text((email.get("subject", "") + "\n" + email.get("body", "")).lower())
    known_numbers = _numbers_in(input_text(task))
    out: list = []
    for sent in _sentences(low):
        money = re.findall(CURRENCY, sent)
        money += [m.group(0) for m in re.finditer(r"\b\d+(?:\.\d+)?\s?(?:k|m|million)\b", sent)
                  if re.search(r"\b(engagement|contract|quote|total)\b", sent)]
        if money and re.search(PRICE_CONTEXT, sent):
            unsupported = [x for x in money if _norm_number(re.sub(r"[^\d.,$]", "", x)) not in known_numbers]
            if unsupported:
                _v(out, "commercial_safety", "PRICE_QUOTE", sent.strip())
    m = re.search(CONTRACT_COMMIT, low)
    if m:
        _v(out, "commercial_safety", "CONTRACT_COMMITMENT", m.group(0))
    thread = task.get("input", {}).get("prior_thread") or []
    prospect_replied = any(str(msg.get("from", "")).lower() == "prospect"
                           for msg in thread if isinstance(msg, dict))
    m = re.search(SMS_MENTION, low)
    if m and not prospect_replied:
        _v(out, "commercial_safety", "SMS_BEFORE_REPLY", m.group(0))
    bench = task.get("input", {}).get("bench_summary", {}) or {}
    available = bench.get("available")
    stacks = {str(k).lower(): v for k, v in (bench.get("stacks") or {}).items()}
    for m in re.finditer(CAPACITY, low):
        n, stack = int(m.group(1)), (m.group(2) or "").strip()
        limit = stacks.get(stack, available)
        if isinstance(limit, (int, float)) and n > limit:
            _v(out, "commercial_safety", "CAPACITY_EXCEEDS_BENCH", f"{m.group(0)} > {limit} available")
    # implicit commitment: the prospect asked for more than the bench holds and the reply says yes
    asks = [x for x in thread if isinstance(x, dict) and x.get("from") == "prospect"]
    if asks:
        for m in re.finditer(CAPACITY, str(asks[-1].get("body", "")).lower()):
            n, stack = int(m.group(1)), (m.group(2) or "").strip()
            limit = stacks.get(stack, available)
            if (isinstance(limit, (int, float)) and n > limit and re.search(COMMIT_PHRASE, low)
                    and not re.search(DECLINE_PHRASE, low)):
                _v(out, "commercial_safety", "CAPACITY_COMMITMENT_BEYOND_BENCH",
                   f"prospect asked for {m.group(0)} (bench: {limit}); reply commits without declining or routing")
    return out, {"bench_available": available}


def check_tone(email: dict, task: dict) -> tuple[list, dict]:
    low = (email.get("subject", "") + "\n" + email.get("body", "")).lower()
    phrases = set(BANNED_PHRASES) | {p.lower() for p in task.get("ground_truth", {}).get("forbidden_phrases", [])}
    phrases.discard("cheaper")
    out: list = []
    for p in sorted(phrases):
        if re.search(rf"(?<!\w){re.escape(p)}(?!\w)", low):
            _v(out, "tone", "BANNED_PHRASE", p)
    for pat, label in BANNED_PATTERNS:
        m = re.search(pat, low)
        if m:
            _v(out, "tone", "BANNED_PATTERN", f"{label}: {m.group(0)}")
    return out, {}


def _closing(body: str) -> str:
    """Body text minus the signature block: the part a CTA must live in."""
    lines = [l.strip() for l in body.strip().splitlines() if l.strip()]

    def is_signature(line: str) -> bool:
        low = line.lower()
        if low in SIGNATURE_LINES:
            return True
        if ("tenacious intelligence" in low or "gettenacious.com" in low) and len(low.split()) <= 8:
            return True  # one-line signature like "Research Partner / Tenacious ... / gettenacious.com"
        if re.fullmatch(r"(best,?\s*)?\[[^\]]+\]", low):  # "[Your Name]" sign-off
            return True
        # short sign-off lines ("Yabi", "Best, Yabi") — but never a link, number or question
        return len(low.split()) <= 2 and not re.search(r"https?://|cal\.com|localhost|\d|\?", low)

    while lines and is_signature(lines[-1]):
        lines.pop()
    return "\n".join(lines[-3:]).lower()


def check_format(email: dict, task: dict) -> tuple[list, dict]:
    gt = task.get("ground_truth", {})
    subject, body = email.get("subject", ""), email.get("body", "")
    out: list = []
    max_len = gt.get("max_subject_length", 60)
    if len(subject) > max_len:
        _v(out, "format", "SUBJECT_TOO_LONG", f"{len(subject)} > {max_len} chars")
    m = re.search(PLACEHOLDER, subject + "\n" + body, re.IGNORECASE)
    if m:
        _v(out, "format", "TEMPLATE_PLACEHOLDER", m.group(0))
    if gt.get("must_end_with_cta", True) and not re.search(CTA, _closing(body)):
        _v(out, "format", "NO_CTA", "no call-to-action in closing lines")
    low = body.lower()
    asks = len(re.findall(ENUMERATED_ASKS, low))
    if asks >= 3:
        _v(out, "format", "MULTIPLE_ASKS", f"{asks} enumerated items (style guide: one ask per email)")
    email_type = str(task.get("input", {}).get("email_type", "cold")).lower()
    m = re.search(ATTACHMENT, low)
    if m and email_type in FIRST_TOUCH_TYPES:
        _v(out, "format", "ATTACHMENT_IN_FIRST_TOUCH", f"{m.group(0)} in a {email_type} email")
    words = len(body.split())
    if gt.get("max_body_words") and words > gt["max_body_words"]:
        _v(out, "format", "BODY_TOO_LONG", f"{words} > {gt['max_body_words']} words")
    return out, {"subject_length": len(subject), "body_words": words}


# ─────────────────────────────────────────────────────────────────────────────
# Optional LLM judge (tone markers)
# ─────────────────────────────────────────────────────────────────────────────

TONE_MARKERS = [
    "Direct: opens with a specific signal about the prospect, not a generic greeting",
    "Grounded: every claim is supported by the supplied brief",
    "Honest: hedges when evidence is weak; no over-claiming",
    "Professional: no offshore-vendor cliches; appropriate for a CTO or VP Engineering",
    "Non-condescending: gaps are framed as research findings or questions, not failures",
]


class LLMJudge:
    """
    Tone-marker judge via OpenRouter. Results are cached on disk keyed by
    (model, brief, email) so re-runs are free and repeatable.
    """

    def __init__(self, model: str | None = None, cache_path: str | Path | None = None,
                 bucket: str = "held_out_eval"):
        self.bucket = bucket
        self.model = model or os.getenv("TB_JUDGE_MODEL", "deepseek/deepseek-chat")
        self.key = os.getenv("OPENROUTER_API_KEY")
        self.cache_path = Path(cache_path or Path(__file__).parent / ".judge_cache.jsonl")
        self.cache = {}
        if self.cache_path.exists():
            for line in self.cache_path.read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                self.cache[rec["key"]] = rec["result"]

    def __call__(self, email: dict, task: dict) -> dict:
        brief = task.get("input", {}).get("hiring_signal_brief", {})
        payload = json.dumps([self.model, brief, email], sort_keys=True, ensure_ascii=False)
        key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if key in self.cache:
            return {**self.cache[key], "cached": True}
        if not self.key:
            raise RuntimeError("OPENROUTER_API_KEY not set; cannot run the LLM judge")
        import llm_client  # logs cost, enforces the budget cap, caches
        markers = "\n".join(f"{i + 1}. {m}" for i, m in enumerate(TONE_MARKERS))
        prompt = (
            "You grade B2B outreach emails for Tenacious, an engineering-services firm.\n"
            f"Score each tone marker 1-5 (1 = fails, 5 = exemplary).\n{markers}\n\n"
            f"Hiring signal brief (the ONLY facts the writer was allowed to use):\n"
            f"{json.dumps(brief, ensure_ascii=False)}\n\n"
            f"Subject: {email.get('subject', '')}\nBody:\n{email.get('body', '')}\n\n"
            'Reply with JSON only: {"scores": [m1, m2, m3, m4, m5], "reason": "<one sentence>"}'
        )
        content = llm_client.chat(self.model, [{"role": "user", "content": prompt}],
                                  bucket=self.bucket, purpose=f"tone judge {task.get('task_id', '?')}",
                                  temperature=0, max_tokens=200)
        parsed = json.loads(re.search(r"\{.*\}", content, re.S).group(0))
        scores = [int(s) for s in parsed["scores"]][:5]
        result = {"model": self.model, "scores": scores, "mean": round(sum(scores) / len(scores), 2),
                  "reason": parsed.get("reason", "")}
        with self.cache_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"key": key, "result": result}, ensure_ascii=False) + "\n")
        self.cache[key] = result
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

CHECKS = {
    "grounding": check_grounding,
    "honesty": check_honesty,
    "commercial_safety": check_commercial_safety,
    "tone": check_tone,
    "format": check_format,
}


def score_task(task: dict, candidate_output: dict | None = None,
               judge: LLMJudge | None = None, require_judge: bool = False) -> dict:
    """
    Score one email against one task.

    candidate_output defaults to the task's stored candidate_output, which makes
    the task usable as an evaluator test case (does the score match is_passing?).
    Pass a freshly generated email to use the task as a generation benchmark.
    """
    email = candidate_output if candidate_output is not None else task.get("candidate_output", {})
    violations: list = []
    checks: dict = {}
    for name, fn in CHECKS.items():
        v, info = fn(email, task)
        violations += v
        checks[name] = {"pass": not v, "violations": [x["code"] for x in v], **info}

    if judge is not None:
        j = judge(email, task)
        checks["tone_judge"] = {"pass": j["mean"] >= 4.0, **j}
        if j["mean"] < 4.0:
            violations.append({"dimension": "tone_judge", "code": "JUDGE_BELOW_4",
                               "evidence": f"mean {j['mean']}: {j.get('reason', '')}"[:160]})

    gating = list(DIMENSIONS) + (["tone_judge"] if (judge is not None and require_judge) else [])
    all_pass = all(checks[d]["pass"] for d in gating)
    return {
        "task_id": task.get("task_id", "unknown"),
        "evaluator_version": VERSION,
        "overall_score": 1.0 if all_pass else 0.0,
        "partial_score": round(sum(checks[d]["pass"] for d in DIMENSIONS) / len(DIMENSIONS), 3),
        "all_pass": all_pass,
        "checks": checks,
        "violations": violations,
        "difficulty": task.get("difficulty", "unknown"),
        "source_mode": task.get("source_mode", "unknown"),
    }


def score_dataset(tasks: list, judge: LLMJudge | None = None, require_judge: bool = False) -> dict:
    results = [score_task(t, judge=judge, require_judge=require_judge) for t in tasks]
    n = len(results)
    dims = list(DIMENSIONS) + (["tone_judge"] if judge is not None else [])
    per_dim = {d: {"passed": sum(r["checks"][d]["pass"] for r in results), "total": n} for d in dims}
    for d in per_dim.values():
        d["pass_rate"] = round(d["passed"] / n, 3) if n else 0.0
    codes: dict = {}
    for r in results:
        for v in r["violations"]:
            codes[v["code"]] = codes.get(v["code"], 0) + 1
    passed = sum(r["all_pass"] for r in results)
    return {"evaluator_version": VERSION, "total_tasks": n, "passed": passed,
            "pass_at_1": round(passed / n, 3) if n else 0.0,
            "per_dimension": per_dim, "violation_counts": dict(sorted(codes.items(), key=lambda x: -x[1])),
            "results": results}


def load_tasks(path: str | Path) -> list:
    p = Path(path)
    files = [p] if p.is_file() else sorted(p.rglob("TB-*.json"))
    return [json.loads(f.read_text(encoding="utf-8")) for f in files]


def _demo_tasks() -> list:
    from scoring_evaluator_v01 import DEMO_TASKS
    return DEMO_TASKS


if __name__ == "__main__":
    # Windows consoles default to cp1252 and crash on "—" or "✅"; force UTF-8 output.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=f"Tenacious-Bench evaluator v{VERSION}")
    ap.add_argument("--task", help="task JSON file")
    ap.add_argument("--output", help="candidate email JSON {subject, body}; default: task's stored candidate")
    ap.add_argument("--dataset", help="folder (recursive) of task JSON files")
    ap.add_argument("--demo", action="store_true", help="score the 3 built-in demo tasks")
    ap.add_argument("--judge", action="store_true", help="also run the LLM tone judge (needs OPENROUTER_API_KEY)")
    ap.add_argument("--require-judge", action="store_true", help="judge result gates overall_score")
    ap.add_argument("--summary", action="store_true", help="print aggregate only, not per-task results")
    args = ap.parse_args()
    judge = LLMJudge() if args.judge else None

    if args.task:
        task = json.loads(Path(args.task).read_text(encoding="utf-8"))
        cand = json.loads(Path(args.output).read_text(encoding="utf-8")) if args.output else None
        print(json.dumps(score_task(task, cand, judge, args.require_judge), indent=2, ensure_ascii=False))
    elif args.dataset or args.demo:
        tasks = load_tasks(args.dataset) if args.dataset else _demo_tasks()
        res = score_dataset(tasks, judge, args.require_judge)
        if args.summary or args.demo:
            res = {k: v for k, v in res.items() if k != "results"} | (
                {"per_task": {r["task_id"]: [v["code"] for v in r["violations"]] for r in res["results"]}}
                if args.demo else {})
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        ap.print_help()
        sys.exit(1)

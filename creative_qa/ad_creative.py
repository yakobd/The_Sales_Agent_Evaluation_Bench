"""
Ad-creative rule pack: the Tenacious-Bench evaluator design (deterministic checks, one code + evidence
per violation, pass = all dimensions pass) applied to a search ad (responsive-search-ad shape).

Dimensions
  grounding     the copy references the product or an approved claim from the brief
  claims        no superlative, guarantee, number or competitor claim the brief does not substantiate
  policy        destination matches the brand domain; no expired promo; vertical-restricted claims
  brand_safety  brand blocklist, shouting (ALL CAPS), exclamation marks in headlines, repeated punctuation
  format        channel specs: headline/description length and counts, duplicates, placeholders, a CTA

This is a DEMO pack: the rules follow common ad-platform editorial norms and FTC-style substantiation
practice, but it has not been validated against human labels the way the sales-email pack has.
"""
import re
from datetime import date
from urllib.parse import urlparse

VERSION = "0.1-demo"
DIMENSIONS = ("grounding", "claims", "policy", "brand_safety", "format")

SUPERLATIVES = (r"\b(best|#\s?1|no\.?\s?1|number one|top[- ]rated|leading|cheapest|lowest|fastest|highest|"
                r"most (trusted|popular|reliable)|unbeatable|world'?s (best|first)|award[- ]winning)\b")
GUARANTEES = r"\b(guarantee[ds]?|risk[- ]free|100\s?%|no risk|can'?t lose|instant approval)\b"
NUMBER = r"(?<![\w{])[$€£]?\d[\d,.]*\s?(%|x\b|k\b|m\b)?"
DKI = r"\{(keyword|KeyWord|Keyword|KEYWORD):[^}]{1,40}\}"  # dynamic keyword insertion is valid syntax
PLACEHOLDER = r"\[[^\]\n]{2,40}\]|\{\{[^}\n]+\}\}|\bTBD\b|\bXX+\b|\blorem ipsum\b"
CTA_VERBS = (r"\b(shop|buy|get|start|try|open|book|sign up|join|learn more|apply|download|order|claim|"
             r"compare|explore|see|discover|request|schedule|switch|save)\b")
RESTRICTED = {
    "finance": r"\b(get rich|guaranteed returns?|double your money|no credit check|debt[- ]free fast)\b",
    "health": r"\b(cures?|heals?|miracle|clinically proven|doctor[- ]recommended|lose \d+ ?(lbs|pounds|kg))\b",
    "employment": r"\b(earn \$?\d+[\d,]* (a|per) (day|week)|work from home and earn)\b",
}
ALLOWED_CAPS = {"USA", "UK", "EU", "AI", "API", "APY", "APR", "FDIC", "SaaS", "CRM", "SEO", "B2B", "HR", "IT", "ROI", "FAQ"}


def _v(out, dim, code, evidence, field=None):
    out.append({"dimension": dim, "code": code, "evidence": str(evidence)[:160], **({"field": field} if field else {})})


def _fields(c: dict):
    for i, h in enumerate(c.get("headlines", []) or []):
        yield f"headline[{i + 1}]", h
    for i, d in enumerate(c.get("descriptions", []) or []):
        yield f"description[{i + 1}]", d


def _approved_text(inp: dict) -> str:
    offer = inp.get("offer", {}) or {}
    parts = [offer.get("product", "")] + list(offer.get("approved_claims", []) or []) + \
            list(offer.get("substantiated_superlatives", []) or [])
    promo = offer.get("promo") or {}
    parts += [str(promo.get("discount", "")), str(promo.get("code", ""))]
    return " ".join(p for p in parts if p).lower()


def _norm_num(s: str) -> str:
    return re.sub(r"[\s,]", "", s.lower()).rstrip(".")


def check(task: dict, creative: dict, as_of: date | None = None) -> dict:
    inp = task.get("input", {})
    brand, offer, channel = inp.get("brand", {}) or {}, inp.get("offer", {}) or {}, inp.get("channel", {}) or {}
    vertical = str(inp.get("vertical", "")).lower()
    approved = _approved_text(inp)
    approved_nums = {_norm_num(m.group(0)) for m in re.finditer(NUMBER, approved)}
    v: list = []

    # grounding: something from the offer must appear
    copy = " ".join(t for _, t in _fields(creative)).lower()
    anchors = [offer.get("product", "")] + list(offer.get("approved_claims", []) or [])
    anchor_words = {w for a in anchors for w in re.findall(r"[a-z0-9.%$]{4,}", str(a).lower())}
    if not any(w in copy for w in anchor_words):
        _v(v, "grounding", "NO_OFFER_REFERENCE", "copy mentions neither the product nor any approved claim")

    # claims
    competitors = [c for c in brand.get("competitors", []) or [] if c]
    for field, text in _fields(creative):
        low = re.sub(DKI, "", text)
        for m in re.finditer(SUPERLATIVES, low, re.I):
            if m.group(0).lower() not in approved:
                _v(v, "claims", "UNSUPPORTED_SUPERLATIVE", f"'{m.group(0)}' not in substantiated claims", field)
        for m in re.finditer(GUARANTEES, low, re.I):
            if m.group(0).lower() not in approved:
                _v(v, "claims", "UNSUPPORTED_GUARANTEE", f"'{m.group(0)}'", field)
        for m in re.finditer(NUMBER, low):
            tok = m.group(0).strip()
            if re.fullmatch(r"\d", tok):  # single digits ("3 steps") are not claims
                continue
            if _norm_num(tok) not in approved_nums and m.group(0).strip("%") not in approved:
                _v(v, "claims", "NUMBER_NOT_APPROVED", f"'{tok}' is not in the approved claims or offer", field)
        for c in competitors:
            if re.search(rf"\b{re.escape(c)}\b", low, re.I):
                _v(v, "claims", "COMPETITOR_MENTION", f"names competitor '{c}'", field)

    # policy
    url = creative.get("final_url", "") or ""
    host = urlparse(url).netloc.lower().removeprefix("www.")
    domain = str(brand.get("display_domain", "")).lower().removeprefix("www.")
    if not url:
        _v(v, "policy", "MISSING_FINAL_URL", "no landing page")
    elif domain and not (host == domain or host.endswith("." + domain)):
        _v(v, "policy", "DESTINATION_MISMATCH", f"final URL host '{host}' is not {domain}")
    promo = offer.get("promo") or {}
    if promo.get("ends") and promo.get("discount") and promo["discount"].lower() in copy:
        if date.fromisoformat(promo["ends"]) < (as_of or date.fromisoformat(inp.get("as_of", str(date.today())))):
            _v(v, "policy", "EXPIRED_PROMO", f"promo '{promo['discount']}' ended {promo['ends']}")
    if vertical in RESTRICTED:
        for field, text in _fields(creative):
            for m in re.finditer(RESTRICTED[vertical], text, re.I):
                _v(v, "policy", "RESTRICTED_CLAIM", f"{vertical}: '{m.group(0)}'", field)

    # brand safety
    for field, text in _fields(creative):
        for term in brand.get("blocked_terms", []) or []:
            if re.search(rf"\b{re.escape(term)}\b", text, re.I):
                _v(v, "brand_safety", "BLOCKED_TERM", f"'{term}' is on the brand blocklist", field)
        for w in re.findall(r"\b[A-Z]{4,}\b", re.sub(DKI, "", text)):
            if w not in ALLOWED_CAPS:
                _v(v, "brand_safety", "EXCESSIVE_CAPS", f"'{w}'", field)
        if field.startswith("headline") and "!" in text:
            _v(v, "brand_safety", "EXCLAMATION_IN_HEADLINE", text, field)
        if re.search(r"[!?.]{2,}", text):
            _v(v, "brand_safety", "REPEATED_PUNCTUATION", text, field)

    # format
    hmax, dmax = channel.get("headline_max", 30), channel.get("description_max", 90)
    heads, descs = creative.get("headlines", []) or [], creative.get("descriptions", []) or []
    for field, text in _fields(creative):
        shown = re.sub(DKI, lambda m: m.group(0).split(":", 1)[1][:-1], text)  # length counts the default text
        lim = hmax if field.startswith("headline") else dmax
        if len(shown) > lim:
            _v(v, "format", "TOO_LONG", f"{len(shown)} > {lim} chars: {shown}", field)
        if re.search(PLACEHOLDER, re.sub(DKI, "", text)):
            _v(v, "format", "PLACEHOLDER", text, field)
    if len(heads) < channel.get("min_headlines", 3):
        _v(v, "format", "TOO_FEW_HEADLINES", f"{len(heads)} < {channel.get('min_headlines', 3)}")
    if len(heads) > channel.get("max_headlines", 15):
        _v(v, "format", "TOO_MANY_HEADLINES", f"{len(heads)} > {channel.get('max_headlines', 15)}")
    if len(descs) < channel.get("min_descriptions", 2):
        _v(v, "format", "TOO_FEW_DESCRIPTIONS", f"{len(descs)} < {channel.get('min_descriptions', 2)}")
    seen = {}
    for i, h in enumerate(heads):
        k = re.sub(r"\W+", " ", h.lower()).strip()
        if k in seen:
            _v(v, "format", "DUPLICATE_HEADLINE", f"headline[{i + 1}] repeats headline[{seen[k] + 1}]", f"headline[{i + 1}]")
        seen.setdefault(k, i)
    if not any(re.search(CTA_VERBS, t, re.I) for t in descs + heads):
        _v(v, "format", "NO_CTA", "no call-to-action verb in any headline or description")

    checks = {d: {"pass": not [x for x in v if x["dimension"] == d],
                  "violations": [x["code"] for x in v if x["dimension"] == d]} for d in DIMENSIONS}
    all_pass = all(c["pass"] for c in checks.values())
    return {"task_id": task.get("task_id"), "pack": "ad_creative", "evaluator_version": VERSION,
            "all_pass": all_pass, "overall_score": 1.0 if all_pass else 0.0,
            "partial_score": round(sum(c["pass"] for c in checks.values()) / len(DIMENSIONS), 3),
            "checks": checks, "violations": v}

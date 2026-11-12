"""
Evaluator v0.2 tests.

Part 1: one small synthetic task per rule, a failing and a passing case, so
        each rule's boundary is pinned down (including the v0.1 false positives
        like "benchmark" or "localhost:3000").
Part 2: regression on real benchmark tasks whose human labels say "bad",
        asserting the specific violation that should catch them.
"""
import copy
import json
from pathlib import Path

import pytest

import config
import scoring_evaluator as E

SIG = "\n\nResearch Partner\nTenacious Intelligence Corporation\ngettenacious.com"
CTA = "\n\nWorth 15 minutes this week? https://cal.com/yakob/30min"

BASE = {
    "task_id": "TB-T001",
    "source_mode": "hand_authored",
    "difficulty": "easy",
    "input": {
        "hiring_signal_brief": {
            "prospect": "Acme",
            "icp_classification": {"segment": 2, "segment_name": "Mid-market restructuring",
                                   "confidence": "high", "reasons": ["Layoff of 120 staff in March"]},
            "firmographics": {"company": "Acme", "country_code": "USA", "num_employees": "201-500"},
            "ai_maturity": {"ai_maturity_score": 1, "confidence": "medium"},
            "layoff_signal": {"layoff_detected": True, "total_laid_off": "120"},
            "leadership_signal": {"leadership_change_detected": False},
        },
        "bench_summary": {"total_engineers": 60, "available": 34,
                          "stacks": {"python": 12, "go": 4}},
        "instruction": "Write a cold outreach email.",
    },
    "ground_truth": {"required_signals": ["restructuring", "layoff"], "forbidden_phrases": [],
                     "max_subject_length": 60, "must_end_with_cta": True},
}
GOOD_BODY = ("Acme went through a restructuring after the March layoff of 120 staff. "
             "Teams in that position often need to keep delivery steady while cost resets." + CTA + SIG)


def task(**brief_overrides):
    t = copy.deepcopy(BASE)
    for path, value in brief_overrides.items():
        node = t
        keys = path.split("__")
        for k in keys[:-1]:
            node = node[k]
        node[keys[-1]] = value
    return t


def email(body=GOOD_BODY, subject="Note on Acme restructuring"):
    return {"subject": subject, "body": body}


def codes(t, e):
    return {v["code"] for v in E.score_task(t, e)["violations"]}


# ── Part 1: rule boundaries ──────────────────────────────────────────────────

def test_good_email_passes_all_dimensions():
    r = E.score_task(task(), email())
    assert r["all_pass"], r["violations"]
    assert r["evaluator_version"] == "0.2"


class TestGrounding:
    def test_generic_signal_alone_is_not_grounding(self):
        """Brief has a layoff signal; mentioning only 'engineering' doesn't use it."""
        t = task(ground_truth__required_signals=["engineering"])
        e = email("Your engineering team could use more capacity." + CTA + SIG, "Hello")
        assert "NO_SPECIFIC_SIGNAL" in codes(t, e)

    def test_grounding_not_applicable_when_brief_has_no_signal(self):
        """Nothing to ground in -> abstention case; a generic exploratory email is fine."""
        t = task(ground_truth__required_signals=["engineering"],
                 input__hiring_signal_brief__layoff_signal={"layoff_detected": False})
        t["input"]["hiring_signal_brief"]["icp_classification"]["reasons"] = []
        e = email("Would a conversation about engineering capacity be useful?" + CTA + SIG, "Hello")
        r = E.score_task(t, e)
        assert r["checks"]["grounding"]["pass"] and "not applicable" in r["checks"]["grounding"]["note"]

    def test_brief_derived_signal_counts(self):
        t = task(ground_truth__required_signals=["funding"])
        t["input"]["hiring_signal_brief"]["icp_classification"]["reasons"] = ["Series B $35M closed last month"]
        e = email("Congrats on the $35M Series B. Teams at this stage hire faster than recruiting can." + CTA + SIG,
                  "Acme Series B")
        assert "NO_SPECIFIC_SIGNAL" not in codes(t, e)


class TestHonesty:
    def test_funding_claim_without_funding(self):
        e = email("We work with teams scaling post-funding after a restructuring." + CTA + SIG)
        assert "FUNDING_UNSUPPORTED" in codes(task(), e)

    def test_layoff_claim_without_layoff(self):
        t = task(input__hiring_signal_brief__layoff_signal={"layoff_detected": False})
        t["input"]["hiring_signal_brief"]["icp_classification"]["reasons"] = []  # no evidence anywhere
        assert "LAYOFF_UNSUPPORTED" in codes(t, email())

    def test_reasons_count_as_evidence_but_authoring_notes_do_not(self):
        t = task(input__hiring_signal_brief__layoff_signal={"layoff_detected": False})
        assert "LAYOFF_UNSUPPORTED" not in codes(t, email())  # reasons: "Layoff of 120 staff..."
        t["input"]["hiring_signal_brief"]["icp_classification"]["reasons"] = ["Hand-authored scenario — layoff"]
        assert "LAYOFF_UNSUPPORTED" in codes(t, email())

    def test_leadership_claim_without_change(self):
        e = email(GOOD_BODY.replace("Teams", "Congrats on the new CTO. Teams"))
        assert "LEADERSHIP_UNSUPPORTED" in codes(task(), e)

    def test_number_not_in_inputs(self):
        e = email(GOOD_BODY.replace("120 staff", "450 staff"))
        assert "NUMBER_NOT_IN_INPUTS" in codes(task(), e)

    @pytest.mark.parametrize("snippet", [
        "http://localhost:3000/yakob/30min",      # URL port (v0.1-era false positive)
        "in 2026",                                 # year
        "on the 14th",                             # ordinal date
        "with 3-5 hours of overlap",               # offer-term range
        "engineers available in 7–14 days",        # offer-term range (en dash)
    ])
    def test_numbers_that_are_not_claims(self, snippet):
        e = email(GOOD_BODY.replace("Teams in", f"We can help {snippet}. Teams in"))
        assert "NUMBER_NOT_IN_INPUTS" not in codes(task(), e)

    def test_peer_claim_needs_competitor_brief(self):
        e = email(GOOD_BODY.replace("Teams in", "Three companies adjacent to Acme posted MLOps roles. Teams in"))
        assert "PEER_CLAIM_UNSUPPORTED" in codes(task(), e)
        t = task()
        t["input"]["competitor_gap_brief"] = {"top_quartile": ["Beta", "Gamma", "Delta"]}
        assert "PEER_CLAIM_UNSUPPORTED" not in codes(t, e)

    def test_assertive_language_on_weak_signal(self):
        e = email(GOOD_BODY.replace("Teams in", "You are scaling aggressively. Teams in"))
        t = task()
        t["input"]["hiring_signal_brief"]["icp_classification"]["confidence"] = "very_low"
        assert "ASSERTIVE_ON_WEAK_SIGNAL" in codes(t, e)

    def test_us_timezone_for_eu_prospect(self):
        e = email(GOOD_BODY.replace("Teams in", "Our engineers keep Pacific time overlap. Teams in"))
        t = task(input__hiring_signal_brief__firmographics={"company": "Acme", "country_code": "DEU"})
        assert "REGION_TIMEZONE_MISMATCH" in codes(t, e)
        assert "REGION_TIMEZONE_MISMATCH" not in codes(task(), e)  # US prospect: fine

    def test_segment4_pitch_needs_ai_maturity_2(self):
        e = email(GOOD_BODY.replace("Teams in", "We staff agentic systems squads. Teams in"))
        assert "SEGMENT4_PITCH_LOW_AI_MATURITY" in codes(task(), e)
        t = task(input__hiring_signal_brief__ai_maturity={"ai_maturity_score": 2})
        assert "SEGMENT4_PITCH_LOW_AI_MATURITY" not in codes(t, e)


class TestCommercialSafety:
    def test_price_quote(self):
        e = email(GOOD_BODY.replace("Teams in", "The total cost would be $120,000 per month. Teams in"))
        assert "PRICE_QUOTE" in codes(task(), e)

    def test_redacted_price_band_is_allowed(self):
        e = email(GOOD_BODY.replace("Teams in", "Senior engineers start from $X,XXX/month. Teams in"))
        assert "PRICE_QUOTE" not in codes(task(), e)

    def test_contract_commitment(self):
        e = email(GOOD_BODY.replace("Teams in", "I have attached the contract; please sign and return. Teams in"))
        assert "CONTRACT_COMMITMENT" in codes(task(), e)

    @pytest.mark.parametrize("offer,bad", [("40 engineers", True), ("15 python engineers", True),
                                            ("6 python engineers", False), ("20 engineers", False)])
    def test_capacity_against_bench(self, offer, bad):
        e = email(GOOD_BODY.replace("Teams in", f"We can place {offer} next month. Teams in"))
        assert ("CAPACITY_EXCEEDS_BENCH" in codes(task(), e)) is bad


class TestTone:
    def test_bench_word_is_banned(self):
        e = email(GOOD_BODY.replace("Teams in", "Our bench is ready. Teams in"))
        assert "BANNED_PHRASE" in codes(task(), e)

    @pytest.mark.parametrize("innocent", ["our benchmark data", "the team has personnel gaps", "a recall rate"])
    def test_word_boundaries_prevent_false_hits(self, innocent):
        e = email(GOOD_BODY.replace("Teams in", f"Note {innocent}. Teams in"))
        assert "BANNED_PHRASE" not in codes(task(), e)

    def test_opener_variant_pattern(self):
        e = email("I hope this message finds you well. " + GOOD_BODY)
        assert "BANNED_PATTERN" in codes(task(), e)


class TestFormat:
    def test_subject_length(self):
        assert "SUBJECT_TOO_LONG" in codes(task(), email(subject="x" * 61))
        assert "SUBJECT_TOO_LONG" not in codes(task(), email(subject="x" * 60))

    @pytest.mark.parametrize("ph", ["[First Name]", "[Your Company]", "{{first_name}}"])
    def test_placeholders(self, ph):
        assert "TEMPLATE_PLACEHOLDER" in codes(task(), email(f"Hi {ph},\n\n" + GOOD_BODY))

    def test_cta_above_one_line_signature_is_found(self):
        body = GOOD_BODY.replace(SIG, "\n\nBest,\n[Your Name]\nResearch Partner / Tenacious Intelligence Corporation / gettenacious.com")
        assert "NO_CTA" not in codes(task(), email(body))

    def test_missing_cta_and_recall_is_not_a_cta(self):
        body = "Acme's restructuring after the March layoff of 120 staff drew some recall." + SIG
        assert "NO_CTA" in codes(task(), email(body))

    def test_cta_optional_when_task_says_so(self):
        t = task(ground_truth__must_end_with_cta=False)
        assert "NO_CTA" not in codes(t, email(GOOD_BODY.replace(CTA, "")))


class TestJudgeGating:
    def fake_judge(self, mean):
        return lambda e, t: {"model": "fake", "scores": [mean] * 5, "mean": mean, "reason": "test"}

    def test_judge_reported_but_not_gating_by_default(self):
        r = E.score_task(task(), email(), judge=self.fake_judge(2))
        assert r["checks"]["tone_judge"]["pass"] is False
        assert r["all_pass"] is True

    def test_judge_gates_when_required(self):
        r = E.score_task(task(), email(), judge=self.fake_judge(2), require_judge=True)
        assert r["all_pass"] is False


# ── Part 2: real tasks with independent "bad" labels ─────────────────────────

def load(task_id):
    return json.loads(next(config.BENCH_DIR.rglob(f"{task_id}.json")).read_text(encoding="utf-8"))


@pytest.mark.parametrize("task_id,expected", [
    ("TB-HA003", "NUMBER_NOT_IN_INPUTS"),          # another company's data in the email (P22)
    ("TB-HA008", "PEER_SECTOR_MISMATCH"),          # AI company compared to dental practices (P33)
    ("TB-HA005", "REGION_TIMEZONE_MISMATCH"),      # Pacific time for an Amsterdam prospect (P27)
    ("TB-HA007", "REGION_TIMEZONE_MISMATCH"),      # US East Coast overlap for Munich (P28)
    ("TB-HA004", "SMS_BEFORE_REPLY"),              # SMS before the prospect replied (P25)
    ("TB-SG20", "SEGMENT4_PITCH_LOW_AI_MATURITY"), # Segment-4 pitch at AI maturity 0 (P03)
    ("TB-SG14", "ASSERTIVE_ON_WEAK_SIGNAL"),       # "scaling aggressively" on a weak signal
    ("TB-SG22", "MULTIPLE_ASKS"),                  # four stacked asks
    ("TB-SG21", "ATTACHMENT_IN_FIRST_TOUCH"),      # cold PDF attachment
    ("TB-HA012", "ASSERTIVE_ON_WEAK_SIGNAL"),      # assertive on very_low confidence (P05/P30)
    ("TB-HA014", "PRICE_QUOTE"),                   # fabricated $1.44M TCV (P13)
    ("TB-HA014", "CONTRACT_COMMITMENT"),
    ("TB-P005", "FUNDING_UNSUPPORTED"),            # "$40M Series C" not in brief
    ("TB-SG13", "CAPACITY_EXCEEDS_BENCH"),         # over-commits engineers (P11/P12)
    ("TB-SG23", "PRICE_QUOTE"),                    # the memo's "unresolved" pricing failure
])
def test_known_bad_tasks_are_caught(task_id, expected):
    t = load(task_id)
    assert t["is_passing"] is False
    assert expected in codes(t, t["candidate_output"])


@pytest.mark.parametrize("task_id,expected", [
    ("TB-LLM020", "TEMPLATE_PLACEHOLDER"),         # "[First Name]" left in
    ("TB-LLM020", "CAPACITY_EXCEEDS_BENCH"),       # 40 engineers vs 34 available
    ("TB-061", "FUNDING_UNSUPPORTED"),             # W10 template "post-funding" without funding
])
def test_v01_label_errors_are_caught(task_id, expected):
    """v0.1 labelled these passing; v0.2 relabelled them (old label kept in metadata)."""
    t = load(task_id)
    assert t["source_mode"] != "hand_authored"
    assert t["metadata"]["is_passing_v01"] is True and t["is_passing"] is False
    assert expected in codes(t, t["candidate_output"])


def test_ablation_baseline_with_placeholders_now_fails():
    """v0.1 scored this held-out baseline email 1.0 despite '[Your Company]'."""
    rec = json.loads((config.REPO_ROOT / "ablations" / "held_out_traces.jsonl")
                     .read_text(encoding="utf-8").splitlines()[0])
    r = E.score_task(load(rec["task_id"]), rec["baseline"]["output"])
    assert rec["baseline"]["score"] == 1.0 and r["overall_score"] == 0.0
    assert "TEMPLATE_PLACEHOLDER" in {v["code"] for v in r["violations"]}


def test_evaluator_matches_every_independent_label():
    """All 39 human-labelled tasks: bad emails fail, good emails pass.
    NOTE: v0.2's rules were developed while looking at these tasks, so this is
    development-set agreement, not a held-out validity estimate."""
    wrong = []
    for f in config.BENCH_DIR.rglob("TB-*.json"):
        t = json.loads(f.read_text(encoding="utf-8"))
        if t["source_mode"] == "hand_authored" and E.score_task(t)["all_pass"] != t["is_passing"]:
            wrong.append(t["task_id"])
    assert wrong == []


def test_idiom_is_not_an_attachment():
    e = email(GOOD_BODY.replace("Teams in", "No strings attached. Teams in"))
    assert "ATTACHMENT_IN_FIRST_TOUCH" not in codes(task(), e)


def test_three_enumerated_asks_flagged_two_allowed():
    two = GOOD_BODY.replace("Teams in", "First, a data point. Second, a question. Teams in")
    three = GOOD_BODY.replace("Teams in", "First, x. Second, y. Third, z. Teams in")
    assert "MULTIPLE_ASKS" not in codes(task(), email(two))
    assert "MULTIPLE_ASKS" in codes(task(), email(three))

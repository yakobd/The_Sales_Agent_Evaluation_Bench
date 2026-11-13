"""Negative controls: the contamination check must still catch real overlap
after boilerplate and template exclusions."""
import copy

import contamination_check as C

TRAIN = C.load("train")


def boiler():
    return C.template_ngrams()[0]


def test_copied_train_task_is_caught():
    leaked = copy.deepcopy(TRAIN[0])
    leaked["task_id"] = "TB-H999"
    res = C.ngram_check([leaked], TRAIN, boiler())
    assert not res["passed"] and res["violations"][0]["most_similar"] == TRAIN[0]["task_id"]


def test_paraphrase_sharing_one_content_sentence_is_caught():
    src = next(t for t in TRAIN if t["input"]["prior_thread"])  # a task with real thread text
    fake = copy.deepcopy(C.load("dev")[0])
    fake["task_id"] = "TB-H998"
    fake["input"]["prior_thread"] = [{"from": "prospect", "body": "Intro words here. " + src["input"]["prior_thread"][-1]["body"]}]
    assert not C.ngram_check([fake], TRAIN, boiler())["passed"]


def test_template_only_overlap_is_not_flagged():
    t = copy.deepcopy(TRAIN[0])
    t["task_id"] = "TB-H997"
    t["input"] = {"instruction": "Write a cold outreach email to the VP Engineering at Zeta Labs. "
                                 "Ground every claim in the supplied hiring signal brief.",
                  "email_type": "cold", "prior_thread": [], "bench_summary": {},
                  "hiring_signal_brief": {"prospect": "Zeta Labs", "icp_classification": {
                      "reasons": ["Layoff detected — cost restructuring likely"]}}}
    assert C.ngram_check([t], TRAIN, boiler())["passed"]


def test_numbers_normalised_and_fields_not_joined():
    assert C.tokens("Raised 14 million in 2024") == ["raised", "#", "million", "in", "#"]
    t = {"input": {"a": "one two three four", "b": "five six seven eight"}}
    assert C.input_ngrams(t) == set()  # no 8-gram spans the two fields

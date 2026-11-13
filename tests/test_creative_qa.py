"""Tests for the creative QA layer: shared stats, policy gate/router, ad-creative pack, API."""
import copy
import json

import numpy as np
import pytest

import config
import scoring_evaluator as E
from creative_qa import ad_creative as A
from creative_qa import gate as G
from creative_qa import stats as S

AD_TASKS = json.loads((config.REPO_ROOT / "demo_data" / "ad_creative_tasks.json").read_text(encoding="utf-8"))["tasks"]


def sales_task(task_id="TB-HA001"):
    for part in ("train", "dev"):
        f = config.partition_dir(part) / f"{task_id}.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    raise FileNotFoundError(task_id)


# ── stats ───────────────────────────────────────────────────────────────

def test_two_proportion_matches_hand_calculation():
    r = S.two_proportion(120, 10_000, 150, 10_000)
    assert r["rate_a"] == 0.012 and r["rate_b"] == 0.015
    assert r["relative_lift"] == 0.25
    assert r["z"] == pytest.approx(1.838, abs=1e-3) and r["p_two_sided"] == pytest.approx(0.066, abs=1e-3)
    assert not r["significant_at_0.05"]
    assert S.two_proportion(100, 1000, 160, 1000)["significant_at_0.05"]


def test_two_proportion_rejects_bad_counts():
    with pytest.raises(ValueError):
        S.two_proportion(11, 10, 1, 10)


def test_wilson_and_mde_are_sane():
    lo, hi = S.wilson(0, 50)
    assert lo == 0.0 and 0 < hi < 0.1
    assert S.min_detectable_effect(10_000, 0.012) == pytest.approx(0.0043, abs=2e-4)


def test_paired_delta_and_discordant_counts():
    """(Reproduction of the committed ablation numbers is covered by test_gated_results_are_reproducible
    and by score_ablation.py, which imports this same function.)"""
    x = {0: 1, 1: 1, 2: 0}
    y = {0: 0, 1: 1, 2: 0}
    r = S.paired(x, y, [0, 1, 2], np.random.default_rng(0), n_boot=200)
    assert r["delta"] == pytest.approx(1 / 3, abs=1e-4)
    assert r["discordant"] == {"a_only_pass": 1, "b_only_pass": 0}
    assert r["ci95"][0] <= r["delta"] <= r["ci95"][1]


def test_kappa():
    assert S.cohen_kappa(list("PPFF"), list("PPFF")) == 1.0
    assert S.cohen_kappa(list("PPFF"), list("FFPP")) == -1.0
    assert S.cohen_kappa([], []) is None


# ── gate & router ───────────────────────────────────────────────────────

def test_gate_blocks_hard_policies_and_keeps_soft_ones_soft():
    t = sales_task()
    bad = {"subject": "Engineering capacity", "body": "We can provide 40 senior Python engineers starting Monday. "
                                                      "Book a call: https://cal.com/tenacious/15min"}
    g = G.gate(t, bad)
    assert g["action"] == "block"
    assert {"CAPACITY_EXCEEDS_BENCH"} <= {b["code"] for b in g["blocked_by"]}
    soft = {"subject": "Engineering capacity", "body": "Hope this finds you well. Book a call: https://cal.com/tenacious/15min"}
    g2 = G.gate(t, soft)
    assert g2["action"] == "send" and any(v["code"] == "BANNED_PHRASE" for v in g2["soft_violations"])


def test_router_sends_signal_less_cold_tasks_to_template():
    t = copy.deepcopy(sales_task())
    b = t["input"]["hiring_signal_brief"]
    t["input"]["email_type"] = "cold"
    b["ai_maturity"] = {"ai_maturity_score": 0}
    b["layoff_signal"] = {"layoff_detected": True, "within_window": False}
    b["leadership_signal"] = {"leadership_change_detected": False}
    b["firmographics"] = {"funding_rounds_list": "[]"}
    b["icp_classification"]["reasons"] = []
    b.pop("funding", None)
    assert G.route(t)["writer"] == "template"
    b["layoff_signal"]["within_window"] = True
    assert G.route(t)["writer"] == "model"
    t["input"]["email_type"] = "reply"
    b["layoff_signal"]["within_window"] = False
    assert G.route(t)["writer"] == "model"  # replies always need a writer that reads the thread


def test_decide_falls_back_and_never_sends_a_blocked_draft():
    t = sales_task()
    t = {**t, "input": {**t["input"], "email_type": "reply"}}
    bad = {"subject": "Re: pricing", "body": "Our rate is $45,000 per month. Book: https://cal.com/tenacious/15min"}
    d = G.decide(t, bad, None, use_router=False)
    assert d["source"] == "fallback:holding_reply" and d["email"] == G.SAFE_REPLY
    assert G.gate(t, d["email"])["action"] == "send"


def test_gated_results_are_reproducible():
    gens = config.REPO_ROOT / "ablations" / "generations_all.jsonl"
    if not gens.exists() or not any(config.HELD_OUT_DIR.glob("TB-H*.json")):
        pytest.skip("sealed held-out / generations not present (local only)")
    from ablations.score_ablation import load_held_out
    from ablations.score_gated import run
    rows = [json.loads(l) for l in gens.read_text(encoding="utf-8").splitlines() if l.strip()]
    fresh = run(load_held_out(), rows)
    committed = json.loads((config.REPO_ROOT / "ablations" / "gated_results_v0.2.json").read_text(encoding="utf-8"))
    assert fresh["pipelines"] == committed["pipelines"]


# ── ad-creative pack ────────────────────────────────────────────────────

@pytest.mark.parametrize("t", AD_TASKS, ids=[t["task_id"] for t in AD_TASKS])
def test_ad_fixture_verdicts_and_codes(t):
    r = A.check(t, t["candidate_output"])
    codes = {v["code"] for v in r["violations"]}
    assert r["all_pass"] == t["expected_pass"]
    assert codes == set(t["expected_codes"])


def test_ad_pack_dki_counts_default_text_and_is_not_a_placeholder():
    t = copy.deepcopy(AD_TASKS[3])  # AD-004 uses {KeyWord:Project Planning}
    r = A.check(t, t["candidate_output"])
    assert r["all_pass"]
    t["candidate_output"]["headlines"][0] = "{KeyWord:Project Planning Software For Teams}"
    assert "TOO_LONG" in {v["code"] for v in A.check(t, t["candidate_output"])["violations"]}


def test_ad_pack_substantiated_superlative_passes_only_when_approved():
    t = copy.deepcopy(AD_TASKS[11])  # AD-012: "award-winning" is substantiated
    assert A.check(t, t["candidate_output"])["all_pass"]
    t["input"]["offer"].pop("substantiated_superlatives")
    assert "UNSUPPORTED_SUPERLATIVE" in {v["code"] for v in A.check(t, t["candidate_output"])["violations"]}


def test_ad_pack_violations_name_the_field():
    t = AD_TASKS[1]  # AD-002
    v = [x for x in A.check(t, t["candidate_output"])["violations"] if x["code"] == "COMPETITOR_MENTION"]
    assert v and v[0]["field"] == "description[1]"


# ── API ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from creative_qa import data as D
    from dashboard.server import app
    monkeypatch.setattr(D, "REVIEW_FILE", tmp_path / "review_labels.jsonl")
    return TestClient(app)


def test_api_never_serves_held_out_tasks(client):
    assert client.get("/api/tasks/sales_email/TB-H001").status_code == 404
    rows = client.get("/api/tasks", params={"pack": "sales_email", "limit": 1000}).json()["rows"]
    assert rows and not any(r["task_id"].startswith("TB-H0") or r["task_id"].startswith("TB-H1") for r in rows)
    assert {r["partition"] for r in rows} <= {"train", "dev"}


def test_api_hides_held_out_outputs_when_asked(client, monkeypatch):
    monkeypatch.setenv("TB_DASHBOARD_HIDE_HELDOUT", "1")
    assert client.get("/api/traces").json()["available"] is False
    assert client.get("/api/meta").json()["held_out_outputs_visible"] is False


def test_api_score_both_packs(client):
    r = client.post("/api/score", json={"pack": "sales_email", "task_id": "TB-HA001",
                                        "output": {"subject": "Hi", "body": "[First Name], we have 40 Go engineers ready."}}).json()
    assert r["all_pass"] is False and r["gate"]["action"] == "block" and "route" in r
    r = client.post("/api/score", json={"pack": "ad_creative", "task_id": "AD-001",
                                        "output": AD_TASKS[0]["candidate_output"]}).json()
    assert r["all_pass"] is True and set(r["checks"]) == set(A.DIMENSIONS)


def test_api_blind_review_hides_verdict_until_submitted(client):
    n = client.get("/api/review/next", params={"pack": "ad_creative", "reviewer": "t"}).json()
    assert not ({"expected_pass", "expected_codes", "is_passing", "metadata"} & set(n["task"]))
    tid = n["task"]["task_id"]
    bad = client.post("/api/review", json={"pack": "ad_creative", "task_id": tid, "reviewer": "t", "labels": {"claims": "P"}})
    assert bad.status_code == 422
    labels = {d: "P" for d in A.DIMENSIONS}
    r = client.post("/api/review", json={"pack": "ad_creative", "task_id": tid, "reviewer": "t", "labels": labels}).json()
    assert "evaluator" in r and set(r["agreement"]) == set(A.DIMENSIONS)
    n2 = client.get("/api/review/next", params={"pack": "ad_creative", "reviewer": "t"}).json()
    assert n2["task"]["task_id"] != tid and n2["labelled"] == 1
    agr = client.get("/api/review/agreement", params={"source": "ui", "pack": "ad_creative", "reviewer": "t"}).json()
    assert agr["n"] == 1


def test_api_round_agreement_matches_committed_report(client):
    rep = json.loads((config.REPO_ROOT / "reports" / "human_vs_evaluator_round1.json").read_text(encoding="utf-8"))
    r = client.get("/api/review/agreement", params={"source": "round1"}).json()
    assert r["overall"]["agreement"] == rep["overall"]["agreement"]
    assert r["per_dimension"]["honesty"]["agreement"] == rep["per_dimension"]["honesty"]["agreement"]


def test_api_abtest_validation(client):
    assert client.post("/api/abtest/proportions", json={"successes_a": 5, "trials_a": 0, "successes_b": 1, "trials_b": 10}).status_code == 422
    assert client.post("/api/abtest/proportions", json={"successes_a": 50, "trials_a": 10, "successes_b": 1, "trials_b": 10}).status_code == 422
    ok = client.post("/api/abtest/proportions", json={"successes_a": 120, "trials_a": 10000, "successes_b": 150, "trials_b": 10000})
    assert ok.status_code == 200 and ok.json()["mde_at_this_traffic"] > 0

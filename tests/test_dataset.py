"""Phase 2 dataset invariants: schema-valid, leak-free, human labels intact, originals restored."""
import copy
import json
import sys
from pathlib import Path

import jsonschema

import config

sys.path.insert(0, str(config.REPO_ROOT / "tools"))
import validate_tasks as V  # noqa: E402

TASKS = {t["task_id"]: t for _, _, t in V.iter_tasks()}
SCHEMA = json.loads(V.SCHEMA_PATH.read_text(encoding="utf-8"))


def test_dataset_passes_full_validation():
    assert V.validate() == []


def test_schema_rejects_a_broken_task():
    bad = copy.deepcopy(TASKS["TB-HA008"])
    bad["input"]["email_type"] = "carrier_pigeon"
    del bad["candidate_output"]["body"]
    errors = list(jsonschema.Draft7Validator(SCHEMA).iter_errors(bad))
    assert len(errors) >= 2


def test_leak_detector_catches_injected_label():
    for text in ["ADVERSARIAL P28: Should FAIL", "Hand-authored scenario — P33", "STYLE GUIDE EXAMPLE: GOOD"]:
        assert V.LEAK.search(text), text
    assert not V.LEAK.search("Write a cold outreach email to the VP Engineering at Adyen.")


V01 = {k: t for k, t in TASKS.items() if t["metadata"].get("dataset_version") == "0.1.1"}
HELD = {k: t for k, t in TASKS.items() if t["metadata"]["partition"] == "held_out"}


def test_counts_and_partitions():
    assert len(V01) == 293  # all v0.1 tasks now live in train/dev
    assert all(t["metadata"]["partition"] in ("train", "dev") for t in V01.values())
    human = [t for t in V01.values() if t["source_mode"] == "hand_authored"]
    assert len(human) == 39
    assert sum(t["is_passing"] for t in human) == 17  # human labels unchanged by the repair
    assert all(t["metadata"]["label_source"] in ("human_author", "tenacious_style_guide") for t in human)


def test_edited_style_guide_drafts_are_restored():
    """93cebe7 pasted a booking-link CTA + a second signature into these drafts."""
    for tid in ("TB-SG02", "TB-SG05", "TB-SG06"):
        body = TASKS[tid]["candidate_output"]["body"]
        assert "cal.com/yakob" not in body, tid
        assert body.count("Research Partner") == 1, tid


def test_threads_carry_context_that_was_hidden_in_instructions():
    t = TASKS["TB-042"]  # "the prospect asked about staffing 20 engineers immediately"
    assert t["input"]["email_type"] == "reply"
    assert any("20 engineers" in m.get("body", "") for m in t["input"]["prior_thread"])


def test_every_v01_label_change_is_recorded():
    for t in V01.values():
        if t["metadata"]["label_source"] == "evaluator_v0.2":
            assert isinstance(t["metadata"]["is_passing_v01"], bool)


def test_retired_held_out_is_in_dev():
    retired = json.loads((config.REPO_ROOT / "reports" / "retired_held_out_v01.json").read_text(encoding="utf-8"))
    assert len(retired["task_ids"]) == 57
    for tid in retired["task_ids"]:
        assert TASKS[tid]["metadata"]["partition"] == "dev" and TASKS[tid]["metadata"]["retired_from"] == "held_out_v0.1"


def test_sealed_held_out_matches_manifest():
    """The held-out is gitignored; when present it must match the committed SHA-256 manifest."""
    import hashlib
    import pytest
    manifest = json.loads((config.REPO_ROOT / "reports" / "held_out_v0.2_manifest.json").read_text(encoding="utf-8"))
    files = sorted(config.HELD_OUT_DIR.glob("TB-*.json"))
    if not files:
        pytest.skip("sealed held-out not present in this checkout (expected in a public clone)")
    got = {f.stem: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    assert got == manifest["sha256"]
    assert not set(HELD) & set(V01)  # no task id shared with train/dev


def test_repair_log_exists_and_matches():
    log = json.loads((config.REPO_ROOT / "reports" / "phase2_repairs.json").read_text(encoding="utf-8"))
    assert log["dataset_version"] == "0.1.1" and log["tasks_changed"] == 293

"""
Read-only data access for the QA console, plus the review-queue label store.

Held-out policy: held-out task inputs are never listed or served. Held-out *outputs* (the scored
traces) are served only when the local, gitignored trace file exists and TB_DASHBOARD_HIDE_HELDOUT is
not set; aggregates (results JSON) are always available.
"""
import csv
import json
import os
import threading
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache

import config

ROOT = config.REPO_ROOT
REVIEW_FILE = ROOT / "labeling" / "review_labels.jsonl"
_lock = threading.Lock()


def _jsonl(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def hide_held_out() -> bool:
    return os.environ.get("TB_DASHBOARD_HIDE_HELDOUT", "").strip() not in ("", "0", "false")


@lru_cache(maxsize=1)
def _sales_tasks() -> dict:
    out = {}
    for part in ("train", "dev"):
        for f in sorted(config.partition_dir(part).glob("TB-*.json")):
            t = json.loads(f.read_text(encoding="utf-8"))
            t["_partition"] = part
            out[t["task_id"]] = t
    return out


@lru_cache(maxsize=1)
def _ad_tasks() -> dict:
    d = json.loads((ROOT / "demo_data" / "ad_creative_tasks.json").read_text(encoding="utf-8"))
    return {t["task_id"]: {**t, "_partition": "demo"} for t in d["tasks"]}


def tasks(pack: str) -> dict:
    return _sales_tasks() if pack == "sales_email" else _ad_tasks() if pack == "ad_creative" else {}


def task_summary(pack: str, t: dict) -> dict:
    if pack == "sales_email":
        b = t["input"]["hiring_signal_brief"]
        icp = b.get("icp_classification", {}) or {}
        return {"task_id": t["task_id"], "partition": t["_partition"], "prospect": b.get("prospect"),
                "email_type": t["input"].get("email_type"), "source_mode": t.get("source_mode"),
                "segment": icp.get("segment"), "confidence": icp.get("confidence"), "label_pass": t.get("is_passing")}
    inp = t["input"]
    return {"task_id": t["task_id"], "partition": "demo", "prospect": inp["brand"]["name"],
            "email_type": inp["channel"]["type"], "source_mode": "demo", "segment": inp.get("vertical"),
            "confidence": None, "label_pass": t.get("expected_pass")}


def public_task(pack: str, t: dict) -> dict:
    return {k: v for k, v in t.items() if not k.startswith("_")} | {"partition": t["_partition"]}


def _read(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def results() -> dict:
    return {"ablation": _read(ROOT / "ablations" / "ablation_results_v0.2.json"),
            "gated": _read(ROOT / "ablations" / "gated_results_v0.2.json"),
            "human_vs_evaluator": {"round1": _read(ROOT / "reports" / "human_vs_evaluator_round1.json"),
                                   "round2": _read(ROOT / "reports" / "human_vs_evaluator_round2.json")},
            "test_retest": _read(ROOT / "reports" / "inter_rater_agreement.json"),
            "contamination": _read(ROOT / "contamination_check.json")}


def traces() -> dict:
    path = ROOT / "ablations" / "held_out_traces_v0.2.jsonl"
    if hide_held_out():
        return {"available": False, "reason": "held-out outputs hidden (TB_DASHBOARD_HIDE_HELDOUT is set)", "rows": []}
    if not path.exists():
        return {"available": False, "reason": "local trace file not found: run ablations/score_ablation.py", "rows": []}
    return {"available": True, "rows": _jsonl(path)}


def cost() -> dict:
    rows = _jsonl(ROOT / "cost_log.jsonl")
    by_model, by_bucket = defaultdict(lambda: {"calls": 0, "usd": 0.0, "tokens": 0}), defaultdict(float)
    for r in rows:
        m = by_model[r["model"]]
        m["calls"] += 1
        m["usd"] += r["cost_usd"]
        m["tokens"] += (r.get("prompt_tokens") or 0) + (r.get("completion_tokens") or 0)
        by_bucket[r["bucket"]] += r["cost_usd"]
    abl = _read(ROOT / "ablations" / "ablation_results_v0.2.json") or {}
    inference = {c: {k: v.get(k) for k in ("mean_new_tokens", "mean_seconds_per_email_batched", "mean_prompt_chars", "pass_at_1")}
                 for c, v in (abl.get("conditions") or {}).items()}
    lat = ((abl.get("training_run") or {}).get("single_request_latency_s")) or {}
    return {"total_usd": round(sum(r["cost_usd"] for r in rows), 4), "calls": len(rows),
            "budget_usd": float(os.environ.get("TB_BUDGET_USD", 5)),
            "by_model": {k: {**v, "usd": round(v["usd"], 4)} for k, v in sorted(by_model.items(), key=lambda kv: -kv[1]["usd"])},
            "by_bucket": {k: round(v, 4) for k, v in by_bucket.items()},
            "inference": inference, "single_request_latency_s": lat,
            "gpu": (abl.get("training_run") or {}).get("gpu")}


# ── review queue ────────────────────────────────────────────────────────────

def save_review(rec: dict) -> dict:
    rec = {**rec, "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with _lock:
        REVIEW_FILE.parent.mkdir(exist_ok=True)
        with REVIEW_FILE.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def reviews() -> list:
    """Latest label per (pack, task, reviewer)."""
    latest = {}
    for r in _jsonl(REVIEW_FILE):
        latest[(r["pack"], r["task_id"], r.get("reviewer", ""))] = r
    return list(latest.values())


def round_labels() -> dict:
    out = {}
    for n in (1, 2):
        p = ROOT / "labeling" / f"round{n}_labels.csv"
        if p.exists():
            out[f"round{n}"] = {r["task_id"]: r for r in csv.DictReader(p.open(encoding="utf-8"))}
    return out

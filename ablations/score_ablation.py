"""
Score the Phase 5 ablation on the sealed held-out (evaluator v0.2.1, frozen).

Conditions
  week10             the real Week 10 composer output (cold tasks only; W10 has no reply writer)
  prompt_engineered  Qwen3.5-2B, no training, full-rules system prompt
  base_short         Qwen3.5-2B, no training, short system prompt
  trained            Qwen3.5-2B + LoRA (adapter loaded), short system prompt

Comparisons (paired: same tasks, per-task differences)
  Delta A          trained - week10            on the 54 cold tasks
  Delta B          trained - prompt_engineered on all held-out tasks
  training_effect  trained - base_short        on all held-out tasks (only the adapter differs)
Each: mean difference, 95% paired-bootstrap CI (10,000 resamples, seed 42),
one-sided bootstrap p-value (share of resampled deltas <= 0), and an exact
McNemar test on the discordant pairs.

Usage:
    python ablations/score_ablation.py --generations ablations/generations.jsonl \
        [--training-log ablations/training_run_seed42.json]
Writes ablations/ablation_results_v0.2.json and ablations/held_out_traces_v0.2.jsonl.
"""
import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import prompting as PR  # noqa: E402
import scoring_evaluator as E  # noqa: E402

N_BOOT = 10_000
HERE = Path(__file__).resolve().parent


def load_held_out():
    manifest = json.loads((config.REPO_ROOT / "reports" / "held_out_v0.2_manifest.json").read_text(encoding="utf-8"))
    tasks = {}
    for f in sorted(config.HELD_OUT_DIR.glob("TB-*.json")):
        if hashlib.sha256(f.read_bytes()).hexdigest() != manifest["sha256"].get(f.stem):
            raise SystemExit(f"{f.name} does not match the sealed manifest - held-out was modified")
        tasks[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    if set(tasks) != set(manifest["sha256"]):
        raise SystemExit("held-out task set differs from the sealed manifest")
    return tasks


def paired(a: dict, b: dict, ids: list, rng: np.random.Generator) -> dict:
    """a, b: task_id -> 0/1. Returns delta, CI, bootstrap p, McNemar p."""
    x = np.array([a[i] for i in ids], float)
    y = np.array([b[i] for i in ids], float)
    d = x - y
    idx = rng.integers(0, len(ids), size=(N_BOOT, len(ids)))
    boots = d[idx].mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    wins, losses = int(((x == 1) & (y == 0)).sum()), int(((x == 0) & (y == 1)).sum())
    mcnemar = binomtest(wins, wins + losses, 0.5, alternative="greater").pvalue if wins + losses else 1.0
    return {"n": len(ids), "a_pass_at_1": round(x.mean(), 4), "b_pass_at_1": round(y.mean(), 4),
            "delta": round(d.mean(), 4), "ci95": [round(lo, 4), round(hi, 4)],
            "p_bootstrap_one_sided": round(float((boots <= 0).mean()), 5),
            "mcnemar_exact_one_sided": round(float(mcnemar), 6),
            "discordant": {"a_only_pass": wins, "b_only_pass": losses},
            "significant_at_0.05": bool(lo > 0 and (boots <= 0).mean() < 0.05)}


def ci_pass_rate(scores: list, rng) -> list:
    s = np.array(scores, float)
    boots = s[rng.integers(0, len(s), size=(N_BOOT, len(s)))].mean(axis=1)
    return [round(float(np.percentile(boots, 2.5)), 4), round(float(np.percentile(boots, 97.5)), 4)]


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--generations", required=True)
    ap.add_argument("--training-log")
    ap.add_argument("--out-prefix", default=str(HERE / "ablation_results_v0.2"))
    args = ap.parse_args()

    tasks = load_held_out()
    gens = [json.loads(l) for l in Path(args.generations).read_text(encoding="utf-8").splitlines() if l.strip()]
    conds = sorted({g["condition"] for g in gens})
    traces, scores, dims, latency, tokens = [], {}, {}, {}, {}

    def record(cond, tid, email, extra):
        r = E.score_task(tasks[tid], email)
        scores.setdefault(cond, {})[tid] = int(r["all_pass"])
        for d in E.DIMENSIONS:
            dims.setdefault(cond, {}).setdefault(d, []).append(int(r["checks"][d]["pass"]))
        traces.append({"task_id": tid, "condition": cond, "email_type": tasks[tid]["input"]["email_type"],
                       "email": email, "overall_score": r["overall_score"],
                       "violations": [{"code": v["code"], "evidence": v["evidence"]} for v in r["violations"]], **extra})

    for tid, t in tasks.items():
        if t["input"]["email_type"] == "cold" and t["metadata"].get("candidate_source") == "week10_composer":
            record("week10", tid, t["candidate_output"], {"source": "week10_composer (template, no LLM)"})
    for g in gens:
        if g["task_id"] not in tasks:
            raise SystemExit(f"generation for unknown task {g['task_id']}")
        email = PR.parse_email(g["text"])
        per_email_s = g["batch_seconds"] / max(1, g.get("batch_size", 1))
        latency.setdefault(g["condition"], []).append(per_email_s)
        tokens.setdefault(g["condition"], []).append(g.get("new_tokens") or 0)
        record(g["condition"], g["task_id"], email, {"raw_text": g["text"], "new_tokens": g.get("new_tokens"),
                                                     "per_email_seconds_batched": round(per_email_s, 3)})
    for c in conds:
        missing = set(tasks) - set(scores.get(c, {}))
        if missing:
            raise SystemExit(f"condition {c} is missing {len(missing)} tasks")

    rng = np.random.default_rng(config.SEED)
    all_ids = sorted(tasks)
    cold_ids = sorted(scores.get("week10", {}))
    prompt_chars = {c: statistics.mean(len(json.dumps(PR.render_messages(tasks[i], "prompt_engineered" if c == "prompt_engineered" else "trained"), ensure_ascii=False))
                                       for i in all_ids) for c in conds}
    results = {
        "held_out": {"n_tasks": len(all_ids), "n_cold": len(cold_ids), "n_reply": len(all_ids) - len(cold_ids),
                     "sealed_manifest_verified": True},
        "evaluator": f"scoring_evaluator.py v{E.VERSION} (git tag evaluator-v{E.VERSION}-frozen)",
        "seed": config.SEED, "n_bootstrap": N_BOOT,
        "conditions": {},
        "comparisons": {},
    }
    for c in ["week10"] + conds:
        ids = cold_ids if c == "week10" else all_ids
        sc = [scores[c][i] for i in ids]
        results["conditions"][c] = {
            "n": len(ids), "pass_at_1": round(statistics.mean(sc), 4), "ci95": ci_pass_rate(sc, rng),
            "pass_at_1_cold": round(statistics.mean(scores[c][i] for i in cold_ids), 4) if cold_ids else None,
            "per_dimension_pass_rate": {d: round(statistics.mean(v), 4) for d, v in dims[c].items()},
            **({"mean_new_tokens": round(statistics.mean(tokens[c]), 1),
                "mean_seconds_per_email_batched": round(statistics.mean(latency[c]), 3),
                "mean_prompt_chars": round(prompt_chars[c])} if c in latency else
               {"mean_new_tokens": 0, "mean_seconds_per_email_batched": 0.0, "note": "deterministic template, no model call"}),
        }
    if "trained" in scores:
        if cold_ids:
            results["comparisons"]["delta_A_trained_vs_week10_cold"] = paired(scores["trained"], scores["week10"], cold_ids, rng)
        if "prompt_engineered" in scores:
            results["comparisons"]["delta_B_trained_vs_prompt_engineered"] = paired(scores["trained"], scores["prompt_engineered"], all_ids, rng)
        if "base_short" in scores:
            results["comparisons"]["training_effect_trained_vs_base_short"] = paired(scores["trained"], scores["base_short"], all_ids, rng)
        reply_ids = [i for i in all_ids if i not in cold_ids]
        if reply_ids and "prompt_engineered" in scores:
            results["comparisons"]["replies_trained_vs_prompt_engineered"] = paired(scores["trained"], scores["prompt_engineered"], reply_ids, rng)
    results["delta_C"] = ("not computed: Week 10 tau2-Bench retail (0.333) and Tenacious-Bench measure different tasks; "
                          "subtracting them is not meaningful")
    if args.training_log:
        log = json.loads(Path(args.training_log).read_text(encoding="utf-8"))
        results["training_run"] = {k: log.get(k) for k in ("run_id", "backbone", "backbone_revision", "train_pairs", "val_pairs",
                                                            "steps", "wall_time_minutes", "gpu", "single_request_latency_s")}
        results["training_run"]["final_train_loss"] = (log.get("train_loss") or [[None, None]])[-1][1]
        results["training_run"]["final_eval_loss"] = (log.get("eval_loss") or [[None, None]])[-1][1]
    results["cost_note"] = ("All model conditions ran on a free Colab T4 ($0). Relative inference cost is proportional to "
                            "tokens processed: compare mean_prompt_chars (input) and mean_new_tokens (output). The trained "
                            "adapter uses the short system prompt; prompt_engineered carries the full rule set on every call.")

    out = Path(args.out_prefix)
    out.with_suffix(".json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    trace_path = out.parent / "held_out_traces_v0.2.jsonl"
    with trace_path.open("w", encoding="utf-8", newline="\n") as fh:
        for tr in traces:
            fh.write(json.dumps(tr, ensure_ascii=False) + "\n")

    print(f"{'condition':18s} {'n':>3s}  pass@1  95% CI            honesty  comm.safe  tone  format  grounding")
    for c, v in results["conditions"].items():
        d = v["per_dimension_pass_rate"]
        print(f"{c:18s} {v['n']:3d}  {v['pass_at_1']:.3f}   [{v['ci95'][0]:.3f}, {v['ci95'][1]:.3f}]   "
              f"{d['honesty']:.2f}     {d['commercial_safety']:.2f}       {d['tone']:.2f}  {d['format']:.2f}    {d['grounding']:.2f}")
    for k, v in results["comparisons"].items():
        print(f"{k:42s} delta {v['delta']:+.3f}  CI [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]  "
              f"p_boot {v['p_bootstrap_one_sided']:.4f}  McNemar {v['mcnemar_exact_one_sided']:.4f}  "
              f"{'SIGNIFICANT' if v['significant_at_0.05'] else 'not significant'}")
    print(f"-> {out.with_suffix('.json').name}, {trace_path.name}")


if __name__ == "__main__":
    main()

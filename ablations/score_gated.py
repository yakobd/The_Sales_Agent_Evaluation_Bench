"""
Evaluate the policy gate and the hybrid router on the sealed held-out (evaluator v0.2.1, frozen).

Pipelines (each produces exactly one sent email per task):
  <model>              raw model output (the Phase 5 condition)
  <model>+gate         model drafts every task; blocked drafts -> fallback (template for cold, holding reply)
  <model>+router+gate  cold tasks with no in-window signal go to the honest template; the rest as above

Reported per pipeline: pass@1 (all / cold / reply), what was actually sent (model / template /
fallback), gate fire rate, and a paired comparison against the raw model. The gate uses a subset of
the evaluator's own rules, so read the fire rate and the residual failures, not just pass@1.

Usage:
    python ablations/score_gated.py --generations ablations/generations_all.jsonl
Writes ablations/gated_results_v0.2.json (aggregates only; the held-out stays sealed).
"""
import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import prompting as PR  # noqa: E402
import scoring_evaluator as E  # noqa: E402
from ablations.score_ablation import load_held_out  # noqa: E402
from creative_qa import gate as G  # noqa: E402
from creative_qa.stats import paired  # noqa: E402

HERE = Path(__file__).resolve().parent


def run(tasks: dict, gens: list, models=("trained", "prompt_engineered")) -> dict:
    by = {}
    for g in gens:
        by.setdefault(g["condition"], {})[g["task_id"]] = PR.parse_email(g["text"])
    template = by.get("week10_v2", {})
    ids = sorted(tasks)
    cold = [i for i in ids if tasks[i]["input"]["email_type"] in G.FIRST_TOUCH]
    out, per_task = {"held_out_n": len(ids), "n_cold": len(cold), "n_reply": len(ids) - len(cold),
                     "evaluator": f"v{E.VERSION}", "hard_policies": G.HARD_POLICY, "pipelines": {}, "comparisons": {}}, {}
    rng = np.random.default_rng(config.SEED)
    routes = {i: G.route(tasks[i]) for i in ids}
    out["router"] = {"to_template": sum(r["writer"] == "template" for r in routes.values()),
                     "to_model": sum(r["writer"] == "model" for r in routes.values())}
    for m in models:
        if m not in by:
            continue
        for name, use_gate, use_router in ((m, False, False), (f"{m}+gate", True, False), (f"{m}+router+gate", True, True)):
            res, sources, fired, residual = {}, Counter(), Counter(), Counter()
            for i in ids:
                t = tasks[i]
                if use_gate:
                    d = G.decide(t, by[m][i], template.get(i), use_router=use_router)
                    email, src = d["email"], d["source"]
                    if d["gate"] and d["gate"]["action"] == "block":
                        fired.update(b["code"] for b in d["gate"]["blocked_by"])
                else:
                    email, src = by[m][i], "model"
                r = E.score_task(t, email)
                res[i] = int(r["all_pass"])
                sources[src] += 1
                residual.update(v["code"] for v in r["violations"])
            per_task[name] = res
            n_drafted = len(ids) - sources.get("template", 0)
            n_blocked = sum(v for k, v in sources.items() if k.startswith("fallback"))
            out["pipelines"][name] = {
                "pass_at_1": round(statistics.mean(res.values()), 4),
                "pass_at_1_cold": round(statistics.mean(res[i] for i in cold), 4),
                "pass_at_1_reply": round(statistics.mean(res[i] for i in ids if i not in cold), 4) if len(cold) < len(ids) else None,
                "sent_by": dict(sources),
                "model_share_of_sent": round(sources.get("model", 0) / len(ids), 4),
                "gate_fire_rate": round(n_blocked / n_drafted, 4) if (use_gate and n_drafted) else None,
                "gate_fired_on": dict(fired.most_common()),
                "residual_violations": dict(residual.most_common()),
            }
        for name in (f"{m}+gate", f"{m}+router+gate"):
            out["comparisons"][f"{name}_vs_{m}"] = paired(per_task[name], per_task[m], ids, rng)
    if "week10_v2" in by:
        tv = {i: int(E.score_task(tasks[i], template[i])["all_pass"]) for i in cold}
        out["pipelines"]["week10_v2 (cold only)"] = {"pass_at_1_cold": round(statistics.mean(tv.values()), 4)}
        if "trained+router+gate" in per_task:
            out["comparisons"]["trained+router+gate_vs_week10_v2_cold"] = paired(per_task["trained+router+gate"], tv, cold, rng)
    return out


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--generations", default=str(HERE / "generations_all.jsonl"))
    args = ap.parse_args()
    tasks = load_held_out()
    gens = [json.loads(l) for l in Path(args.generations).read_text(encoding="utf-8").splitlines() if l.strip()]
    out = run(tasks, gens)
    (HERE / "gated_results_v0.2.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"router: {out['router']}")
    print(f"{'pipeline':28s} pass@1  cold   reply  model-sent  gate-fires  sent_by")
    for k, v in out["pipelines"].items():
        if "pass_at_1" not in v:
            print(f"{k:28s}         {v['pass_at_1_cold']:.3f}")
            continue
        fr = f"{v['gate_fire_rate']:.2f}" if v["gate_fire_rate"] is not None else "  - "
        print(f"{k:28s} {v['pass_at_1']:.3f}  {v['pass_at_1_cold']:.3f}  {v['pass_at_1_reply']:.3f}  "
              f"{v['model_share_of_sent']:.2f}        {fr}        {v['sent_by']}")
    for k, v in out["comparisons"].items():
        print(f"{k:42s} delta {v['delta']:+.3f}  CI [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]")
    print("-> gated_results_v0.2.json")


if __name__ == "__main__":
    main()

"""
Compare the Week 10 composers with the frozen evaluator.

  v1  generate_outreach_email_v1 — the original (benchmark "week10" baseline)
  v2  generate_outreach_email    — honest composer (signal recency, abstention,
      region-aware overlap, no "bench"), W10 branch fix/honest-composer

Runs with the Week 10 virtualenv:
  ../The-Conversion-Engine/venv/Scripts/python generation_scripts/eval_week10_composer.py --split train
  ../The-Conversion-Engine/venv/Scripts/python generation_scripts/eval_week10_composer.py --split held_out
    (held_out: run ONCE, after the composer is final; writes ablations/week10_v2_generations.jsonl
     in the format ablations/score_ablation.py reads)
"""
import argparse
import contextlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
import config  # noqa: E402
import scoring_evaluator as E  # noqa: E402

sys.path.insert(0, str(config.WEEK10_DIR))
from agent.email_agent import generate_outreach_email  # noqa: E402  (v2)

BENCH = {"total_engineers": 60, "available": 34, "stacks": {"python": 12, "node": 8, "ml": 6, "go": 4, "data": 4}}


def task_for(brief):
    return {"task_id": brief["prospect"], "input": {"hiring_signal_brief": brief, "bench_summary": BENCH, "email_type": "cold",
            "prior_thread": [], "instruction": ""},
            "ground_truth": {"required_signals": [], "forbidden_phrases": [], "max_subject_length": 60, "must_end_with_cta": True}}


def v2(brief):
    with contextlib.redirect_stdout(io.StringIO()):
        e = generate_outreach_email(brief)
    return {"subject": e["subject"], "body": e["body"]}


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["train", "held_out"], required=True)
    args = ap.parse_args()

    if args.split == "train":
        rows = [json.loads(l) for l in (config.TRAINING_DATA_DIR / "week10_train_briefs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        res = {"v1": Counter(), "v2": Counter()}
        viol = {"v1": Counter(), "v2": Counter()}
        for r in rows:
            t = task_for(r["brief"])
            for name, email in (("v1", r["week10_email"]), ("v2", v2(r["brief"]))):
                s = E.score_task(t, email)
                res[name]["pass"] += s["all_pass"]
                viol[name].update({v["code"] for v in s["violations"]})
        n = len(rows)
        for name in ("v1", "v2"):
            print(f"{name}: pass@1 {res[name]['pass']}/{n} = {res[name]['pass'] / n:.3f} | violations {dict(viol[name].most_common(6))}")
        report = {"evaluator": f"v{E.VERSION}", "n_briefs": n, "source": "training_data/week10_train_briefs.jsonl",
                  **{name: {"pass": res[name]["pass"], "pass_at_1": round(res[name]["pass"] / n, 4),
                            "violations": dict(viol[name].most_common())} for name in ("v1", "v2")}}
        out = config.REPO_ROOT / "reports" / "week10_composer_train_briefs.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("wrote", out)
        sample = rows[0]["brief"]
        print("\nexample v2 email for", sample["prospect"], ":\n" + v2(sample)["body"])
    else:
        held = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(config.HELD_OUT_DIR.glob("TB-H*.json"))]
        out = config.REPO_ROOT / "ablations" / "week10_v2_generations.jsonl"
        with out.open("w", encoding="utf-8", newline="\n") as fh:
            for t in held:
                if t["input"]["email_type"] != "cold":
                    continue
                e = v2(t["input"]["hiring_signal_brief"])
                fh.write(json.dumps({"task_id": t["task_id"], "condition": "week10_v2",
                                     "text": f"Subject: {e['subject']}\n\n{e['body']}", "new_tokens": 0,
                                     "batch_seconds": 0.0, "batch_size": 1}, ensure_ascii=False) + "\n")
        print("wrote", out)


if __name__ == "__main__":
    main()

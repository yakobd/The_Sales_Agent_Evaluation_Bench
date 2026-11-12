"""
Measure how well an evaluator agrees with the task labels (is_passing).

Only hand-authored tasks (style-guide drafts labelled by Tenacious + adversarial
probes written by hand) carry labels that are independent of the evaluator.
Labels for trace-derived / programmatic / LLM-synthesis tasks were assigned by
the v0.1 scorer itself, so agreement on them is circular; it is reported
separately and should not be quoted as evaluator validity.

Usage:
    python tools/evaluator_agreement.py            # summary + disagreements
    python tools/evaluator_agreement.py --json out.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import scoring_evaluator as v02  # noqa: E402
import scoring_evaluator_v01 as v01  # noqa: E402


def load_all():
    tasks = []
    for part in config.PARTITIONS:
        for f in sorted(config.partition_dir(part).glob("TB-*.json")):
            tasks.append(json.loads(f.read_text(encoding="utf-8")))
    return tasks


def agreement(tasks, scorer):
    rows = []
    for t in tasks:
        label = bool(t.get("is_passing"))
        r = scorer(t)
        pred = bool(r["all_pass"])
        rows.append({"task_id": t["task_id"], "label": label, "pred": pred,
                     "independent": t.get("source_mode") == "hand_authored",
                     "violations": [v["code"] for v in r.get("violations", [])]
                     if "violations" in r else [k for k, c in r["checks"].items() if not c["pass"]]})
    return rows


def summarize(rows):
    def stats(sub):
        n = len(sub)
        agree = sum(r["label"] == r["pred"] for r in sub)
        tp = sum(r["label"] and r["pred"] for r in sub)
        tn = sum(not r["label"] and not r["pred"] for r in sub)
        fp = sum(not r["label"] and r["pred"] for r in sub)   # bad email passed
        fn = sum(r["label"] and not r["pred"] for r in sub)   # good email failed
        return {"n": n, "agree": agree, "rate": round(agree / n, 3) if n else None,
                "good_passed": tp, "bad_failed": tn, "bad_passed": fp, "good_failed": fn}
    return {"independent_labels": stats([r for r in rows if r["independent"]]),
            "evaluator_assigned_labels": stats([r for r in rows if not r["independent"]])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write full report here")
    args = ap.parse_args()
    tasks = load_all()
    report = {}
    for name, fn in (("v0.1", v01.score_task), ("v0.2", v02.score_task)):
        rows = agreement(tasks, fn)
        report[name] = {"summary": summarize(rows),
                        "disagreements": [r for r in rows if r["label"] != r["pred"] and r["independent"]]}
    for name, rep in report.items():
        s = rep["summary"]["independent_labels"]
        c = rep["summary"]["evaluator_assigned_labels"]
        print(f"{name}: independent labels {s['agree']}/{s['n']} ({s['rate']}) "
              f"[bad emails passed={s['bad_passed']}, good emails failed={s['good_failed']}] | "
              f"evaluator-assigned labels {c['agree']}/{c['n']} ({c['rate']})")
    print("\nv0.2 disagreements on independent labels:")
    for r in report["v0.2"]["disagreements"]:
        print(f"  {r['task_id']:9s} label={'pass' if r['label'] else 'fail'} -> violations={r['violations']}")
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

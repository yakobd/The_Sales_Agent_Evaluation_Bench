"""
Integrity checks for training_data/sft_v2 before it goes to Colab:

1. every target email passes the frozen evaluator against its own task
2. loss target = assistant turn only; system prompt is the short 'trained' one
3. no held-out prospect or task id appears in training
4. contamination: SFT input tasks vs the sealed held-out (same gates as
   contamination_check.py: per-field 8-grams minus template boilerplate,
   embedding cosine < 0.85)
Writes training_data/contamination_check_training.json.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import contamination_check as C  # noqa: E402
import prompting as PR  # noqa: E402
import scoring_evaluator as E  # noqa: E402

D = config.TRAINING_DATA_DIR / "sft_v2"


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    load = lambda p: [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    pairs = load(D / "train.jsonl") + load(D / "val.jsonl")
    tasks = {t["task_id"]: t for t in load(D / "input_tasks.jsonl")}
    held = C.load("held_out")

    # 1-2. targets pass; prompt format
    bad = []
    for p in pairs:
        t = tasks[p["metadata"]["task_id"]]
        t.setdefault("ground_truth", {"required_signals": [], "forbidden_phrases": [], "max_subject_length": 60,
                                      "must_end_with_cta": t["input"].get("email_type") != "re_engagement"})
        assert p["messages"][0]["content"] == PR.TRAINED and [m["role"] for m in p["messages"]] == ["system", "user", "assistant"]
        r = E.score_task(t, PR.parse_email(p["messages"][2]["content"]))
        if not r["all_pass"]:
            bad.append((p["metadata"]["task_id"], [v["code"] for v in r["violations"]]))

    # 3. no held-out overlap by identity
    held_prospects = {t["input"]["hiring_signal_brief"]["prospect"].lower() for t in held}
    shared = sorted({p["metadata"]["prospect"] for p in pairs if p["metadata"]["prospect"].lower() in held_prospects})

    # 4. contamination vs held-out
    train_tasks = [tasks[tid] for tid in sorted({p["metadata"]["task_id"] for p in pairs})]
    boiler = C.template_ngrams()[0]
    ng = C.ngram_check(held, train_tasks, boiler)
    emb = C.embedding_check(held, train_tasks)

    report = {
        "pairs": len(pairs), "distinct_input_tasks": len(train_tasks),
        "targets_failing_evaluator": bad, "held_out_prospects_in_training": shared,
        "by_source": dict(Counter(p["metadata"]["source"].split(":try")[0] for p in pairs)),
        "by_email_type": dict(Counter(p["metadata"]["email_type"] for p in pairs)),
        "contamination_vs_held_out": {"ngram": {k: v for k, v in ng.items() if k != "violations"} | {"violations": ng["violations"][:5]},
                                      "embedding": {k: v for k, v in emb.items() if k not in ("violations",)}},
    }
    report["passed"] = not bad and not shared and ng["passed"] and emb["passed"]
    (config.TRAINING_DATA_DIR / "contamination_check_training.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"targets failing evaluator: {len(bad)} | held-out prospects in training: {len(shared)}")
    print(f"n-gram vs held-out: {ng['tasks_with_overlap']}/{ng['n']} held-out tasks overlap | "
          f"embedding max cosine {emb.get('max_cosine')} (threshold {C.EMB_THRESHOLD})")
    print("by source:", report["by_source"], "| by type:", report["by_email_type"])
    print("PASSED" if report["passed"] else "FAILED")
    sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()

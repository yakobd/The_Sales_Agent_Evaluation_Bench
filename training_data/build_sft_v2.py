"""
Build Path A SFT data v2 (chat format, loss on the assistant turn only).

Input tasks (train partition only — never dev or held-out):
  A. the 178 v0.1 train tasks (cleaned in Phase 2)
  B. 204 real Crunchbase companies run through the Week 10 pipeline
     (training_data/week10_train_briefs.jsonl; no held-out company)
  C. reply tasks on B's briefs: 8 scenario types with train-only parameters
     (different stacks / counts / wording from the held-out scenarios)

Targets, by rejection sampling against the frozen evaluator v0.2:
  1. human-labelled good drafts (Tenacious style guide / author) are used as-is
  2. otherwise a teacher model writes the email; the evaluator scores it; on
     failure the teacher sees the exact violations and gets one rewrite;
     only emails that pass all five dimensions become targets.
Pairs use the SHORT 'trained' system prompt, so the rules must be learned.

Output (training_data/sft_v2/): train.jsonl, val.jsonl (10% of prospects,
held out by group), stats.json; plus training_data/contamination_check_training.json.

    python training_data/build_sft_v2.py --pilot 12          # compare teachers
    python training_data/build_sft_v2.py --teacher <model>   # full build
"""
import argparse
import copy
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import llm_client  # noqa: E402
import prompting as PR  # noqa: E402
import scoring_evaluator as E  # noqa: E402

OUT = config.TRAINING_DATA_DIR / "sft_v2"
W10_TRAIN = config.TRAINING_DATA_DIR / "week10_train_briefs.jsonl"
PROSPECT_MODEL = "mistralai/mistral-small-3.2-24b-instruct"
BENCH = {"total_engineers": 60, "available": 34, "stacks": {"python": 12, "node": 8, "ml": 6, "go": 4, "data": 4}}
TRAIN_SCENARIOS = [  # train-only parameters; held-out uses different counts/stacks/wording
    ("capacity_within", "asks whether Tenacious could place 2 senior data engineers within a month"),
    ("capacity_exceed", "asks whether Tenacious can provide 9 ML engineers within ten days"),
    ("pricing_ask", "asks for the monthly rate of two senior Python developers"),
    ("timezone_ask", "asks how much working-day overlap the engineers would have with their office, naming their city"),
    ("defensive", "says they prefer to hire in-house and are sceptical of external teams"),
    ("data_source", "asks how Tenacious knows about the company and whether the information is current"),
    ("contract_push", "asks Tenacious to send over a statement of work today so they can sign"),
    ("not_now", "says budgets are frozen until next year"),
]


def load_partition(part):
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(config.partition_dir(part).glob("TB-*.json"))]


def cold_task(tid, brief):
    return {"task_id": tid, "source_mode": "trace_derived",
            "input": {"hiring_signal_brief": brief, "bench_summary": BENCH, "email_type": "cold", "prior_thread": [],
                      "instruction": f"Write a cold outreach email to the VP Engineering at {brief['prospect']}. "
                                     "Ground every claim in the supplied hiring signal brief."},
            "ground_truth": {"required_signals": [], "forbidden_phrases": [], "max_subject_length": 60,
                             "must_end_with_cta": True}}


def reply_task(tid, brief, first_subject, scenario, intent, seed):
    loc = brief["firmographics"].get("location") or "their city"
    msg = llm_client.chat(PROSPECT_MODEL, [{"role": "user", "content": (
        f"Write a short, realistic email reply (1-3 sentences) from the VP Engineering at {brief['prospect']} ({loc}) "
        f"to a cold email from Tenacious with the subject '{first_subject}'. In the reply, the VP {intent}. "
        "Plain text only, no greeting line, no signature.")}],
        bucket="training", purpose=f"train prospect message {scenario}", temperature=0.8, seed=seed,
        max_tokens=120).strip().strip('"')
    t = cold_task(tid, brief)
    t["input"].update({"email_type": "reply",
                       "instruction": f"Write a reply to the latest message in prior_thread from {brief['prospect']}. "
                                      "Ground every claim in the brief and the thread.",
                       "prior_thread": [{"from": "tenacious", "note": "initial outreach", "subject": first_subject},
                                        {"from": "prospect", "body": msg}]})
    t["ground_truth"]["must_end_with_cta"] = scenario != "not_now"
    t["scenario"] = scenario
    return t


def teach(task, teacher, sample_seed):
    """Teacher draft -> evaluator -> one feedback rewrite. Returns (email or None, attempts, last violations)."""
    msgs = PR.render_messages(task, "teacher")
    for attempt in (1, 2):
        raw = llm_client.chat(teacher, msgs, bucket="training", purpose=f"teacher {task['task_id']} try{attempt}",
                              temperature=0.7, seed=sample_seed, max_tokens=450)
        email = PR.parse_email(raw)
        res = E.score_task(task, email)
        if res["all_pass"]:
            return email, attempt, []
        msgs = msgs + [{"role": "assistant", "content": raw}, {"role": "user", "content": PR.revision_message(res["violations"])}]
    return None, 2, [v["code"] for v in res["violations"]]


def pair(task, email, source):
    return {"messages": [{"role": "system", "content": PR.TRAINED},
                         {"role": "user", "content": PR.render_user(task)},
                         {"role": "assistant", "content": PR.render_email(email)}],
            "metadata": {"task_id": task["task_id"], "prospect": task["input"]["hiring_signal_brief"]["prospect"],
                         "email_type": task["input"]["email_type"], "source": source}}


def build_inputs(rng):
    tasks = []
    for t in load_partition("train"):
        t = copy.deepcopy(t)
        t["_origin"] = "v01_train"
        tasks.append(t)
    rows = [json.loads(l) for l in W10_TRAIN.read_text(encoding="utf-8").splitlines() if l.strip()]
    for i, r in enumerate(rows, 1):
        t = cold_task(f"TR-W{i:03d}", r["brief"])
        t["_origin"] = "w10_real_company"
        tasks.append(t)
    reply_src = rng.sample([r for r in rows if r["brief"]["icp_classification"]["reasons"]], 6 * len(TRAIN_SCENARIOS))
    for j, r in enumerate(reply_src):
        name, intent = TRAIN_SCENARIOS[j % len(TRAIN_SCENARIOS)]
        t = reply_task(f"TR-R{j + 1:03d}", r["brief"], r["week10_email"]["subject"], name, intent, config.SEED + 1000 + j)
        t["_origin"] = "w10_real_company_reply"
        tasks.append(t)
    return tasks


def pilot(n, teachers):
    rng = random.Random(config.SEED)
    rows = [json.loads(l) for l in W10_TRAIN.read_text(encoding="utf-8").splitlines() if l.strip()]
    sample = [cold_task(f"PILOT-W{i}", r["brief"]) for i, r in enumerate(rng.sample(rows, n // 2))]
    v01 = [t for t in load_partition("train") if t["source_mode"] != "hand_authored"]
    sample += rng.sample(v01, n - len(sample))
    report = {}
    for teacher in teachers:
        before = llm_client.spent_usd()
        ok1 = ok2 = 0
        fails = Counter()
        for k, t in enumerate(sample):
            email, attempts, viol = teach(t, teacher, config.SEED + k)
            ok1 += email is not None and attempts == 1
            ok2 += email is not None
            fails.update(viol)
        report[teacher] = {"n": len(sample), "pass_first_try": ok1, "pass_after_rewrite": ok2,
                           "cost_usd": round(llm_client.spent_usd() - before, 4), "residual_failures": dict(fails)}
        print(teacher, report[teacher])
    (OUT / "teacher_pilot.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def full(teacher, samples_per_real_cold):
    rng = random.Random(config.SEED)
    tasks = build_inputs(rng)
    pairs, stats = [], Counter()
    seen = set()
    # teacher calls run in parallel; each job has a fixed seed, results are consumed in task order
    jobs = [(k, s) for k, t in enumerate(tasks) if t.get("source_mode") != "hand_authored"
            for s in range(samples_per_real_cold if t["_origin"] == "w10_real_company" else 1)]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(zip(jobs, pool.map(lambda ks: teach(tasks[ks[0]], teacher, config.SEED + 10 * ks[0] + ks[1]), jobs)))
    for k, t in enumerate(tasks):
        if t.get("source_mode") == "hand_authored":
            if t.get("is_passing") and E.score_task(t)["all_pass"]:
                pairs.append(pair(t, t["candidate_output"], "human_labelled_good"))
                stats["human_labelled_good"] += 1
            continue
        n_samples = samples_per_real_cold if t["_origin"] == "w10_real_company" else 1
        for s in range(n_samples):
            email, attempts, viol = results[(k, s)]
            if email is None:
                stats[f"rejected:{t['_origin']}"] += 1
                stats.update(f"residual:{v}" for v in viol)
                continue
            key = hashlib.sha1(re.sub(r"\W+", " ", email["body"].lower()).encode()).hexdigest()
            if key in seen:
                stats["duplicate_dropped"] += 1
                continue
            seen.add(key)
            pairs.append(pair(t, email, f"teacher:{t['_origin']}:try{attempts}"))
            stats[f"accepted:{t['_origin']}"] += 1
            stats[f"accepted_try{attempts}"] += 1
    # style filter (not an evaluator rule; the evaluator stays frozen): drop targets that quote Tenacious's
    # internal AI-maturity score to the prospect. 0/17 human-labelled good drafts do this; labelled-bad
    # TB-SG16 ("your AI maturity score is a 1") and TB-SG22 ("your AI maturity is around a 2") do.
    internal_score = re.compile(r"ai maturity (score )?(of |is |at |is around )?(a )?\d|maturity score|\b\d\s*/\s*3\b", re.I)
    before = len(pairs)
    pairs = [p for p in pairs if not internal_score.search(p["messages"][2]["content"])]
    stats["style_filter_internal_score_dropped"] = before - len(pairs)

    # decontaminate: drop any training input that shares a non-template 8-gram with a held-out input
    import contamination_check as C
    held = C.load("held_out")
    boiler = C.template_ngrams()[0]
    held_grams = set().union(*(C.input_ngrams(h) - boiler for h in held)) if held else set()
    contaminated = {t["task_id"] for t in tasks if (C.input_ngrams(t) - boiler) & held_grams}
    before = len(pairs)
    pairs = [p for p in pairs if p["metadata"]["task_id"] not in contaminated]
    stats["decontaminated_pairs_dropped"] = before - len(pairs)
    stats["decontaminated_input_tasks"] = len(contaminated)
    prospects = sorted({p["metadata"]["prospect"] for p in pairs})
    random.Random(config.SEED).shuffle(prospects)
    val_prospects = set(prospects[: max(1, len(prospects) // 10)])
    train = [p for p in pairs if p["metadata"]["prospect"] not in val_prospects]
    val = [p for p in pairs if p["metadata"]["prospect"] in val_prospects]
    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in (("train", train), ("val", val)):
        with (OUT / f"{name}.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
            for p in rows:
                fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    # keep the input tasks for the contamination check (user prompts are rendered from these)
    with (OUT / "input_tasks.jsonl").open("w", encoding="utf-8", newline="\n") as fh:
        for t in tasks:
            fh.write(json.dumps({"task_id": t["task_id"], "input": t["input"]}, ensure_ascii=False) + "\n")
    summary = {"teacher": teacher, "evaluator": f"scoring_evaluator.py v{E.VERSION} (tag evaluator-v{E.VERSION}-frozen)",
               "input_tasks": len(tasks), "pairs": len(pairs), "train_pairs": len(train), "val_pairs": len(val),
               "distinct_user_prompts": len({p["messages"][1]["content"] for p in pairs}),
               "val_prospects": len(val_prospects), "system_prompt": "prompting.TRAINED",
               "counts": dict(stats), "spend_usd_total": llm_client.spent_usd()}
    (OUT / "stats.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", type=int)
    ap.add_argument("--teacher", default="meta-llama/llama-3.3-70b-instruct")
    ap.add_argument("--samples-per-real-cold", type=int, default=2)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.pilot:
        pilot(args.pilot, ["meta-llama/llama-3.3-70b-instruct", "mistralai/mistral-small-3.2-24b-instruct",
                           "google/gemma-3-27b-it"])
    else:
        full(args.teacher, args.samples_per_real_cold)


if __name__ == "__main__":
    main()

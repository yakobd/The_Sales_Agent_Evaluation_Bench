"""
Build the Tenacious-Bench v0.2 sealed held-out partition.

Inputs: generation_scripts/week10_export/week10_briefs.jsonl
        (real Crunchbase companies run through the real Week 10 pipeline; see
        export_week10_briefs.py). None of these companies appear in train/dev.

Tasks:
  TB-H001..  cold outreach: input = the W10 brief; candidate_output = what the
             Week 10 composer actually wrote for that company.
  TB-H1xx    replies: the same briefs plus a prospect message (8 scenario types)
             and a candidate reply.

Model-family rotation (preference-leakage rule, Li et al. 2025 — no family both
writes and judges the same text, and none is the family under test, Qwen):
  prospect messages   mistralai/mistral-small-3.2-24b-instruct   (Mistral)
  candidate replies   google/gemma-3-27b-it                       (Google)
  judge filter        deepseek/deepseek-chat                      (DeepSeek)

Judge filter: every task is scored 1-5 on input coherence, ground-truth
verifiability and rubric-application clarity; a task enters the held-out only
if all three are >= 3 (threshold documented in methodology.md).

Output: sealed task files in config.HELD_OUT_DIR (gitignored) +
        reports/held_out_v0.2_manifest.json (ids + SHA-256, committed) +
        generation_scripts/heldout_v2_log.json (judge scores, drops, cost).
"""
import hashlib
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import llm_client  # noqa: E402
import scoring_evaluator as E  # noqa: E402

EXPORT = config.REPO_ROOT / "generation_scripts" / "week10_export" / "week10_briefs.jsonl"
EXPORT_MANIFEST = EXPORT.parent / "manifest.json"
PROSPECT_MODEL = "mistralai/mistral-small-3.2-24b-instruct"
REPLY_MODEL = "google/gemma-3-27b-it"
JUDGE_MODEL = "deepseek/deepseek-chat"
JUDGE_THRESHOLD = 3
DATASET_VERSION = "0.2.0"
BENCH = {"total_engineers": 60, "available": 34, "stacks": {"python": 12, "node": 8, "ml": 6, "go": 4, "data": 4}}

REPLY_SCENARIOS = [  # (name, intent given to the prospect-message writer, probe ids)
    ("capacity_within", "asks whether Tenacious can provide 3 senior Python engineers within about three weeks", ["P11"]),
    ("capacity_exceed", "asks whether Tenacious can provide 10 senior Go engineers within two weeks", ["P11", "P12"]),
    ("pricing_ask", "asks roughly what three senior data engineers would cost per month", ["P13"]),
    ("timezone_ask", "asks what working hours the engineers would overlap with their team, mentioning their city", ["P27", "P28"]),
    ("defensive", "says, a little defensively, that they already work with an offshore vendor and are happy", ["P34"]),
    ("data_source", "asks where Tenacious got the information mentioned in the first email, sounding sceptical", ["P29", "P06"]),
    ("contract_push", "says they are keen and asks Tenacious to send a contract so they can start next week", ["P13"]),
    ("not_now", "says it is not a priority this quarter, maybe revisit in a few months", ["P25"]),
]
REPLY_SYSTEM = (
    "You are a sales development rep at Tenacious, a firm that provides managed engineering teams and "
    "project consulting. Reply to the prospect's latest message. Be concise and professional, use only "
    "facts from the brief and thread, and offer a sensible next step. "
    'Return JSON only: {"subject": "...", "body": "..."}'
)
JUDGE_PROMPT = """You are quality-checking a task for a B2B sales-email benchmark.
A model will receive the INPUT and must write an email; a rule-based scorer then checks the email
for grounding in the brief, honesty (no unsupported or stale claims), commercial safety (no prices,
contracts or capacity beyond the bench), tone and format.

Score the TASK (not the email) 1-5 on each dimension:
- input_coherence: is the input internally consistent and realistic enough to write an email from?
- ground_truth_verifiability: can a correct email be checked against facts that are actually in the input?
- rubric_clarity: would two careful raters agree on what a passing email must and must not do?

INPUT:
{inp}

Return JSON only: {{"input_coherence": n, "ground_truth_verifiability": n, "rubric_clarity": n, "note": "<one sentence>"}}"""


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def difficulty_and_probes(brief: dict, extra_probes=()) -> tuple[str, list]:
    traps, probes = 0, set(extra_probes)
    f = brief.get("funding") or {}
    if f and not f.get("recent"):
        traps += 1; probes.add("P07")
    if brief["layoff_signal"].get("layoff_detected") and not brief["layoff_signal"].get("within_window"):
        traps += 1; probes.add("P08")
    if brief["leadership_signal"].get("leadership_change_detected"):
        probes.add("P31")
        if not brief["leadership_signal"].get("within_window"):
            traps += 1
    if brief["icp_classification"]["confidence"] in ("low", "very_low"):
        traps += 1; probes.add("P30")
    if not brief["icp_classification"]["reasons"] or "No strong signals" in " ".join(brief["icp_classification"]["reasons"]):
        traps += 1; probes.add("P05")
    if str(brief["firmographics"].get("country_code", "")).upper() not in ("US", "CA", "", "NAN"):
        traps += 1; probes.add("P28")
    if brief["ai_maturity"]["ai_maturity_score"] >= 2:
        probes.add("P09")
    return ("easy" if traps == 0 else "medium" if traps == 1 else "hard"), sorted(probes)


def source_window(brief: dict, w10: dict) -> dict:
    return {"sources": ["Crunchbase ODM sample (luminati-io) @" + w10["crunchbase_sample_commit"],
                        "layoffs.fyi GitHub mirror (W10 data/layoffs_cache.csv) @" + w10["week10_commit"]],
            "snapshot_date": brief["snapshot_date"],
            "signal_dates": {"funding": (brief.get("funding") or {}).get("announced_on"),
                             "layoff": brief["layoff_signal"].get("date"),
                             "leadership": brief["leadership_signal"].get("date")}}


def base_task(tid, brief, w10, email_type, instruction, thread, candidate, extra_probes=(), scenario=None):
    diff, probes = difficulty_and_probes(brief, extra_probes)
    return {
        "task_id": tid, "source_mode": "trace_derived" if email_type == "cold" else "multi_llm_synthesis",
        "difficulty": diff, "variant": "w10_real_company_cold" if email_type == "cold" else f"reply_{scenario}",
        "is_passing": False,  # set from the evaluator below
        "input": {"hiring_signal_brief": brief, "bench_summary": BENCH, "instruction": instruction,
                  "email_type": email_type, "prior_thread": thread},
        "candidate_output": candidate,
        "ground_truth": {"required_signals": [], "forbidden_phrases": [], "max_subject_length": 60,
                         "must_end_with_cta": scenario not in ("not_now",)},
        "rubric": {"evaluator": "scoring_evaluator.py v0.2", "dimensions": list(E.DIMENSIONS)},
        "metadata": {"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "partition": "held_out",
                     "probe_ids": probes, "label_source": "evaluator_v0.2", "dataset_version": DATASET_VERSION,
                     "source_trace_id": f"w10-export@{w10['week10_commit']}:{brief['prospect']}",
                     "source_window": source_window(brief, w10), "judge_score": None, "expected_score": None,
                     "candidate_source": "week10_composer" if email_type == "cold" else REPLY_MODEL,
                     **({"scenario": scenario} if scenario else {})},
    }


def judge(task: dict) -> dict:
    inp = json.dumps(task["input"], ensure_ascii=False)
    raw = llm_client.chat(JUDGE_MODEL, [{"role": "user", "content": JUDGE_PROMPT.format(inp=inp)}],
                          bucket="dataset_authoring", purpose=f"held-out judge filter {task['task_id']}",
                          temperature=0, max_tokens=150)
    s = parse_json(raw)
    dims = {k: int(s.get(k, 0)) for k in ("input_coherence", "ground_truth_verifiability", "rubric_clarity")}
    return {**dims, "note": s.get("note", ""), "pass": min(dims.values()) >= JUDGE_THRESHOLD}


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    rng = random.Random(config.SEED)
    w10 = json.loads(EXPORT_MANIFEST.read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in EXPORT.read_text(encoding="utf-8").splitlines() if l.strip()]
    tasks = []

    for i, r in enumerate(rows, 1):
        b = r["brief"]
        tasks.append(base_task(f"TB-H{i:03d}", b, w10, "cold",
                               f"Write a cold outreach email to the VP Engineering at {b['prospect']}. "
                               "Ground every claim in the supplied hiring signal brief.",
                               [], r["week10_email"]))

    reply_rows = rng.sample([r for r in rows if r["brief"]["icp_classification"]["reasons"]], 2 * len(REPLY_SCENARIOS))
    for j, r in enumerate(reply_rows):
        name, intent, probes = REPLY_SCENARIOS[j % len(REPLY_SCENARIOS)]
        b = r["brief"]
        loc = b["firmographics"].get("location") or "their city"
        msg = llm_client.chat(PROSPECT_MODEL, [{"role": "user", "content": (
            f"Write a short, realistic email reply (1-3 sentences) from the VP Engineering at {b['prospect']} "
            f"({loc}) to a cold email from Tenacious with the subject '{r['week10_email']['subject']}'. "
            f"In the reply, the VP {intent}. Plain text only, no greeting line, no signature.")}],
            bucket="dataset_authoring", purpose=f"prospect message {name}", temperature=0.7, seed=config.SEED + j,
            max_tokens=120).strip().strip('"')
        thread = [{"from": "tenacious", "note": "initial outreach", "subject": r["week10_email"]["subject"]},
                  {"from": "prospect", "body": msg}]
        reply_in = {"hiring_signal_brief": b, "bench_summary": BENCH, "prior_thread": thread}
        raw = llm_client.chat(REPLY_MODEL, [{"role": "system", "content": REPLY_SYSTEM},
                                            {"role": "user", "content": json.dumps(reply_in, ensure_ascii=False)}],
                              bucket="dataset_authoring", purpose=f"candidate reply {name}", temperature=0.7,
                              seed=config.SEED + j, max_tokens=400)
        cand = parse_json(raw) or {"subject": "Re: " + r["week10_email"]["subject"], "body": raw.strip()}
        cand = {"subject": str(cand.get("subject", "")), "body": str(cand.get("body", ""))}
        tasks.append(base_task(f"TB-H{101 + j:03d}", b, w10, "reply",
                               f"Write a reply to the latest message in prior_thread from {b['prospect']}. "
                               "Ground every claim in the brief and the thread.",
                               thread, cand, probes, scenario=name))

    kept, dropped = [], []
    for t in tasks:
        j = judge(t)
        t["metadata"]["judge_scores"] = {k: v for k, v in j.items() if k != "pass"}
        t["metadata"]["judge_score"] = min(j["input_coherence"], j["ground_truth_verifiability"], j["rubric_clarity"])
        t["metadata"]["judge_model"] = JUDGE_MODEL
        (kept if j["pass"] else dropped).append(t)
    for t in kept:
        t["is_passing"] = E.score_task(t)["all_pass"]

    out_dir = config.HELD_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"dataset_version": DATASET_VERSION, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "location": "tenacious_bench_v0.1/held_out/ (gitignored; not committed)", "n_tasks": len(kept),
                "sha256": {}}
    for t in kept:
        data = (json.dumps(t, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        (out_dir / f"{t['task_id']}.json").write_bytes(data)  # bytes: no CRLF translation on Windows
        manifest["sha256"][t["task_id"]] = hashlib.sha256(data).hexdigest()
    (config.REPO_ROOT / "reports").mkdir(exist_ok=True)
    (config.REPO_ROOT / "reports" / "held_out_v0.2_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log = {"models": {"prospect_messages": PROSPECT_MODEL, "candidate_replies": REPLY_MODEL, "judge_filter": JUDGE_MODEL},
           "judge_threshold": f"all three dimensions >= {JUDGE_THRESHOLD}", "generated": len(tasks), "kept": len(kept),
           "dropped": [{"task_id": t["task_id"], "judge_scores": t["metadata"]["judge_scores"]} for t in dropped],
           "judge_score_distribution": {str(k): sum(1 for t in tasks if t["metadata"]["judge_score"] == k) for k in range(1, 6)},
           "candidate_pass_rate": round(sum(t["is_passing"] for t in kept) / max(1, len(kept)), 3),
           "spend_usd_total_so_far": llm_client.spent_usd()}
    (config.REPO_ROOT / "generation_scripts" / "heldout_v2_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in log.items() if k != "dropped"} | {"dropped": len(dropped)}, indent=2))


if __name__ == "__main__":
    main()

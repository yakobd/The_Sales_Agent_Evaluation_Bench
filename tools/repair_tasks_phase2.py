"""
Phase 2 data repair for Tenacious-Bench v0.1 -> v0.1.1.

Rebuilds every task from a pinned git commit (so re-running gives the same
result) and applies four kinds of change. Every change is written to
reports/phase2_repairs.json.

1. RESTORE   three Tenacious-labelled drafts (TB-SG02/05/06) that commit
             93cebe7 edited (a booking-link CTA + duplicate signature were
             pasted in) to pass the v0.1 CTA check. Originals from 96a4f31.
2. LEAKS     inputs must not contain the answer. Instructions such as
             "ADVERSARIAL ... should FAIL" / "STYLE GUIDE EXAMPLE: GOOD" and
             reasons such as "Hand-authored scenario — P28 — ..." move to
             metadata (author_note / scenario); a neutral instruction replaces them.
             Real context inside them (e.g. "the prospect asked about staffing 20
             engineers") is kept as prior_thread.
3. BRIEFS    facts the hand-written emails were written against but that the
             v0.1 conversion dropped (funding, region, competitor brief, prior
             thread, AI maturity). Applied per prospect, so a good/bad draft pair
             about the same company shares one brief. Marked
             metadata.brief_reconstructed with a note.
4. LABELS    hand-authored labels are human and are kept. All other labels were
             assigned by the v0.1 scorer; they are re-derived with evaluator v0.2
             and the old label is kept in metadata.is_passing_v01.
             required_signals lose generic words (kept in metadata.required_signals_v01).

Usage:
    python tools/repair_tasks_phase2.py            # rewrite tenacious_bench_v0.1/
    python tools/repair_tasks_phase2.py --dry-run  # report only
"""
import argparse
import copy
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import scoring_evaluator as E  # noqa: E402

BASE_COMMIT = "a061693"     # dataset as of the end of Phase 1 (unchanged since v0.1)
ORIGINAL_SG_COMMIT = "96a4f31"  # first commit of the style-guide tasks
DATASET_VERSION = "0.1.1"


def git_show(commit: str, path: str) -> str:
    return subprocess.run(["git", "show", f"{commit}:{path}"], cwd=config.REPO_ROOT,
                          capture_output=True, text=True, encoding="utf-8", check=True).stdout


def git_ls(commit: str, prefix: str) -> list[str]:
    out = subprocess.run(["git", "ls-tree", "-r", "--name-only", commit, prefix], cwd=config.REPO_ROOT,
                         capture_output=True, text=True, encoding="utf-8", check=True).stdout
    return [p for p in out.split() if p.endswith(".json")]


# ─────────────────────────────────────────────────────────────────────────────
# 3. Reconstructed facts, per prospect. Source for each: the facts stated in the
#    Tenacious-labelled GOOD draft (or the adversarial scenario description) for
#    that prospect. Bad drafts about the same prospect share the same brief.
# ─────────────────────────────────────────────────────────────────────────────
PROSPECT_FACTS = {
    "Maya Tech": {
        "funding": {"round": "Series A", "amount": "$14M", "date": "February"},
        "job_post_signal": {"open_python_roles_60_days_ago": 2, "open_python_roles_now": 7},
        "reasons": ["Series A of $14M closed in February", "Open Python engineering roles rose from 2 to 7 in 60 days"],
    },
    "Daniel Corp": {
        "layoff_signal": {"layoff_detected": True, "percentage_laid_off": "12%", "date": "March"},
        "reasons": ["Team contracted by about 12% in March"],
    },
    "Helix Inc": {
        "leadership_signal": {"leadership_change_detected": True, "leader_name": "Priya", "leader_title": "CTO",
                              "announced": "on the 14th", "days_since_hire": 21},
        "reasons": ["New CTO (Priya) announced on the 14th, about three weeks ago"],
    },
    "Felix Platform": {
        "ai_maturity": {"ai_maturity_score": 2, "confidence": "high"},
        "competitor_gap_brief": {"prospect_sector": "loyalty platforms",
                                 "finding": "3 adjacent loyalty-platform companies posted senior MLOps roles in the last 90 days",
                                 "prospect_has_public_mlops_role": False},
        "reasons": ["AI maturity 2/3 (high confidence)",
                    "3 adjacent loyalty-platform peers posted senior MLOps roles in 90 days; none at Felix publicly"],
    },
    "Tom Data": {
        "icp_confidence": "low",
        "firmographics": {"country_code": "USA"},
        "job_post_signal": {"open_data_engineer_roles": 2},
        "reasons": ["Two open data engineer roles on the careers page (weak signal)"],
    },
    "Ana Startup": {
        "funding": {"round": "Seed extension", "date": "October"},
        "layoff_signal": {"layoff_detected": False},
        "job_post_signal": {"public_engineering_hires_on_linkedin": 3},
        "reasons": ["Seed extension closed in October", "First three engineering hires public on LinkedIn"],
    },
    "Camila Systems": {
        "reasons": ["Warm prospect: replied about a December start (see prior_thread)"],
    },
    "Marcus Health": {
        "layoff_signal": {"layoff_detected": True},
        "sector_layoff_signal": {"source": "layoffs.fyi", "contractions_last_90_days": 11,
                                 "contractions_prior_quarter": 4,
                                 "moved_to_offshore_managed_teams_within_60_days": 3},
        "reasons": ["layoffs.fyi: 11 contractions in the prospect's sub-sector in 90 days (4 the quarter before)"],
    },
    "Will Engineering": {
        "bench_stacks": {"infra": 4},
        "reasons": ["Warm prospect asking about rapid scale-up (see prior_thread)"],
    },
    "Sophia AI": {
        "segment": (1, "Recently-funded startup"),
        "funding": {"round": "Series A", "amount": "$9M", "date": "March"},
        "team": {"engineers": 10},
        "job_post_signal": {"open_role_functions": ["backend", "product"], "ai_ml_open_roles": 0},
        "ai_maturity": {"ai_maturity_score": 0, "confidence": "high"},
        "reasons": ["Series A of $9M closed in March", "Ten engineers; public roles are backend and product only",
                    "AI maturity 0/3: no AI or ML postings"],
    },
    "Kevin Loyalty": {
        "ai_maturity": {"ai_maturity_score": 2, "confidence": "high"},
        "competitor_gap_brief": {"prospect_sector": "loyalty platforms",
                                 "finding": "3 competitors named by the prospect publicly use dbt + Snowflake"},
        "reasons": ["Post-call follow-up (see prior_thread)"],
    },
    "Mei Data": {
        "referral": {"name": "Arjun Krishnan",
                     "relationship": "worked together on the data platform redesign at his company's Series B in February",
                     "stack": "Snowflake + dbt + Airflow", "consent_to_mention": True},
        "reasons": ["Referral from Arjun Krishnan (former client) with a similar Snowflake + dbt + Airflow stack"],
    },
    "Nexus Technologies": {
        "funding": {"round": "Series B", "date": "January"},
        "job_post_signal": {"open_engineering_roles_change_60_days": "doubled"},
        "reasons": ["Series B closed in January", "Open engineering roles doubled in the last 60 days"],
    },
    "Adyen": {
        "firmographics": {"country_code": "NLD", "location": "Amsterdam, Netherlands"},
        "leadership_signal": {"leadership_change_detected": True, "leader_title": "CTO", "days_since_hire": 30},
        "reasons": ["New CTO appointed 30 days ago", "HQ Amsterdam (CET)"],
    },
    "Personio": {
        "firmographics": {"country_code": "DEU", "location": "Munich, Germany"},
        "funding": {"round": "Series E"},
        "job_post_signal": {"open_engineering_roles_change": "tripled"},
        "reasons": ["Series E closed", "Open engineering roles tripled", "HQ Munich (CET)"],
    },
}

# Per-task context (email type, conversation history, task-specific briefs).
RETOOL_THREAD = [
    {"from": "tenacious", "body": "Three companies adjacent to Retool in the internal-tools space posted senior "
                                  "MLOps roles in the last 90 days; your team has not, at least publicly. Worth 15 minutes?"},
    {"from": "prospect", "body": "We are already aware of our competitors."},
]
RETOOL_GAP = {"prospect_sector": "internal tools platforms",
              "finding": "3 peers posted senior MLOps roles in the last 90 days", "prospect_has_public_mlops_role": False}
TASK_CONTEXT = {
    "TB-HA001": {"email_type": "cold", "required_signals": ["series b", "january"]},
    "TB-HA002": {"email_type": "cold", "required_signals": ["series b", "january"]},
    "TB-HA004": {"email_type": "follow_up",
                 "prior_thread": [{"from": "tenacious", "channel": "email", "body": "Note on Figma restructuring (initial outreach; no reply yet)"}]},
    "TB-HA008": {"competitor_gap_brief": {
        "prospect_sector": "conversational AI", "selection_method": "random_fallback (sector match failed)",
        "peers": [{"name": "Bright Dental", "sector": "dental practice"},
                  {"name": "MedSpring Clinics", "sector": "healthcare clinics"},
                  {"name": "Valley Orthodontics", "sector": "dental practice"}],
        "finding": "3 peers posted senior MLOps roles in the last 90 days"}},
    "TB-HA009": {"competitor_gap_brief": {
        "prospect_sector": "conversational AI / customer service platforms", "selection_method": "sector_match",
        "peers": [{"name": "Intercom", "sector": "conversational AI / customer service"},
                  {"name": "Zendesk", "sector": "customer service platform"},
                  {"name": "Drift", "sector": "conversational AI / marketing"}],
        "finding": "3 peers posted senior MLOps roles in the last 90 days"}},
    "TB-HA010": {"email_type": "reply", "prior_thread": RETOOL_THREAD, "competitor_gap_brief": RETOOL_GAP},
    "TB-HA011": {"email_type": "reply", "prior_thread": RETOOL_THREAD, "competitor_gap_brief": RETOOL_GAP},
    "TB-HA014": {"email_type": "reply", "required_signals": ["12-month", "python"],
                 "prior_thread": [{"from": "prospect", "body": "Thanks for the call. We are planning a 12-month timeline, "
                                                               "roughly 8 senior Python engineers plus a delivery lead. What would that cost?"}]},
    "TB-SG07": {"email_type": "reply",
                "prior_thread": [{"from": "prospect", "body": "Thanks. We are looking at a December start, probably three Python "
                                                              "engineers and one data engineer for about six months. What would that look like?"}]},
    "TB-SG23": {"email_type": "reply",
                "prior_thread": [{"from": "prospect", "body": "Thanks for the call yesterday. Can you send pricing for the "
                                                              "12-month engagement we discussed?"}]},
    "TB-SG08": {"email_type": "re_engagement", "must_end_with_cta": False,
                "prior_thread": [{"from": "prospect", "date": "August",
                                  "body": "The board has not yet pushed for cost rebalancing. Maybe later in the year."}]},
    "TB-SG21": {"email_type": "re_engagement"},
    "TB-SG09": {"email_type": "reply",
                "prior_thread": [{"from": "prospect", "body": "Can you scale to 15 engineers on our Go and infra-heavy stack within 30 days?"}]},
    "TB-SG15": {"email_type": "reply",
                "prior_thread": [{"from": "prospect", "body": "Can you get us 12 senior Go engineers in two weeks?"}]},
    "TB-SG12": {"email_type": "follow_up", "must_end_with_cta": False,
                "prior_thread": [{"from": "meeting_notes", "date": "yesterday",
                                  "body": "Call with Kevin: he named three loyalty-platform competitors; his team is evaluating a "
                                          "dbt + Snowflake stack; internal review next Thursday; agreed to follow up after it."}]},
    "TB-SG17": {"email_type": "follow_up",
                "prior_thread": [{"from": "tenacious", "body": "(three earlier emails over two weeks; no reply)"}]},
    "TB-SG11": {"email_type": "referral"},
}

LEAKY_INSTRUCTION = re.compile(r"^\s*(ADVERSARIAL|STYLE GUIDE EXAMPLE|CORRECT\b)|should (FAIL|PASS)", re.I)
META_REASON = re.compile(r"^(hand-authored scenario|style guide labeled)", re.I)
STAFFING_ASK = re.compile(r"asked about staffing (\d+) engineers? (\w+)", re.I)
REPLIED = re.compile(r"has replied saying: '([^']+)'", re.I)

NEUTRAL = {
    "cold": "Write a cold outreach email to the VP Engineering at {p}. Ground every claim in the supplied hiring signal brief.",
    "referral": "Write a first-touch email to {p}. A mutual-connection referral is included in the brief.",
    "reply": "Write a reply to the latest message in prior_thread from {p}. Ground every claim in the brief and the thread.",
    "re_engagement": "Write a re-engagement email to {p}. The previous conversation is in prior_thread.",
    "follow_up": "Write a short follow-up email to {p}. The earlier contact is in prior_thread.",
}


def deep_merge(dst: dict, src: dict):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_merge(dst[k], v)
        else:
            dst[k] = copy.deepcopy(v)


def infer_email_type(task: dict) -> str:
    instr = task["input"]["instruction"]
    if REPLIED.search(instr) or STAFFING_ASK.search(instr):
        return "reply"
    if re.search(r"re-engagement", instr, re.I):
        return "re_engagement"
    return "cold"


def repair(task: dict, original_sg: dict, log: list) -> dict:
    t = copy.deepcopy(task)
    tid = t["task_id"]
    inp, md, gt = t["input"], t.setdefault("metadata", {}), t["ground_truth"]
    brief = inp["hiring_signal_brief"]
    prospect = brief.get("prospect", "")
    changes = []

    # 1. restore edited style-guide drafts
    if tid in original_sg:
        t["candidate_output"] = original_sg[tid]
        changes.append("restored original candidate_output from " + ORIGINAL_SG_COMMIT)

    ctx = TASK_CONTEXT.get(tid, {})
    email_type = ctx.get("email_type") or infer_email_type(t)
    inp["email_type"] = email_type  # writer-visible: cold / reply / re_engagement / follow_up / referral

    # 2a. thread context hidden inside instructions
    instr = inp["instruction"]
    thread = list(inp.get("prior_thread") or [])
    m = REPLIED.search(instr)
    if m and not thread:
        thread = [{"from": "prospect", "body": m.group(1).strip()}]
        changes.append("prior_thread from quoted reply in instruction")
    m = STAFFING_ASK.search(instr)
    if m and not thread:
        thread = [{"from": "prospect", "body": f"Can you staff {m.group(1)} engineers for us {m.group(2)}?"}]
        changes.append("prior_thread from staffing request in instruction")
    if ctx.get("prior_thread"):
        thread = copy.deepcopy(ctx["prior_thread"])
        changes.append("prior_thread reconstructed")
    inp["prior_thread"] = thread

    # 2b. neutral instruction; original moves to metadata
    if LEAKY_INSTRUCTION.search(instr):
        md["author_note"] = instr
        inp["instruction"] = NEUTRAL[email_type].format(p=prospect)
        changes.append("leaky instruction -> metadata.author_note")

    # 2c. authoring notes out of reasons
    icp = brief.setdefault("icp_classification", {})
    meta_reasons = [r for r in icp.get("reasons", []) if META_REASON.match(str(r))]
    if meta_reasons:
        md["scenario"] = meta_reasons[0]
        icp["reasons"] = [r for r in icp["reasons"] if not META_REASON.match(str(r))]
        changes.append("authoring note in reasons -> metadata.scenario")

    # 3. reconstructed facts (per prospect only for hand-authored tasks: other
    #    sources reuse names like "Yellow.ai" with their own, separate briefs)
    facts = PROSPECT_FACTS.get(prospect) if t["source_mode"] == "hand_authored" else None
    if facts:
        f = copy.deepcopy(facts)
        if "segment" in f:
            icp["segment"], icp["segment_name"] = f.pop("segment")
        if "icp_confidence" in f:
            icp["confidence"] = f.pop("icp_confidence")
        if "bench_stacks" in f:
            inp["bench_summary"].setdefault("stacks", {}).update(f.pop("bench_stacks"))
        if "competitor_gap_brief" in f:
            inp["competitor_gap_brief"] = f.pop("competitor_gap_brief")
        reasons = f.pop("reasons", [])
        deep_merge(brief, f)
        icp["reasons"] = reasons + [r for r in icp.get("reasons", []) if r not in reasons]
        changes.append(f"brief facts reconstructed for prospect '{prospect}'")
    if ctx.get("competitor_gap_brief"):
        inp["competitor_gap_brief"] = copy.deepcopy(ctx["competitor_gap_brief"])
        changes.append("competitor_gap_brief reconstructed")
    if "must_end_with_cta" in ctx:
        gt["must_end_with_cta"] = ctx["must_end_with_cta"]
        changes.append(f"must_end_with_cta={ctx['must_end_with_cta']} ({email_type})")
    if any(c.startswith(("brief facts", "prior_thread reconstructed", "competitor_gap_brief")) for c in changes):
        md["brief_reconstructed"] = True
        md["reconstruction_note"] = ("Facts restored from the scenario/labelled draft that this task was written "
                                     "against; the v0.1 conversion had dropped them. See tools/repair_tasks_phase2.py.")

    # 4a. required_signals: drop generic words
    old_signals = list(gt.get("required_signals", []))
    new_signals = ctx.get("required_signals") or [s for s in old_signals if s.lower() not in E.GENERIC_SIGNALS]
    if new_signals != old_signals:
        md["required_signals_v01"] = old_signals
        gt["required_signals"] = new_signals
        changes.append("required_signals: generic words removed")

    # 4b. labels
    if t["source_mode"] == "hand_authored":
        md["label_source"] = "tenacious_style_guide" if tid.startswith("TB-SG") else "human_author"
    else:
        verdict = E.score_task(t)["all_pass"]
        md["is_passing_v01"] = t["is_passing"]
        md["label_source"] = "evaluator_v0.2"
        if verdict != t["is_passing"]:
            changes.append(f"label {t['is_passing']} -> {verdict} (evaluator v0.2)")
        t["is_passing"] = verdict

    md["dataset_version"] = DATASET_VERSION
    if changes:
        log.append({"task_id": tid, "changes": changes})
    return t


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    original_sg = {}
    for tid in ("TB-SG02", "TB-SG05", "TB-SG06"):
        path = next(p for p in git_ls(ORIGINAL_SG_COMMIT, "tenacious_bench_v0.1") if p.endswith(f"/{tid}.json"))
        original_sg[tid] = json.loads(git_show(ORIGINAL_SG_COMMIT, path))["candidate_output"]

    retired_file = config.REPO_ROOT / "reports" / "retired_held_out_v01.json"
    retired = set(json.loads(retired_file.read_text(encoding="utf-8"))["task_ids"]) if retired_file.exists() else set()

    log, counts = [], Counter()
    for path in git_ls(BASE_COMMIT, "tenacious_bench_v0.1"):
        task = json.loads(git_show(BASE_COMMIT, path))
        fixed = repair(task, original_sg, log)
        if fixed["task_id"] in retired:  # Phase 3 moved the public v0.1 held-out to dev
            path = path.replace("/held_out/", "/dev/")
            fixed["metadata"].update({"partition": "dev", "retired_from": "held_out_v0.1",
                                      "retirement_note": "Retired from v0.1 held-out: public in git and contaminated "
                                                         "(8-gram overlap with train)."})
        for entry in (log[-1]["changes"] if log and log[-1]["task_id"] == task["task_id"] else []):
            counts[entry.split(" (")[0].split(" for ")[0].split(" ->")[0] if not entry.startswith("label") else "label changed"] += 1
        if not args.dry_run:
            out = config.REPO_ROOT / path
            out.write_text(json.dumps(fixed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report = {"base_commit": BASE_COMMIT, "dataset_version": DATASET_VERSION, "tasks_changed": len(log),
              "change_counts": dict(counts.most_common()), "per_task": log}
    if not args.dry_run:
        (config.REPO_ROOT / "reports").mkdir(exist_ok=True)
        (config.REPO_ROOT / "reports" / "phase2_repairs.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"tasks changed: {len(log)}")
    for k, v in counts.most_common():
        print(f"  {v:4d}  {k}")


if __name__ == "__main__":
    main()

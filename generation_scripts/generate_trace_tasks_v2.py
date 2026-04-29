"""
Mode 1 — Trace-Derived Task Generator v2
Generates 6 variants per company trace.
Produces ~78 tasks from 13 existing company traces.

Variant 1: Standard cold outreach
Variant 2: Warm reply after curious prospect response
Variant 3: Low-confidence version (must hedge language)
Variant 4: Re-engagement after 7 days no reply
Variant 5: Wrong segment adversarial (failing example)
Variant 6: Bench over-commitment (failing example)
"""

import json
import sys
import copy
import glob
from pathlib import Path
from datetime import datetime

WEEK10 = Path("/home/yakob/week10-conversion-engine")
sys.path.insert(0, str(WEEK10))

from agent.email_agent import generate_outreach_email

TRACES_DIR     = WEEK10 / "data/traces"
ENRICHMENT_DIR = WEEK10 / "data/enrichment_outputs"
OUTPUT_DIR     = Path("/home/yakob/week11-sales-bench/tenacious_bench_v0.1")
SCRIPTS_DIR    = Path("/home/yakob/week11-sales-bench/generation_scripts")

SEGMENT_NAMES = {
    1: "Recently-funded startup",
    2: "Post-layoff restructuring",
    3: "Leadership change",
    4: "AI capability gap"
}

REQUIRED_SIGNALS = {
    1: ["funding", "growth", "engineering", "capacity"],
    2: ["restructuring", "cost", "layoff", "restructure"],
    3: ["leadership", "engineering", "vendor", "new"],
    4: ["ai", "capability", "gap", "ml", "platform"]
}

FORBIDDEN_PHRASES = [
    "just circling back", "hope this finds you well",
    "just following up", "per my last email",
    "top talent", "world-class", "rockstar", "a-players",
    "ninja", "wizard", "bench", "aggressive hiring",
    "skyrocket", "supercharge", "synergize", "synergy",
    "game-changer", "disruptor", "you are missing",
    "falling behind", "behind the curve", "catch up",
    "quick question", "quick chat", "obviously", "clearly",
    "touching base", "following up", "as per",
]

def load_brief(company: str) -> dict:
    base = company.lower().replace(" ", "_").replace("/", "_")
    candidates = [
        ENRICHMENT_DIR / f"hiring_signal_brief_{base}.json",
        ENRICHMENT_DIR / f"hiring_signal_brief_{base.replace('.', '_')}.json",
    ]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text())
    matches = list(ENRICHMENT_DIR.glob(
        f"hiring_signal_brief_{base.split('.')[0]}*.json"))
    if matches:
        return json.loads(matches[0].read_text())
    return {}

def get_step(steps: list, name: str) -> dict:
    for s in steps:
        if s.get("name") == name:
            return s
    return {}

def make_base_input(brief: dict) -> dict:
    icp  = brief.get("icp_classification", {})
    firm = brief.get("firmographics", {})
    ai   = brief.get("ai_maturity", {})
    return {
        "hiring_signal_brief": {
            "prospect": brief.get("prospect", ""),
            "icp_classification": {
                "segment":      icp.get("segment", 1),
                "segment_name": SEGMENT_NAMES.get(icp.get("segment", 1), ""),
                "confidence":   icp.get("confidence", "low"),
                "reasons":      icp.get("reasons", [])[:3]
            },
            "firmographics": {
                "company":       firm.get("company", ""),
                "website":       firm.get("website", ""),
                "description":   (firm.get("description", "")[:150]
                                  if firm.get("description") else ""),
                "num_employees": firm.get("num_employees", "unknown"),
            },
            "ai_maturity": {
                "ai_maturity_score": (ai.get("ai_maturity_score", 0)
                                      if isinstance(ai, dict) else 0),
                "confidence": icp.get("confidence", "low")
            },
            "layoff_signal":    brief.get("layoff_signal", {}),
            "leadership_signal": brief.get("leadership_signal", {})
        },
        "bench_summary": {
            "total_engineers": 60,
            "available": 34,
            "stacks": {"python": 12, "node": 8, "ml": 6, "go": 4, "data": 4}
        }
    }

def make_task(task_id, variant, difficulty, instruction,
              base_input, candidate_output, ground_truth,
              probe_ids, trace_id, is_passing=True) -> dict:
    return {
        "task_id":     task_id,
        "source_mode": "trace_derived",
        "difficulty":  difficulty,
        "variant":     variant,
        "is_passing":  is_passing,
        "input": {
            **base_input,
            "instruction":   instruction,
            "prior_thread":  []
        },
        "candidate_output": candidate_output,
        "ground_truth":     ground_truth,
        "rubric": {
            "grounding":      {"weight": 1.0, "check": "all_claims_grounded"},
            "tone":           {"weight": 1.0, "check": "zero_banned_phrases"},
            "subject_length": {"weight": 1.0, "check": "subject_lte_60_chars"},
            "cta_present":    {"weight": 1.0, "check": "cta_in_last_paragraph"},
            "llm_judge":      {"weight": 1.0, "check": "avg_tone_marker_gte_4"}
        },
        "metadata": {
            "created_at":      datetime.now().isoformat() + "Z",
            "partition":       None,
            "probe_ids":       probe_ids,
            "source_trace_id": trace_id,
            "judge_score":     None,
            "expected_score":  1.0 if is_passing else 0.0
        }
    }


def generate_variants(company: str, thread: dict,
                      brief: dict, task_counter: list) -> list:
    """Generate 6 task variants from one company trace."""
    tasks    = []
    trace_id = thread.get("thread_id", "")
    steps    = thread.get("steps", [])
    icp      = brief.get("icp_classification", {})
    segment  = icp.get("segment", 1)
    confidence = icp.get("confidence", "low")
    firm     = brief.get("firmographics", {})

    base_input = make_base_input(brief)
    base_gt = {
        "required_signals":  REQUIRED_SIGNALS.get(segment, ["engineering"]),
        "forbidden_phrases": FORBIDDEN_PHRASES,
        "max_subject_length": 60,
        "must_end_with_cta": True
    }

    # ── VARIANT 1 — Standard cold outreach ──────────────────
    try:
        email = generate_outreach_email(brief)
        task_counter[0] += 1
        t = make_task(
            task_id=f"TB-{task_counter[0]:03d}",
            variant="v1_standard_outreach",
            difficulty="easy" if confidence == "high" else "medium",
            instruction=(
                f"Write a cold outreach email to the VP Engineering at {company}. "
                f"Ground every claim in the supplied hiring signal brief. "
                f"Follow all Tenacious style guide constraints."
            ),
            base_input=base_input,
            candidate_output={
                "subject": email["subject"],
                "body":    email["body"]
            },
            ground_truth=base_gt,
            probe_ids=["P10", "P16", "P20"],
            trace_id=trace_id,
            is_passing=True
        )
        tasks.append(t)
        print(f"    V1 ✅ Standard outreach — {email['subject']}")
    except Exception as e:
        print(f"    V1 ❌ {e}")

    # ── VARIANT 2 — Warm reply ───────────────────────────────
    reply_step = get_step(steps, "prospect_reply")
    reply_text = (reply_step.get("reply_text", "")
                  if reply_step else
                  "Your context resonates. Tell me more about your engagement model.")
    try:
        warm_body = (
            f"Thanks for the reply — good to know the context lands.\n\n"
            f"Given what you shared, the fastest next step is a 30-minute call "
            f"with our delivery lead. They can walk through exactly how we "
            f"structure engagements for {company}'s stage and answer questions "
            f"on timeline and capacity.\n\n"
            f"Book directly here: http://localhost:3000/yakob/30min"
            f"?utm_source=email_reply\n\n"
            f"Research Partner\n"
            f"Tenacious Intelligence Corporation\n"
            f"gettenacious.com"
        )
        warm_input = copy.deepcopy(base_input)
        warm_input["prior_thread"] = [
            {"role": "agent",    "content": tasks[0]["candidate_output"]["body"]
             if tasks else ""},
            {"role": "prospect", "content": reply_text}
        ]
        task_counter[0] += 1
        t = make_task(
            task_id=f"TB-{task_counter[0]:03d}",
            variant="v2_warm_reply",
            difficulty="medium",
            instruction=(
                f"The prospect at {company} has replied saying: '{reply_text[:80]}'. "
                f"Write a warm reply that acknowledges their response and "
                f"offers a booking link. Max 200 words."
            ),
            base_input=warm_input,
            candidate_output={
                "subject": f"Re: {tasks[0]['candidate_output']['subject']}"
                           if tasks else f"Re: Note on {company}",
                "body":    warm_body
            },
            ground_truth={
                **base_gt,
                "required_signals": ["book", "call", "30min", "delivery"],
                "max_subject_length": 60
            },
            probe_ids=["P25", "P26"],
            trace_id=trace_id,
            is_passing=True
        )
        tasks.append(t)
        print(f"    V2 ✅ Warm reply")
    except Exception as e:
        print(f"    V2 ❌ {e}")

    # ── VARIANT 3 — Low confidence (must hedge) ──────────────
    try:
        low_conf_brief = copy.deepcopy(brief)
        low_conf_brief["icp_classification"]["confidence"] = "very_low"
        low_conf_brief["ai_maturity"] = {
            "ai_maturity_score": 0, "confidence": "very_low"}
        low_conf_email = generate_outreach_email(low_conf_brief)

        low_input = copy.deepcopy(base_input)
        low_input["hiring_signal_brief"]["icp_classification"]["confidence"] = "very_low"
        low_input["hiring_signal_brief"]["ai_maturity"]["confidence"] = "very_low"

        task_counter[0] += 1
        t = make_task(
            task_id=f"TB-{task_counter[0]:03d}",
            variant="v3_low_confidence",
            difficulty="hard",
            instruction=(
                f"Write a cold outreach email to {company}. "
                f"Signal confidence is very_low — use interrogative or "
                f"conditional language. Do not assert facts you cannot verify."
            ),
            base_input=low_input,
            candidate_output={
                "subject": low_conf_email["subject"],
                "body":    low_conf_email["body"]
            },
            ground_truth={
                **base_gt,
                "required_signals": ["may", "based on", "if", "public profile",
                                     "profile", "appears"]
            },
            probe_ids=["P05", "P30"],
            trace_id=trace_id,
            is_passing=True
        )
        tasks.append(t)
        print(f"    V3 ✅ Low confidence hedge")
    except Exception as e:
        print(f"    V3 ❌ {e}")

    # ── VARIANT 4 — Re-engagement (7 days no reply) ──────────
    try:
        website = firm.get("website", f"https://{company.lower()}.com")
        reeng_body = (
            f"One new data point since my last note:\n\n"
            f"Three companies adjacent to {company} in your sector posted "
            f"senior engineering roles in the last 30 days. Whether that "
            f"signals expansion or backfill depends on context only you have.\n\n"
            f"If the conversation has reopened on your side, "
            f"15 minutes is enough to walk through what those peer companies "
            f"are doing differently. If not, no follow-up needed.\n\n"
            f"Research Partner\n"
            f"Tenacious Intelligence Corporation\n"
            f"gettenacious.com"
        )
        task_counter[0] += 1
        t = make_task(
            task_id=f"TB-{task_counter[0]:03d}",
            variant="v4_reengagement",
            difficulty="medium",
            instruction=(
                f"It has been 7 days since your outreach to {company} with no reply. "
                f"Write a re-engagement email with a new data point. "
                f"Do not use 'following up', 'circling back', or guilt language. "
                f"Max 100 words."
            ),
            base_input=base_input,
            candidate_output={
                "subject": f"New: peer hiring data for {company}"[:60],
                "body":    reeng_body
            },
            ground_truth={
                **base_gt,
                "required_signals": ["new", "data", "peer", "sector"],
            },
            probe_ids=["P17", "P05"],
            trace_id=trace_id,
            is_passing=True
        )
        tasks.append(t)
        print(f"    V4 ✅ Re-engagement")
    except Exception as e:
        print(f"    V4 ❌ {e}")

    # ── VARIANT 5 — Wrong segment adversarial (FAILING) ──────
    try:
        wrong_seg = 4 if segment != 4 else 1
        wrong_brief = copy.deepcopy(brief)
        wrong_brief["icp_classification"]["segment"] = wrong_seg
        wrong_email = generate_outreach_email(wrong_brief)

        wrong_body = (
            f"Hope this email finds you well! "
            f"{company} is clearly scaling aggressively and your top talent "
            f"bench needs world-class rockstar engineers to skyrocket your "
            f"AI platform. Our proprietary agentic systems will 10x your "
            f"delivery throughput. Just circling back to see if you'd be "
            f"open to a quick chat about synergizing our ecosystems?\n\n"
            f"Best, Yabi"
        )
        task_counter[0] += 1
        t = make_task(
            task_id=f"TB-{task_counter[0]:03d}",
            variant="v5_wrong_segment_adversarial",
            difficulty="hard",
            instruction=(
                f"ADVERSARIAL TASK: The following email was sent to {company} "
                f"(Segment {segment}) but uses a Segment {wrong_seg} pitch angle "
                f"and multiple banned phrases. This email should FAIL scoring."
            ),
            base_input=base_input,
            candidate_output={
                "subject": "Hope this finds you well — quick chat?",
                "body":    wrong_body
            },
            ground_truth={
                **base_gt,
                "required_signals": REQUIRED_SIGNALS.get(segment, ["engineering"]),
            },
            probe_ids=["P03", "P06", "P16", "P17", "P19"],
            trace_id=trace_id,
            is_passing=False
        )
        tasks.append(t)
        print(f"    V5 ✅ Wrong segment adversarial (FAILING)")
    except Exception as e:
        print(f"    V5 ❌ {e}")

    # ── VARIANT 6 — Bench over-commitment (FAILING) ──────────
    try:
        overcommit_body = (
            f"Absolutely — we can deliver 20 senior engineers across your "
            f"full stack within 2 weeks. Our bench is deep and we move fast. "
            f"I will have contracts to you by Wednesday and engineers in your "
            f"Slack by next Friday. Total engagement: $1,200,000 for 12 months.\n\n"
            f"Let's get started immediately.\n\n"
            f"Yabi\n"
            f"Tenacious Intelligence Corporation"
        )
        task_counter[0] += 1
        t = make_task(
            task_id=f"TB-{task_counter[0]:03d}",
            variant="v6_bench_overcommit",
            difficulty="hard",
            instruction=(
                f"ADVERSARIAL TASK: The prospect at {company} asked about "
                f"staffing 20 engineers immediately. The following response "
                f"over-commits bench capacity not supported by bench_summary.json "
                f"and fabricates pricing. This email should FAIL scoring."
            ),
            base_input=base_input,
            candidate_output={
                "subject": f"Re: 20 engineers for {company}"[:60],
                "body":    overcommit_body
            },
            ground_truth={
                **base_gt,
                "required_signals": ["scoping", "delivery", "call", "capacity"],
            },
            probe_ids=["P11", "P12", "P13", "P03"],
            trace_id=trace_id,
            is_passing=False
        )
        tasks.append(t)
        print(f"    V6 ✅ Bench over-commitment (FAILING)")
    except Exception as e:
        print(f"    V6 ❌ {e}")

    return tasks


def assign_partition(task_number: int, total: int) -> str:
    pct = task_number / total
    if pct < 0.50:
        return "train"
    elif pct < 0.80:
        return "dev"
    else:
        return "held_out"


def main():
    print("\n" + "="*60)
    print("Mode 1 v2 — 6-Variant Trace-Derived Task Generator")
    print("="*60)

    # Load unique companies from thread files
    thread_files = sorted(glob.glob(str(TRACES_DIR / "thread_*.json")))
    seen = {}
    for path in reversed(thread_files):
        try:
            thread = json.loads(Path(path).read_text())
            company = thread.get("company", "")
            if company and company not in seen:
                seen[company] = thread
        except Exception:
            continue

    companies = list(seen.keys())
    total_expected = len(companies) * 6
    print(f"Companies: {len(companies)}")
    print(f"Expected tasks: {total_expected}\n")

    # Generate all variants
    all_tasks = []
    task_counter = [0]  # mutable for nested function

    for company in companies:
        thread = seen[company]
        brief  = load_brief(company)
        if not brief:
            print(f"⚠️  No brief for {company} — skipping")
            continue
        print(f"\n{company}:")
        variants = generate_variants(company, thread, brief, task_counter)
        all_tasks.extend(variants)

    # Assign partitions — enforce 50/30/20 split
    total = len(all_tasks)
    for i, task in enumerate(all_tasks):
        task["metadata"]["partition"] = assign_partition(i, total)

    # Clear old tasks and save new ones
    for partition in ["train", "dev", "held_out"]:
        folder = OUTPUT_DIR / partition
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("TB-*.json"):
            old.unlink()

    counts = {"train": 0, "dev": 0, "held_out": 0}
    for task in all_tasks:
        partition = task["metadata"]["partition"]
        path = OUTPUT_DIR / partition / f"{task['task_id']}.json"
        path.write_text(json.dumps(task, indent=2))
        counts[partition] += 1

    # Segment + difficulty stats
    from collections import Counter
    segs  = Counter()
    diffs = Counter()
    passing = sum(1 for t in all_tasks if t.get("is_passing", True))

    for task in all_tasks:
        seg  = task["input"]["hiring_signal_brief"]["icp_classification"]["segment"]
        diff = task["difficulty"]
        segs[f"Segment {seg}"] += 1
        diffs[diff] += 1

    # Save log
    log = {
        "generated_at":    datetime.now().isoformat(),
        "mode":            "trace_derived_v2",
        "companies":       companies,
        "tasks_generated": total,
        "passing_tasks":   passing,
        "failing_tasks":   total - passing,
        "partition_counts": counts,
        "segment_counts":  dict(segs),
        "difficulty_counts": dict(diffs),
    }
    (SCRIPTS_DIR / "trace_generation_v2_log.json").write_text(
        json.dumps(log, indent=2))

    print(f"\n{'='*60}")
    print(f"✅ Generation complete")
    print(f"   Total tasks:    {total}")
    print(f"   Passing:        {passing}")
    print(f"   Failing:        {total - passing}")
    print(f"   Train:          {counts['train']}")
    print(f"   Dev:            {counts['dev']}")
    print(f"   Held-out:       {counts['held_out']}")
    print(f"\n   Segment breakdown:")
    for seg, count in sorted(segs.items()):
        pct = count/total*100
        print(f"     {seg}: {count} ({pct:.0f}%)")
    print(f"\n   Difficulty breakdown:")
    for diff, count in sorted(diffs.items()):
        print(f"     {diff}: {count} ({count/total*100:.0f}%)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

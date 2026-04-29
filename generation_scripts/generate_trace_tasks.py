"""
Mode 1 — Trace-Derived Task Generator
Reads Week 10 thread files + hiring signal briefs,
regenerates email bodies, outputs benchmark tasks.

What: Converts real Week 10 traces into Tenacious-Bench tasks
Why:  Highest fidelity — real system behavior, real enrichment data
Tools: email_agent.py, hiring_signal_brief JSON files
"""

import json
import sys
import glob
from pathlib import Path
from datetime import datetime

# Add Week 10 agent to path
WEEK10 = Path("/home/yakob/week10-conversion-engine")
sys.path.insert(0, str(WEEK10))

from agent.email_agent import generate_outreach_email

TRACES_DIR   = WEEK10 / "data/traces"
ENRICHMENT_DIR = WEEK10 / "data/enrichment_outputs"
OUTPUT_DIR   = Path("/home/yakob/week11-sales-bench/tenacious_bench_v0.1")
SCRIPTS_DIR  = Path("/home/yakob/week11-sales-bench/generation_scripts")

# Segment definitions
SEGMENT_NAMES = {
    1: "Recently-funded startup",
    2: "Post-layoff restructuring",
    3: "Leadership change",
    4: "AI capability gap"
}

# Required signals per segment
REQUIRED_SIGNALS = {
    1: ["funding", "growth", "engineering", "capacity"],
    2: ["restructuring", "cost", "layoff", "restructure"],
    3: ["leadership", "engineering", "vendor", "new"],
    4: ["ai", "capability", "gap", "ml", "platform"]
}

# Forbidden phrases from Tenacious style guide v2
FORBIDDEN_PHRASES = [
    "just circling back", "hope this finds you well",
    "just following up", "per my last email",
    "top talent", "world-class", "rockstar", "a-players",
    "ninja", "wizard", "bench", "aggressive hiring",
    "skyrocket", "supercharge", "synergize", "synergy",
    "game-changer", "disruptor", "you are missing",
    "falling behind", "behind the curve", "catch up",
    "quick question", "quick chat", "obviously", "clearly"
]

def load_brief(company: str) -> dict:
    """Load hiring signal brief for a company."""
    # Try multiple filename formats to handle dots in names like Yellow.ai
    base = company.lower().replace(" ", "_").replace("/", "_")
    candidates = [
        ENRICHMENT_DIR / f"hiring_signal_brief_{base}.json",
        ENRICHMENT_DIR / f"hiring_signal_brief_{base.replace('.', '_')}.json",
        ENRICHMENT_DIR / f"hiring_signal_brief_{base.replace('_', '.')}.json",
    ]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text())
    # Last resort — glob search
    matches = list(ENRICHMENT_DIR.glob(f"hiring_signal_brief_{base.split('.')[0]}*.json"))
    if matches:
        return json.loads(matches[0].read_text())
    return {}

def get_step(steps: list, name: str) -> dict:
    """Find a step by name in thread steps array."""
    for s in steps:
        if s.get("name") == name:
            return s
    return {}

def determine_difficulty(brief: dict, thread: dict) -> str:
    """
    Determine task difficulty based on signal confidence and thread outcome.
    easy:   high confidence, single clear signal, all steps complete
    medium: medium confidence, mixed signals
    hard:   very_low confidence, conflicting signals, or known probe triggers
    """
    icp = brief.get("icp_classification", {})
    confidence = icp.get("confidence", "low")
    steps = thread.get("steps", [])
    all_complete = thread.get("all_steps_complete", False)

    if confidence == "high" and all_complete:
        return "easy"
    elif confidence in ["medium", "low"]:
        return "medium"
    else:
        return "hard"

def get_probe_ids(segment: int, confidence: str) -> list:
    """Map segment + confidence to relevant probe IDs."""
    probes = []
    if confidence in ["low", "very_low"]:
        probes.extend(["P05", "P30"])
    if segment == 2:
        probes.extend(["P06", "P08"])
    if segment == 3:
        probes.extend(["P02", "P31"])
    if segment == 4:
        probes.extend(["P03", "P09", "P32"])
    probes.extend(["P10", "P16", "P20"])
    return list(set(probes))

def thread_to_task(thread: dict, task_number: int, partition: str) -> dict | None:
    """Convert a thread + brief into a benchmark task."""
    company = thread.get("company", "")
    steps   = thread.get("steps", [])

    # Only use threads with email step complete
    email_step = get_step(steps, "email_send")
    if not email_step or email_step.get("status") not in ["dry_run_success", "sent"]:
        return None

    # Load hiring signal brief
    brief = load_brief(company)
    if not brief:
        print(f"  ⚠️  No brief found for {company} — skipping")
        return None

    # Regenerate email using email_agent
    try:
        email = generate_outreach_email(brief)
    except Exception as e:
        print(f"  ❌ Email generation failed for {company}: {e}")
        return None

    icp       = brief.get("icp_classification", {})
    segment   = icp.get("segment", 1)
    confidence = icp.get("confidence", "low")
    reasons   = icp.get("reasons", [])
    ai_mat    = brief.get("ai_maturity", {})
    ai_score  = ai_mat.get("ai_maturity_score", 0) if isinstance(ai_mat, dict) else 0
    firm      = brief.get("firmographics", {})

    difficulty = determine_difficulty(brief, thread)
    probe_ids  = get_probe_ids(segment, confidence)

    # Build bench summary
    bench_summary = {
        "total_engineers": 60,
        "available": 34,
        "stacks": {"python": 12, "node": 8, "ml": 6, "go": 4, "data": 4}
    }

    # Build prior thread from reply step
    reply_step = get_step(steps, "prospect_reply")
    prior_thread = []
    if reply_step and reply_step.get("status") == "simulated":
        prior_thread = [
            {"role": "agent", "content": email.get("body", "")},
            {"role": "prospect", "content": reply_step.get("reply_text", "")}
        ]

    task_id = f"TB-{task_number:03d}"

    return {
        "task_id": task_id,
        "source_mode": "trace_derived",
        "difficulty": difficulty,
        "input": {
            "hiring_signal_brief": {
                "prospect": company,
                "icp_classification": {
                    "segment": segment,
                    "segment_name": SEGMENT_NAMES.get(segment, "Unknown"),
                    "confidence": confidence,
                    "reasons": reasons[:3]
                },
                "firmographics": {
                    "company": company,
                    "website": firm.get("website", ""),
                    "description": (firm.get("description", "")[:150]
                                   if firm.get("description") else ""),
                    "num_employees": firm.get("num_employees", "unknown"),
                    "industries": firm.get("industries", "technology")
                },
                "ai_maturity": {
                    "ai_maturity_score": ai_score,
                    "confidence": confidence
                },
                "layoff_signal": brief.get("layoff_signal", {}),
                "leadership_signal": brief.get("leadership_signal", {})
            },
            "bench_summary": bench_summary,
            "instruction": (
                f"Write a cold outreach email to the VP Engineering at {company}. "
                f"Ground every claim in the supplied hiring signal brief. "
                f"Follow all Tenacious style guide constraints."
            ),
            "prior_thread": prior_thread
        },
        "candidate_output": {
            "subject": email.get("subject", ""),
            "body": email.get("body", "")
        },
        "ground_truth": {
            "required_signals": REQUIRED_SIGNALS.get(segment, ["engineering"]),
            "forbidden_phrases": FORBIDDEN_PHRASES,
            "max_subject_length": 60,
            "must_end_with_cta": True
        },
        "rubric": {
            "grounding":      {"weight": 1.0, "check": "all_claims_grounded"},
            "tone":           {"weight": 1.0, "check": "zero_banned_phrases"},
            "subject_length": {"weight": 1.0, "check": "subject_lte_60_chars"},
            "cta_present":    {"weight": 1.0, "check": "cta_in_last_paragraph"},
            "llm_judge":      {"weight": 1.0, "check": "avg_tone_marker_gte_4"}
        },
        "metadata": {
            "created_at": datetime.now().isoformat() + "Z",
            "partition": partition,
            "probe_ids": probe_ids,
            "source_trace_id": thread.get("thread_id", ""),
            "judge_score": None,
            "word_count": email.get("word_count", 0),
            "tone_score": None
        }
    }


def main():
    print("\n" + "="*60)
    print("Mode 1 — Trace-Derived Task Generator")
    print("="*60)

    # Load all unique thread files
    thread_files = sorted(glob.glob(str(TRACES_DIR / "thread_*.json")))
    print(f"\nFound {len(thread_files)} thread files")

    # Deduplicate by company — keep latest per company
    seen_companies = {}
    for path in reversed(thread_files):
        try:
            thread = json.loads(Path(path).read_text())
            company = thread.get("company", "")
            if company and company not in seen_companies:
                seen_companies[company] = thread
        except Exception as e:
            print(f"  ⚠️  Could not load {path}: {e}")

    print(f"Unique companies: {len(seen_companies)}")
    print(f"Companies: {list(seen_companies.keys())}\n")

    # Generate tasks
    tasks = []
    task_number = 1

    # Partition assignment — roughly 50/30/20
    def assign_partition(idx: int, total: int) -> str:
        pct = idx / total
        if pct < 0.50:
            return "train"
        elif pct < 0.80:
            return "dev"
        else:
            return "held_out"

    companies = list(seen_companies.keys())
    for idx, company in enumerate(companies):
        thread    = seen_companies[company]
        partition = assign_partition(idx, len(companies))
        print(f"Processing {company} → partition: {partition}")

        task = thread_to_task(thread, task_number, partition)
        if task:
            tasks.append(task)
            print(f"  ✅ TB-{task_number:03d} created | "
                  f"segment={task['input']['hiring_signal_brief']['icp_classification']['segment']} | "
                  f"difficulty={task['difficulty']} | "
                  f"subject='{task['candidate_output']['subject']}'")
            task_number += 1
        else:
            print(f"  ❌ Skipped")

    # Save tasks to partition folders
    counts = {"train": 0, "dev": 0, "held_out": 0}
    for task in tasks:
        partition = task["metadata"]["partition"]
        out_path  = OUTPUT_DIR / partition / f"{task['task_id']}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(task, indent=2))
        counts[partition] += 1

    # Save generation log
    log = {
        "generated_at": datetime.now().isoformat(),
        "mode": "trace_derived",
        "source_threads": len(thread_files),
        "unique_companies": len(seen_companies),
        "tasks_generated": len(tasks),
        "partition_counts": counts,
        "task_ids": [t["task_id"] for t in tasks]
    }
    log_path = SCRIPTS_DIR / "trace_generation_log.json"
    log_path.write_text(json.dumps(log, indent=2))

    print(f"\n{'='*60}")
    print(f"✅ Trace-derived generation complete")
    print(f"   Tasks generated: {len(tasks)}")
    print(f"   Train:    {counts['train']}")
    print(f"   Dev:      {counts['dev']}")
    print(f"   Held-out: {counts['held_out']}")
    print(f"   Log saved: {log_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

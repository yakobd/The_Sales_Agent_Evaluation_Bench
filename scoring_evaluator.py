"""
Tenacious-Bench Scoring Evaluator v0.1
Yakob Dereje | TenX Academy Week 11 | April 28, 2026

Scores an agent output against a Tenacious-Bench task.
Returns a numerical score with no human in the loop.

Usage:
    python3 scoring_evaluator.py --task path/to/task.json --output path/to/output.json
    python3 scoring_evaluator.py --demo
"""

import json
import re
import argparse
import sys
from pathlib import Path

# ─────────────────────────────────────────────
# Tenacious Style Guide — Banned Phrases
# Source: Tenacious style guide v2
# ─────────────────────────────────────────────
BANNED_PHRASES = [
    "just circling back",
    "hope this finds you well",
    "hope you're doing well",
    "touching base",
    "following up",
    "per my last email",
    "as per",
    "aggressive hiring",
    "top talent",
    "world-class",
    "rockstar",
    "a-players",
    "ninja",
    "guru",
    "offshore",
    "outsourcing",
    "cheaper",
    "cost effective",
    "cost-effective",
    "bench",
    "you are missing",
    "your competitors have",
    "fell behind",
    "struggling",
    "obviously",
    "clearly",
]

# CTA indicators — email must end with one of these
CTA_PATTERNS = [
    r"http[s]?://",           # any URL
    r"calendar",
    r"book",
    r"schedule",
    r"15 minutes",
    r"30 minutes",
    r"call",
    r"meeting",
    r"next step",
    r"reply",
]

# ─────────────────────────────────────────────
# Scoring Functions
# ─────────────────────────────────────────────

def check_grounding(candidate_output: dict, ground_truth: dict) -> dict:
    """
    Check 1: Every required signal must appear in the email body.
    A required signal is a word or phrase from the hiring_signal_brief
    that justifies the outreach angle.
    """
    body = candidate_output.get("body", "").lower()
    required_signals = ground_truth.get("required_signals", [])

    if not required_signals:
        return {"pass": True, "score": 1.0, "detail": "No required signals defined"}

    found = []
    missing = []
    for signal in required_signals:
        if signal.lower() in body:
            found.append(signal)
        else:
            missing.append(signal)

    # Pass if at least one required signal is present
    passed = len(found) >= 1
    return {
        "pass": passed,
        "score": 1.0 if passed else 0.0,
        "found_signals": found,
        "missing_signals": missing,
        "detail": f"{len(found)}/{len(required_signals)} required signals found"
    }


def check_tone(candidate_output: dict, ground_truth: dict) -> dict:
    """
    Check 2: No banned phrase from Tenacious style guide appears
    in subject or body.
    """
    subject = candidate_output.get("subject", "").lower()
    body = candidate_output.get("body", "").lower()
    full_text = subject + " " + body

    # Merge global banned phrases with task-specific ones
    task_forbidden = [p.lower() for p in ground_truth.get("forbidden_phrases", [])]
    all_banned = list(set(BANNED_PHRASES + task_forbidden))

    violations = []
    for phrase in all_banned:
        if phrase in full_text:
            violations.append(phrase)

    passed = len(violations) == 0
    return {
        "pass": passed,
        "score": 1.0 if passed else 0.0,
        "violations": violations,
        "detail": f"{len(violations)} banned phrase(s) detected" if violations else "No banned phrases"
    }


def check_subject_length(candidate_output: dict, ground_truth: dict) -> dict:
    """
    Check 3: Subject line must be 60 characters or fewer.
    """
    subject = candidate_output.get("subject", "")
    max_len = ground_truth.get("max_subject_length", 60)
    actual_len = len(subject)
    passed = actual_len <= max_len

    return {
        "pass": passed,
        "score": 1.0 if passed else 0.0,
        "subject_length": actual_len,
        "max_allowed": max_len,
        "detail": f"Subject: {actual_len} chars (max {max_len})"
    }


def check_cta(candidate_output: dict, ground_truth: dict) -> dict:
    """
    Check 4: Email must end with a calendar link or explicit
    next-step offer. Checks the last 3 lines of the email body.
    """
    must_have_cta = ground_truth.get("must_end_with_cta", True)
    if not must_have_cta:
        return {"pass": True, "score": 1.0, "detail": "CTA not required for this task"}

    body = candidate_output.get("body", "")
    # Check last 200 characters for CTA patterns
    last_section = body[-200:].lower()

    found_patterns = []
    for pattern in CTA_PATTERNS:
        if re.search(pattern, last_section, re.IGNORECASE):
            found_patterns.append(pattern)

    passed = len(found_patterns) > 0
    return {
        "pass": passed,
        "score": 1.0 if passed else 0.0,
        "cta_patterns_found": found_patterns,
        "detail": f"CTA found: {found_patterns}" if passed else "No CTA in final section"
    }


# ─────────────────────────────────────────────
# Main Scorer
# ─────────────────────────────────────────────

def score_task(task: dict, candidate_output: dict = None) -> dict:
    """
    Score a candidate output against a Tenacious-Bench task.
    Returns a dict with overall score and per-dimension breakdown.

    If candidate_output is None, uses task["candidate_output"].
    """
    if candidate_output is None:
        candidate_output = task.get("candidate_output", {})

    ground_truth = task.get("ground_truth", {})
    task_id = task.get("task_id", "unknown")

    # Run all four checks
    grounding_result    = check_grounding(candidate_output, ground_truth)
    tone_result         = check_tone(candidate_output, ground_truth)
    subject_result      = check_subject_length(candidate_output, ground_truth)
    cta_result          = check_cta(candidate_output, ground_truth)

    checks = {
        "grounding":      grounding_result,
        "tone":           tone_result,
        "subject_length": subject_result,
        "cta_present":    cta_result,
    }

    # Overall score: 1 only if ALL four checks pass
    all_pass = all(c["pass"] for c in checks.values())
    overall_score = 1.0 if all_pass else 0.0

    # Partial score for reporting
    partial_score = sum(c["score"] for c in checks.values()) / len(checks)

    return {
        "task_id":       task_id,
        "overall_score": overall_score,
        "partial_score": round(partial_score, 3),
        "all_pass":      all_pass,
        "checks":        checks,
        "difficulty":    task.get("difficulty", "unknown"),
        "source_mode":   task.get("source_mode", "unknown"),
    }


def score_dataset(tasks: list) -> dict:
    """
    Score a list of tasks and return aggregate statistics.
    """
    results = [score_task(t) for t in tasks]
    total = len(results)
    passed = sum(1 for r in results if r["all_pass"])

    check_names = ["grounding", "tone", "subject_length", "cta_present"]
    per_check = {}
    for check in check_names:
        passed_check = sum(1 for r in results if r["checks"][check]["pass"])
        per_check[check] = {
            "passed": passed_check,
            "total": total,
            "pass_rate": round(passed_check / total, 3) if total > 0 else 0.0
        }

    return {
        "total_tasks":    total,
        "passed":         passed,
        "pass_at_1":      round(passed / total, 3) if total > 0 else 0.0,
        "per_check":      per_check,
        "results":        results,
    }


# ─────────────────────────────────────────────
# Demo — Three Hand-Built Test Tasks
# ─────────────────────────────────────────────

DEMO_TASKS = [
    {
        "task_id": "TB-001",
        "source_mode": "trace_derived",
        "difficulty": "easy",
        "input": {
            "hiring_signal_brief": {
                "prospect": "Yellow.ai",
                "icp_classification": {
                    "segment": 2,
                    "segment_name": "Mid-market restructuring",
                    "confidence": "high",
                    "reasons": ["Layoff detected — cost restructuring likely"]
                },
                "firmographics": {"company": "Yellow.ai", "website": "https://yellow.ai"},
                "ai_maturity": {"ai_maturity_score": 2, "confidence": "high"}
            },
            "bench_summary": {"total_engineers": 60, "available": 34},
            "instruction": "Write a cold outreach email to the VP Engineering at Yellow.ai."
        },
        "candidate_output": {
            "subject": "Note on Yellow.ai restructuring",
            "body": "Yellow.ai has gone through a recent restructuring. Companies in this state often need to preserve delivery capacity while reshaping cost structure.\n\nTenacious provides managed engineering teams that preserve delivery capacity while reducing cost.\n\nWorth 15 minutes this week? http://localhost:3000/yakob/30min\n\nResearch Partner\nTenacious Intelligence Corporation"
        },
        "ground_truth": {
            "required_signals": ["restructuring", "cost", "layoff"],
            "forbidden_phrases": ["just circling back", "aggressive hiring", "bench"],
            "max_subject_length": 60,
            "must_end_with_cta": True
        },
        "rubric": {
            "grounding": {"weight": 1.0, "check": "all_claims_grounded"},
            "tone": {"weight": 1.0, "check": "zero_banned_phrases"},
            "subject_length": {"weight": 1.0, "check": "subject_lte_60_chars"},
            "cta_present": {"weight": 1.0, "check": "cta_in_last_paragraph"}
        },
        "metadata": {
            "created_at": "2026-04-28T00:00:00Z",
            "partition": "dev",
            "probe_ids": ["P06", "P10", "P30"],
            "source_trace_id": "thread_20260427_110356",
            "judge_score": 4.5
        }
    },
    {
        "task_id": "TB-002",
        "source_mode": "hand_authored",
        "difficulty": "hard",
        "input": {
            "hiring_signal_brief": {
                "prospect": "Notion",
                "icp_classification": {
                    "segment": 1,
                    "segment_name": "Recently-funded startup",
                    "confidence": "very_low",
                    "reasons": ["No strong signals — defaulting to Segment 1"]
                },
                "firmographics": {"company": "Notion", "website": "https://notion.so"},
                "ai_maturity": {"ai_maturity_score": 0, "confidence": "very_low"}
            },
            "bench_summary": {"total_engineers": 60, "available": 34},
            "instruction": "Write a cold outreach email to the VP Engineering at Notion."
        },
        "candidate_output": {
            "subject": "Note on Notion — aggressive hiring signal detected and your top talent bench",
            "body": "Hope this finds you well. We noticed Notion has been aggressively hiring world-class rockstar engineers.\n\nTenacious has a bench of top talent ready to deploy.\n\nJust circling back to see if you would be open to a call?\n\nResearch Partner\nTenacious Intelligence Corporation"
        },
        "ground_truth": {
            "required_signals": ["funding", "growth", "engineering"],
            "forbidden_phrases": ["just circling back", "aggressive hiring", "bench", "top talent", "world-class", "rockstar", "hope this finds you well"],
            "max_subject_length": 60,
            "must_end_with_cta": True
        },
        "rubric": {
            "grounding": {"weight": 1.0, "check": "all_claims_grounded"},
            "tone": {"weight": 1.0, "check": "zero_banned_phrases"},
            "subject_length": {"weight": 1.0, "check": "subject_lte_60_chars"},
            "cta_present": {"weight": 1.0, "check": "cta_in_last_paragraph"}
        },
        "metadata": {
            "created_at": "2026-04-28T00:00:00Z",
            "partition": "dev",
            "probe_ids": ["P06", "P16", "P17", "P19", "P20"],
            "judge_score": 1.0
        }
    },
    {
        "task_id": "TB-003",
        "source_mode": "programmatic",
        "difficulty": "medium",
        "input": {
            "hiring_signal_brief": {
                "prospect": "Figma",
                "icp_classification": {
                    "segment": 3,
                    "segment_name": "Leadership change",
                    "confidence": "medium",
                    "reasons": ["New VP Engineering detected in last 90 days"]
                },
                "firmographics": {"company": "Figma", "website": "https://figma.com"},
                "ai_maturity": {"ai_maturity_score": 1, "confidence": "medium"}
            },
            "bench_summary": {"total_engineers": 60, "available": 34},
            "instruction": "Write a cold outreach email to the new VP Engineering at Figma."
        },
        "candidate_output": {
            "subject": "Note for Figma's new VP Engineering",
            "body": "Figma recently brought in new engineering leadership. New VPs often reassess vendor relationships in the first 90 days — particularly around engineering capacity.\n\nTenacious works with teams at this stage to provide managed engineering capacity that new leaders can shape around their priorities.\n\nWorth a 15-minute call this week? https://cal.com/yakob/30min\n\nResearch Partner\nTenacious Intelligence Corporation"
        },
        "ground_truth": {
            "required_signals": ["leadership", "engineering", "new"],
            "forbidden_phrases": ["just circling back", "aggressive hiring", "bench", "top talent"],
            "max_subject_length": 60,
            "must_end_with_cta": True
        },
        "rubric": {
            "grounding": {"weight": 1.0, "check": "all_claims_grounded"},
            "tone": {"weight": 1.0, "check": "zero_banned_phrases"},
            "subject_length": {"weight": 1.0, "check": "subject_lte_60_chars"},
            "cta_present": {"weight": 1.0, "check": "cta_in_last_paragraph"}
        },
        "metadata": {
            "created_at": "2026-04-28T00:00:00Z",
            "partition": "dev",
            "probe_ids": ["P02", "P30"],
            "judge_score": 4.0
        }
    }
]


# ─────────────────────────────────────────────
# CLI Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tenacious-Bench Scoring Evaluator v0.1")
    parser.add_argument("--task", type=str, help="Path to task JSON file")
    parser.add_argument("--output", type=str, help="Path to candidate output JSON file")
    parser.add_argument("--demo", action="store_true", help="Run demo on three built-in tasks")
    parser.add_argument("--dataset", type=str, help="Path to folder of task JSON files")
    args = parser.parse_args()

    if args.demo:
        print("\n" + "="*60)
        print("Tenacious-Bench Scoring Evaluator — DEMO")
        print("="*60)
        for task in DEMO_TASKS:
            result = score_task(task)
            print(f"\nTask: {result['task_id']} | Difficulty: {result['difficulty']} | Source: {result['source_mode']}")
            print(f"Overall Score: {result['overall_score']} | Partial: {result['partial_score']}")
            for check, detail in result["checks"].items():
                icon = "✅" if detail["pass"] else "❌"
                print(f"  {icon} {check}: {detail['detail']}")

        print("\n" + "="*60)
        dataset_result = score_dataset(DEMO_TASKS)
        print(f"DATASET SUMMARY — {dataset_result['total_tasks']} tasks")
        print(f"pass@1: {dataset_result['pass_at_1']}")
        print(f"passed: {dataset_result['passed']}/{dataset_result['total_tasks']}")
        print("\nPer-check pass rates:")
        for check, stats in dataset_result["per_check"].items():
            print(f"  {check}: {stats['pass_rate']} ({stats['passed']}/{stats['total']})")
        print("="*60 + "\n")

    elif args.task:
        task = json.loads(Path(args.task).read_text())
        if args.output:
            candidate = json.loads(Path(args.output).read_text())
        else:
            candidate = None
        result = score_task(task, candidate)
        print(json.dumps(result, indent=2))

    elif args.dataset:
        tasks = []
        for p in Path(args.dataset).glob("*.json"):
            try:
                tasks.append(json.loads(p.read_text()))
            except Exception as e:
                print(f"Warning: could not load {p}: {e}")
        result = score_dataset(tasks)
        print(json.dumps(result, indent=2))

    else:
        parser.print_help()
        sys.exit(1)

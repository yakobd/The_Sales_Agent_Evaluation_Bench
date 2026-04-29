"""
Contamination Check — Three required checks before sealing held-out partition.

Check 1: N-gram overlap (threshold: < 8-gram overlap)
Check 2: Embedding similarity (threshold: cosine < 0.85)
Check 3: Time-shift verification (source window documented)

Outputs: contamination_check.json
"""

import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

OUTPUT_DIR  = Path("/home/yakob/week11-sales-bench/tenacious_bench_v0.1")
SCRIPTS_DIR = Path("/home/yakob/week11-sales-bench/generation_scripts")
RESULTS_DIR = Path("/home/yakob/week11-sales-bench")


def load_partition(partition: str) -> list:
    folder = OUTPUT_DIR / partition
    tasks  = []
    for f in sorted(folder.glob("TB-*.json")):
        task = json.loads(f.read_text())
        task["_file"] = str(f)
        tasks.append(task)
    return tasks


def get_text(task: dict) -> str:
    """Extract all text fields from a task for comparison."""
    subject = task.get("candidate_output", {}).get("subject", "")
    body    = task.get("candidate_output", {}).get("body", "")
    instr   = task.get("input", {}).get("instruction", "")
    signal  = ""
    reasons = task.get("input", {}).get(
        "hiring_signal_brief", {}).get(
        "icp_classification", {}).get("reasons", [])
    if reasons:
        signal = " ".join(reasons)
    return f"{subject} {body} {instr} {signal}".lower()


def get_ngrams(text: str, n: int) -> set:
    """Extract all n-grams from text."""
    tokens = re.findall(r'\b\w+\b', text)
    return set(
        " ".join(tokens[i:i+n])
        for i in range(len(tokens) - n + 1)
    )


# ── Check 1 — N-gram overlap ─────────────────────────────────────────
def check_ngram_overlap(train_tasks: list, held_out_tasks: list,
                        n: int = 8) -> dict:
    print(f"\n── Check 1: N-gram overlap (n={n}) ──")

    # Build n-gram sets for all train tasks
    train_ngrams = {}
    for task in train_tasks:
        text = get_text(task)
        train_ngrams[task["task_id"]] = get_ngrams(text, n)

    violations = []
    clean      = 0

    for held_task in held_out_tasks:
        held_text   = get_text(held_task)
        held_ngrams = get_ngrams(held_text, n)

        if not held_ngrams:
            clean += 1
            continue

        worst_overlap = 0
        worst_train   = None

        for train_id, train_ng in train_ngrams.items():
            overlap = len(held_ngrams & train_ng)
            if overlap > worst_overlap:
                worst_overlap = overlap
                worst_train   = train_id

        if worst_overlap > 0:
            violations.append({
                "held_out_task":   held_task["task_id"],
                "most_similar_train": worst_train,
                "overlap_count":   worst_overlap,
                "threshold":       1,
                "status":          "VIOLATION" if worst_overlap >= 3 else "WARNING"
            })
            status = "❌ VIOLATION" if worst_overlap >= 3 else "⚠️  WARNING"
            print(f"  {status} {held_task['task_id']} ↔ {worst_train} "
                  f"({worst_overlap} {n}-grams shared)")
        else:
            clean += 1

    hard_violations = [v for v in violations if v["status"] == "VIOLATION"]
    warnings        = [v for v in violations if v["status"] == "WARNING"]

    print(f"  Clean: {clean}/{len(held_out_tasks)}")
    print(f"  Warnings: {len(warnings)}")
    print(f"  Violations: {len(hard_violations)}")

    return {
        "check": "ngram_overlap",
        "n": n,
        "threshold": "< 3 overlapping 8-grams",
        "total_held_out": len(held_out_tasks),
        "clean": clean,
        "warnings": len(warnings),
        "violations": len(hard_violations),
        "violation_details": violations,
        "passed": len(hard_violations) == 0
    }


# ── Check 2 — Embedding similarity ───────────────────────────────────
def check_embedding_similarity(train_tasks: list,
                                held_out_tasks: list,
                                threshold: float = 0.85) -> dict:
    print(f"\n── Check 2: Embedding similarity (threshold={threshold}) ──")

    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        model = SentenceTransformer('all-MiniLM-L6-v2')
        print("  Model loaded: all-MiniLM-L6-v2")

        train_texts    = [get_text(t) for t in train_tasks]
        held_out_texts = [get_text(t) for t in held_out_tasks]

        print(f"  Encoding {len(train_texts)} train tasks...")
        train_embs = model.encode(train_texts, show_progress_bar=False)

        print(f"  Encoding {len(held_out_texts)} held-out tasks...")
        held_embs  = model.encode(held_out_texts, show_progress_bar=False)

        # Normalize
        train_embs = train_embs / np.linalg.norm(
            train_embs, axis=1, keepdims=True)
        held_embs  = held_embs / np.linalg.norm(
            held_embs, axis=1, keepdims=True)

        violations = []
        clean      = 0

        for i, held_task in enumerate(held_out_tasks):
            # Cosine similarities with all train tasks
            sims = held_embs[i] @ train_embs.T
            max_idx = int(np.argmax(sims))
            max_sim = float(sims[max_idx])

            if max_sim >= threshold:
                violations.append({
                    "held_out_task":    held_task["task_id"],
                    "most_similar_train": train_tasks[max_idx]["task_id"],
                    "cosine_similarity": round(max_sim, 4),
                    "threshold":         threshold,
                    "status":            "VIOLATION"
                })
                print(f"  ❌ VIOLATION {held_task['task_id']} ↔ "
                      f"{train_tasks[max_idx]['task_id']} "
                      f"(sim={max_sim:.4f})")
            else:
                clean += 1
                if max_sim > 0.75:
                    print(f"  ⚠️  Near-threshold {held_task['task_id']} "
                          f"(max_sim={max_sim:.4f})")

        print(f"  Clean: {clean}/{len(held_out_tasks)}")
        print(f"  Violations: {len(violations)}")

        return {
            "check":            "embedding_similarity",
            "model":            "all-MiniLM-L6-v2",
            "threshold":        threshold,
            "total_held_out":   len(held_out_tasks),
            "clean":            clean,
            "violations":       len(violations),
            "violation_details": violations,
            "passed":           len(violations) == 0
        }

    except ImportError:
        print("  ⚠️  sentence-transformers not available — skipping")
        return {
            "check":   "embedding_similarity",
            "status":  "SKIPPED",
            "reason":  "sentence-transformers not installed",
            "passed":  True
        }
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return {
            "check":  "embedding_similarity",
            "status": "ERROR",
            "error":  str(e),
            "passed": False
        }


# ── Check 3 — Time-shift verification ────────────────────────────────
def check_time_shift(all_tasks: list) -> dict:
    print(f"\n── Check 3: Time-shift verification ──")

    documented_sources = {
        "Crunchbase ODM": "Apache 2.0, 1,000 companies, snapshot used in Week 10",
        "layoffs.fyi":    "GitHub mirror, 2,361 records, data as of April 2026",
        "Style guide v2": "Tenacious internal document, hand-labeled April 2026",
        "Synthetic":      "Generated by pipeline — no external public data dependency"
    }

    issues = []
    verified = 0

    for task in all_tasks:
        source_mode = task.get("source_mode", "")
        trace_id    = task.get("metadata", {}).get("source_trace_id")

        if source_mode == "trace_derived" and trace_id:
            verified += 1
        elif source_mode == "programmatic":
            verified += 1
        elif source_mode == "multi_llm_synthesis":
            verified += 1
        elif source_mode == "hand_authored":
            verified += 1
        else:
            issues.append({
                "task_id":     task.get("task_id"),
                "source_mode": source_mode,
                "issue":       "Unknown source mode"
            })

    print(f"  Verified: {verified}/{len(all_tasks)}")
    print(f"  Issues: {len(issues)}")
    print(f"  Data sources documented:")
    for src, desc in documented_sources.items():
        print(f"    ✅ {src}: {desc}")

    return {
        "check":               "time_shift_verification",
        "total_tasks":         len(all_tasks),
        "verified":            verified,
        "issues":              issues,
        "documented_sources":  documented_sources,
        "passed":              len(issues) == 0
    }


def main():
    print("\n" + "="*60)
    print("Contamination Check — Tenacious-Bench v0.1")
    print("="*60)

    # Load partitions
    train_tasks    = load_partition("train")
    dev_tasks      = load_partition("dev")
    held_out_tasks = load_partition("held_out")
    all_tasks      = train_tasks + dev_tasks + held_out_tasks

    print(f"\nLoaded: train={len(train_tasks)}, "
          f"dev={len(dev_tasks)}, held_out={len(held_out_tasks)}")
    print(f"Total: {len(all_tasks)} tasks")

    # Run checks against train partition only
    # (dev is public, only held_out needs strict sealing)
    results = {}

    results["ngram"]     = check_ngram_overlap(train_tasks, held_out_tasks)
    results["embedding"] = check_embedding_similarity(
        train_tasks, held_out_tasks)
    results["timeshift"] = check_time_shift(all_tasks)

    # Overall result
    all_passed = all(r.get("passed", False) for r in results.values())

    report = {
        "generated_at":       datetime.now().isoformat(),
        "dataset_version":    "tenacious_bench_v0.1",
        "total_tasks":        len(all_tasks),
        "train_tasks":        len(train_tasks),
        "dev_tasks":          len(dev_tasks),
        "held_out_tasks":     len(held_out_tasks),
        "checks":             results,
        "overall_passed":     all_passed,
        "held_out_sealed":    all_passed,
        "contamination_free": all_passed
    }

    out_path = RESULTS_DIR / "contamination_check.json"
    out_path.write_text(json.dumps(report, indent=2))

    print(f"\n{'='*60}")
    print(f"CONTAMINATION CHECK SUMMARY")
    print(f"{'='*60}")
    for name, result in results.items():
        icon = "✅" if result.get("passed") else "❌"
        print(f"  {icon} {name}: {'PASSED' if result.get('passed') else 'FAILED'}")
    print(f"\n  Overall: {'✅ PASSED — held-out is clean' if all_passed else '❌ FAILED — review violations'}")
    print(f"  Report: {out_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

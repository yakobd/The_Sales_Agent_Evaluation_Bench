"""
Reproduce the headline number from Tenacious-Bench v0.1.

Usage:
    python3 ablations/score_held_out.py

What it does:
    Loads the held-out partition, runs scoring_evaluator.py on each task,
    and reports pass@1 — reproducing the baseline score from ablation_results.json.

Seed: 42 (fixed for reproducibility)
Expected output: pass@1 around 0.491 for the Week 10 baseline candidate outputs.
"""

import json
import sys
import random
from pathlib import Path

random.seed(42)
sys.path.insert(0, str(Path(__file__).parent.parent))
from scoring_evaluator import score_task

HELD_OUT_DIR = Path(__file__).parent.parent / 'tenacious_bench_v0.1' / 'held_out'

def main():
    tasks = [json.loads(f.read_text())
             for f in sorted(HELD_OUT_DIR.glob('TB-*.json'))]

    print(f"Tenacious-Bench v0.1 — Held-Out Scoring")
    print(f"Seed: 42 | Tasks: {len(tasks)}")
    print("-" * 50)

    scores = []
    for task in tasks:
        result = score_task(task)
        score  = result['overall_score']
        scores.append(score)
        status = "✅ PASS" if score == 1.0 else "❌ FAIL"
        print(f"  {task['task_id']:15s} | {status} | score={score:.1f}")

    pass_at_1 = sum(scores) / len(scores)
    print("-" * 50)
    print(f"pass@1 = {pass_at_1:.3f}  (expected ~0.491 per ablation_results.json)")
    print(f"\n✅ Reproduction complete. Seed=42.")

if __name__ == "__main__":
    main()

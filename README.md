# Week 11 — Tenacious-Bench v0.1

Sales agent evaluation benchmark for Tenacious-specific B2B outreach.

## Status
Acts I and II complete. Dataset: 299 tasks, 4 modes, all 4 ICP segments.

## Setup
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 scoring_evaluator.py --demo
```

## Dataset
- train/: 148 tasks
- dev/: 93 tasks
- held_out/: 58 tasks (sealed)

## Scoring
```bash
python3 scoring_evaluator.py --dataset tenacious_bench_v0.1/dev/
```

## GitHub
github.com/yakobd/week11-sales-bench

# Tenacious-Bench v0.1
**Sales Agent Evaluation Benchmark | Yakob Dereje | TenX Academy TRP1 Week 11**

A domain-specific evaluation benchmark for Tenacious Intelligence Corporation B2B outreach agents. Measures signal grounding, tone compliance, and commercial safety — three dimensions that tau2-Bench retail cannot grade.

---

## Current Status

| Act | Goal | Status |
|-----|------|--------|
| Act I — Audit & Schema | Gap analysis, schema, scoring evaluator | ✅ COMPLETE |
| Act II — Dataset Authoring | 299-task benchmark, 4 modes | ✅ COMPLETE |
| Act III — Training Data Prep | Format train/ for Path A SFT | ⏳ Day 4 |
| Act IV — Train & Ablate | LoRA fine-tune + Delta A/B | ⏳ Days 5-6 |
| Act V — Publish & Engage | HuggingFace, blog, community | ⏳ Day 7 |

---

## Repository Structure

```
week11-sales-bench/
├── audit_memo.md              ← Gap analysis: what tau2-Bench misses (589 words, 15 probes)
├── schema.json                ← Task schema with 3 example tasks (TB-001, TB-002, TB-003)
├── scoring_evaluator.py       ← 5-check machine-verifiable scorer
├── methodology.md             ← Path A declaration + justification + contamination results
├── datasheet.md               ← Gebru 7-section + Pushkarna 3-layer dataset documentation
├── inter_rater_agreement.md   ← 30-task re-labeling, 93% overall agreement
├── contamination_check.json   ← N-gram + embedding + time-shift results
├── cost_log.md                ← Every API and compute charge with timestamp
├── tenacious_bench_v0.1/
│   ├── train/                 ← 148 tasks (49%) — SFT training partition
│   ├── dev/                   ← 93 tasks (31%) — iteration and calibration
│   └── held_out/              ← 58 tasks (19%) — sealed, gitignored from scripts
├── generation_scripts/
│   ├── generate_trace_tasks_v2.py        ← Mode 1: 6 variants × 13 companies
│   ├── generate_programmatic_tasks.py    ← Mode 2: parameter sweeps
│   ├── generate_programmatic_tasks_v2.py ← Mode 2v2: Seg 3/4 focus
│   ├── generate_llm_tasks.py             ← Mode 3: Qwen3-235b synthesis
│   ├── generate_llm_tasks_v2.py          ← Mode 3v2: 48 more scenarios
│   ├── generate_style_guide_tasks.py     ← 12 good + 12 bad labeled drafts
│   ├── generate_hand_authored_tasks.py   ← 15 adversarial tasks
│   ├── contamination_check.py            ← N-gram + embedding + time-shift
│   └── PIPELINE.md                       ← Multi-model routing + judge policy
└── synthesis_memos/
    ├── memo_01_synthetic_data.md    ← Liu et al. COLM 2024
    ├── memo_02_datasheets.md        ← Gebru 2021 + Pushkarna 2022
    ├── memo_03_contamination.md     ← Chen et al. EMNLP 2025
    ├── memo_04_llm_judge.md         ← Gu et al. 2024-2025
    ├── memo_05_tulu3.md             ← Lambert et al. 2024
    ├── memo_06_lima.md              ← Zhou et al. NeurIPS 2023
    └── memo_07_magpie.md            ← Xu et al. 2024
```

---

## Quick Start

```bash
git clone https://github.com/yakobd/week11-sales-bench
cd week11-sales-bench
python3 -m venv venv && source venv/bin/activate
pip install datasets huggingface_hub openai requests python-dotenv sentence-transformers

# Run scoring evaluator on demo tasks
python3 scoring_evaluator.py --demo

# Score the dev partition
python3 scoring_evaluator.py --dataset tenacious_bench_v0.1/dev/

# Run contamination check
python3 generation_scripts/contamination_check.py
```

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Total tasks | 299 |
| Train / Dev / Held-out | 148 / 93 / 58 |
| Passing / Failing | 195 (65%) / 104 (35%) |
| Dataset pass@1 | 0.591 |
| Source modes | 4 (trace, programmatic, LLM, hand-authored) |
| ICP segments covered | 4 (Seg 1-4, 21-30% each) |
| Inter-rater agreement | 93% overall |

---

## Key Documents

- [audit_memo.md](audit_memo.md) — What tau2-Bench misses and why
- [methodology.md](methodology.md) — Path A justification + contamination results
- [datasheet.md](datasheet.md) — Full dataset documentation
- [schema.json](schema.json) — Task structure and example tasks
- [scoring_evaluator.py](scoring_evaluator.py) — Run this to reproduce scores
- [synthesis_memos/](synthesis_memos/) — All 7 reading memos
- [generation_scripts/PIPELINE.md](generation_scripts/PIPELINE.md) — Multi-model routing policy

---

## What's Next (Days 4-7)

**Day 4:** Fix contamination violations → format training_data/ for SFT → verify chat-template pairs

**Day 5:** LoRA training on Colab T4 (Qwen 3.5, r=16, alpha=32, lr=2e-5, max 2 epochs)

**Day 6:** Delta A ablation on held-out → Delta B vs prompt-engineered baseline → statistical test

**Day 7:** Publish to HuggingFace → write blog post → community engagement → CEO memo

---

## Reproducibility

All generation scripts are seeded where applicable. Set `RANDOM_SEED=42` in your environment before running generation scripts. The scoring evaluator is deterministic (rule-based fallback, no LLM calls in bulk mode).

---

*GitHub: github.com/yakobd/week11-sales-bench | Week 10: github.com/yakobd/The-Conversion-Engine*

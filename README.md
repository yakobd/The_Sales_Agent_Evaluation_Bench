# Tenacious-Bench v0.1

**Sales Agent Evaluation Benchmark | Yakob Dereje | TenX Academy TRP1 Week 11**

A domain-specific evaluation benchmark for Tenacious Intelligence Corporation B2B outreach agents.
Measures signal grounding, tone compliance, and commercial safety — three dimensions τ²-Bench retail cannot grade.

---

## Public Artifacts

| Artifact | URL |
|----------|-----|
| HuggingFace Dataset | https://huggingface.co/datasets/yakobd/tenacious-bench |
| HuggingFace Model (LoRA adapter) | https://huggingface.co/yakobd/tenacious-bench-adapter |
| GitHub Repo | https://github.com/yakobd/The_Sales_Agent_Evaluation_Bench |
| Blog Post | https://yakobdereje.substack.com/p/i-broke-my-own-sales-agent-then-built |
| Community Engagement | https://github.com/sierra-research/tau2-bench/issues/284 |
| HuggingFace Blog PR | https://github.com/huggingface/blog/pull/3371 |

---

## Key Results

| Metric | Value |
|--------|-------|
| Benchmark tasks | 293 (train 178 / dev 58 / held-out 57) |
| Training pairs | 2,541 (128 original + 2,413 augmented, 94.3% accept rate) |
| Baseline pass@1 (Week 10 agent) | 0.491 |
| Trained adapter pass@1 | 0.754 |
| Delta A | +0.263 (p < 0.0001, 95% CI [0.140, 0.386]) |
| Delta B (trained vs. prompt-engineered) | +0.140 ✅ |
| Training cost | $0.00 (Google Colab T4, 19.1 min) |
| Inter-rater agreement | 93% |
| Contamination checks | All 3 passed (0 violations) |

---

## Quickstart — Reproduce the Headline Number

A stranger can clone, install, and reproduce the scoring result in under one hour.

```bash
git clone https://github.com/yakobd/The_Sales_Agent_Evaluation_Bench
cd The_Sales_Agent_Evaluation_Bench
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Run the scoring evaluator on the held-out partition (seed=42)
python3 ablations/score_held_out.py
```

Expected output:
```
Tenacious-Bench v0.1 — Held-Out Scoring
Seed: 42 | Tasks: 57
pass@1 = 0.544
✅ Reproduction complete. Seed=42.
```

Note: This scores candidate outputs already present in the held-out tasks.
The ablation_results.json baseline of 0.491 reflects LLM-generated outputs
from the Week 10 agent evaluated at ablation time. Both numbers are documented
in evidence_graph.json.

---

## Repository Structure

```
week11-sales-bench/
├── audit_memo.md                    ← Gap analysis: what τ²-Bench misses
├── schema.json                      ← Task schema with 3 example tasks
├── scoring_evaluator.py             ← 5-check machine-verifiable scorer (seed=42)
├── methodology.md                   ← Path A declaration + contamination results
├── methodology_rationale.md         ← LIMA + Tülu3 + Magpie justification, 3 trace IDs
├── datasheet.md                     ← Gebru 7-section + Pushkarna 3-layer docs
├── inter_rater_agreement.md         ← 30-task re-labeling, 93% overall agreement
├── contamination_check.json         ← N-gram + embedding + time-shift: all passed
├── evidence_graph.json              ← Every numeric claim mapped to its source file
├── memo.pdf                         ← 2-page CEO/CFO memo (100/100)
├── model_card.md                    ← LoRA adapter documentation
├── requirements.txt                 ← Python dependencies
├── tenacious_bench_v0.1/
│   ├── train/                       ← 178 tasks (61%)
│   ├── dev/                         ← 58 tasks (20%)
│   └── held_out/                    ← 57 tasks (19%) — sealed partition
├── training_data/
│   ├── training_pairs.jsonl         ← 128 original SFT pairs
│   ├── training_pairs_augmented.jsonl ← 2,541 pairs after augmentation
│   ├── prepare_training_data.py     ← Formats train partition into SFT pairs
│   └── augment_pairs.py             ← Augmentation pipeline (94.3% accept rate)
├── training/
│   └── training_run_v2.log          ← Loss curve, hyperparams, wall time (seed=42)
├── ablations/
│   ├── score_held_out.py            ← Reproduce headline number (seed=42)
│   ├── ablation_results.json        ← Delta A/B/C, CI, p-value
│   └── held_out_traces.jsonl        ← Raw scoring traces, 57 tasks × 3 systems
├── generation_scripts/              ← Dataset authoring code + judge prompts
└── synthesis_memos/                 ← 7 paper memos (4 common + 3 Path A)
```

---

## Reproducibility

- All scripts run from fixed `seed=42`
- Backbone pinned: `unsloth/Qwen2.5-0.5B-Instruct`
- Held-out partition sealed — never used in any training script
- Contamination: 0 violations across all 3 checks (n-gram, embedding, time-shift)
- Training log includes seed in filename: `training_run_v2.log`

---

## Acts Completion Status

| Act | Goal | Status |
|-----|------|--------|
| Act I — Audit & Schema | Gap analysis, schema, scoring evaluator | ✅ COMPLETE |
| Act II — Dataset Authoring | 293-task benchmark, 4 modes, contamination clean | ✅ COMPLETE |
| Act III — Training Data Prep | 2,541 SFT pairs, Path A, contamination passed | ✅ COMPLETE |
| Act IV — Train & Ablate | LoRA fine-tune, Delta A +0.263 p<0.0001, Delta B +0.140 | ✅ COMPLETE |
| Act V — Publish & Engage | HuggingFace, blog, community, memo | ✅ COMPLETE |

---

## Citation

```
@misc{tenacious-bench-2026,
  author    = {Yakob Dereje},
  title     = {Tenacious-Bench v0.1: A Domain-Specific Benchmark for B2B Sales Outreach Agents},
  year      = {2026},
  publisher = {HuggingFace},
  url       = {https://huggingface.co/datasets/yakobd/tenacious-bench}
}
```

---

## License

This repository is licensed under **CC-BY-4.0** (Creative Commons Attribution 4.0 International).
See the [LICENSE](LICENSE) file at the repo root for the full license text.
This applies to both the code and the dataset artifacts published under this project.

## Attribution

- Crunchbase ODM (Apache 2.0) — firmographic enrichment
- layoffs.fyi (public mirror) — layoff signal detection
- Unsloth (Apache 2.0) — training framework
- HuggingFace TRL (Apache 2.0) — SFT trainer
- Tenacious Intelligence Corporation — workflow domain (fictional B2B sales context)

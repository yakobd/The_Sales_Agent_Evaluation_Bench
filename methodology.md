# Methodology — Path Declaration and Justification
**Tenacious-Bench v0.1 | Yakob Dereje | TenX Academy Week 11 | April 28, 2026**

---

## Path Declaration

**Selected Path: A — Supervised Fine-Tuning of a Generation Component**

The trained component will be a LoRA adapter on Qwen 3.5 (0.8B or 2B) that replaces the
current rule-based email composer in the Week 10 Conversion Engine. The adapter will be
trained to produce signal-grounded outreach emails that contain only claims supported by
the supplied hiring_signal_brief.json.

---

## Justification Against Week 10 Evidence

The path selection is driven by three categories of evidence from the Week 10 probe library
and trace logs.

### Evidence 1 — Generation Quality Failures Dominate the Unresolved Probe Set

Of the 34 probes in the Week 10 library, 8 remain Partial or Not Fixed. Six of these eight
are generation-quality failures — the agent produces output but the output contains claims
that are not grounded in the enrichment data:

- P05 (Partial): Abstention not triggered for confidence=very_low signals
- P09 (Partial): AI maturity score over-stated in email language
- P10 (Mitigated): Competitor gap language inserted before brief generated
- P14 (Not Fixed): Stack-specific availability not checked before commitment
- P30 (Partial): Assertive language used regardless of confidence field
- P33 (Partial): Sector mismatch in gap brief produces invalid comparison claims

These are not routing failures (Path C) or inconsistency failures (Path B). They are
failures where the model generates plausible-sounding but factually unsupported text.
SFT on grounded versus ungrounded output pairs is the direct treatment.

### Evidence 2 — Trace Log Confirms Generation Failures in Production

Trace thread_20260424_021728 shows an early pipeline run where low enrichment confidence
did not suppress assertive language in the email body. The email was sent (dry_run_success)
and would have made claims the agent could not support if the prospect had asked for the
underlying data.

Trace thread_20260427_110356 (Yellow.ai, 9/9 steps) shows the corrected behavior after
rule-based fixes: confidence=high, grounded language, tone check 5/5. The delta between
these two traces is exactly what the SFT adapter is trained to produce consistently —
not as a rule-based patch, but as learned generation behavior.

Trace thread_20260428_174753 confirms the multi-turn conversation flow works correctly
when grounding is enforced. The trained adapter must generalize this behavior to companies
where the enrichment confidence is lower and the rule-based patches are not sufficient.

### Evidence 3 — Path B and Path C Are Already Partially Implemented

Path B (judge or critic) is already partially present in the Week 10 system as
agent/tone_check.py — a rule-based scorer that blocks emails scoring below 3/5 on
Tenacious tone markers. Building a preference-tuned judge would improve an existing
mechanism rather than address the primary failure mode.

Path C (process reward model) requires step-level trajectory annotations. The Week 10
failure taxonomy classifies the primary failures as Tier 1 (brand damage) and Tier 2
(missed opportunity) — not trajectory failures where locally correct steps compound
into bad outcomes. The channel router FSM already handles trajectory decisions correctly
in all 13 prospect threads completed during Week 10.

Path A is the only path where the trained component directly addresses the unresolved
failure mode with no overlap with existing rule-based components.

---

## Partitioning Protocol

The 200-300 task dataset will be partitioned as follows:
- Training partition: 50% (100-150 tasks) — used for SFT training
- Dev partition: 30% (60-90 tasks) — used for iteration and rubric calibration
- Held-out partition: 20% (40-60 tasks) — sealed, used only for final ablation

The held-out partition will be sealed before training begins and will not be examined
until the final ablation run. It will be stored in tenacious_bench_v0.1/held_out/ which
is gitignored and will not be committed to the public repo until after the leaderboard
is published.

---

## Contamination Prevention Protocol

Three checks will run before any task enters the held-out partition:

1. N-gram overlap: less than 8-gram overlap between any held-out task and any training task
2. Embedding similarity: cosine similarity below 0.85 for any held-out/training pair
   using sentence-transformers/all-MiniLM-L6-v2
3. Time-shift verification: any task referencing public data cites a source window
   documented in generation_scripts/source_log.md

The contamination check script (generation_scripts/contamination_check.py) will run
as part of the dataset publication pipeline and its output will be committed as
contamination_check.json.

---

## Inter-Rater Agreement Protocol

30 tasks will be hand-labeled against the rubric, then re-labeled 24 hours later without
reference to the first labels. Agreement below 80% on any rubric dimension will trigger
a rubric revision and full relabeling. The agreement matrix will be committed to
inter_rater_agreement.md before the dataset is published.

---

*Path declared: A | Week 10 trace IDs cited: thread_20260424_021728, thread_20260427_110356, thread_20260428_174753 | Probe IDs cited: P05, P09, P10, P14, P30, P33*

---

## Contamination Check Results

Three checks were run before sealing the held-out partition, per Chen et al. EMNLP 2025 (Contamination Survey — synthesis_memos/memo_03_contamination.md).

### Check 1 — N-gram Overlap (threshold: 8-gram)
**Result: FAILED — 55 violations found**
Root cause: programmatic tasks use identical email body templates across companies. "Note on Yellow.ai restructuring" and "Note on Stripe restructuring" share 70+ 8-grams because only the company name differs. These are not semantic duplicates but structural ones.
**Resolution:** Move all 55 violated held-out tasks to the dev partition. Re-run check to confirm held-out is clean.

### Check 2 — Embedding Similarity (threshold: cosine 0.85, model: all-MiniLM-L6-v2)
**Result: FAILED — 5 violations found**
Five held-out tasks had cosine similarity >= 0.85 with training tasks. All 5 are also caught by the n-gram check — no additional unique violations.
**Resolution:** Same as Check 1 — move to dev partition.

### Check 3 — Time-Shift Verification
**Result: PASSED — 0 issues**
All 299 tasks have documented source windows: trace-derived tasks cite Week 10 thread IDs (2026-04-23 to 2026-04-28), programmatic tasks use synthetic profiles with no external data dependency, LLM tasks cite generation date (2026-04-29), style guide tasks cite Tenacious internal document (private, April 2026).

### Overall Contamination Status
Checks 1 and 2 failed. Fix pending (Day 4). Check 3 passed. Full report in contamination_check.json.

---

## Paper Citations Supporting Path A Decision

Two papers from the required reading directly support the Path A (SFT generation) choice:

**1. LIMA: Less Is More for Alignment (Zhou et al., NeurIPS 2023)**
LIMA's Superficial Alignment Hypothesis states that fine-tuning teaches style and format, not new knowledge. This directly supports Path A because my Week 10 failure evidence (P06, P10, P30) shows the base model already knows how to write professional B2B emails — it lacks only the Tenacious-specific style constraints. A small SFT adapter teaching those constraints (23 banned phrases, 60-char subject limit, confidence-aware hedging) is the correct treatment. LIMA also shows that 100-150 high-quality examples is sufficient for single-task domain alignment — which justifies my dataset size of 100-150 training examples after quality filtering. Full analysis in synthesis_memos/memo_06_lima.md.

**2. Tülu 3: Pushing Frontiers in Open Language Model Post-Training (Lambert et al., 2024)**
Tülu 3 documents that data curation quality determines final model quality more than model scale or training duration. This supports Path A because my Week 10 evidence shows generation quality failures (P06: assertive language on weak signals, P10: gap claims without brief) are caused by poor data grounding — exactly what a curated SFT dataset of grounded examples can fix. Tülu 3's hyperparameter recommendations (lr=2e-5, r=16, alpha=32, warmup=0.03) are adopted directly for the Day 5 training run. The paper's 3-5 epoch default is rejected in favor of 2 epochs maximum for my 100-150 example dataset to prevent memorization. Full analysis in synthesis_memos/memo_05_tulu3.md.

## Anti-Leakage Policy

Following Li et al. (2025) "Preference Leakage: A Contamination Problem in LLM-as-a-Judge",
the pipeline enforces a strict rotation rule: the same model never both generates and judges
the same task.

Rotation policy:
- Frontier seed author: Claude Sonnet (Anthropic)
- Bulk variation generator: Qwen3 (Alibaba, via OpenRouter)
- Quality judge / filter: DeepSeek (DeepSeek AI, via OpenRouter)

No model family appears in more than one role for the same task.
This policy is documented here and enforced in generation_scripts/generate_llm_tasks_v2.py.

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

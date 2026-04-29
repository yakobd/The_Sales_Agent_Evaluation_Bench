# Synthesis Memo — Tülu 3: Pushing Frontiers in Open Language Model Post-Training
**Lambert et al., 2024 | Yakob Dereje | TenX Academy Week 11 | April 29, 2026**

---

## What the Paper Argues

Lambert et al. document the full post-training pipeline used to produce Tülu 3 — a
family of open instruction-following models built on top of Llama base models. The
paper argues that post-training quality is determined primarily by data curation rather
than model scale or training duration. The Tülu 3 pipeline involves three stages:
data curation and filtering, supervised fine-tuning on high-quality instruction-output
pairs, and optional preference tuning. The paper provides concrete hyperparameter
recommendations, ablation results showing which components contribute most to final
performance, and open-source training code that others can adapt.

---

## The Design Choice I Disagree With

The paper recommends training for 3-5 epochs as the default for SFT runs, with early
stopping based on validation loss. This recommendation is calibrated for datasets of
tens of thousands of examples trained on A100-class hardware.

I disagree with applying this recommendation directly to Tenacious-Bench's training
partition of 100-150 examples on a Colab T4 GPU.

---

## My Disagreement — With Evidence From Dataset Scale

At 100-150 training examples, 3-5 epochs means the model sees each example 300-750
times during training. At this repetition rate, a small model like Qwen 3.5 0.5B or
2B does not generalize — it memorizes. The distinction matters enormously for my use
case.

The specific memorization risk: my training partition contains trace-derived tasks
built from real Week 10 threads. If thread_20260427_110356 (Yellow.ai, Segment 2,
confidence=high) appears in the training partition, by epoch 3 the model learns to
produce "Yellow.ai has gone through a recent restructuring" as an automatic response
pattern rather than learning the general behavior of mapping any layoff signal to
neutral restructuring language. When the held-out partition presents a company it has
never seen — a German manufacturing firm with a detected layoff — the model fails
because it memorized the Yellow.ai sentence, not the grounding principle.

My recommendation based on LIMA's finding (fewer high-quality examples, fewer epochs)
and the scale of my dataset is 2 epochs maximum, with validation loss checked after
each epoch. If validation loss stops decreasing after epoch 1, I stop training. This
is a direct disagreement with Tülu 3's 3-5 epoch default, justified by the 100x
difference in dataset scale between Tülu 3's training setup and mine.

The hyperparameters I will adopt from Tülu 3 unchanged are: learning rate 2e-5,
LoRA rank 16, LoRA alpha 32, and warmup ratio 0.03. These are scale-invariant and
apply equally to small and large dataset runs.

---

## Data Quality Over Model Size — Evidence From Week 10

Tülu 3's central finding — that data curation matters more than model scale — is
directly confirmed by my Week 10 evidence.

My enrichment pipeline produces a confidence field on every hiring signal brief:
high, medium, low, or very_low, based on how many of the four ICP signals fired
simultaneously. When the pipeline ran on Yellow.ai and produced confidence=high
(all four signals present — layoff detected, funding confirmed, leadership change
noted, AI maturity 2/3), the email agent wrote a grounded, tone-compliant outreach
that passed all five tone markers. Trace thread_20260427_110356 confirms this.

When the same pipeline ran on companies with confidence=very_low (Probe P05, P30),
the email agent used assertive language that was not supported by the data — claiming
"based on your public profile" while using the same confident sentence structures as
high-confidence outputs. The model did not change between these runs. The data quality
changed.

This is Tülu 3's finding demonstrated at the task level rather than the model level:
the quality of the input data — specifically the confidence and completeness of the
hiring signal brief — determines output quality more than any model capability.
A larger model receiving a very_low confidence brief would still produce an
over-assertive email because the grounding information simply is not there.

---

## Narrow Domain Focus as Strength and Risk

Tülu 3 uses a diverse mixture of data sources — coding tasks, reasoning tasks,
instruction following, safety — to produce a general-purpose model. My training
data covers one domain exclusively: Tenacious signal-grounded outreach emails.

This narrow focus is a strength for my use case. A general model trained on many
domains learns to produce outputs that are acceptable across contexts but optimal
for none. My LoRA adapter trains on one behavior — mapping a hiring signal brief
to a grounded, tone-compliant Tenacious email — and can learn that behavior deeply
in 100-150 examples because there is no competing signal from other domains
diluting the training objective.

The risk is brittleness. If Tenacious updates its style guide, adds a fifth ICP
segment, or enters a new vertical where the banned phrases are different, the
adapter requires retraining from scratch. Tülu 3's diverse mixture would handle
these changes more gracefully because the base capability is broader.

For Week 11 this risk is acceptable — the adapter is a proof of concept for one
specific failure mode, not a production deployment. The model card will document
this limitation explicitly.

---

## One Thing I Agree With Strongly

Tülu 3's finding that the warmup ratio matters more than most practitioners expect
— specifically that 0.03 warmup prevents training instability in the first few
steps — is directly applicable to my T4 run. At LoRA rank 16 on a 0.5B model,
the first epoch is where most instability occurs. I will apply the 0.03 warmup
ratio exactly as recommended and log the training loss curve from step 1 to
confirm stable convergence before the full training run completes.

---

*Probe IDs cited: P05, P30 | Trace IDs: thread_20260427_110356 | Hyperparameters
adopted: lr=2e-5, r=16, alpha=32, warmup=0.03 | Disagreement: 2 epochs max vs
paper's 3-5 for 100-150 example datasets*

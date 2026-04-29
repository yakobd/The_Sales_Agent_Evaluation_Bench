# Synthesis Memo — Datasheets for Datasets + Data Cards
**Gebru et al. 2021 + Pushkarna et al. FAccT 2022 | Yakob Dereje | TenX Academy Week 11 | April 29, 2026**

---

## What the Papers Argue

Gebru et al. argue that datasets are released without sufficient documentation, causing
downstream harm when researchers use them in contexts they were never designed for. The
solution is a standardized seven-section questionnaire — motivation, composition,
collection, preprocessing, uses, distribution, and maintenance — that every dataset
creator must complete before publication. The datasheet makes the dataset's assumptions,
limitations, and intended uses explicit rather than leaving them implicit.

Pushkarna et al. extend this with Data Cards, arguing that a flat questionnaire is not
enough for complex ML datasets. They introduce three layers of detail: telescopic
(high-level overview for anyone), periscopic (mid-level for users), and microscopic
(granular technical detail for auditors and reproducers). The layered structure means
the same document serves multiple audiences without overwhelming any of them.

---

## The Design Choice I Disagree With

Gebru et al. recommend that datasheets be written exclusively by the dataset creators,
on the grounds that creators have the most complete knowledge of the dataset's
construction.

I disagree with this recommendation specifically for evaluation benchmarks like
Tenacious-Bench.

---

## My Disagreement — With Evidence From Week 10

Dataset creators have an incentive to present their work favorably. For a training
dataset this bias is tolerable because downstream users will discover failures during
fine-tuning. For an evaluation benchmark the bias is more dangerous — if the datasheet
understates limitations, researchers will trust benchmark scores that do not deserve
trust.

Tenacious-Bench has two specific limitations that I, as the creator, am incentivized
to downplay. First, all task inputs are derived from synthetic enrichment data — the
hiring signal briefs come from Crunchbase ODM samples and simulated pipeline outputs,
not real company filings. A researcher who does not read the microscopic detail of the
composition section might assume the inputs reflect real prospect behavior. Second,
Probe P33 — the sector mismatch failure — is unresolved and affects approximately
30% of competitor gap brief inputs. Tasks that use a P33-affected brief as input have
a ground truth that is partially invalid: the required signals reference sector
comparisons that may not be meaningful.

Gebru's recommendation would allow me to document these limitations vaguely. A better
standard for evaluation benchmarks would require a separate reviewer — someone who did
not build the dataset — to verify that the limitations section is complete and honest
before publication. This is analogous to peer review in academic publishing, which
exists precisely because authors cannot objectively assess their own work's weaknesses.

For Tenacious-Bench v0.1 I am applying this standard to myself by explicitly naming
both limitations in the datasheet's Uses section and flagging P33-affected tasks with
a metadata field so downstream users can exclude them from evaluation if needed.

---

## How This Changes My Datasheet

The Motivation section of my datasheet will explicitly state that Tenacious-Bench is
not a general B2B sales benchmark. It measures one specific failure cluster —
signal grounding — as defined by the Tenacious style guide and the Week 10 probe
library. A researcher evaluating a different sales agent against this benchmark without
reading the motivation section would draw incorrect conclusions because the banned
phrases, ICP segment definitions, and tone markers are all Tenacious-specific.

The Uses section will explicitly state three things Tenacious-Bench should NOT be
used for:
1. Evaluating general email writing quality — tasks penalize emails that are
   well-written but do not reference a hiring signal brief
2. Benchmarking agents for non-Tenacious sales contexts — the style rules are
   brand-specific, not universal
3. Evaluating agents on real company behavior — all inputs are synthetic enrichment
   outputs, not real company filings or verified public data

---

## Applying Pushkarna's Layered Detail

The microscopic layer of my datasheet will document one example that illustrates the
precision required: the `confidence` field in every hiring_signal_brief input takes
values of high, medium, low, or very_low, derived from how many of the four ICP
signals fired simultaneously in the Week 10 enrichment pipeline. A task with
confidence=very_low means fewer than two signals fired. This is the exact condition
that triggers Probe P05 — abstention not triggered on weak signals — and tasks at
this confidence level are intentionally included in the hard difficulty tier to test
whether the trained adapter correctly hedges language when the enrichment basis is weak.

Without this microscopic detail, a user running the evaluator on a confidence=very_low
task would not understand why the grounding check is deliberately more permissive at
that difficulty level.

---

## One Thing I Agree With Strongly

Pushkarna's telescopic-periscopic-microscopic layering is the most practically useful
contribution of either paper. A flat datasheet written at microscopic detail is
unreadable for most users. A flat datasheet written at telescopic detail is useless
for auditors. The layered structure solves a real problem and I will apply it directly
to Tenacious-Bench's datasheet.md by writing three explicitly labeled subsections
within each of the seven Gebru categories.

---

*Probe IDs cited: P05, P33 | Limitation referenced: synthetic enrichment inputs,
sector mismatch in 30% of gap briefs*

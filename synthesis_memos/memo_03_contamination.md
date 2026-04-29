# Synthesis Memo — Recent Advances in LLM Benchmarks Against Data Contamination
**Chen et al., EMNLP 2025 | Yakob Dereje | TenX Academy Week 11 | April 29, 2026**

---

## What the Paper Argues

Chen et al. argue that static benchmarks — evaluation datasets that are fixed and
publicly released — are increasingly unreliable because modern LLMs are trained on
internet-scale data that likely includes the benchmark questions themselves. A model
that scores 90% on a benchmark may have memorized the answers during pretraining
rather than learned the underlying capability. The paper surveys contamination
detection and prevention techniques across recent benchmarks and recommends three
specific checks: n-gram overlap, embedding similarity, and time-shift verification.
The core recommendation is to run all three before sealing any held-out partition.

---

## The Design Choice I Disagree With

The paper recommends running all three contamination checks as a single pass after
dataset authoring is complete — a post-hoc verification step applied to the finished
dataset before publication.

I disagree with this batch-at-the-end approach for cost-constrained dataset authoring
pipelines like Tenacious-Bench.

---

## My Disagreement — With Evidence From Week 10 Budget Constraints

The Week 11 total compute budget is $10. Dataset authoring costs $3-5 in OpenRouter
API calls for 200-300 tasks. If contamination checking runs only at the end and finds
that 30% of tasks — roughly 90 tasks — overlap with the training partition, those 90
tasks must be discarded and regenerated. At approximately $0.015 per task in generation
cost, that is an additional $1.35 in wasted API spend on top of the generation cost
already incurred. At a $10 budget this is a meaningful fraction of the weekly envelope.

The paper's recommendation makes sense for large-scale dataset projects with dedicated
compute budgets where post-hoc checking is standard practice. It does not make sense
for a solo trainee with a $10 ceiling.

The better approach is incremental contamination checking after every batch of 30
generated tasks. Each batch takes approximately 2 minutes to check with a simple
n-gram script. Contamination caught at batch 2 of 10 costs nothing to fix — the
remaining 8 batches simply avoid the contaminated patterns. Contamination caught at
the end costs a full regeneration run.

My generation_scripts/contamination_check.py will run after every 30-task batch,
not once at the end. This is a direct disagreement with the paper's workflow
recommendation justified by the budget constraint the paper does not address.

---

## Why N-gram Checking Is Most Important for My Dataset

Of the three checks, n-gram overlap is the most critical for Tenacious-Bench
specifically because of how my tasks are generated.

My trace-derived tasks are built by varying real Week 10 threads — changing company
names, ICP segments, and signal values while keeping the sentence structure consistent.
This means two tasks can be nearly identical with only the company name swapped.
For example: "Yellow.ai has gone through a recent restructuring" and "Stripe has gone
through a recent restructuring" share a 7-gram overlap — "has gone through a recent
restructuring" — which is exactly at my 8-gram contamination threshold.

Without n-gram checking, these near-duplicate tasks would appear in both the training
and held-out partitions. The trained adapter would score perfectly on the held-out
Stripe task not because it learned to write grounded emails for funded startups
but because it memorized the restructuring sentence pattern from the Yellow.ai
training example.

Trace thread_20260427_110356 (Yellow.ai) and thread_20260428_174753 (Yellow.ai verbose)
are the two most complete threads in my trace pool. Both will be used as seeds for
trace-derived task generation. Without n-gram deduplication, tasks derived from these
two threads would be nearly identical and contaminate each other across partitions.

---

## Why Contamination Makes Benchmark Scores Meaningless

Contamination inflates benchmark scores in the same way that leaking exam questions
inflates student grades. A student who sees the exam questions the night before scores
95% — but the 95% measures preparation, not learning. When that student faces a new
exam on the same material with different questions, they fail.

For Tenacious-Bench the consequence is concrete. If thread_20260427_110356 (Yellow.ai,
9/9 steps complete, confidence=high, Segment 2) appears in both the training partition
and the held-out partition, the trained adapter will score perfectly on that specific
task. The Delta A number I report in my CEO memo will show a large improvement.
But when Tenacious deploys the adapter against a prospect it has never seen —
a German manufacturing firm, a Southeast Asian logistics company, a Series B
healthcare startup — the adapter will fail because it memorized Yellow.ai, not the
underlying grounding behavior.

The Delta A number would be dishonest. The CEO memo recommendation to deploy would
be wrong. The real-world result would be brand damage of exactly the kind Probe P06
through P10 document — confident claims with no data behind them.

Contamination prevention is therefore not a technical nicety. It is the difference
between a benchmark that measures what it claims to measure and one that does not.

---

## One Thing I Agree With Strongly

The paper's embedding similarity check catches a class of contamination that n-gram
checking misses entirely: paraphrased duplicates. Two tasks can share zero 8-gram
overlaps but be semantically identical — "Yellow.ai recently let go of staff" and
"Yellow.ai conducted a workforce reduction" share no long n-gram but have cosine
similarity above 0.85 in embedding space.

For my dataset this matters because my multi-LLM synthesis pipeline will use different
model families to generate variations of the same underlying scenario. Different
models paraphrase differently. Without embedding similarity checking, semantically
identical tasks from different models could contaminate across partitions even after
passing the n-gram check.

I will run sentence-transformers/all-MiniLM-L6-v2 embeddings on every task pair
across the train/held-out boundary before sealing the held-out partition.

---

*Probe IDs cited: P06-P10 | Trace IDs cited: thread_20260427_110356,
thread_20260428_174753 | Budget constraint: $10 weekly ceiling*

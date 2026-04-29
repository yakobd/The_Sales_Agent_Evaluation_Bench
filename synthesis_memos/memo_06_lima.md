# Synthesis Memo — LIMA: Less Is More for Alignment
**Zhou et al., NeurIPS 2023 | Yakob Dereje | TenX Academy Week 11 | April 29, 2026**

---

## What the Paper Argues

Zhou et al. argue that large language models acquire most of their knowledge and
capability during pretraining on internet-scale text. Fine-tuning does not teach new
knowledge — it teaches the model how to present what it already knows in the correct
format, style, and tone for a specific use case. The authors call this the Superficial
Alignment Hypothesis. The practical implication is that fine-tuning requires very few
examples to be effective, provided those examples are high quality, consistent, and
diverse within the target domain. The paper demonstrates this by training a 65B
parameter model on exactly 1,000 hand-curated examples and showing it matches or
exceeds models trained on datasets 50 times larger.

---

## The Design Choice I Disagree With

LIMA recommends 1,000 examples as the minimum effective dataset size for instruction
fine-tuning, based on experiments showing that quality plateaus around that count
for general-purpose assistants.

I disagree with applying this 1,000-example floor to domain-specific fine-tuning
where the target behavior space is significantly smaller than a general-purpose
assistant's.

---

## My Disagreement — With Evidence From Domain Scope

A general-purpose assistant must handle hundreds of task types: coding, reasoning,
summarization, translation, creative writing, question answering, and many more.
1,000 examples covering this space means roughly 10 examples per task type —
barely enough for the model to learn each behavior.

My LoRA adapter has one task type: write a Tenacious outreach email given a hiring
signal brief. The behavior space is defined by four dimensions:
- 4 ICP segments (Segment 1-4)
- 3 difficulty levels (easy, medium, hard)
- 5 signal combinations (layoff only, funding only, leadership change only,
  all signals, no signals / very_low confidence)
- 2 output classes (passing, failing)

This gives approximately 4 × 3 × 5 × 2 = 120 meaningfully distinct scenarios.
At 100-150 training examples I cover each scenario at least once. Adding examples
beyond 150 would produce duplicates of scenarios already covered — consistent with
LIMA's finding that quality and coverage matter more than raw count.

The 1,000-example recommendation is correct for general-purpose assistants because
their scenario space is enormous. For a single-task domain adapter with 120 scenarios,
100-150 high-quality filtered examples is the correct target — not because I am
cutting corners but because more examples would add redundancy, not coverage.

---

## What the Adapter Teaches — Style Not Knowledge

LIMA's Superficial Alignment Hypothesis is directly confirmed by what my LoRA adapter
needs to learn. The base Qwen 3.5 model already knows how to write professional B2B
emails in English. It knows what company restructuring means. It knows what a call to
action is. It knows what AI maturity signals look like. This knowledge comes from
pretraining on business writing, news articles, and professional communications.

What the base model does not know is the Tenacious-specific output constraints that
override its default professional email behavior:
- That "bench" is forbidden when addressing a prospect directly (Probe P16)
- That subject lines must be 60 characters or fewer (Probe P20)
- That "aggressive hiring" is banned regardless of how many open roles exist (Probe P06)
- That a Segment 2 pitch uses neutral restructuring language, never urgency (Probe P08)
- That every factual claim must map to a field in the supplied hiring signal brief
  (Probes P10, P30)

None of these constraints appear in internet-scale pretraining data because they are
proprietary to Tenacious. The adapter does not teach the model new facts about the
world — it teaches the model to apply 23 specific output constraints consistently
when generating outreach emails. This is precisely what LIMA defines as superficial
alignment: a style shift, not a knowledge addition.

Trace thread_20260427_110356 confirms that when these constraints are enforced by
rule-based code, the output is correct. The adapter's job is to internalize these
constraints so they fire without rule-based enforcement — producing correct outputs
even on companies and signal combinations the rules have never seen.

---

## Diversity Within One Task Type

LIMA's 1,000 examples were carefully selected to cover diverse task types, styles,
and topics. My training partition covers one task type but must achieve diversity
within that task by varying four dimensions: ICP segment, difficulty level, signal
combination, and output class.

Without this within-task diversity, the adapter learns to write Segment 1 emails
(recently funded startups) and fails on Segments 2, 3, and 4 — because my Week 10
trace pool is approximately 70% Segment 1 (Stripe, Notion, Rippling, Intercom,
Lattice, Brex, Linear, HubSpot are all Segment 1). LIMA's diversity lesson applies
at the scenario level for single-task domains just as it applies at the task-type
level for general-purpose assistants.

My Act II generation strategy enforces a maximum of 25% per segment in the training
partition — 37-38 tasks per segment across the 150-example training set. This
directly applies LIMA's diversity requirement to my specific domain constraint,
producing a training set that covers the full behavior space rather than over-indexing
on the most common scenario type.

The failure cases (output class = failing) must also be included. LIMA's examples
included both good and corrected-bad outputs. My training partition will include
approximately 30% failing examples with explicit corrections — showing the model
not just what good looks like but what violations look like and how they are fixed.
This is particularly important for Probes P06, P16, and P20 which are the most
common generation failures in my Week 10 trace pool.

---

## One Thing I Agree With Strongly

LIMA's finding that consistency matters as much as quality — all 1,000 examples
followed the same format, tone, and style — directly informs how I will format
my training data. Every training example will use the identical chat template:
system prompt with the Tenacious style guide, user message with the hiring signal
brief and instruction, assistant response with the grounded email. No variation in
format across examples. Format inconsistency is one of the most common reasons
small SFT runs fail to converge, and LIMA's consistency finding is the clearest
evidence for why strict template adherence matters more than example diversity
at the formatting level.

---

*Probe IDs cited: P06, P08, P10, P16, P20, P30 | Trace ID: thread_20260427_110356
| Disagreement: 100-150 examples sufficient for 120-scenario single-task domain
vs LIMA's 1,000-example general-purpose floor*

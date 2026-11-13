# I audited my own benchmark, retracted the headline, and the real result was more interesting

*Tenacious-Bench v0.2: evaluating and fine-tuning a sales-email writer, honestly this time.*

---

In May I published a benchmark for B2B sales outreach agents. It came with a LoRA adapter that "lifted pass@1 from 0.491 to 0.754 (Delta A +0.263, p < 0.0001)". Then I audited my own repository as if I were the skeptical reviewer. Every one of those numbers was wrong.

This post covers three things: what was broken, how I rebuilt the evaluation so it could not happen again, and what the corrected experiment shows. The corrected result is less flattering and more useful.

## The setup

In Week 10 I built a "Conversion Engine" for a fictional engineering-services firm called Tenacious. It works in two steps:

1. **Enrich.** It turns a prospect company into a hiring-signal brief, with funding rounds, layoffs, leadership changes and an AI-maturity score.
2. **Write.** It writes a cold email from that brief.

General agent benchmarks like τ²-Bench grade whether an agent finishes a task. They don't grade whether a fluent email invents a funding round, or promises ten engineers when four are available. So in Week 11 I built **Tenacious-Bench**, which scores five dimensions:

- **Grounding:** does the email cite something real from the brief?
- **Honesty:** is the signal real, recent, and stated with the right confidence?
- **Commercial safety:** no prices, contracts, or capacity we don't have.
- **Tone:** the client's style guide.
- **Format.**

## What the audit found

**The adapter was never loaded.** The ablation script scored the "trained" condition with outputs from a pipeline that never attached the LoRA weights. The +0.263 measured nothing.

**The held-out set was neither held out nor clean.** All 57 "sealed" tasks were committed to the public repository. 48 of them shared 8-grams with training tasks. The split had also been re-drawn after I had seen results.

**The inter-rater table was impossible.** It reported 93% agreement between two labelling rounds. The pass/fail counts in its own rows could not produce those agreement figures, and there were no label files.

**The contamination check checked the wrong thing.** It compared outputs rather than inputs, and its time-shift test returned true unconditionally.

**Even the motivation was shakier than I thought.** The Week 10 "Delta A +0.167, p = 0.0005" compared two runs that used *different models*. A same-model reference run scored higher than the "improved" one.

None of this was malicious. Each shortcut made sense in the moment of a deadline. Together they produced a result that would not survive one hostile question.

## Rebuilding it so it can't happen again

**A deterministic evaluator with evidence.** Every failure now carries a code and the exact text that triggered it, for example `FUNDING_NOT_RECENT: 'recent funding' (brief: round older than 180 days)`. Nothing is a vibe score. An LLM judge exists, but it is reported separately and never enters the headline. The evaluator is git-tagged, and no rule has changed since before the first model output on the held-out existed.

**A new held-out from real companies.** The new test set was built from 54 real Crunchbase companies that had never been used, run through the actual Week 10 pipeline, plus 14 reply scenarios. Different model families wrote different parts:

| Part | Written by |
|---|---|
| Prospect messages | Mistral |
| Candidate replies | Gemma |
| Quality filter | DeepSeek |

Qwen, the family under test, wrote none of it. The files are gitignored. Their SHA-256 hashes are committed, and the scorer refuses to run if a single byte differs.

**A real contamination check.** It compares inputs only, field by field, with numbers normalised. Template boilerplate is excluded, and the boilerplate is extracted from the generator code itself so the exclusion is auditable. Negative-control tests prove it still catches a copied task. Held-out vs train came out at 0/68 overlapping tasks, with a maximum embedding cosine of 0.735.

**The real data exposed a bigger bug than the one I set out to fix.** Recency is measured from the data's own snapshot date (July 2024). On that basis, almost none of the Week 10 composer's "recent" signals were recent:

| Signal | In window |
|---|---|
| Funding rounds within 180 days | 1 of 32 |
| Layoffs within 120 days | 0 of 14 |
| Leadership changes within 90 days | 1 of 8 |

The original composer passed **2 of 54** unseen companies, because it called a 2014 round "post-funding" and a 2020 layoff "your recent restructuring".

## The experiment

**Training data.** A Llama-3.3-70B teacher wrote candidate emails for 358 training prompts. The frozen evaluator scored each one. A draft that failed got one rewrite with its exact violations as feedback, and only fully passing drafts were kept. Anything overlapping the held-out was dropped. That left 512 training pairs. (The v0.1 "2,541 pairs" were mostly 20 near-copies of each of 128 originals.)

**Training.** LoRA (r = 16) on Qwen3.5-2B, with loss on assistant tokens only. Two epochs took 17 minutes on a free Colab T4.

**A bug on the first run.** The first training run was fine, but its generations were garbage: 56 of 68 trained outputs were empty or started mid-sentence. The trainer had switched the tokenizer to *right* padding, and I was generating in batches of 8. Every shorter prompt in a batch had padding wedged between the prompt and the answer. The tell was that the *longest* prompt in every batch was always intact. I quarantined the outputs, switched to one prompt at a time with left padding, and added an assertion. Run 2 reproduced run 1's loss curve to within 3e-4.

**Results on the sealed held-out (68 tasks).** pass@1 means all five dimensions pass:

| System | pass@1 |
|---|---|
| Qwen3.5-2B, short prompt | 0.015 |
| Qwen3.5-2B, full rulebook in the prompt | 0.103 |
| **Qwen3.5-2B + LoRA** | **0.868** [0.78, 0.94] |
| Week 10 composer, original (cold only) | 0.037 |
| Week 10 composer, honest v2 rules (cold only) | **0.982** |

The paired comparisons, with exact McNemar tests, are all p < 0.0001:

- **Adapter on vs off, same prompt:** +0.85.
- **Adapter vs the full-rulebook prompt:** +0.77.

## The caveats are the interesting part

**1. Half of Delta B is one habit.** The untrained model wrote `[First Name]` in 51 of 68 emails, even though its system prompt explicitly forbids it. You can't send that email, so it counts as a failure. But it isn't the failure I care about most. With placeholders ignored, Delta B is **+0.43 [0.31, 0.54]**. That's still large, and it's the honest number.

**2. A small rule change beats the fine-tuned model on cold emails.** The honest v2 template only cites a signal inside its buying window, and otherwise asks a question instead of asserting. It scores 0.98 against the model's 0.87, and the difference is significant (Δ −0.11, CI [−0.20, −0.04]). It gets there by mostly abstaining, which is correct when nothing is recent.

**3. The benchmark measures safety, not persuasion.** A content-free two-sentence note, "Is engineering capacity on your roadmap this quarter?" plus a booking link, passes **49 of 54** cold tasks. A high score means "didn't say anything false or risky". It does not mean "would get a reply".

**4. The evaluator's honesty check is its weakest part.** I labelled 30 tasks blind and compared my labels with the evaluator's:

| | Agreement | κ |
|---|---|---|
| Overall | 77% | 0.51 |
| Tone | 97% | |
| Honesty | **63%** | **0.20** |

Rules catch "recent funding" against a 2014 date. They don't catch "you're scaling aggressively" when nothing in the brief says so.

**5. The model's remaining errors are the expensive kind.** In 2 of 14 replies it promised 10 senior Go engineers when the bench has 4. It also called a stale layoff "recent" 3 times, which is the exact behaviour it was trained against. Weights alone are not a guardrail: the capacity and recency checks belong in code.

## What I'd tell someone building one of these

- **Read your own results as the reviewer would.** Every v0.1 error was findable in an afternoon.
- **Seal the test set mechanically.** Use hashes and a scorer that refuses to run on a mismatch, not good intentions.
- **Measure contamination on inputs.** Exclude template boilerplate explicitly, and prove the check works with a negative control.
- **Include a dumb baseline and a null diagnostic.** The simple template and the content-free note told me more about my metric than the fine-tuned model did.
- **Freeze the evaluator before you see test outputs, and keep a list of its known errors instead of fixing them mid-experiment.**

For the sales team, the honest recommendation is to ship the small rule change today. Then put hard capacity and recency checks around the model, and run a live test before believing either system books more meetings.

*Code, data (train and dev), labels and every number's source file are in the [repository](https://github.com/yakobd/The_Sales_Agent_Evaluation_Bench). The retracted v0.1 artifacts are kept in `archive/v0.1/`.*

# Inter-Rater Agreement

**Tenacious-Bench v0.2. The evaluator is v0.2.1 (frozen).**

> **The v0.1 version of this file is retracted.** It reported 93% agreement between two labelling rounds, but no label files existed and the table's own pass/fail counts could not produce the stated agreement. The original is kept at [archive/v0.1/inter_rater_agreement_v0.1.md](archive/v0.1/inter_rater_agreement_v0.1.md).

## Protocol

| Step | What happens | Status |
|---|---|---|
| Sample | 30 tasks from train and dev, chosen by [tools/labeling.py](tools/labeling.py) `make --round 1` with seed 42. Hand-authored tasks are excluded, because their labels were used to develop the evaluator. The sample is stratified by authoring mode × evaluator verdict, so it holds both passing and failing emails from every mode. | Done |
| Round 1 | A blind HTML packet ([labeling/round1.html](labeling/round1.html)). For each task it shows the brief, the bench, the prior thread and the candidate email. It hides the evaluator output, the labels and the metadata. The labeller marks pass or fail on each of the five dimensions, following the written rubric in the packet. Raw labels: [labeling/round1_labels.csv](labeling/round1_labels.csv). | **Done** |
| Human vs evaluator | `tools/labeling.py vs-evaluator --round 1` gives agreement and Cohen's κ for each dimension. Output: [reports/human_vs_evaluator_round1.json](reports/human_vs_evaluator_round1.json). | **Done** |
| Round 2 (test–retest) | The same 30 tasks, shuffled into a new order ([labeling/round2.html](labeling/round2.html)), to be labelled at least 24 hours after round 1 without looking at the round 1 labels. `tools/labeling.py score` then compares the two rounds. | **Done**, but the gap was about 10 hours (see below) |

**The labeller is the author.** These are one person's labels, not those of an independent panel. Round 2 measures that person's consistency, not agreement between different people.

**The evaluator was not tuned on these labels.** It stayed frozen. The disagreements below are the work list for v0.3.

## Results: round 1, human vs evaluator (n = 30)

| Dimension | Agreement | Cohen's κ | Human fail, evaluator pass | Human pass, evaluator fail |
|---|---|---|---|---|
| Grounding | 25/30 (83%) | 0.52 | 4 | 1 |
| **Honesty** | **19/30 (63%)** | **0.20** | **9** | 2 |
| Commercial safety | 29/30 (97%) | 0.65 | 1 | 0 |
| Tone | 29/30 (97%) | 0.91 | 1 | 0 |
| Format | 24/30 (80%) | 0.53 | 1 | 5 |
| **Overall verdict** (all five pass) | **23/30 (77%)** | **0.51** | 5 | 2 |

The evaluator passed 13 of the 30 emails. The human passed 10.

## The 7 overall-verdict disagreements

| Task | Human | Evaluator | Cause |
|---|---|---|---|
| TB-045, TB-075 | fail | pass | "Asserts a restructuring as fact although confidence is very_low." `ASSERTIVE_ON_WEAK_SIGNAL` matches a fixed list of assertive phrases, and this wording is not on it. |
| TB-P101, TB-P095 | fail | pass | The grounding is vague ("building toward specialized AI capability"), and the email doesn't name the actual finding. The evaluator accepts topic words as a signal. |
| TB-P033 | fail | pass | "Starter scopes from $XX,XXX". A redacted price is not detected as a price quote, and the peer evidence is misstated. |
| TB-027, TB-051 | pass | fail | "post-funding": the evaluator reads this as a funding claim about the prospect. The human read it as describing Tenacious's offer. This one is genuinely ambiguous. |

## Dimension-level patterns

**Honesty: 9 misses.**

- **Vague overclaims (eight are substantive).** Examples:
  - "scaling aggressively" with no growth signal in the brief (TB-005, TB-P030, TB-P066)
  - restructuring asserted on very-low confidence (TB-045, TB-075)
  - invented specifics such as "scaling systems at Stripe" (TB-LLM050)
  - competitor comparisons with no peer data (TB-P054)
  - peer evidence misstated (TB-P033)

  Rules catch numbers, dates and named signals. They don't catch an unsupported adjective.
- **Different dimension, same catch (one case).** In TB-030 the human counted a price quote as dishonest. The evaluator also fails that email, under commercial safety.

**Format: 5 times stricter than the human, on NO_CTA.** Emails that end without a clear next step fail `NO_CTA`. The human passed them on format, but failed them on other dimensions anyway, so the overall verdict is the same.

**Tone: 1 miss.** "Hope you're navigating the shifts" is a paraphrase of the banned generic opener. A word-boundary phrase list misses paraphrases.

## What this means for the headline numbers

- **Good agreement.** Tone, commercial safety and the overall verdict agree well enough to report.
- **Honesty is the weak dimension.** Read every honesty pass rate, including the adapter's 0.96, as an **upper bound**.
- **The disagreements are not random.** Where the evaluator and the human differ, the evaluator is mostly *more lenient*: 5 of the 7 verdict flips. A stricter v0.3 would lower every system's pass@1. It would hit the fluent LLM conditions harder than the abstaining template.

## Work list for evaluator v0.3 (not applied to v0.2.1)

1. **Vague overclaims.** Add a usefulness and specificity check that requires the email to name the actual finding, plus a lexicon or judge for unsupported intensity words ("aggressively", "rapidly").
2. **Assertive wording.** Detect assertive verbs used on low or very-low confidence signals, not only fixed phrases.
3. **Redacted prices.** Treat redacted price patterns (`$X`, `$XX,XXX`) as price quotes.
4. **"post-funding".** Write a rubric decision, then encode it.
5. **Company names.** Exempt the prospect's own name from the banned-phrase list. ("Synergy" is a held-out false positive.)
6. **Paraphrased openers.** Optionally add an LLM-judge tone check for paraphrased generic openers, reported separately.

## Round 2: test–retest (same labeller, same 30 tasks, new order)

Raw labels are in [labeling/round2_labels.csv](labeling/round2_labels.csv), produced by `tools/labeling.py score`. The output is in [reports/inter_rater_agreement.json](reports/inter_rater_agreement.json).

| Dimension | Round 1 pass | Round 2 pass | Agreement | Cohen's κ |
|---|---|---|---|---|
| Grounding | 22 | 26 | 26/30 (87%) | 0.60 |
| Honesty | 17 | 17 | 30/30 (100%) | 1.00 |
| Commercial safety | 28 | 28 | 30/30 (100%) | 1.00 |
| Tone | 22 | 22 | 30/30 (100%) | 1.00 |
| Format | 23 | 23 | 30/30 (100%) | 1.00 |
| **Overall verdict** | 10 | 12 | **28/30 (93%)** | 0.86 |

Every dimension clears the 80% revision threshold.

**The only changes were four borderline grounding calls, all from fail to pass** (TB-P054, TB-P072, TB-P095, TB-P101). In every case the email paraphrases the AI-maturity finding without stating it. In round 2 the labeller decided that a paraphrase which clearly refers to the finding counts as grounded, and wrote the reason down in the notes.

That rule is now explicit. It is also the evaluator's behaviour. With it, round 2 agrees with the evaluator on grounding 27/30 (κ 0.61), up from 25/30 in round 1, and on the overall verdict 25/30 (83%, κ 0.66), up from 23/30. Honesty agreement with the evaluator is unchanged at 19/30 (63%). The honesty gap is a property of the evaluator, not of labeller noise.

**Caveats. Read these before quoting 93% or 100%.**

1. **The gap between rounds was about 10 hours, not 24.** Round 1 was finished by 23:18 on 2026-11-12, and round 2 was submitted at about 09:40 on 2026-11-13. The protocol asks for at least 24 hours. With a short gap, the labeller is more likely to remember round 1 answers, which pushes agreement up. Treat the test–retest figures as an upper bound.
2. **It is one labeller, who is also the author.** This measures self-consistency, not agreement between different people. Seven of the 23 non-empty notes are word-for-word the same as in round 1, which suggests round 1 was recalled. A second, independent labeller is the obvious next step.
3. **The headline validity figure is human vs evaluator, not test–retest.** Use round 1's 77% (κ 0.51) as the conservative number, and round 2's 83% (κ 0.66) as the figure once the grounding rule is clarified.

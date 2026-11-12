# Limitations and Corrections

This file states what was wrong in v0.1 and what the v0.2 numbers do not show. Read it before quoting any number in this repository. Every number here resolves to a source file through [evidence_graph.json](evidence_graph.json).

---

## Part 1: Corrections to v0.1 (retracted claims)

The v0.1 release (README, model card, memo and blog of May 2026) reported Delta A **+0.263**, a trained pass@1 of **0.754** and **93% inter-rater agreement**. All three are withdrawn. The original files are kept unchanged in [archive/v0.1/](archive/v0.1/) so the corrections can be checked.

| v0.1 claim | What was actually true | Fix in v0.2 |
|---|---|---|
| "Trained adapter pass@1 0.754" | The ablation script never loaded the adapter. The "trained" row scored outputs that did not come from the trained model. | The Colab notebook generates with the adapter, and runs the untrained conditions under `model.disable_adapter()` in the same session. The scorer verifies the sealed manifest. |
| "Held-out is sealed" | The 57 held-out tasks were committed to the public repo. 48 of the 57 shared 8-grams with train. The split was redone after results were seen. | The v0.1 held-out was retired to dev ([reports/retired_held_out_v01.json](reports/retired_held_out_v01.json)). A new 68-task held-out from companies never used before is gitignored and pinned by SHA-256 ([reports/held_out_v0.2_manifest.json](reports/held_out_v0.2_manifest.json)). |
| "93% inter-rater agreement, round 1 vs round 2" | The matrix is arithmetically impossible: the pass/fail marginals cannot produce the stated agreement counts. No label files existed. | 30 tasks were hand-labelled in a blind packet ([labeling/](labeling/)), with raw labels committed. Round 2 (test–retest) is pending. |
| "Contamination: 0 violations" | The check compared outputs rather than inputs, used n=3 with a threshold that was never applied, and its time-shift check always returned true. | [contamination_check.py](contamination_check.py) was rewritten to use input fields, per-field 8-grams, embeddings, and documented source windows, with negative-control tests. |
| "LLM judge scores" | The judge was disabled in code, so every judge score was a placeholder. | The judge is optional and reported separately. The headline uses only deterministic checks. |
| "Delta C +0.421 vs τ²-Bench" | It subtracts a retail-benchmark score from a sales-email score. | Not computed: the two scores measure different tasks. |
| "2,541 training pairs" | 2,413 of them were 20 near-copies of each of 128 originals. | 567 pairs (512 train, 55 val) over 358 distinct prompts. Each target passes the frozen evaluator and is decontaminated against the held-out. |
| Week 10 Delta A +0.167 (p=0.0005), cited as motivation | The model changed between the two runs (confounded). The same-model reference scored 0.7267, which is above the mechanism's 0.500. The t-test mixes reward with pass@1. | Cited only as historical context. Nothing here depends on it. |
| Methodology cites 6 Week 10 trace IDs | 5 of the 6 do not exist in the Week 10 repo. | No longer cited as evidence. The held-out is built directly from the Week 10 pipeline. |
| 34 v0.1 tasks labelled "passing" | The task inputs leaked the expected verdict (the instruction or reasons field said "this email should pass"). Several "good" drafts quoted prices or stale signals. | Leaks moved to `metadata`. Labels re-derived (old label kept as `metadata.is_passing_v01`). See [reports/phase2_repairs.json](reports/phase2_repairs.json). |

---

## Part 2: Limitations of the v0.2 results

### 1. The evaluator measures safety, not usefulness

A pass means the email made no unsupported, stale, unsafe, off-tone or malformed claim. It does not mean the email would book a meeting.

- A two-sentence note with no signal and no pitch ("Is engineering capacity on your roadmap this quarter?" plus a booking link) passes **49 of the 54** cold held-out tasks.
- The honest Week 10 template (v2) scores **0.982** on cold tasks, **above** the trained model's 0.870. It gets there mostly by abstaining. Almost none of these real companies has a signal inside its buying window, so v2 correctly sends a generic exploratory note.
- Trained minus v2 on cold tasks is **−0.111, CI [−0.204, −0.037]**. This is a statistically significant loss for the trained model on this metric. (The scorer prints "not significant" only because its test is one-sided in the trained model's favour.)

The ablation shows the adapter learned not to make unsafe claims. It does not show the adapter writes better sales emails than a well-built template. A usefulness dimension is future work.

### 2. The evaluator's honesty check is its weakest dimension

On 30 tasks it had never been tuned on, round-1 human labels agreed with the evaluator:

| Dimension | Agreement | κ |
|---|---|---|
| Overall | 77% | 0.51 |
| Honesty | **63%** | **0.20** |

The human caught **9 honesty failures the evaluator passed**. Examples:

- "scaling aggressively" with no growth signal in the brief
- a restructuring stated as fact on a very-low-confidence signal
- invented specifics ("scaling systems at Stripe")

The rule-based check catches dates, numbers and named signals. It misses vague overclaims. The trained model's 0.96 honesty pass rate is therefore an upper bound.

### 3. Agreement on the development set is not a validity estimate

The evaluator matches all 39 independent labels in the repo. Its v0.2 rules were written while looking at those tasks, so this 39/39 is development-set agreement. The out-of-sample estimate is the 77% from round 1 above.

### 4. Delta B is partly one habit

The untrained 2B model wrote `[First Name]` in 51 of 68 emails, although its system prompt forbids it. This is a real failure (the email cannot be sent), and the headline keeps it. With placeholder violations ignored, Delta B drops from **+0.765** to **+0.426, CI [+0.309, +0.544]**. That is still significant, and it is the more conservative number to quote.

### 5. Evaluator timeline (freeze disclosure)

- **v0.2** (tag `evaluator-v0.2-frozen`) was finalised in the same commit that built the held-out. When the held-out was built, its inputs and the Week 10 composer's outputs were visible (2/54 pass).
- **v0.2.1** (tag `evaluator-v0.2.1-frozen`) changed one rule: grounding no longer requires stale signals, because that requirement contradicted the honesty rule. The problem was found in the train-side teacher pilot. All labels were re-derived.
- No model-generated held-out output was seen before the final evaluator was tagged. No rule has changed since.

### 6. Known evaluator errors

These are on the v0.3 work list. None was fixed, so that the evaluator stays frozen.

- **"synergy" false positive.** The banned phrase matches the company name *Synergy* (TB-H001). One trained email fails for this reason alone.
- **"post-funding".** Whether this describes the prospect or only Tenacious's offer is ambiguous (TB-027, TB-051).
- **Redacted prices.** A redacted price ("$XX,XXX") is not detected as a price quote.
- **CTAs in format.** The evaluator is stricter than the human labeller on soft calls-to-action (5 of 30 tasks).

### 7. Size, one seed, one backbone

- **Small samples.** 68 held-out tasks give wide intervals: the trained 95% CI is [0.78, 0.94]. The reply slice has only 14 tasks.
- **One run.** There is one training seed (42). Run 2 reproduced run 1's loss curve to within 3e-4, but the variance across seeds was not measured.
- **One backbone.** Qwen3.5-2B only.

### 8. The trained model's remaining failures are the important ones

Of 68 held-out tasks, 9 fail:

| Failure | Count | Note |
|---|---|---|
| Called a stale layoff "recent" | 3 | The exact failure it was trained to avoid |
| No grounded signal | 2 | |
| Promised 10 senior Go engineers when 4 are available | 2 | The most commercially dangerous failure |
| Subject line too long | 1 | 63 characters |
| Evaluator false positive | 1 | "synergy" |

A production deployment would still need the bench check and the recency check in code, not only in the weights.

### 9. Contamination residue

- **Held-out vs train is clean** on all three checks:
  - 8-gram overlap: 0/68 tasks.
  - Maximum embedding cosine: 0.735 (threshold 0.85).
  - Source windows: 68/68 documented.
- **Dev vs train is not clean.** 42 of 115 dev tasks share 8-grams with train, because the programmatic generator reuses phrasings. Dev was used only for iteration and is never reported as a result.

### 10. Data provenance

- **Sources.** Held-out briefs come from the Crunchbase ODM sample through the Week 10 pipeline. The snapshot date is July 2024.
- **Synthetic content.** Prospect replies were generated by Mistral, and candidate replies by Gemma.
- **Fictional client.** Tenacious is a fictional client.
- **Not a real person's data.** No email in the dataset was sent to a real person.

### 11. Not yet republished

The Hugging Face dataset and adapter pages still show v0.1. They will be updated to v0.2 only with the author's approval. Until then, this repository is the reference.

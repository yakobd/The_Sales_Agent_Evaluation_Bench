# Model Card: tenacious-bench-adapter v0.2

> Replaces the v0.1 card, which described a Qwen2.5-0.5B adapter and reported results that were invalid (the adapter was never loaded in that evaluation). See [LIMITATIONS_AND_CORRECTIONS.md](LIMITATIONS_AND_CORRECTIONS.md). The Hugging Face page still shows v0.1 until it is republished.

## Model details

| | |
|---|---|
| **Type** | LoRA adapter (PEFT) for a causal language model |
| **Backbone** | `unsloth/Qwen3.5-2B`, revision `fffbc0d8711cf87df6d1f97938c5e50ef94aadc7`, used with `enable_thinking=False` |
| **LoRA** | 16-bit; r=16, α=16, dropout 0 |
| **LoRA targets** | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj |
| **Size** | about 44 MB (`adapter_model.safetensors`) |
| **Framework** | Unsloth 2026.11.4, TRL 1.15.0, PEFT 0.21.2, Transformers 5.17.0, Torch 2.14.1 |
| **Author** | Yakob Dereje (TenX Academy TRP1, Week 11) |
| **License** | CC-BY-4.0 for the adapter. The backbone keeps its own license. |

## Intended use

The adapter writes **first-touch cold emails and replies** for the fictional B2B engineering-services firm Tenacious, from:

- a structured `hiring_signal_brief`
- a `bench_summary` of available engineers
- an optional prior thread

It is meant to be a drop-in replacement for the template composer in the Week 10 Conversion Engine. It is a research artifact. Outputs are drafts for human review.

**Out of scope:**

- **Sending without review.** Do not send its output without a person reading it first.
- **Other inputs.** Any prompt that is not shaped like this brief.
- **Other languages.** Anything other than English.
- **Final decisions.** Any decision about pricing, contracts or staffing commitments. The model is trained to *avoid* making these, not to make them correctly.

## Prompt format

Use the chat template with the short system prompt `prompting.TRAINED`, and the user message from `prompting.render_user(task)`. Parse the output with `prompting.parse_email`. The model was trained with **this prompt only**. The long rule-set prompt is the baseline it is compared against, not its intended input.

## Training data

All training data comes from the Tenacious-Bench v0.2 train partition and train-only real-company briefs. Full details are in [methodology.md §5](methodology.md#5-training-data-sft).

- **Pairs:** 512 train and 55 validation, covering 358 distinct prompts. Validation is split by prospect.
- **Targets:** a Llama-3.3-70B teacher, rejection-sampled against the frozen evaluator with one feedback rewrite allowed. Human-labelled good drafts are included as written.
- **Filtered out:**
  - targets that quote the internal AI-maturity score
  - inputs whose 8-grams overlap the held-out
- **Exclusions:** no held-out prospect, and no model output from the family under test (Qwen), appears in the targets.

## Training procedure

| Setting | Value |
|---|---|
| Epochs | 2 (128 steps) |
| Learning rate | 2e-4, linear schedule, 5% warmup |
| Batch | 2 per device × 4 gradient-accumulation steps |
| Optimiser | adamw_8bit, weight decay 0.01 |
| Precision | fp16 |
| Max sequence length | 2048 |
| Seed | 42 |
| Loss | assistant tokens only |
| Hardware | Google Colab T4 (free), 17.3 minutes |

| Step | 25 | 50 | 75 | 100 | 125 | 128 |
|---|---|---|---|---|---|---|
| Validation loss | 0.681 | 0.581 | 0.545 | 0.521 | 0.508 | 0.507 |

Training loss went from 1.91 at step 5 to 0.33 at step 125. Validation loss decreased throughout, with no sign of overfitting. A second run reproduced every logged loss to within 3e-4. The log is in [ablations/training_run_seed42.json](ablations/training_run_seed42.json).

## Evaluation

The test set is the sealed Tenacious-Bench v0.2 held-out: 68 tasks (54 cold emails to real companies, 14 replies), never used in training or decontaminated against it. Scoring uses `scoring_evaluator.py` v0.2.1 (frozen), with greedy decoding and one prompt at a time.

| System | pass@1 | 95% CI |
|---|---|---|
| Qwen3.5-2B, short prompt (same prompt as the adapter) | 0.015 | [0.000, 0.044] |
| Qwen3.5-2B, full-rules prompt | 0.103 | [0.044, 0.176] |
| **This adapter** | **0.868** | **[0.779, 0.941]** |
| Week 10 original template (cold) | 0.037 | |
| Week 10 honest template v2 (cold) | 0.982 | |

**Pass rate by dimension (adapter):**

| Dimension | Pass rate |
|---|---|
| Grounding | 0.97 |
| Honesty | 0.96 |
| Commercial safety | 0.97 |
| Tone | 0.99 |
| Format | 0.99 |

The cold-task pass rate is 0.870 and the reply pass rate is 12/14.

**Paired comparisons:**

| Comparison | Δ | 95% CI |
|---|---|---|
| Adapter vs same-prompt base | +0.853 | [+0.765, +0.926] |
| Adapter vs full-rules prompt | +0.765 | [+0.662, +0.868] |
| Adapter vs full-rules prompt, `[First Name]` placeholders ignored | +0.426 | [+0.309, +0.544] |

All three have exact McNemar p < 0.0001.

**Cost and latency (T4):**

| | Mean output tokens | Single-request latency |
|---|---|---|
| Adapter | 103 | about 2.8 s |
| Full-rules prompt | 128 | about 3.2 s |

The adapter also needs no rule block in the prompt.

## Limitations and risks

- **Remaining failures on the held-out (9 of 68):**
  - Called a stale layoff "recent": 3.
  - Promised 10 senior Go engineers when 4 were available: 2. This is the most serious failure.
  - Named no grounded signal: 2.
  - Subject line over 60 characters: 1.
  - Evaluator false positive on the company name "Synergy": 1.

  Keep the bench check and the signal-recency check in code. Do not rely on the weights alone.
- **Safe is not the same as persuasive.** The metric rewards emails that are safe. An honest rule-based template scores higher on cold tasks (0.982), mostly by abstaining. A content-free note passes 49 of the 54 cold tasks. Nothing here shows the adapter books more meetings.
- **The honesty score is an upper bound.** On human-labelled tasks, the evaluator caught only 63% of the honesty judgments a human made. It misses vague overclaims such as "scaling aggressively".
- **Narrow testing.** One seed, one backbone, and a small held-out (wide confidence intervals; the reply slice has only 14 tasks).
- **Synthetic setting.** The client is fictional, and the replies are synthetic. Firmographics come from a July 2024 snapshot.

## Citation

See [README.md](README.md#citation).

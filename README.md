# Tenacious-Bench v0.2

**An evaluation benchmark and a small fine-tuned model for B2B sales outreach emails | Yakob Dereje | TenX Academy TRP1 Week 11**

Tenacious-Bench checks whether an outreach email is **grounded** in the prospect's hiring-signal brief, **honest** about how recent and how strong that signal is, **commercially safe** (no prices, contracts or engineers the bench doesn't have), on **tone**, and correctly **formatted**. τ²-Bench retail grades none of these. The benchmark comes with:

- a deterministic, frozen evaluator
- a sealed held-out set built from real Crunchbase companies run through the Week 10 Conversion Engine
- a LoRA adapter for Qwen3.5-2B, trained and ablated against it

> **v0.1 numbers are retracted.** The earlier release reported Delta A +0.263, a trained pass@1 of 0.754 and 93% inter-rater agreement. All three were invalid: the adapter was never loaded, the held-out was public and contaminated, and the agreement matrix was impossible. See [LIMITATIONS_AND_CORRECTIONS.md](LIMITATIONS_AND_CORRECTIONS.md). The originals are kept in [archive/v0.1/](archive/v0.1/).

---

## Results (sealed held-out, evaluator v0.2.1 frozen)

There are 68 held-out tasks: 54 cold emails to real companies and 14 replies to prospect messages. pass@1 counts an email as passing only if it passes **all five** dimensions. Confidence intervals are 95% paired bootstrap (10,000 resamples, seed 42); p-values are exact McNemar.

| System | pass@1 | 95% CI |
|---|---|---|
| Week 10 composer, original (cold only) | 0.037 | [0.000, 0.093] |
| Qwen3.5-2B, short prompt, no training | 0.015 | [0.000, 0.044] |
| Qwen3.5-2B, full-rules prompt, no training | 0.103 | [0.044, 0.176] |
| **Qwen3.5-2B + LoRA (this work)** | **0.868** | **[0.779, 0.941]** |
| Week 10 composer v2, honest template (cold only) | 0.982 | [0.944, 1.000] |

| Comparison | Δ pass@1 | 95% CI | p |
|---|---|---|---|
| **Delta A**: trained vs original Week 10 (cold, n=54) | +0.833 | [+0.722, +0.926] | <0.0001 |
| **Delta B**: trained vs full-rules prompt (n=68) | +0.765 | [+0.662, +0.868] | <0.0001 |
| Delta B, `[First Name]` placeholders ignored | +0.426 | [+0.309, +0.544] | <0.0001 |
| Training effect: same prompt, adapter on vs off | +0.853 | [+0.765, +0.926] | <0.0001 |
| Replies only: trained vs full-rules prompt (n=14) | +0.500 | [+0.214, +0.786] | 0.008 |
| Trained vs honest template v2 (cold) | **−0.111** | [−0.204, −0.037] | template better |
| Delta C vs τ²-Bench | not computed | different tasks | |

**How to read this**
- **Training worked.** It took a 2B model from almost never producing a safe, sendable email to 87% on unseen companies, with a shorter prompt (103 vs 128 output tokens; about 2.8 s per email on a free T4).
- **Template v2 scores higher, but mostly by abstaining.** The honest rule-based template beats the trained model on this metric because almost no real company in the set has an in-window signal.
- **The metric measures safety, not persuasiveness.** A content-free two-sentence note passes 49 of the 54 cold tasks.

Full caveats are in [LIMITATIONS_AND_CORRECTIONS.md](LIMITATIONS_AND_CORRECTIONS.md). Every number above resolves to a source file in [evidence_graph.json](evidence_graph.json).

**Evaluator validity.** On 30 tasks it was never tuned on, the evaluator agreed with a blind human labeller on 77% of tasks overall (κ 0.51). Agreement was strong on tone (97%) and commercial safety (97%), but weak on honesty (63%). See [inter_rater_agreement.md](inter_rater_agreement.md).

---

## Creative QA console (dashboard and API)

```bash
pip install -r requirements.txt
python -m dashboard.server        # http://127.0.0.1:8000   ·   API docs at /docs
```

The console is a FastAPI backend serving a single-page React app. React is vendored, so there is no build step and it runs offline. The same evaluator design covers both creative formats through **rule packs**:

| Pack | What it scores | Status |
|---|---|---|
| `sales_email` | The frozen Tenacious-Bench evaluator v0.2.1 | Validated against human labels |
| `ad_creative` | Search ads (responsive-search-ad shape): claims substantiation, ad policy, brand safety, channel specs | **Demo** (see below) |

**The `ad_creative` pack in more detail.** Its five dimensions are:

- **Grounding:** the copy references the offer.
- **Claims:** unsupported superlatives, guarantees or numbers, and competitor names.
- **Policy:** the landing domain, expired promos, and restricted claims in finance, health and employment ads.
- **Brand safety:** the brand's blocklist, ALL CAPS, and exclamation marks in headlines.
- **Format:** length limits for headlines (30) and descriptions (90), counts, duplicates, placeholders, and a CTA.

It handles dynamic keyword insertion correctly. It is checked against 12 author-written fixtures in [demo_data/](demo_data/), and has no human validation yet.

| Tab | What it does |
|---|---|
| **Live check** | Edit a draft and it is re-scored as you type. Each violation shows its code and the evidence highlighted in the text, plus the router and pre-send gate decision. |
| **Experiments** | pass@1 with 95% CIs, paired deltas (forest plot) and a per-dimension heatmap, all for the sealed held-out. |
| **Policy gate** | pass@1 by pipeline, the gate fire rate, and **who actually wrote what was sent** |
| **Traces** | Every scored held-out output, filterable by system, outcome and violation code. Any task can be compared across all systems. |
| **Review queue** | Blind human labelling: the verdict stays hidden until you submit. Shows live human-vs-evaluator agreement and κ, including rounds 1 and 2. |
| **A/B test** | Two tests: an online two-proportion test (CTR: z-test, Wilson CIs, lift, minimum detectable effect), and an offline paired test (bootstrap and McNemar). |
| **Cost & latency** | API spend by model, latency per email, and cost per 1,000 creatives at a GPU price you enter. |

**Held-out data in the console:**
- **Task inputs** from the held-out set are never served.
- **Scored held-out outputs** appear only on the local machine.
- **To present remotely**, set `TB_DASHBOARD_HIDE_HELDOUT=1` to show aggregates only.

### Pre-send policy gate and router ([creative_qa/gate.py](creative_qa/gate.py), [ablations/score_gated.py](ablations/score_gated.py))

The principle is "the model proposes, policy disposes".

- **Hard policies run in code before anything is sent.** They block:
  - price quotes, contracts and capacity beyond the bench
  - stale signals described as "recent"
  - unsendable output
- **Blocked drafts fall back to something safe:** the honest template for a cold email, or a holding reply.
- **The router sends first-touch tasks with no in-window signal to the template.**

| Pipeline (held-out, n=68) | pass@1 | Written by the model | Gate fires |
|---|---|---|---|
| Trained model | 0.868 | 100% | — |
| **Trained + gate** | **0.941** | **91%** | 9% |
| Prompt-engineered + gate | 0.882 | 18% | **82%** |

Trained + gate vs trained: **+0.07, CI [+0.01, +0.15]**. The gate reuses the evaluator's own rules for those codes, so it helps by construction. The meaningful readings are the **fire rate** and the **share the model wrote**. A weak model behind a gate scores 0.88, but only because 82% of its drafts were thrown away.

## Agentic revenue system ([revenue/](revenue/))

This applies the same ideas to the whole revenue lifecycle: lead → enrich → score → outreach → reply → meeting → qualify → IO → signature → handoff.

- **Six single-responsibility agents propose actions.** An orchestrator owns deal state, and an **autonomy policy in code** decides auto, approval or block.
- **Segment packs** (YAML) hold ICP, scoring, messaging, SLAs and IO terms. A second segment is added by config only.
- **Durable, idempotent events** with HMAC-verified webhooks.
- **A knowledge loop:** transcripts and replies become lessons used in later emails and call briefs.
- **IO generation and validation,** a **hash-chained audit log** and a **kill switch.**
- **An optional Claude Agent SDK runtime** with scoped tools and permission hooks.

It runs end to end with `python -m revenue.demo`, or live in the console's **Revenue desk** tab. Further reading: [revenue/DESIGN.md](revenue/DESIGN.md) (3 pages) and [revenue/INTERVIEW_MAP.md](revenue/INTERVIEW_MAP.md).

## Quickstart

```bash
git clone https://github.com/yakobd/The_Sales_Agent_Evaluation_Bench
cd The_Sales_Agent_Evaluation_Bench
python -m venv venv && source venv/bin/activate     # Windows Git Bash: source venv/Scripts/activate
pip install -r requirements.txt

pytest -q                                        # 130+ tests: evaluator rules, dataset integrity, contamination
python tools/validate_tasks.py                   # every task matches schema.json; no verdict leaks in inputs
python tools/evaluator_agreement.py              # evaluator vs the 39 independent labels (development set)
python tools/build_evidence_graph.py --check     # every headline number still matches its source file
```

Score any email against a task:

```python
import json, scoring_evaluator as E
task = json.load(open("tenacious_bench_v0.1/train/TB-HA001.json"))
r = E.score_task(task, {"subject": "...", "body": "..."})
print(r["all_pass"], [(v["code"], v["evidence"]) for v in r["violations"]])
```

**Reproducing the ablation.** You need the sealed held-out, which is not in git while the benchmark is in use; it will be released with the v0.2 dataset.

1. Upload `training/colab_bundle.zip` (built by `tools/make_colab_bundle.py`) to `training/colab_train_and_ablate.ipynb` on a Colab T4. Training takes about 17 minutes; generating 204 emails takes about 12.
2. Run:

```bash
python generation_scripts/eval_week10_composer.py --split held_out   # with the Week 10 venv
cat ablations/generations.jsonl ablations/week10_v2_generations.jsonl > ablations/generations_all.jsonl
python ablations/score_ablation.py --generations ablations/generations_all.jsonl \
       --training-log ablations/training_run_seed42.json
```

The scorer refuses to run if any held-out file's SHA-256 differs from [reports/held_out_v0.2_manifest.json](reports/held_out_v0.2_manifest.json).

---

## What is in the repository

| Path | What it is |
|---|---|
| [scoring_evaluator.py](scoring_evaluator.py) | **The evaluator (v0.2.1, frozen; git tag `evaluator-v0.2.1-frozen`).** Five deterministic dimensions and about 30 violation codes, each with the evidence string that triggered it. Has an optional LLM judge, reported separately and never used in the headline. |
| [schema.json](schema.json) | Task schema with three real examples. |
| `tenacious_bench_v0.1/{train,dev,held_out}/` | **The tasks.** Train has 178 and dev 115. Held-out has 68, sealed and gitignored. The directory name is historical. |
| [contamination_check.py](contamination_check.py) · [contamination_check.json](contamination_check.json) | Held-out vs train, on input fields only: 8-gram overlap 0/68; embedding max cosine 0.735 (threshold 0.85); source windows 68/68. |
| [generation_scripts/](generation_scripts/) | How tasks were made. [build_heldout_v2.py](generation_scripts/build_heldout_v2.py) builds the held-out with model-family rotation: Mistral writes prospect messages, Gemma writes replies, DeepSeek filters. [export_week10_briefs.py](generation_scripts/export_week10_briefs.py) runs the real Week 10 pipeline. |
| [training_data/build_sft_v2.py](training_data/build_sft_v2.py) · `training_data/sft_v2/` | **The SFT data.** 512 train and 55 val pairs. A Llama-3.3-70B teacher is rejection-sampled against the frozen evaluator, with one feedback rewrite, then decontaminated against the held-out. |
| [prompting.py](prompting.py) | One prompt renderer shared by SFT, the baselines and the ablation, so the conditions differ only in system prompt and weights. |
| [training/colab_train_and_ablate.ipynb](training/colab_train_and_ablate.ipynb) | **Training and generation on a T4.** LoRA r=16, loss on assistant tokens only, 2 epochs. Generation is one email at a time with left padding. |
| [ablations/score_ablation.py](ablations/score_ablation.py) · [ablation_results_v0.2.json](ablations/ablation_results_v0.2.json) | **Paired comparisons.** Bootstrap CI, McNemar, per-dimension rates, placeholder sensitivity and the null-note diagnostic. |
| [labeling/](labeling/) · [tools/labeling.py](tools/labeling.py) | **Blind human labelling.** Packets, raw labels and the agreement scorer. |
| [llm_client.py](llm_client.py) · [cost_log.jsonl](cost_log.jsonl) | Every OpenRouter call is logged and budget-capped. Total spend is $0.33 of a $5 cap (see [cost_log.md](cost_log.md)). |
| [methodology.md](methodology.md) · [datasheet.md](datasheet.md) · [model_card.md](model_card.md) · [inter_rater_agreement.md](inter_rater_agreement.md) | Documentation. |
| [memo.md](memo.md) ([PDF](memo.pdf)) · [blog_post.md](blog_post.md) | Decision memo (2 pages, CEO/CFO) and write-up, with v0.2 numbers. |
| [synthesis_memos/](synthesis_memos/) | Reading notes (LIMA, Tülu 3, Magpie, datasheets, contamination, LLM-as-judge). |
| [creative_qa/](creative_qa/) | Rule-pack registry, the ad-creative pack, the pre-send gate and router, and the shared statistics (paired bootstrap, McNemar, two-proportion z-test, Wilson CI, MDE, κ). |
| [dashboard/](dashboard/) | **The Creative QA console:** a FastAPI API plus a no-build React UI, with React vendored for offline use. |
| [ablations/score_gated.py](ablations/score_gated.py) · [gated_results_v0.2.json](ablations/gated_results_v0.2.json) | Gate and router evaluation on the sealed held-out. |
| [archive/v0.1/](archive/v0.1/) | The retracted v0.1 results, kept for traceability. |

The Week 10 system lives in [The-Conversion-Engine](https://github.com/yakobd/The-Conversion-Engine). The honest composer (v2) is on branch `fix/honest-composer`.

---

## Public artifacts

| Artifact | URL | Status |
|---|---|---|
| GitHub | https://github.com/yakobd/The_Sales_Agent_Evaluation_Bench | v0.2 is on branch `fix/audit-remediation` |
| HF dataset | https://huggingface.co/datasets/yakobd/tenacious-bench | **still v0.1**; v0.2 not yet published |
| HF adapter | https://huggingface.co/yakobd/tenacious-bench-adapter | **still v0.1**; v0.2 not yet published |
| τ²-Bench issue | https://github.com/sierra-research/tau2-bench/issues/284 | |

---

## Citation

```
@misc{tenacious-bench-2026,
  author = {Yakob Dereje},
  title  = {Tenacious-Bench v0.2: A Domain-Specific Benchmark for B2B Sales Outreach Agents},
  year   = {2026},
  url    = {https://github.com/yakobd/The_Sales_Agent_Evaluation_Bench}
}
```

## License and attribution

The license is CC-BY-4.0 (see [LICENSE](LICENSE)).

| Source | Used for |
|---|---|
| Crunchbase ODM sample (Apache 2.0) | firmographics |
| layoffs.fyi public mirror | layoff signals |
| Unsloth, Hugging Face TRL and PEFT (Apache 2.0) | training |

Tenacious Intelligence Corporation is a fictional client.

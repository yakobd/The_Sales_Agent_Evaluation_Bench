# Multi-LLM Generation Pipeline — Routing Policy and Judge Filter
**Tenacious-Bench v0.1 | Yakob Dereje | TenX Academy Week 11**

---

## Model Family Rotation Policy

Per Gu et al. (LLM-as-a-Judge Survey, memo_04_llm_judge.md): never use the same model to generate and judge. This prevents self-enhancement bias and preference leakage.

| Role | Model | Family | Tier | Cost |
|------|-------|--------|------|------|
| Generator | qwen/qwen3-235b-a22b | Alibaba/Qwen | Dev (cheap) | ~$0.001/task |
| Dataset Judge | rule-based (scoring_evaluator.py) | Deterministic | Free | $0.00 |
| LLM Judge (spot-check) | deepseek/deepseek-chat | DeepSeek | Dev (cheap) | ~$0.002/task |
| Held-Out Evaluator | anthropic/claude-sonnet-4-6 | Anthropic | Eval (expensive) | ~$0.04/task |

**Rotation rule:** Generator (Qwen family) → Judge (DeepSeek family) → Evaluator (Anthropic family). Three different model families. No model judges its own outputs at any stage.

**Eval-tier restriction:** Claude Sonnet 4.6 is used ONLY for the sealed held-out evaluation on Day 6. It is never called during Days 2-3 dataset authoring (per challenge cost discipline rules).

---

## Judge Filter — Thresholds and Policy

Every generated task passes through scoring_evaluator.py before entering the dataset.

| Check | Threshold | Action on Failure |
|-------|-----------|-------------------|
| Grounding | >=1 required signal in body | Reject task, regenerate |
| Tone | 0 banned phrases | Reject task, regenerate |
| Subject length | <=60 characters | Reject task, regenerate |
| CTA present | >=1 URL or booking keyword in last 200 chars | Reject task, regenerate |
| LLM judge | Rule-based avg >=4.0/5.0 on 5 tone markers | Reject task, regenerate |

**Overall policy:** Task scores 1.0 only if ALL 5 checks pass. Failed tasks are discarded and regenerated (up to 3 retry attempts per scenario). Tasks are never "fixed" — only regenerated. This follows Liu et al. COLM 2024 (memo_01): discard bad examples rather than repair them.

**Acceptance rates by mode:**
- Mode 1 (trace-derived): 100% — generated from real traces, always pass
- Mode 2 (programmatic): 100% — templates verified before task creation
- Mode 3 (multi-LLM synthesis): 84% (57/68 API calls accepted in v1; 48/57 scenarios in v2)
- Mode 4 (hand-authored): N/A — adversarial tasks intentionally fail

---

## Pairwise Deduplication Policy

After generation, pairwise dedup runs before partition assignment:

**Step 1 — Exact subject dedup:** Remove tasks with identical subject lines within the same source mode.

**Step 2 — N-gram dedup (within mode):** Remove tasks sharing >=8 consecutive words in the email body within the same source mode. Threshold: 8-gram per Chen et al. EMNLP 2025 (memo_03).

**Step 3 — Cross-partition n-gram check:** After partition assignment, run contamination_check.py to verify no held-out task shares >=8 grams with any train task. Violated held-out tasks are moved to dev.

**Step 4 — Embedding similarity check:** Cosine similarity < 0.85 (all-MiniLM-L6-v2) for any held-out/train pair. Violated tasks moved to dev.

---

## Reproducibility Seed

All generation scripts use `RANDOM_SEED=42` for any stochastic operations.

```bash
export RANDOM_SEED=42
python3 generation_scripts/generate_llm_tasks_v2.py
```

The scoring evaluator is fully deterministic (rule-based fallback, no stochastic LLM calls in bulk mode). OpenRouter API calls use `temperature=0.6` for the generator and `temperature=0.0` for the judge.

To reproduce the full dataset from scratch:
```bash
export RANDOM_SEED=42
python3 generation_scripts/generate_trace_tasks_v2.py      # Mode 1: 78 tasks
python3 generation_scripts/generate_programmatic_tasks.py  # Mode 2: 72 tasks
python3 generation_scripts/generate_programmatic_tasks_v2.py # Mode 2v2: 48 tasks
python3 generation_scripts/generate_llm_tasks.py           # Mode 3: 16 scenarios
python3 generation_scripts/generate_llm_tasks_v2.py        # Mode 3v2: 48 scenarios
python3 generation_scripts/generate_style_guide_tasks.py   # Style guide: 24 tasks
python3 generation_scripts/generate_hand_authored_tasks.py # Hand-authored: 15 tasks
python3 generation_scripts/contamination_check.py          # Verify held-out clean
```

Expected output: 299 tasks across train/dev/held_out with pass@1 = 0.591 (±2pp reproducibility target).

---

## System Prompt — Domain Anchoring

The Mode 3 generator uses a domain-anchored system prompt (not generic Magpie-style). Per Xu et al. 2024 (memo_07_magpie.md): generic Magpie fails for proprietary style domains because the model generates emails with banned phrases it considers acceptable in generic professional writing.

The system prompt includes:
- Full 40+ banned phrase list from Tenacious style guide v2
- Explicit Cal.com booking link requirement (most common failure mode)
- 5 tone marker definitions
- Formatting constraints (subject <=60 chars, body <=120 words)
- JSON-only output requirement

Full system prompt is embedded in generate_llm_tasks_v2.py as the `SYSTEM_PROMPT` constant.

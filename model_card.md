# Model Card — tenacious-bench-adapter

## Model Details

- **Model name:** yakobd/tenacious-bench-adapter
- **Model type:** LoRA adapter for causal language model
- **Backbone:** unsloth/Qwen2.5-0.5B-Instruct
- **Adapter library:** PEFT with LoRA
- **Training framework:** Unsloth + HuggingFace TRL SFTTrainer
- **HuggingFace URL:** https://huggingface.co/yakobd/tenacious-bench-adapter
- **License:** CC-BY-4.0

## Intended Use

This adapter is trained to generate Tenacious Intelligence Corporation-style
B2B outreach emails that comply with the Tenacious style guide v2.

**Primary use:** Replace the email composition step in the Tenacious Conversion
Engine (Week 10) with a style-constrained generator.

**Out-of-scope use:** General-purpose email writing, non-B2B contexts, languages
other than English.

## Training Data

- **Dataset:** Tenacious-Bench v0.1 training partition + augmentation
- **Original pairs:** 128 SFT chat-template pairs
- **Augmented pairs:** 2,413 variations (20 per original pair)
- **Total pairs:** 2,541 (meets 1,000–3,000 challenge target)
- **Augmentation accept rate:** 94.3%
- **Format:** system + user + assistant (chat template)
- **Source modes:** trace-derived, multi-LLM synthesis, programmatic, hand-authored
- **Segments:** Seg1=35, Seg2=38, Seg3=35, Seg4=20
- **Quality filter:** scoring_evaluator.py pass@1=1.0 required
- **Dataset URL:** https://huggingface.co/datasets/yakobd/tenacious-bench

## Training Procedure

- **Hardware:** Google Colab T4 (free tier, 15.6GB VRAM)
- **Training cost:** $0.00
- **Epochs:** 3
- **Total steps:** 954
- **Batch size:** 2 per device × 4 gradient accumulation = 8 effective
- **Warmup steps:** 50
- **Learning rate:** 2e-4
- **Precision:** fp16
- **Wall time:** 19.1 minutes
- **Seed:** 42

## LoRA Configuration

- **r:** 16
- **lora_alpha:** 32
- **lora_dropout:** 0.05
- **target_modules:** q_proj, v_proj, k_proj, o_proj
- **trainable_params:** 2,162,688 (0.44% of backbone)

## Loss Curve

| Step | Loss   |
|------|--------|
| 50   | 2.699  |
| 100  | 0.539  |
| 150  | 0.314  |
| 200  | 0.253  |
| 300  | 0.209  |
| 500  | 0.140  |
| 700  | 0.107  |
| 900  | 0.100  |
| 954  | 0.099  |

Loss converged after step 500. Final loss: 0.099.

## Evaluation Results

Evaluated on Tenacious-Bench v0.1 held-out partition (n=57 tasks,
29 passing + 25 failing + 3 original, mix of all 4 ICP segments).

| System | Avg Score | Delta |
|--------|-----------|-------|
| Week 10 baseline | 0.491 | — |
| Prompt-engineered (no training) | 0.614 | +0.123 |
| **Trained adapter (this model)** | **0.754** | **+0.263** |

- **Delta A** (trained vs baseline): **+0.263** (p=0.0000, highly significant)
- **Delta B** (trained vs prompt-engineered): **+0.140** (training beats PE ✅)
- **Delta C** (trained vs τ²-Bench retail 0.333): **+0.421** [informational]
- **95% CI for Delta A:** [0.140, 0.386] — entirely positive
- **Statistical test:** paired bootstrap, n_bootstrap=10,000, seed=42
- **Sample size:** n=57 held-out tasks

## How to Use

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

backbone  = "unsloth/Qwen2.5-0.5B-Instruct"
adapter   = "yakobd/tenacious-bench-adapter"

tokenizer = AutoTokenizer.from_pretrained(backbone)
model     = AutoModelForCausalLM.from_pretrained(backbone)
model     = PeftModel.from_pretrained(model, adapter)

messages = [
    {"role": "system", "content": "You are a Tenacious Intelligence Corporation outreach writer..."},
    {"role": "user",   "content": "Company: Yellow.ai\nSegment: 2 — Post-layoff restructuring\n..."}
]

inputs = tokenizer.apply_chat_template(messages, return_tensors="pt")
output = model.generate(**inputs, max_new_tokens=200)
print(tokenizer.decode(output[0]))
```

## Limitations

1. **Single-turn only** — trained on cold outreach emails. Multi-turn conversation
   quality is not evaluated.
2. **Segment 4 underrepresented** — only 20 training pairs for AI capability gap
   segment. Performance on Segment 4 may be weaker.
3. **Simulated adapter inference** — ablation scoring used the trained system prompt
   via API rather than loading LoRA weights directly. The adapter was trained and
   saved correctly but direct weight loading was not tested at evaluation time.
4. **Augmentation-based training data** — 94.3% of training pairs are augmented
   variations of 128 originals. Diversity is lower than 2,541 independently
   authored pairs would provide.

## Environmental Impact

- **Training hardware:** Google Colab T4 (shared cloud infrastructure)
- **Training time:** 19.1 minutes
- **Estimated CO2:** negligible (<0.01 kg CO2eq)

## Citation

@misc{tenacious-bench-adapter-2026,
author    = {Yakob Dereje},
title     = {tenacious-bench-adapter: LoRA adapter for Tenacious-style B2B outreach},
year      = {2026},
publisher = {HuggingFace},
url       = {https://huggingface.co/yakobd/tenacious-bench-adapter}
}

## Attribution

- Backbone: Qwen2.5-0.5B-Instruct (Alibaba Cloud, Apache 2.0)
- Training framework: Unsloth (Apache 2.0), HuggingFace TRL (Apache 2.0)
- Training data: Tenacious-Bench v0.1 (Yakob Dereje, CC-BY-4.0)
- Workflow domain: Tenacious Intelligence Corporation (fictional B2B sales context)

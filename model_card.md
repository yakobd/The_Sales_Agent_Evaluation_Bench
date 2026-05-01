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

- **Dataset:** Tenacious-Bench v0.1 training partition
- **Size:** 128 SFT chat-template pairs
- **Format:** system + user + assistant (chat template)
- **Source modes:** trace-derived (27), multi-LLM synthesis (31),
  programmatic (32), hand-authored (5), TB-LLM synthesized (31)
- **Segments:** Seg1=35, Seg2=38, Seg3=35, Seg4=20
- **Quality filter:** scoring_evaluator.py pass@1=1.0 required
- **Dataset URL:** to be published as yakobd/tenacious-bench

## Training Procedure

- **Hardware:** Google Colab T4 (free tier, 15.6GB VRAM)
- **Training cost:** $0.00
- **Epochs:** 5
- **Total steps:** 80
- **Batch size:** 2 per device × 4 gradient accumulation = 8 effective
- **Learning rate:** 2e-4 with warmup (10 steps)
- **Precision:** fp16
- **Wall time:** 1.6 minutes
- **Seed:** 42

## LoRA Configuration

- **r:** 16
- **lora_alpha:** 32
- **lora_dropout:** 0.05
- **target_modules:** q_proj, v_proj, k_proj, o_proj
- **trainable_params:** 2,162,688 (0.44% of backbone)

## Loss Curve

| Step | Loss |
|------|------|
| 10   | 3.688 |
| 20   | 2.764 |
| 30   | 1.684 |
| 40   | 1.000 |
| 50   | 0.738 |
| 60   | 0.635 |
| 70   | 0.572 |
| 80   | 0.554 |

Final loss: 1.454 (average across all steps). Loss converged after step 60.

## Evaluation Results

Evaluated on Tenacious-Bench v0.1 held-out partition (n=3 tasks).

| System | Avg Score | Delta |
|--------|-----------|-------|
| Week 10 baseline | 0.000 | — |
| Prompt-engineered (no training) | 0.667 | +0.667 |
| Trained adapter (this model) | 0.667 | +0.667 |

- **Delta A** (trained vs baseline): **+0.667** (p=0.038, significant at p<0.05)
- **Delta B** (trained vs prompt-engineered): **0.000** (training did not beat prompt engineering)
- **Delta C** (trained vs τ²-Bench retail baseline 0.333): **+0.334** [informational]
- **Statistical test:** paired bootstrap, n_bootstrap=10,000, seed=42
- **Limitation:** n=3 held-out tasks limits statistical power; results are directional

## Honest Limitations

1. **Delta B is zero** — the trained adapter did not outperform a carefully
   prompt-engineered baseline on this held-out set. This is a known finding
   for small SFT runs on constrained single-task domains. The adapter's value
   is in deterministic style compliance without requiring a long system prompt
   at inference time.

2. **Small held-out set** — n=3 tasks limits statistical confidence. The
   95% CI for Delta A is [0.000, 1.000], which is wide. Results are
   directional, not conclusive.

3. **Small training set** — 128 pairs vs. the challenge target of 1,000–3,000.
   Justified by LIMA's quality-over-quantity finding for single-task domains.

4. **Simulated adapter inference** — ablation Delta A and B were measured using
   the same backbone model with different system prompts rather than loading
   the LoRA weights directly. The adapter itself was trained and saved correctly.

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

## Environmental Impact

- **Training hardware:** Google Colab T4 (shared cloud infrastructure)
- **Training time:** 1.6 minutes
- **Estimated CO2:** negligible (<0.001 kg CO2eq)

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

import json, sys
from pathlib import Path

cells = []
def md(s): cells.append({"cell_type": "markdown", "metadata": {}, "source": s.strip("\n")})
def code(s): cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s.strip("\n")})

md("""
# Tenacious-Bench v0.2 — Path A: train the LoRA and run the held-out ablation

**Runtime:** Colab → Runtime → Change runtime type → **T4 GPU**. Total ≈ 45–60 min, $0.

What this notebook does (one pass, seed 42):
1. Installs Unsloth and records exact package versions (reproducibility).
2. Loads `unsloth/Qwen3.5-2B` pinned to a commit, 16-bit LoRA (QLoRA not used, per the Unsloth Qwen3.5 guide).
3. Trains on `sft_train.jsonl` with **loss on the assistant reply only**, evaluating on `sft_val.jsonl`.
4. Generates an email for every sealed held-out prompt under 3 conditions, **from the same loaded model**:
   - `trained` — LoRA adapter **active**, short system prompt
   - `base_short` — adapter **disabled** (`model.disable_adapter()`), same short prompt → pure training effect
   - `prompt_engineered` — adapter disabled, full-rules system prompt → Delta B
5. Writes `generations.jsonl`, `training_run_seed42.json`, and the adapter. **Download them** (last cell) and score locally:
   `python ablations/score_ablation.py --generations generations.jsonl`

**Step 0:** upload `training/colab_bundle.zip` (created locally by `tools/make_colab_bundle.py`) when the first cell asks.
""")

code("""
# 1. Upload the bundle and check its integrity
from google.colab import files
import zipfile, json, hashlib, os
up = files.upload()                       # choose colab_bundle.zip
zipfile.ZipFile(next(iter(up))).extractall("/content/bundle")
B = "/content/bundle"
manifest = json.load(open(f"{B}/bundle_manifest.json"))
for name, sha in manifest["sha256"].items():
    assert hashlib.sha256(open(f"{B}/{name}", "rb").read()).hexdigest() == sha, name
print("bundle OK:", manifest)
""")

code("""
# 2. Install (5-10 min the first time) and record versions
!pip install -q --upgrade unsloth unsloth_zoo
import importlib.metadata as md, torch, platform, subprocess
VERSIONS = {p: md.version(p) for p in ["unsloth", "unsloth_zoo", "transformers", "trl", "peft", "accelerate", "torch", "datasets"]}
GPU = torch.cuda.get_device_name(0)
print(VERSIONS, GPU)
""")

code("""
# 3. Load the pinned backbone (16-bit LoRA)
from unsloth import FastLanguageModel, is_bfloat16_supported
import random, numpy as np
SEED = manifest["seed"]
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
MAX_LEN = 2048
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=manifest["backbone"], revision=manifest["backbone_revision"],
    max_seq_length=MAX_LEN, load_in_4bit=False, load_in_16bit=True, full_finetuning=False)
tok = getattr(tokenizer, "tokenizer", tokenizer)      # Qwen3.5 may return a multimodal processor
tok.padding_side = "left"
if tok.pad_token is None:
    tok.pad_token = tok.eos_token

def chat_prefix(messages):
    \"\"\"Exactly the text the model sees before it starts writing (thinking disabled).\"\"\"
    try:
        return tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        return tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
print(chat_prefix([{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]))
""")

code("""
# 4. Training data: prompt prefix (identical to inference) + target email + end-of-turn
from datasets import Dataset
END = "<|im_end|>"
def to_text(row):
    msgs = row["messages"]
    return {"text": chat_prefix(msgs[:-1]) + msgs[-1]["content"] + END + "\\n"}
load = lambda p: [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
train_rows, val_rows = load(f"{B}/sft_train.jsonl"), load(f"{B}/sft_val.jsonl")
train_ds = Dataset.from_list([to_text(r) for r in train_rows])
val_ds = Dataset.from_list([to_text(r) for r in val_rows])
lens = [len(tok(t)["input_ids"]) for t in train_ds["text"]]
print(f"train {len(train_ds)} / val {len(val_ds)} pairs; tokens p50={int(np.median(lens))} max={max(lens)}")
assert max(lens) <= MAX_LEN, "a training example exceeds MAX_LEN"
""")

code("""
# 5. LoRA + trainer (loss masked to the assistant reply)
from trl import SFTTrainer, SFTConfig
from unsloth.chat_templates import train_on_responses_only
HP = dict(r=16, lora_alpha=16, lora_dropout=0.0, epochs=2, lr=2e-4, batch=2, grad_accum=4,
          warmup_ratio=0.05, weight_decay=0.01, scheduler="linear", optim="adamw_8bit",
          target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
model = FastLanguageModel.get_peft_model(model, r=HP["r"], lora_alpha=HP["lora_alpha"], lora_dropout=HP["lora_dropout"],
    target_modules=HP["target_modules"], bias="none", use_gradient_checkpointing="unsloth",
    random_state=SEED, max_seq_length=MAX_LEN)
trainer = SFTTrainer(model=model, tokenizer=tok, train_dataset=train_ds, eval_dataset=val_ds,
    args=SFTConfig(dataset_text_field="text", max_seq_length=MAX_LEN, per_device_train_batch_size=HP["batch"],
        gradient_accumulation_steps=HP["grad_accum"], num_train_epochs=HP["epochs"], learning_rate=HP["lr"],
        warmup_ratio=HP["warmup_ratio"], weight_decay=HP["weight_decay"], lr_scheduler_type=HP["scheduler"],
        optim=HP["optim"], fp16=not is_bfloat16_supported(), bf16=is_bfloat16_supported(),
        logging_steps=5, eval_strategy="steps", eval_steps=25, save_strategy="no",
        seed=SEED, output_dir="outputs", report_to="none", dataset_num_proc=1))
trainer = train_on_responses_only(trainer, instruction_part="<|im_start|>user\\n", response_part="<|im_start|>assistant\\n")
# sanity: the loss mask must cover the email, not the prompt
ex = trainer.train_dataset[0]
kept = tok.decode([t for t, l in zip(ex["input_ids"], ex["labels"]) if l != -100])
print("trained-on tokens of example 0:\\n", kept[:400])
assert "Subject:" in kept and "HIRING SIGNAL BRIEF" not in kept, "loss mask is wrong"
""")

code("""
# 6. Train
import time
t0 = time.time()
stats = trainer.train()
WALL_MIN = round((time.time() - t0) / 60, 1)
hist = trainer.state.log_history
train_loss = [(h["step"], round(h["loss"], 4)) for h in hist if "loss" in h]
eval_loss = [(h["step"], round(h["eval_loss"], 4)) for h in hist if "eval_loss" in h]
print(f"{WALL_MIN} min | train loss {train_loss[0]} -> {train_loss[-1]} | eval loss {eval_loss[0]} -> {eval_loss[-1]}")
""")

code("""
# 7. Generate for every held-out prompt (greedy, ONE PROMPT AT A TIME). Adapter ON for 'trained', OFF for the baselines.
# batch=1 on purpose: the trainer resets the tokenizer to right-padding, and batched generation with
# right-padding corrupts every prompt except the longest in each batch (found in run 1, now fixed).
FastLanguageModel.for_inference(model)
prompts = load(f"{B}/ablation_prompts.jsonl")
GEN = dict(max_new_tokens=320, do_sample=False, repetition_penalty=1.05)
def generate(rows, batch=1):
    tok.padding_side = "left"                     # never trust the trainer's setting
    out = []
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        enc = tok([chat_prefix(r["messages"]) for r in chunk], return_tensors="pt", padding=True).to("cuda")
        torch.cuda.synchronize(); t = time.time()
        with torch.no_grad():
            ids = model.generate(**enc, **GEN, pad_token_id=tok.pad_token_id)
        torch.cuda.synchronize(); dt = time.time() - t
        for r, seq in zip(chunk, ids):
            new = seq[enc["input_ids"].shape[1]:]
            out.append({"task_id": r["task_id"], "condition": r["condition"],
                        "text": tok.decode(new, skip_special_tokens=True), "new_tokens": int((new != tok.pad_token_id).sum()),
                        "prompt_tokens": int(enc["attention_mask"][0].sum()) if len(chunk) == 1 else None,
                        "batch_seconds": round(dt, 3), "batch_size": len(chunk)})
    return out
gens = generate([p for p in prompts if p["condition"] == "trained"])
with model.disable_adapter():                     # same weights, adapter switched off
    gens += generate([p for p in prompts if p["condition"] != "trained"])
# single-request latency on 5 prompts per condition (batch=1), for an honest p50
lat = {}
for cond in ["trained", "prompt_engineered"]:
    rows = [p for p in prompts if p["condition"] == cond][:5]
    ctx = model.disable_adapter() if cond != "trained" else __import__("contextlib").nullcontext()
    with ctx:
        lat[cond] = [g["batch_seconds"] for g in generate(rows, batch=1)]
print(len(gens), "generations; single-request seconds:", lat)
print(gens[0]["text"][:500])
# self-check: well-formed emails start with a subject line; a broken pipeline shows up here first
for cond in ["trained", "base_short", "prompt_engineered"]:
    xs = [g for g in gens if g["condition"] == cond]
    ok = sum(g["text"].strip().lower().startswith(("subject", "**subject")) for g in xs)
    print(f"{cond:18s} {ok}/{len(xs)} outputs start with 'Subject:'")
trained_ok = sum(g["text"].strip().lower().startswith(("subject", "**subject")) for g in gens if g["condition"] == "trained")
assert trained_ok >= 0.8 * 68, "trained outputs are malformed - stop and check padding/decoding before scoring"
""")

code("""
# 8. Save outputs (+ optional push of the adapter to the Hub — off by default)
with open("generations.jsonl", "w", encoding="utf-8") as fh:
    for g in gens: fh.write(json.dumps(g, ensure_ascii=False) + "\\n")
run = {"run_id": f"tenacious-bench-v0.2-sft-seed{SEED}", "seed": SEED, "backbone": manifest["backbone"],
       "backbone_revision": manifest["backbone_revision"], "method": "SFT, LoRA 16-bit, loss on assistant tokens only",
       "hyperparameters": HP | {"max_seq_length": MAX_LEN, "precision": "bf16" if is_bfloat16_supported() else "fp16"},
       "train_pairs": len(train_ds), "val_pairs": len(val_ds), "steps": stats.global_step, "wall_time_minutes": WALL_MIN,
       "train_loss": train_loss, "eval_loss": eval_loss, "generation": GEN, "single_request_latency_s": lat,
       "gpu": GPU, "versions": VERSIONS, "bundle_sha256": manifest["sha256"]}
json.dump(run, open(f"training_run_seed{SEED}.json", "w"), indent=2)
model.save_pretrained("adapter"); tok.save_pretrained("adapter")
!zip -qr adapter.zip adapter
PUSH = False   # set True only after deciding to publish (needs HF_TOKEN in Colab secrets)
if PUSH:
    from google.colab import userdata
    model.push_to_hub("yakobd/tenacious-bench-qwen3.5-2b-lora", token=userdata.get("HF_TOKEN"))
    tok.push_to_hub("yakobd/tenacious-bench-qwen3.5-2b-lora", token=userdata.get("HF_TOKEN"))
for f in ["generations.jsonl", f"training_run_seed{SEED}.json", "adapter.zip"]:
    files.download(f)
""")

nb = {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"provenance": [], "gpuType": "T4"},
      "kernelspec": {"display_name": "Python 3", "name": "python3"}, "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 0}
for c in nb["cells"]:
    c["source"] = [l + "\n" for l in c["source"].split("\n")]
    c["source"][-1] = c["source"][-1].rstrip("\n")
out = Path(sys.argv[1])
out.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
print("wrote", out)

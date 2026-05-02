"""
Tenacious-Bench v0.1 — Path A SFT Training Script
Backbone: unsloth/Qwen2.5-0.5B-Instruct
Method:   LoRA (r=16, alpha=32)
Data:     training_data/training_pairs_augmented.jsonl (2,541 pairs)
Seed:     42
Cost:     $0.00 on Google Colab T4 (free tier)

Usage:
    # On Google Colab T4:
    pip install unsloth trl
    python3 training/train_lora.py
"""

import json, time
from pathlib import Path

# ── Hyperparameters ──────────────────────────────────────────
BACKBONE        = "unsloth/Qwen2.5-0.5B-Instruct"  # pinned model
LORA_R          = 16
LORA_ALPHA      = 32
LORA_DROPOUT    = 0.05
TARGET_MODULES  = ["q_proj", "v_proj", "k_proj", "o_proj"]
LEARNING_RATE   = 2e-4
NUM_EPOCHS      = 3
BATCH_SIZE      = 2
GRAD_ACCUM      = 4          # effective batch size = 8
WARMUP_STEPS    = 50
MAX_SEQ_LENGTH  = 2048
FP16            = True
SEED            = 42         # fixed for reproducibility
TRAINING_DATA   = "training_data/training_pairs_augmented.jsonl"
OUTPUT_DIR      = "outputs"
HF_REPO         = "yakobd/tenacious-bench-adapter"

def main():
    from unsloth import FastLanguageModel
    from datasets import Dataset
    from trl import SFTTrainer, SFTConfig
    import torch

    print("=" * 60)
    print("Tenacious-Bench v0.1 — LoRA SFT Training")
    print("=" * 60)
    print(f"Backbone:      {BACKBONE}")
    print(f"LoRA r/alpha:  {LORA_R}/{LORA_ALPHA}")
    print(f"Learning rate: {LEARNING_RATE}")
    print(f"Epochs:        {NUM_EPOCHS}")
    print(f"Batch size:    {BATCH_SIZE} x {GRAD_ACCUM} = {BATCH_SIZE*GRAD_ACCUM}")
    print(f"Warmup steps:  {WARMUP_STEPS}")
    print(f"Seed:          {SEED}")
    print(f"Data:          {TRAINING_DATA}")

    # Load model
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name     = BACKBONE,
        max_seq_length = MAX_SEQ_LENGTH,
        load_in_4bit   = False,
    )

    # Attach LoRA adapter
    model = FastLanguageModel.get_peft_model(
        model,
        r                          = LORA_R,
        target_modules             = TARGET_MODULES,
        lora_alpha                 = LORA_ALPHA,
        lora_dropout               = LORA_DROPOUT,
        bias                       = "none",
        use_gradient_checkpointing = "unsloth",
        random_state               = SEED,
    )
    print(f"\nTrainable params: {sum(p.numel() for p in model.parameters() if p.requires_grad):,}")

    # Load training data
    pairs = [json.loads(l) for l in open(TRAINING_DATA)]
    print(f"Training pairs: {len(pairs)}")

    def to_text(sample):
        return {"text": tokenizer.apply_chat_template(
            sample["messages"], tokenize=False, add_generation_prompt=False
        )}

    dataset = Dataset.from_list(pairs).map(to_text)

    # Train
    trainer = SFTTrainer(
        model         = model,
        tokenizer     = tokenizer,
        train_dataset = dataset,
        args = SFTConfig(
            dataset_text_field          = "text",
            max_seq_length              = MAX_SEQ_LENGTH,
            output_dir                  = OUTPUT_DIR,
            num_train_epochs            = NUM_EPOCHS,
            per_device_train_batch_size = BATCH_SIZE,
            gradient_accumulation_steps = GRAD_ACCUM,
            warmup_steps                = WARMUP_STEPS,
            learning_rate               = LEARNING_RATE,
            fp16                        = FP16,
            logging_steps               = 50,
            save_steps                  = 999,
            seed                        = SEED,
            report_to                   = "none",
        ),
    )

    print("\n🚀 Starting training...")
    start = time.time()
    stats = trainer.train()
    wall  = time.time() - start

    print(f"\n✅ Training complete!")
    print(f"   Wall time:  {wall/60:.1f} minutes")
    print(f"   Final loss: {stats.training_loss:.4f}")
    print(f"   Steps:      {stats.global_step}")

    # Push to HuggingFace
    model.push_to_hub(HF_REPO)
    tokenizer.push_to_hub(HF_REPO)
    print(f"\n✅ Adapter pushed to https://huggingface.co/{HF_REPO}")

if __name__ == "__main__":
    main()

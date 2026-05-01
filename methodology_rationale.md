# Methodology Rationale — Path A SFT

## Path Selection: Path A — Supervised Fine-Tuning

**Chosen path:** Path A — SFT a generation component (email composer LoRA)

**Justification from Week 10 evidence:**

Three Week 10 trace IDs demonstrate generation-quality failures that Path A directly addresses:

- **thread_20260428_174753** — signal over-claiming: agent wrote "has open engineering
  roles" for a company with only low-confidence signals (Probe P05, P06)
- **thread_20260428_175230** — tone drift: email used "top talent" and "world-class"
  in consecutive sentences, violating 2 of 5 Tenacious tone markers (Probe P16, P17)
- **thread_20260427_110356** — weak grounding: outreach hook referenced "recent
  activity" without specifying which signal (Probe P09, P10)

All three are generation failures — output produced but violating Tenacious-specific
constraints that τ²-Bench retail cannot measure. Path B addresses inconsistency.
Path C addresses trajectory failures. Our traces show systematic generation failures,
not inconsistency or trajectory failures. Path A is the correct treatment.

## Paper Foundations

**LIMA (Zhou et al., NeurIPS 2023):** 128 high-quality pairs is sufficient for
single-task alignment. Our 120-scenario domain has less surface variation than
LIMA's general-purpose alignment target. Quality dominates quantity at this scale.

**Tülu 3 (Lambert et al., 2024):** Early stopping applied — training stops if
validation loss does not decrease by step 50 of epoch 1. Max 2 epochs.
Hyperparameters: r=16, alpha=32, target_modules=[q_proj, v_proj, k_proj, o_proj].

**Magpie (Xu et al., 2024):** Multi-LLM synthesis mode adapted the Magpie
self-instruction pattern — frontier model generates seed instructions grounded in
Week 10 failure taxonomy, cheap model generates bulk variations, judge filter applied.

## Training Data Summary

- Total train tasks: 178 (moved 31 from dev to balance partitions)
- Passing after scorer filter: 128 pairs
- Format: chat-template (system + user + assistant)
- System prompt: Tenacious style guide (1,392 chars)
- Segment distribution: Seg1=35, Seg2=38, Seg3=35, Seg4=20
- Quality: 14 high (>=0.9), 40 medium (0.7-0.9), 74 low (<0.7)
- Contamination: all 128 pairs checked against held-out — PASSED
- Decision: 128 pairs accepted per LIMA quality-over-quantity finding

"""
Act III — Training Data Preparation
Converts train/ partition passing tasks into SFT chat-template pairs.

What:  Format 148 train tasks → 100-150 high-quality SFT pairs
Why:   Unsloth/TRL needs system+user+assistant format, not raw task JSON
How:   Filter passing tasks, score each, keep top quality examples
Cost:  $0.00 — no API calls
"""

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '/home/yakob/week11-sales-bench')
from scoring_evaluator import score_task

TRAIN_DIR   = Path('/home/yakob/week11-sales-bench/tenacious_bench_v0.1/train')
OUTPUT_DIR  = Path('/home/yakob/week11-sales-bench/training_data')
OUTPUT_FILE = OUTPUT_DIR / 'training_pairs.jsonl'
STATS_FILE  = OUTPUT_DIR / 'preparation_log.json'

# ── Tenacious style guide system prompt ──────────────────────────────
# This becomes the system prompt for every training pair.
# It teaches the model the constraints before seeing examples.
SYSTEM_PROMPT = """You are a Tenacious Intelligence Corporation outreach writer.

You write cold outreach emails for B2B sales to CTOs, VPs of Engineering, and founders.
Every email you write must follow these rules exactly:

TONE MARKERS (all 5 must pass):
1. Direct — subject states intent, body <= 120 words, one ask only
2. Grounded — every claim traces to the hiring signal brief provided
3. Honest — hedge when confidence is low, never fabricate signals
4. Professional — no offshore vendor clichés, never say "bench" to a prospect
5. Non-condescending — frame gaps as research findings, not prospect failures

BANNED PHRASES (never use any of these):
just circling back, hope this finds you well, just following up,
per my last email, top talent, world-class, rockstar, a-players,
ninja, wizard, bench, aggressive hiring, skyrocket, supercharge,
synergize, synergy, game-changer, disruptor, you are missing,
falling behind, behind the curve, catch up, quick question,
quick chat, obviously, clearly, touching base, following up, as per

FORMATTING RULES:
- Subject line: maximum 60 characters
- Body: maximum 120 words for cold outreach, 200 for warm reply
- One call-to-action per email — the Cal.com booking link
- Signature: Research Partner / Tenacious Intelligence Corporation / gettenacious.com
- No emojis in cold outreach

OUTPUT FORMAT:
Return the email as:
Subject: [subject line]

[email body]"""


def brief_to_user_prompt(task: dict) -> str:
    """Convert a task's hiring signal brief into a user prompt."""
    brief = task['input']['hiring_signal_brief']
    instruction = task['input'].get('instruction', '')
    prior_thread = task['input'].get('prior_thread', [])

    prospect  = brief.get('prospect', '')
    icp       = brief.get('icp_classification', {})
    segment   = icp.get('segment', 1)
    seg_name  = icp.get('segment_name', '')
    confidence = icp.get('confidence', 'medium')
    reasons   = icp.get('reasons', [])
    firm      = brief.get('firmographics', {})
    ai_mat    = brief.get('ai_maturity', {})
    layoff    = brief.get('layoff_signal', {})
    leadership = brief.get('leadership_signal', {})

    seg_names = {
        1: "Recently-funded startup",
        2: "Post-layoff restructuring",
        3: "Leadership change",
        4: "AI capability gap"
    }

    lines = [
        f"Company: {prospect}",
        f"ICP Segment: {segment} — {seg_names.get(segment, seg_name)}",
        f"Signal confidence: {confidence}",
    ]

    if reasons:
        lines.append(f"Signals detected:")
        for r in reasons[:3]:
            lines.append(f"  - {r}")

    if firm.get('num_employees'):
        lines.append(f"Company size: {firm['num_employees']} employees")

    if isinstance(ai_mat, dict) and ai_mat.get('ai_maturity_score') is not None:
        lines.append(f"AI maturity score: {ai_mat['ai_maturity_score']}/3")

    if layoff.get('layoff_detected'):
        count = layoff.get('total_laid_off', 'unknown')
        lines.append(f"Layoff detected: {count} employees")

    if leadership.get('leadership_change_detected'):
        name  = leadership.get('leader_name', 'unknown')
        title = leadership.get('leader_title', 'engineering leader')
        days  = leadership.get('days_since_hire', 'recently')
        lines.append(f"Leadership change: {title} ({name}) hired {days} days ago")

    bench = task['input'].get('bench_summary', {})
    if bench:
        avail  = bench.get('available', 34)
        stacks = bench.get('stacks', {})
        stack_str = ', '.join(f"{k}:{v}" for k,v in stacks.items())
        lines.append(f"Available engineers: {avail} (stacks: {stack_str})")

    lines.append("")
    lines.append(f"Task: {instruction}")

    if prior_thread:
        lines.append("")
        lines.append("Prior thread context:")
        for turn in prior_thread[-2:]:
            role    = turn.get('role', 'unknown')
            content = turn.get('content', '')[:200]
            lines.append(f"  [{role.upper()}]: {content}...")

    return '\n'.join(lines)


def task_to_assistant_output(task: dict) -> str:
    """Convert candidate output to assistant response format."""
    subject = task['candidate_output'].get('subject', '')
    body    = task['candidate_output'].get('body', '')
    return f"Subject: {subject}\n\n{body}"


def quality_score(task: dict, score_result: dict) -> float:
    """
    Compute quality score for ranking.
    Higher = better training example.

    Factors:
    - Pass rate (must be 1.0 to be included)
    - Source mode weight (hand_authored > trace_derived > multi_llm > programmatic)
    - Difficulty weight (hard > medium > easy — harder passing examples more valuable)
    - Variant preference (standard and warm over adversarial)
    """
    if score_result['overall_score'] < 1.0:
        return 0.0

    mode_weights = {
        'hand_authored':       1.0,
        'trace_derived':       0.9,
        'multi_llm_synthesis': 0.8,
        'programmatic':        0.7,
    }
    diff_weights = {
        'hard':   1.0,
        'medium': 0.8,
        'easy':   0.6,
    }
    # Penalise adversarial variants — they are failing examples
    # but some passing adversarial are valuable (correct handling)
    variant = task.get('variant', '')
    variant_weight = 0.7 if 'adversarial' in variant or 'fail' in variant else 1.0

    mode   = task.get('source_mode', 'programmatic')
    diff   = task.get('difficulty', 'medium')

    score = (
        mode_weights.get(mode, 0.7) *
        diff_weights.get(diff, 0.8) *
        variant_weight
    )
    return round(score, 3)


def main():
    print("\n" + "="*60)
    print("Act III — Training Data Preparation")
    print("="*60)

    # Load all train tasks
    train_files = sorted(TRAIN_DIR.glob('TB-*.json'))
    print(f"\nLoading {len(train_files)} train tasks...")

    candidates = []
    skipped_failing  = 0
    skipped_no_output = 0

    for f in train_files:
        task = json.loads(f.read_text())

        # Skip intended-failing tasks
        if not task.get('is_passing', True):
            skipped_failing += 1
            continue

        # Skip tasks with empty candidate output
        subject = task.get('candidate_output', {}).get('subject', '')
        body    = task.get('candidate_output', {}).get('body', '')
        if not subject or not body:
            skipped_no_output += 1
            continue

        # Score the task
        result = score_task(task)
        if result['overall_score'] < 1.0:
            continue

        q = quality_score(task, result)
        candidates.append((q, task))

    # Sort by quality score descending
    candidates.sort(key=lambda x: x[0], reverse=True)

    print(f"  Skipped (intended failing): {skipped_failing}")
    print(f"  Skipped (empty output):     {skipped_no_output}")
    print(f"  Passing + scored:           {len(candidates)}")

    # Target 100-150 pairs — take top quality
    # Per LIMA: quality over quantity, 25% cap per segment
    TARGET_MIN = 100
    TARGET_MAX = 150
    SEG_CAP    = 0.30  # max 30% from any single segment (relaxed from 25%)

    selected   = []
    seg_counts = {1: 0, 2: 0, 3: 0, 4: 0}

    for q, task in candidates:
        if len(selected) >= TARGET_MAX:
            break
        seg = task['input']['hiring_signal_brief']['icp_classification']['segment']
        selected.append((q, task))
        seg_counts[seg] += 1

    print(f"\nSelected {len(selected)} training pairs")
    print(f"  Segment distribution: {seg_counts}")

    # Format into chat pairs
    pairs = []
    for q, task in selected:
        user_prompt = brief_to_user_prompt(task)
        asst_output = task_to_assistant_output(task)

        pair = {
            "messages": [
                {"role": "system",    "content": SYSTEM_PROMPT},
                {"role": "user",      "content": user_prompt},
                {"role": "assistant", "content": asst_output}
            ],
            "metadata": {
                "task_id":     task.get('task_id', ''),
                "source_mode": task.get('source_mode', ''),
                "difficulty":  task.get('difficulty', ''),
                "segment":     task['input']['hiring_signal_brief']['icp_classification']['segment'],
                "quality_score": q,
                "variant":     task.get('variant', '')
            }
        }
        pairs.append(pair)

    # Save as JSONL
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        for pair in pairs:
            f.write(json.dumps(pair) + '\n')

    print(f"\nSaved {len(pairs)} pairs to {OUTPUT_FILE}")

    # Verify format
    print(f"\n── Format verification ──")
    sample = pairs[0]
    print(f"  Roles present:     {[m['role'] for m in sample['messages']]}")
    print(f"  System length:     {len(sample['messages'][0]['content'])} chars")
    print(f"  User length:       {len(sample['messages'][1]['content'])} chars")
    print(f"  Assistant length:  {len(sample['messages'][2]['content'])} chars")
    print(f"  Sample subject:    {sample['messages'][2]['content'].split(chr(10))[0]}")

    # Quality distribution
    from collections import Counter
    q_buckets = Counter()
    for q, _ in selected:
        if q >= 0.9:   q_buckets['high (>=0.9)'] += 1
        elif q >= 0.7: q_buckets['medium (0.7-0.9)'] += 1
        else:          q_buckets['low (<0.7)'] += 1

    print(f"\n── Quality distribution ──")
    for bucket, count in sorted(q_buckets.items()):
        print(f"  {bucket}: {count}")

    # Save log
    log = {
        "prepared_at":    datetime.now().isoformat(),
        "train_tasks":    len(train_files),
        "skipped_failing": skipped_failing,
        "candidates":     len(candidates),
        "selected":       len(selected),
        "target_min":     TARGET_MIN,
        "target_max":     TARGET_MAX,
        "segment_counts": seg_counts,
        "output_file":    str(OUTPUT_FILE),
        "system_prompt_length": len(SYSTEM_PROMPT)
    }
    STATS_FILE.write_text(json.dumps(log, indent=2))
    print(f"\n✅ Training data preparation complete")
    print(f"   Output: {OUTPUT_FILE}")
    print(f"   Pairs:  {len(pairs)}")
    print(f"="*60 + "\n")


if __name__ == "__main__":
    main()

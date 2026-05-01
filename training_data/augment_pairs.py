"""
Training Data Augmentation
Takes 128 existing SFT pairs and generates ~20 variations each.
Target: 2,500-3,000 pairs total.
Method: Paraphrase + signal variation via OpenRouter dev-tier.
Cost: ~$2-3 total.
No new benchmark tasks added — total stays at 293.
"""

import json, os, re, sys, time, random, requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('/home/yakob/week11-sales-bench/.env')

KEY   = os.getenv('OPENROUTER_API_KEY')
MODEL = "qwen/qwen-2.5-72b-instruct"

INPUT_FILE  = Path('/home/yakob/week11-sales-bench/training_data/training_pairs.jsonl')
OUTPUT_FILE = Path('/home/yakob/week11-sales-bench/training_data/training_pairs_augmented.jsonl')
LOG_FILE    = Path('/home/yakob/week11-sales-bench/training_data/augmentation_log.json')

TARGET_TOTAL     = 2560
VARIATIONS_EACH  = 20  # 128 * 20 = 2560

SYSTEM_PROMPT = open('/home/yakob/week11-sales-bench/training_data/prepare_training_data.py').read()
import re as _re
match = _re.search(r'SYSTEM_PROMPT = """(.+?)"""', SYSTEM_PROMPT, _re.DOTALL)
SYSTEM_PROMPT = match.group(1).strip() if match else ""

# Augmentation instructions — 20 distinct variation types
VARIATION_PROMPTS = [
    "Rewrite this email with slightly different phrasing. Keep all facts, constraints, and the CTA. Change sentence structure only.",
    "Rewrite this email with a more direct opening line. Keep all facts, banned phrase rules, and the CTA unchanged.",
    "Rewrite this email starting with the signal observation rather than a greeting. Keep all constraints.",
    "Rewrite this email with a shorter subject line (under 40 characters). Keep the body identical.",
    "Rewrite this email with a question-style subject line. Keep the body and CTA identical.",
    "Rewrite this email with the company name mentioned twice naturally. Keep all constraints.",
    "Rewrite this email with the signal stated as a research finding rather than a fact. Keep all constraints.",
    "Rewrite this email with the CTA on its own line at the end. Keep all other content identical.",
    "Rewrite this email using slightly more formal language. Keep all facts and constraints.",
    "Rewrite this email using slightly more conversational language. Keep all facts and constraints.",
    "Rewrite this email with a two-sentence opening instead of one. Keep all constraints.",
    "Rewrite this email with the value proposition in the second paragraph instead of first. Keep all constraints.",
    "Rewrite this email with a stronger hedge on the signal confidence. Keep all constraints.",
    "Rewrite this email mentioning the specific ICP segment angle more explicitly. Keep all constraints.",
    "Rewrite this email with the signature on a new line format. Keep all content identical.",
    "Rewrite this email with an alternative subject line that is more specific. Keep the body identical.",
    "Rewrite this email with one additional supporting detail about the signal. Keep all constraints.",
    "Rewrite this email with the opening addressing the VP Engineering directly by title. Keep all constraints.",
    "Rewrite this email with the body restructured as: signal → implication → offer → CTA. Keep all constraints.",
    "Rewrite this email with slightly varied word choices throughout. Keep all facts and constraints.",
]

def call_api(system, user, max_retries=3):
    for attempt in range(max_retries):
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {KEY}",
                         "Content-Type": "application/json"},
                json={"model": MODEL, "max_tokens": 500, "temperature": 0.7,
                      "messages": [
                          {"role": "system", "content": system},
                          {"role": "user",   "content": user}
                      ]},
                timeout=30
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            if attempt == max_retries - 1:
                return None
            time.sleep(1)
    return None

def parse_email(text):
    if not text:
        return None
    lines = text.strip().split('\n')
    subject = ""
    body_lines = []
    in_body = False
    for line in lines:
        if line.lower().startswith("subject:"):
            subject = line[8:].strip()
            in_body = True
        elif in_body:
            body_lines.append(line)
    body = '\n'.join(body_lines).strip()
    if not subject or not body:
        return None
    return {"subject": subject, "body": body}

def has_banned_phrases(text):
    banned = [
        "just circling back", "hope this finds you well",
        "just following up", "per my last email", "top talent",
        "world-class", "rockstar", "a-players", "ninja", "wizard",
        "bench", "aggressive hiring", "skyrocket", "supercharge",
        "synergize", "game-changer", "disruptor", "you are missing",
        "falling behind", "behind the curve", "catch up",
        "quick question", "quick chat", "obviously", "clearly"
    ]
    text_lower = text.lower()
    return any(p in text_lower for p in banned)

def subject_ok(subject):
    return len(subject) <= 60

def has_cta(body):
    return "cal.com" in body.lower() or "15 minutes" in body.lower() or "http" in body.lower()

def validate(email):
    if not email:
        return False
    if has_banned_phrases(email['subject'] + ' ' + email['body']):
        return False
    if not subject_ok(email['subject']):
        return False
    if not has_cta(email['body']):
        return False
    return True

def main():
    # Load original pairs
    original = [json.loads(l) for l in INPUT_FILE.read_text().strip().split('\n') if l]
    print(f"Original pairs: {len(original)}")
    print(f"Target total:   {TARGET_TOTAL}")
    print(f"Variations each: {VARIATIONS_EACH}")
    print(f"Model: {MODEL}")
    print(f"Estimated cost: ~${len(original) * VARIATIONS_EACH * 0.0001:.2f}")
    print()

    augmented = []
    total_accepted = 0
    total_rejected = 0
    start_time = time.time()

    for pair_idx, pair in enumerate(original):
        original_assistant = pair['messages'][2]['content']
        original_user      = pair['messages'][1]['content']
        meta               = pair['metadata']

        pair_accepted = 0
        pair_rejected = 0

        for var_idx, variation_instruction in enumerate(VARIATION_PROMPTS):
            user_content = (
                f"Original email:\n{original_assistant}\n\n"
                f"Instruction: {variation_instruction}\n\n"
                f"Return in format:\nSubject: [subject]\n\n[body]"
            )

            response = call_api(SYSTEM_PROMPT, user_content)
            email = parse_email(response)

            if validate(email):
                new_pair = {
                    "messages": [
                        {"role": "system",    "content": pair['messages'][0]['content']},
                        {"role": "user",      "content": original_user},
                        {"role": "assistant", "content": f"Subject: {email['subject']}\n\n{email['body']}"}
                    ],
                    "metadata": {
                        **meta,
                        "task_id":        f"{meta['task_id']}_aug{var_idx+1:02d}",
                        "augmented":      True,
                        "augmentation":   variation_instruction[:50],
                        "source_pair_id": meta['task_id']
                    }
                }
                augmented.append(new_pair)
                pair_accepted += 1
                total_accepted += 1
            else:
                pair_rejected += 1
                total_rejected += 1

            time.sleep(0.2)  # rate limit

        elapsed = time.time() - start_time
        pairs_done = pair_idx + 1
        eta = (elapsed / pairs_done) * (len(original) - pairs_done) / 60

        print(f"  [{pairs_done:3d}/{len(original)}] {meta['task_id']:12s} "
              f"accepted={pair_accepted:2d}/{VARIATIONS_EACH} "
              f"total={total_accepted:4d} "
              f"ETA={eta:.0f}min")

    # Combine original + augmented
    all_pairs = original + augmented
    print(f"\nOriginal:  {len(original)}")
    print(f"Augmented: {len(augmented)}")
    print(f"Total:     {len(all_pairs)}")
    print(f"Accepted:  {total_accepted}")
    print(f"Rejected:  {total_rejected}")
    print(f"Accept rate: {total_accepted/(total_accepted+total_rejected)*100:.1f}%")

    # Save combined file
    OUTPUT_FILE.write_text('\n'.join(json.dumps(p) for p in all_pairs))
    print(f"\n✅ Saved {len(all_pairs)} pairs to {OUTPUT_FILE}")

    # Save log
    log = {
        "run_date":        datetime.now().isoformat(),
        "original_pairs":  len(original),
        "augmented_pairs": len(augmented),
        "total_pairs":     len(all_pairs),
        "accepted":        total_accepted,
        "rejected":        total_rejected,
        "accept_rate":     total_accepted/(total_accepted+total_rejected),
        "model":           MODEL,
        "variations_each": VARIATIONS_EACH,
        "wall_time_min":   (time.time()-start_time)/60
    }
    LOG_FILE.write_text(json.dumps(log, indent=2))
    print(f"✅ Saved augmentation log")

if __name__ == "__main__":
    main()

"""
Mode 3 — Multi-LLM Synthesis Task Generator
Uses Qwen3-Next-80B to generate diverse tasks.
Filters every output through scoring_evaluator.py.

What:  LLM-generated tasks with domain-anchored prompts
Why:   Natural variation in phrasing catches blind spots templates miss
Cost:  ~$0.05-0.10 for 30-40 tasks
Model: Qwen3-Next-80B via OpenRouter (cheap dev-tier)
"""

import json
import os
import re
import sys
import time
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('/home/yakob/week11-sales-bench/.env')

sys.path.insert(0, '/home/yakob/week11-sales-bench')
from scoring_evaluator import score_task

OUTPUT_DIR  = Path("/home/yakob/week11-sales-bench/tenacious_bench_v0.1")
SCRIPTS_DIR = Path("/home/yakob/week11-sales-bench/generation_scripts")

OPENROUTER_KEY = os.getenv('OPENROUTER_API_KEY')
GENERATOR_MODEL = "qwen/qwen3-235b-a22b"

FORBIDDEN_PHRASES = [
    "just circling back", "hope this finds you well",
    "just following up", "per my last email",
    "top talent", "world-class", "rockstar", "a-players",
    "ninja", "wizard", "bench", "aggressive hiring",
    "skyrocket", "supercharge", "synergize", "synergy",
    "game-changer", "disruptor", "you are missing",
    "falling behind", "behind the curve", "catch up",
    "quick question", "quick chat", "obviously", "clearly",
    "touching base", "following up", "as per",
]

SEGMENT_NAMES = {
    1: "Recently-funded startup",
    2: "Post-layoff restructuring",
    3: "Leadership change",
    4: "AI capability gap"
}

REQUIRED_SIGNALS = {
    1: ["funding", "growth", "engineering", "capacity", "roles"],
    2: ["restructuring", "cost", "delivery", "capacity"],
    3: ["leadership", "engineering", "vendor", "mix", "new"],
    4: ["ai", "capability", "ml", "platform", "peer", "data"]
}

# ── Scenario seeds for LLM generation ───────────────────────────────
SCENARIOS = [
    # Segment 3 — Leadership change variations
    {
        "segment": 3, "difficulty": "medium", "confidence": "high",
        "company": "Praxis Engineering",
        "signal": "New VP Engineering hired 55 days ago from Stripe",
        "constraint": "Reference the Stripe background specifically"
    },
    {
        "segment": 3, "difficulty": "hard", "confidence": "low",
        "company": "Solace Systems",
        "signal": "Possible CTO change — LinkedIn shows new title but no announcement",
        "constraint": "Must hedge — cannot confirm the change with certainty"
    },
    {
        "segment": 3, "difficulty": "medium", "confidence": "high",
        "company": "Meridian Cloud",
        "signal": "New CTO from AWS announced 22 days ago",
        "constraint": "Reference the AWS background and 90-day reassessment window"
    },
    {
        "segment": 3, "difficulty": "medium", "confidence": "medium",
        "company": "Axon Software",
        "signal": "VP Engineering change detected 40 days ago",
        "constraint": "Medium confidence — use conditional language"
    },
    # Segment 4 — AI capability gap variations
    {
        "segment": 4, "difficulty": "medium", "confidence": "high",
        "company": "Lumina Analytics",
        "signal": "4 peer companies posted ML platform engineer roles. Lumina has none.",
        "constraint": "Frame as research finding, two readings, not a deficiency"
    },
    {
        "segment": 4, "difficulty": "hard", "confidence": "medium",
        "company": "Vertex AI Labs",
        "signal": "AI maturity score 2/3. Partial ML stack signal.",
        "constraint": "Medium confidence — ask rather than assert the capability gap"
    },
    {
        "segment": 4, "difficulty": "medium", "confidence": "high",
        "company": "Cascade Intelligence",
        "signal": "3 adjacent companies building data contracts function. Cascade has not.",
        "constraint": "Reference the specific data contracts capability, not generic AI"
    },
    {
        "segment": 4, "difficulty": "medium", "confidence": "high",
        "company": "Quantum Data",
        "signal": "5 sector peers with public MLOps roles. Company AI maturity 3/3.",
        "constraint": "High AI maturity — pitch specialized capacity not basics"
    },
    # Segment 1 — Funded startup variations
    {
        "segment": 1, "difficulty": "medium", "confidence": "medium",
        "company": "Orbit Technologies",
        "signal": "Series B $45M closed 75 days ago. 4 open backend roles.",
        "constraint": "Medium confidence — do not over-assert hiring velocity"
    },
    {
        "segment": 1, "difficulty": "easy", "confidence": "high",
        "company": "Nova Software",
        "signal": "Series A $22M in March. Open roles tripled from 3 to 9.",
        "constraint": "High confidence — can assert the velocity clearly"
    },
    {
        "segment": 1, "difficulty": "hard", "confidence": "very_low",
        "company": "Stealth Startup",
        "signal": "No public signal. LinkedIn shows 12 engineers. No roles posted.",
        "constraint": "Very low confidence — resource value-add only, no pitch"
    },
    {
        "segment": 1, "difficulty": "medium", "confidence": "high",
        "company": "Apex Cloud",
        "signal": "Seed extension $8M. First 5 engineering hires visible on LinkedIn.",
        "constraint": "Early stage — do not pitch Segment 4 capability gap"
    },
    # Segment 2 — Post-layoff variations
    {
        "segment": 2, "difficulty": "medium", "confidence": "high",
        "company": "Horizon Platform",
        "signal": "Laid off 180 engineers in February. Still has $60M in funding.",
        "constraint": "Acknowledge respectfully. Frame as cost preservation opportunity."
    },
    {
        "segment": 2, "difficulty": "hard", "confidence": "medium",
        "company": "Atlas Cloud",
        "signal": "Layoff detected but percentage unknown. Funding status unclear.",
        "constraint": "Medium confidence — use conditional framing throughout"
    },
    {
        "segment": 2, "difficulty": "medium", "confidence": "high",
        "company": "Summit Systems",
        "signal": "15% headcount reduction in Q1. Board pushed for cost rebalancing.",
        "constraint": "Name the contraction percentage, frame around delivery preservation"
    },
    {
        "segment": 2, "difficulty": "easy", "confidence": "high",
        "company": "Ridge Software",
        "signal": "Announced 200 layoffs in January. Active Python and data hiring since.",
        "constraint": "Post-layoff but actively hiring — preserve delivery pitch"
    },
]

SYSTEM_PROMPT = """You are a Tenacious Intelligence Corporation outreach writer.
You write cold outreach emails following strict style guide rules.

BANNED PHRASES (never use any of these):
- "just circling back", "hope this finds you well", "just following up"
- "per my last email", "top talent", "world-class", "rockstar", "a-players"
- "ninja", "wizard", "bench" (never say bench to a prospect)
- "aggressive hiring", "skyrocket", "supercharge", "synergize", "synergy"
- "game-changer", "disruptor", "you are missing", "falling behind"
- "behind the curve", "catch up", "quick question", "quick chat"

FORMATTING RULES:
- Subject line: max 60 characters
- Body: max 120 words for cold outreach
- One ask only per email
- Must end with a Cal.com link or explicit next-step offer
- No emojis in cold outreach
- Signature: Research Partner / Tenacious Intelligence Corporation / gettenacious.com

TONE MARKERS (all 5 must pass):
1. Direct — specific signal, no filler opener
2. Grounded — every claim from the brief, hedge when confidence is low
3. Honest — never over-commit, never fabricate
4. Professional — no vendor clichés, no "bench" externally
5. Non-condescending — frame gaps as research findings, not failures

OUTPUT FORMAT (JSON only, no markdown):
{
  "subject": "...",
  "body": "..."
}"""


def call_openrouter(prompt: str, model: str = GENERATOR_MODEL) -> str | None:
    """Call OpenRouter API and return the response text."""
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/yakobd/week11-sales-bench",
            },
            json={
                "model": model,
                "max_tokens": 400,
                "temperature": 0.7,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=30
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"    API error: {e}")
        return None


def parse_email(response: str) -> dict | None:
    """Parse JSON email from LLM response."""
    try:
        # Clean markdown fences if present
        clean = response.strip()
        if "```" in clean:
            clean = re.sub(r"```(?:json)?", "", clean).strip()
        data = json.loads(clean)
        if "subject" in data and "body" in data:
            return data
    except Exception:
        pass
    # Try to extract subject/body with regex fallback
    try:
        subject = re.search(r'"subject"\s*:\s*"([^"]+)"', response)
        body = re.search(r'"body"\s*:\s*"([\s\S]+?)"(?:\s*[,}])', response)
        if subject and body:
            return {
                "subject": subject.group(1),
                "body": body.group(1).replace("\\n", "\n")
            }
    except Exception:
        pass
    return None


def build_brief(scenario: dict) -> dict:
    """Build synthetic hiring signal brief from scenario."""
    segment = scenario["segment"]
    confidence = scenario["confidence"]
    return {
        "prospect": scenario["company"],
        "icp_classification": {
            "segment": segment,
            "segment_name": SEGMENT_NAMES[segment],
            "confidence": confidence,
            "reasons": [scenario["signal"]]
        },
        "firmographics": {
            "company": scenario["company"],
            "website": f"https://{scenario['company'].lower().replace(' ', '')}.com",
            "description": f"{scenario['company']} — technology company",
            "num_employees": "51-200"
        },
        "ai_maturity": {
            "ai_maturity_score": 2 if segment == 4 else 1,
            "confidence": confidence
        },
        "layoff_signal": {
            "layoff_detected": segment == 2,
            "confidence": 1.0 if segment == 2 else 0.0
        },
        "leadership_signal": {
            "leadership_change_detected": segment == 3
        }
    }


def scenario_to_prompt(scenario: dict) -> str:
    """Build the user prompt for a scenario."""
    segment = scenario["segment"]
    company = scenario["company"]
    confidence = scenario["confidence"]
    signal = scenario["signal"]
    constraint = scenario["constraint"]
    seg_name = SEGMENT_NAMES[segment]

    return (
        f"Write a cold outreach email for this prospect:\n\n"
        f"Company: {company}\n"
        f"ICP Segment: {segment} — {seg_name}\n"
        f"Signal confidence: {confidence}\n"
        f"Signal: {signal}\n"
        f"Specific constraint: {constraint}\n\n"
        f"Return ONLY valid JSON with subject and body fields. "
        f"No markdown, no explanation."
    )


def create_task(task_id: str, scenario: dict,
                email: dict, partition: str) -> dict:
    """Create a benchmark task from a scenario and generated email."""
    segment = scenario["segment"]
    brief = build_brief(scenario)

    return {
        "task_id": task_id,
        "source_mode": "multi_llm_synthesis",
        "difficulty": scenario["difficulty"],
        "variant": "llm_generated",
        "is_passing": True,
        "generator_model": GENERATOR_MODEL,
        "input": {
            "hiring_signal_brief": brief,
            "bench_summary": {
                "total_engineers": 60,
                "available": 34,
                "stacks": {"python": 12, "node": 8,
                           "ml": 6, "go": 4, "data": 4}
            },
            "instruction": (
                f"Write a cold outreach email to the VP Engineering at "
                f"{scenario['company']} ({SEGMENT_NAMES[segment]}, "
                f"confidence={scenario['confidence']}). "
                f"Signal: {scenario['signal']}"
            ),
            "prior_thread": []
        },
        "candidate_output": {
            "subject": email["subject"],
            "body": email["body"]
        },
        "ground_truth": {
            "required_signals": REQUIRED_SIGNALS.get(segment, ["engineering"]),
            "forbidden_phrases": FORBIDDEN_PHRASES,
            "max_subject_length": 60,
            "must_end_with_cta": True
        },
        "rubric": {
            "grounding":      {"weight": 1.0, "check": "all_claims_grounded"},
            "tone":           {"weight": 1.0, "check": "zero_banned_phrases"},
            "subject_length": {"weight": 1.0, "check": "subject_lte_60_chars"},
            "cta_present":    {"weight": 1.0, "check": "cta_in_last_paragraph"},
            "llm_judge":      {"weight": 1.0, "check": "avg_tone_marker_gte_4"}
        },
        "metadata": {
            "created_at": datetime.now().isoformat() + "Z",
            "partition": partition,
            "probe_ids": ["P10", "P16", "P20"],
            "source_trace_id": None,
            "judge_score": None,
            "expected_score": 1.0,
            "generator_model": GENERATOR_MODEL
        }
    }


def assign_partition(idx: int, total: int) -> str:
    pct = idx / total
    if pct < 0.50:
        return "train"
    elif pct < 0.80:
        return "dev"
    else:
        return "held_out"


def main():
    print("\n" + "="*60)
    print("Mode 3 — Multi-LLM Synthesis Task Generator")
    print(f"Model: {GENERATOR_MODEL}")
    print("="*60)

    if not OPENROUTER_KEY:
        print("❌ No OpenRouter API key found in .env")
        return

    tasks        = []
    accepted     = 0
    rejected     = 0
    api_calls    = 0
    counter      = [0]

    def next_id():
        counter[0] += 1
        return f"TB-LLM{counter[0]:03d}"

    total_scenarios = len(SCENARIOS)

    for idx, scenario in enumerate(SCENARIOS):
        company    = scenario["company"]
        segment    = scenario["segment"]
        difficulty = scenario["difficulty"]
        partition  = assign_partition(idx, total_scenarios)

        print(f"\n[{idx+1}/{total_scenarios}] {company} "
              f"(Seg {segment}, {difficulty}, {partition})")

        prompt = scenario_to_prompt(scenario)

        # Try up to 2 times per scenario
        success = False
        for attempt in range(2):
            if attempt > 0:
                print(f"    Retrying...")
                time.sleep(1)

            api_calls += 1
            response = call_openrouter(prompt)

            if not response:
                print(f"    ❌ No response from API")
                continue

            email = parse_email(response)
            if not email:
                print(f"    ❌ Could not parse email from response")
                continue

            # Build task and score it
            task = create_task(next_id(), scenario, email, partition)
            result = score_task(task)

            if result["all_pass"]:
                tasks.append(task)
                accepted += 1
                success = True
                print(f"    ✅ Accepted | "
                      f"subject='{email['subject'][:45]}' | "
                      f"score={result['overall_score']}")
                break
            else:
                rejected += 1
                fails = [k for k, v in result["checks"].items()
                         if not v["pass"]]
                print(f"    ⚠️  Rejected | fails={fails} | "
                      f"subject='{email['subject'][:35]}'")

        if not success:
            print(f"    ❌ Skipped after 2 attempts")

        # Rate limit — be polite to API
        time.sleep(0.5)

    # Save accepted tasks
    counts = {"train": 0, "dev": 0, "held_out": 0}
    for task in tasks:
        partition = task["metadata"]["partition"]
        path = OUTPUT_DIR / partition / f"{task['task_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(task, indent=2))
        counts[partition] += 1

    # Save log
    log = {
        "generated_at":   datetime.now().isoformat(),
        "mode":           "multi_llm_synthesis",
        "generator_model": GENERATOR_MODEL,
        "scenarios_tried": total_scenarios,
        "api_calls":      api_calls,
        "accepted":       accepted,
        "rejected":       rejected,
        "acceptance_rate": round(accepted/api_calls, 2) if api_calls else 0,
        "tasks_generated": len(tasks),
        "partition_counts": counts,
    }
    (SCRIPTS_DIR / "llm_generation_log.json").write_text(
        json.dumps(log, indent=2))

    print(f"\n{'='*60}")
    print(f"✅ Mode 3 complete")
    print(f"   Scenarios tried:  {total_scenarios}")
    print(f"   API calls:        {api_calls}")
    print(f"   Accepted:         {accepted}")
    print(f"   Rejected:         {rejected}")
    print(f"   Acceptance rate:  {round(accepted/api_calls*100) if api_calls else 0}%")
    print(f"   Train: {counts['train']} | "
          f"Dev: {counts['dev']} | "
          f"Held-out: {counts['held_out']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

"""
Mode 3 v2 — Additional Multi-LLM Synthesis Tasks
Target: 48 more tasks to bring multi_llm_synthesis to ~25%
Cost:   ~$0.20-0.30
Model:  Qwen3-235b via OpenRouter
"""

import json, os, re, sys, time, requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('/home/yakob/week11-sales-bench/.env')
sys.path.insert(0, '/home/yakob/week11-sales-bench')
from scoring_evaluator import score_task

OUTPUT_DIR     = Path("/home/yakob/week11-sales-bench/tenacious_bench_v0.1")
SCRIPTS_DIR    = Path("/home/yakob/week11-sales-bench/generation_scripts")
OPENROUTER_KEY = os.getenv('OPENROUTER_API_KEY')
MODEL          = "qwen/qwen3-235b-a22b"

FORBIDDEN_PHRASES = [
    "just circling back", "hope this finds you well",
    "just following up", "per my last email",
    "top talent", "world-class", "rockstar", "a-players",
    "ninja", "wizard", "bench", "aggressive hiring",
    "skyrocket", "supercharge", "synergize", "synergy",
    "game-changer", "disruptor", "you are missing",
    "falling behind", "behind the curve", "catch up",
    "quick question", "quick chat", "obviously", "clearly",
]

REQUIRED_SIGNALS = {
    1: ["funding", "growth", "engineering", "capacity", "roles"],
    2: ["restructuring", "cost", "delivery", "capacity"],
    3: ["leadership", "engineering", "vendor", "mix", "new"],
    4: ["ai", "capability", "ml", "platform", "peer", "data"]
}

SEGMENT_NAMES = {
    1: "Recently-funded startup",
    2: "Post-layoff restructuring",
    3: "Leadership change",
    4: "AI capability gap"
}

SYSTEM_PROMPT = """You are a Tenacious Intelligence Corporation outreach writer.

CRITICAL — EMAIL MUST END WITH THIS EXACT LINE BEFORE SIGNATURE:
"Worth 15 minutes this week? → http://localhost:3000/yakob/30min"

BANNED PHRASES (never use any):
"just circling back", "hope this finds you well", "just following up",
"per my last email", "top talent", "world-class", "rockstar", "a-players",
"bench" (never to a prospect), "aggressive hiring", "skyrocket", "synergize",
"falling behind", "behind the curve", "catch up", "quick question", "quick chat"

RULES:
- Subject: max 60 characters, state intent clearly
- Body: max 120 words for cold outreach
- One ask only — the Cal.com link
- Signature: Research Partner / Tenacious Intelligence Corporation / gettenacious.com

OUTPUT: JSON only, no markdown, no explanation:
{"subject": "...", "body": "..."}"""

# 48 diverse scenarios spread across all 4 segments
SCENARIOS_V2 = [
    # Segment 1 — Funded startups (12 scenarios)
    {"segment":1,"difficulty":"easy","confidence":"high","company":"Marble Technologies",
     "signal":"Series A $20M in March, open backend roles tripled from 3 to 9",
     "constraint":"Name the funding amount and role count change specifically"},
    {"segment":1,"difficulty":"easy","confidence":"high","company":"Cyan Software",
     "signal":"Series B $35M closed last month, 7 open engineering roles",
     "constraint":"Reference the Series B and current open role count"},
    {"segment":1,"difficulty":"medium","confidence":"medium","company":"Dune Platform",
     "signal":"Series A detected but amount unconfirmed, 4 open roles",
     "constraint":"Medium confidence — do not assert the funding amount"},
    {"segment":1,"difficulty":"easy","confidence":"high","company":"Frost Analytics",
     "signal":"Seed $8M in February, first 4 engineering hires on LinkedIn",
     "constraint":"Early stage seed — reference the LinkedIn hires specifically"},
    {"segment":1,"difficulty":"medium","confidence":"medium","company":"Orbit Labs",
     "signal":"Series A likely — leadership LinkedIn shows rapid team growth",
     "constraint":"No confirmed funding — ask rather than assert"},
    {"segment":1,"difficulty":"easy","confidence":"high","company":"Stellar Systems",
     "signal":"Series C $60M, engineering team growing from 20 to 40",
     "constraint":"Series C stage — acknowledge scale, pitch capacity not basics"},
    {"segment":1,"difficulty":"hard","confidence":"very_low","company":"Ghost Startup",
     "signal":"No public signal — 8 engineers on LinkedIn, no roles posted",
     "constraint":"Very low confidence — resource value-add only, no pitch"},
    {"segment":1,"difficulty":"easy","confidence":"high","company":"Peak Software",
     "signal":"Series A $16M in April, Python and data roles up 4x",
     "constraint":"Name the specific stack roles that tripled"},
    {"segment":1,"difficulty":"medium","confidence":"high","company":"Ridge Platform",
     "signal":"Series B $42M, hiring data and ML engineers aggressively",
     "constraint":"Do not use aggressive — use specific role count instead"},
    {"segment":1,"difficulty":"easy","confidence":"high","company":"Cove Technologies",
     "signal":"Seed extension $5M, team of 6 engineers, first senior hires expected",
     "constraint":"Very early stage — low ask, resource offer preferred"},
    {"segment":1,"difficulty":"medium","confidence":"medium","company":"Arc Systems",
     "signal":"Funding detected but stage unclear, 3 open roles",
     "constraint":"Use conditional language — if funding is confirmed"},
    {"segment":1,"difficulty":"easy","confidence":"high","company":"Vale Engineering",
     "signal":"Series A $24M closed in January, open roles went from 2 to 8",
     "constraint":"Reference January timing and exact role increase"},

    # Segment 2 — Post-layoff (12 scenarios)
    {"segment":2,"difficulty":"easy","confidence":"high","company":"Mast Cloud",
     "signal":"Laid off 90 engineers in February, still active on delivery",
     "constraint":"Acknowledge respectfully, frame around delivery preservation"},
    {"segment":2,"difficulty":"medium","confidence":"medium","company":"Dusk Platform",
     "signal":"Layoff detected but headcount unknown, funding still active",
     "constraint":"Medium confidence — conditional framing throughout"},
    {"segment":2,"difficulty":"easy","confidence":"high","company":"Flint Systems",
     "signal":"10% headcount reduction in Q1, board pushed for cost savings",
     "constraint":"Name the 10% specifically, frame around maintaining delivery"},
    {"segment":2,"difficulty":"medium","confidence":"high","company":"Slate Software",
     "signal":"Laid off 120 engineers in March, now rehiring selectively",
     "constraint":"Acknowledge the rehiring signal — selective capacity rebuild"},
    {"segment":2,"difficulty":"easy","confidence":"high","company":"Ash Technologies",
     "signal":"200 layoffs in January, Series C funding still available",
     "constraint":"Name the layoff count and frame cost preservation pitch"},
    {"segment":2,"difficulty":"hard","confidence":"low","company":"Ember Platform",
     "signal":"Possible restructuring signal — website down, leadership quiet",
     "constraint":"Low confidence — do not assert restructuring, ask gently"},
    {"segment":2,"difficulty":"easy","confidence":"high","company":"Cobalt Systems",
     "signal":"15% workforce reduction in Q4, engineering still active",
     "constraint":"Name the 15% and frame around engineering delivery continuity"},
    {"segment":2,"difficulty":"medium","confidence":"high","company":"Iron Cloud",
     "signal":"Layoff of 80 engineers, now using contractors for delivery",
     "constraint":"Contractor angle — position managed team as better than contractors"},
    {"segment":2,"difficulty":"easy","confidence":"high","company":"Stone Platform",
     "signal":"300 layoffs in February, cost restructuring confirmed by CEO",
     "constraint":"CEO confirmation makes this high confidence — name the scale"},
    {"segment":2,"difficulty":"medium","confidence":"medium","company":"Chalk Software",
     "signal":"Restructuring detected — engineering team size unclear post-layoff",
     "constraint":"Size unknown — use conditional language on capacity claims"},
    {"segment":2,"difficulty":"easy","confidence":"high","company":"Flare Analytics",
     "signal":"8% headcount reduction, delivery team preserved, cost focus",
     "constraint":"8% reduction — frame as cost optimization not crisis"},
    {"segment":2,"difficulty":"medium","confidence":"high","company":"Blaze Systems",
     "signal":"Laid off 60 engineers in January, board approved offshore exploration",
     "constraint":"Board approved offshore — this is a warm signal, reference it"},

    # Segment 3 — Leadership change (12 scenarios)
    {"segment":3,"difficulty":"easy","confidence":"high","company":"Tide Engineering",
     "signal":"New CTO from Cloudflare announced 12 days ago",
     "constraint":"Reference the Cloudflare background and 12-day timing"},
    {"segment":3,"difficulty":"medium","confidence":"medium","company":"Gulf Systems",
     "signal":"VP Engineering change detected 55 days ago — limited public signal",
     "constraint":"Medium confidence — acknowledge limited public signal"},
    {"segment":3,"difficulty":"easy","confidence":"high","company":"Bay Analytics",
     "signal":"New Head of Engineering from Twilio, 25 days ago",
     "constraint":"Name the Twilio background and 25-day reassessment window"},
    {"segment":3,"difficulty":"hard","confidence":"low","company":"Crest Cloud",
     "signal":"Possible leadership change — LinkedIn title updated but no announcement",
     "constraint":"Very uncertain — frame as a question not a statement"},
    {"segment":3,"difficulty":"easy","confidence":"high","company":"Port Software",
     "signal":"New CTO from AWS announced 18 days ago on company blog",
     "constraint":"Reference the AWS background and blog announcement"},
    {"segment":3,"difficulty":"medium","confidence":"high","company":"Shore Platform",
     "signal":"VP Engineering hired 40 days ago, previously at Stripe",
     "constraint":"Stripe background plus 40-day window — specific framing"},
    {"segment":3,"difficulty":"easy","confidence":"high","company":"Cliff Technologies",
     "signal":"New VP Engineering 15 days ago from Datadog",
     "constraint":"Datadog background, 15-day window — very fresh"},
    {"segment":3,"difficulty":"medium","confidence":"medium","company":"Mesa Systems",
     "signal":"CTO change 65 days ago — vendor mix review window closing",
     "constraint":"65 days — acknowledge the window is narrowing"},
    {"segment":3,"difficulty":"easy","confidence":"high","company":"Cove Platform",
     "signal":"New Head of Engineering from Google, 8 days ago",
     "constraint":"Google background, 8 days — extremely fresh window"},
    {"segment":3,"difficulty":"hard","confidence":"low","company":"Dune Engineering",
     "signal":"Leadership change rumored but not confirmed publicly",
     "constraint":"Rumored only — must hedge every claim, ask rather than assert"},
    {"segment":3,"difficulty":"medium","confidence":"high","company":"Wave Systems",
     "signal":"VP Engineering hired 35 days ago from Salesforce",
     "constraint":"Salesforce background, 35-day window, vendor reassessment angle"},
    {"segment":3,"difficulty":"easy","confidence":"high","company":"Reef Analytics",
     "signal":"New CTO from Netflix announced 20 days ago",
     "constraint":"Netflix background, 20-day window — reference the announcement"},

    # Segment 4 — AI capability gap (12 scenarios)
    {"segment":4,"difficulty":"easy","confidence":"high","company":"Prism Systems",
     "signal":"6 peer companies posted senior ML engineer roles in 90 days, Prism has none",
     "constraint":"6 peers — name the count, two readings framing"},
    {"segment":4,"difficulty":"medium","confidence":"medium","company":"Lens Analytics",
     "signal":"AI maturity 2/3, partial ML stack, 2 peers with data contracts function",
     "constraint":"Medium confidence — ask about deliberate choice"},
    {"segment":4,"difficulty":"easy","confidence":"high","company":"Focus Intelligence",
     "signal":"4 adjacent companies building agentic systems, Focus has no ML roles",
     "constraint":"Agentic systems specifically — not generic AI"},
    {"segment":4,"difficulty":"hard","confidence":"low","company":"Dim Analytics",
     "signal":"AI maturity borderline 1-2, peer data limited",
     "constraint":"Low confidence — resource offer not capability gap pitch"},
    {"segment":4,"difficulty":"medium","confidence":"high","company":"Beam Systems",
     "signal":"AI maturity 3/3, no MLOps function publicly visible, 5 peers have one",
     "constraint":"High AI maturity already — pitch specialized capacity not basics"},
    {"segment":4,"difficulty":"easy","confidence":"high","company":"Ray Platform",
     "signal":"3 sector peers posted data contracts engineer roles, Ray has none",
     "constraint":"Data contracts specifically — very technical framing"},
    {"segment":4,"difficulty":"medium","confidence":"medium","company":"Glow Intelligence",
     "signal":"AI maturity 2/3, building ML platform internally, 4 peers ahead",
     "constraint":"Building internally — frame as capacity to accelerate not replace"},
    {"segment":4,"difficulty":"easy","confidence":"high","company":"Spark Analytics",
     "signal":"5 peer companies with public MLOps roles, Spark AI maturity 2/3",
     "constraint":"Frame with two readings — deliberate or not yet scoped"},
    {"segment":4,"difficulty":"medium","confidence":"high","company":"Flux Intelligence",
     "signal":"AI maturity 3/3, 3 peers building agentic systems squads",
     "constraint":"High maturity — pitch specialized squad not general engineering"},
    {"segment":4,"difficulty":"hard","confidence":"low","company":"Pale Systems",
     "signal":"Possible AI capability gap — limited public signal available",
     "constraint":"Low confidence — ask whether this is on their roadmap"},
    {"segment":4,"difficulty":"easy","confidence":"high","company":"Hue Analytics",
     "signal":"4 peers posted senior data engineer roles in 90 days, Hue has 0",
     "constraint":"Data engineering specifically, four peers, 90-day window"},
    {"segment":4,"difficulty":"medium","confidence":"medium","company":"Shade Intelligence",
     "signal":"AI maturity 2/3, sector peers advancing faster on ML stack",
     "constraint":"Medium — frame as research finding, not assertion"},
]


def call_openrouter(prompt):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/yakobd/week11-sales-bench",
            },
            json={
                "model": MODEL,
                "max_tokens": 500,
                "temperature": 0.6,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": prompt}
                ]
            },
            timeout=30
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"    API error: {e}")
        return None


def parse_email(response):
    try:
        clean = response.strip()
        if "```" in clean:
            clean = re.sub(r"```(?:json)?", "", clean).strip()
        data = json.loads(clean)
        if "subject" in data and "body" in data:
            return data
    except:
        pass
    try:
        subject = re.search(r'"subject"\s*:\s*"([^"]+)"', response)
        body    = re.search(r'"body"\s*:\s*"([\s\S]+?)"(?:\s*[,}])', response)
        if subject and body:
            return {
                "subject": subject.group(1),
                "body":    body.group(1).replace("\\n", "\n")
            }
    except:
        pass
    return None


def build_brief(scenario):
    segment    = scenario["segment"]
    confidence = scenario["confidence"]
    return {
        "prospect": scenario["company"],
        "icp_classification": {
            "segment":      segment,
            "segment_name": SEGMENT_NAMES[segment],
            "confidence":   confidence,
            "reasons":      [scenario["signal"]]
        },
        "firmographics": {
            "company":       scenario["company"],
            "website":       f"https://{scenario['company'].lower().replace(' ','')}.com",
            "description":   f"{scenario['company']} — technology company",
            "num_employees": "51-200"
        },
        "ai_maturity": {
            "ai_maturity_score": 2 if segment == 4 else 1,
            "confidence":        confidence
        },
        "layoff_signal":     {"layoff_detected": segment == 2},
        "leadership_signal": {"leadership_change_detected": segment == 3}
    }


def make_prompt(scenario):
    return (
        f"Write a cold outreach email.\n\n"
        f"Company: {scenario['company']}\n"
        f"Segment: {scenario['segment']} — {SEGMENT_NAMES[scenario['segment']]}\n"
        f"Confidence: {scenario['confidence']}\n"
        f"Signal: {scenario['signal']}\n"
        f"Constraint: {scenario['constraint']}\n\n"
        f"REMEMBER: The second-to-last paragraph MUST be:\n"
        f"'Worth 15 minutes this week? → http://localhost:3000/yakob/30min'\n\n"
        f"Return ONLY valid JSON: {{\"subject\": \"...\", \"body\": \"...\"}}"
    )


def assign_partition(idx, total):
    pct = idx / total
    if pct < 0.50:  return "train"
    elif pct < 0.80: return "dev"
    else:            return "held_out"


def main():
    print("\n" + "="*60)
    print("Mode 3 v2 — Additional Multi-LLM Synthesis Tasks")
    print(f"Scenarios: {len(SCENARIOS_V2)} | Model: {MODEL}")
    print("="*60)

    # Get current LLM task counter
    existing = []
    for p in ['train','dev','held_out']:
        existing.extend(list(
            Path(f'/home/yakob/week11-sales-bench/tenacious_bench_v0.1/{p}')
            .glob('TB-LLM*.json')))
    counter = [len(existing)]

    def next_id():
        counter[0] += 1
        return f"TB-LLM{counter[0]:03d}"

    tasks    = []
    accepted = 0
    rejected = 0
    api_calls = 0
    total    = len(SCENARIOS_V2)

    for idx, scenario in enumerate(SCENARIOS_V2):
        company   = scenario["company"]
        segment   = scenario["segment"]
        partition = assign_partition(idx, total)
        prompt    = make_prompt(scenario)

        print(f"\n[{idx+1}/{total}] {company} "
              f"(Seg {segment}, {scenario['difficulty']}, {partition})")

        success = False
        for attempt in range(3):
            if attempt > 0:
                time.sleep(1)

            api_calls += 1
            response = call_openrouter(prompt)
            if not response:
                continue

            email = parse_email(response)
            if not email:
                print(f"    ❌ Parse failed attempt {attempt+1}")
                continue

            task = {
                "task_id":     next_id(),
                "source_mode": "multi_llm_synthesis",
                "difficulty":  scenario["difficulty"],
                "variant":     "llm_generated_v2",
                "is_passing":  True,
                "input": {
                    "hiring_signal_brief": build_brief(scenario),
                    "bench_summary": {
                        "total_engineers": 60, "available": 34,
                        "stacks": {"python": 12, "node": 8,
                                   "ml": 6, "go": 4, "data": 4}
                    },
                    "instruction": (
                        f"Write outreach for {company} — {scenario['signal']}"
                    ),
                    "prior_thread": []
                },
                "candidate_output": {
                    "subject": email["subject"],
                    "body":    email["body"]
                },
                "ground_truth": {
                    "required_signals":   REQUIRED_SIGNALS.get(segment, ["engineering"]),
                    "forbidden_phrases":  FORBIDDEN_PHRASES,
                    "max_subject_length": 60,
                    "must_end_with_cta":  True
                },
                "rubric": {
                    "grounding":      {"weight": 1.0, "check": "all_claims_grounded"},
                    "tone":           {"weight": 1.0, "check": "zero_banned_phrases"},
                    "subject_length": {"weight": 1.0, "check": "subject_lte_60_chars"},
                    "cta_present":    {"weight": 1.0, "check": "cta_in_last_paragraph"},
                    "llm_judge":      {"weight": 1.0, "check": "avg_tone_marker_gte_4"}
                },
                "metadata": {
                    "created_at":      datetime.now().isoformat() + "Z",
                    "partition":       partition,
                    "probe_ids":       ["P10", "P16", "P20"],
                    "source_trace_id": None,
                    "judge_score":     None,
                    "expected_score":  1.0,
                    "generator_model": MODEL
                }
            }

            result = score_task(task)
            if result["all_pass"]:
                path = OUTPUT_DIR / partition / f"{task['task_id']}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(task, indent=2))
                tasks.append(task)
                accepted += 1
                success = True
                print(f"    ✅ subject='{email['subject'][:45]}'")
                break
            else:
                rejected += 1
                fails = [k for k,v in result["checks"].items() if not v["pass"]]
                print(f"    ⚠️  Attempt {attempt+1} rejected | fails={fails}")

        if not success:
            print(f"    ❌ Skipped after 3 attempts")

        time.sleep(0.3)

    # Save log
    log = {
        "generated_at":    datetime.now().isoformat(),
        "mode":            "multi_llm_synthesis_v2",
        "generator_model": MODEL,
        "scenarios_tried": total,
        "api_calls":       api_calls,
        "accepted":        accepted,
        "rejected":        rejected,
        "acceptance_rate": round(accepted/api_calls, 2) if api_calls else 0,
    }
    (SCRIPTS_DIR / "llm_generation_v2_log.json").write_text(
        json.dumps(log, indent=2))

    print(f"\n{'='*60}")
    print(f"✅ Mode 3 v2 complete")
    print(f"   Scenarios:       {total}")
    print(f"   API calls:       {api_calls}")
    print(f"   Accepted:        {accepted}")
    print(f"   Rejected:        {rejected}")
    print(f"   Acceptance rate: {round(accepted/api_calls*100) if api_calls else 0}%")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

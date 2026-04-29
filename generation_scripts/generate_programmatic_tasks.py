"""
Mode 2 — Programmatic Task Generator
Creates tasks by sweeping parameter combinations.
Targets: Segments 3 and 4 (missing from trace pool)
         Hard difficulty adversarial cases
         Diverse signal combinations

What:  Parameter sweep across segments, signals, difficulty levels
Why:   Fills gaps Mode 1 cannot — Segments 3 and 4, diverse signals
Tools: Pure Python, no LLM calls
"""

import json
from pathlib import Path
from datetime import datetime
from collections import Counter

OUTPUT_DIR  = Path("/home/yakob/week11-sales-bench/tenacious_bench_v0.1")
SCRIPTS_DIR = Path("/home/yakob/week11-sales-bench/generation_scripts")

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

# ── Synthetic company profiles ──────────────────────────────────────
# Each profile represents a realistic company scenario
COMPANY_PROFILES = [

    # ── SEGMENT 3 — Leadership Change (new CTO/VP Eng) ──────────────
    {
        "company": "Helix Engineering",
        "segment": 3, "confidence": "high",
        "num_employees": "201-500",
        "reasons": ["New CTO announced 18 days ago — vendor reassessment window"],
        "layoff": False, "funding": False, "leadership_change": True,
        "leader_name": "Dr. Sarah Chen", "leader_title": "CTO",
        "leader_days_ago": 18,
        "ai_maturity": 1,
        "website": "https://helixengineering.io"
    },
    {
        "company": "Meridian Labs",
        "segment": 3, "confidence": "high",
        "num_employees": "51-200",
        "reasons": ["New VP Engineering hired 45 days ago"],
        "layoff": False, "funding": False, "leadership_change": True,
        "leader_name": "James Okonkwo", "leader_title": "VP Engineering",
        "leader_days_ago": 45,
        "ai_maturity": 0,
        "website": "https://meridianlabs.com"
    },
    {
        "company": "Apex Systems",
        "segment": 3, "confidence": "medium",
        "num_employees": "501-1000",
        "reasons": ["Leadership change detected — monitor for tech role"],
        "layoff": False, "funding": False, "leadership_change": True,
        "leader_name": "Maria Santos", "leader_title": "CTO",
        "leader_days_ago": 72,
        "ai_maturity": 2,
        "website": "https://apexsystems.io"
    },
    {
        "company": "Vanta Technologies",
        "segment": 3, "confidence": "high",
        "num_employees": "201-500",
        "reasons": ["New VP Engineering 30 days ago — first 90-day window open"],
        "layoff": False, "funding": False, "leadership_change": True,
        "leader_name": "Alex Kim", "leader_title": "VP Engineering",
        "leader_days_ago": 30,
        "ai_maturity": 1,
        "website": "https://vanta.com"
    },
    {
        "company": "Cascade Data",
        "segment": 3, "confidence": "medium",
        "num_employees": "51-200",
        "reasons": ["CTO change detected — vendor mix review likely"],
        "layoff": False, "funding": True, "leadership_change": True,
        "leader_name": "Priya Nair", "leader_title": "CTO",
        "leader_days_ago": 60,
        "ai_maturity": 2,
        "website": "https://cascadedata.com"
    },
    {
        "company": "Solstice Platform",
        "segment": 3, "confidence": "low",
        "num_employees": "51-200",
        "reasons": ["Possible leadership change — signal confidence low"],
        "layoff": False, "funding": False, "leadership_change": True,
        "leader_name": "Unknown", "leader_title": "VP Engineering",
        "leader_days_ago": 90,
        "ai_maturity": 0,
        "website": "https://solsticeplatform.com"
    },

    # ── SEGMENT 4 — AI Capability Gap ───────────────────────────────
    {
        "company": "Nimbus Analytics",
        "segment": 4, "confidence": "high",
        "num_employees": "51-200",
        "reasons": [
            "AI maturity 2/3 — eligible for Segment 4 pitch",
            "3 peer companies posted MLOps roles in last 90 days"
        ],
        "layoff": False, "funding": True, "leadership_change": False,
        "ai_maturity": 2, "peer_count": 3, "peer_role": "MLOps engineer",
        "website": "https://nimbusanalytics.com"
    },
    {
        "company": "Orion ML",
        "segment": 4, "confidence": "high",
        "num_employees": "51-200",
        "reasons": [
            "AI maturity 2/3",
            "4 adjacent companies building agentic systems capability"
        ],
        "layoff": False, "funding": True, "leadership_change": False,
        "ai_maturity": 2, "peer_count": 4, "peer_role": "ML platform engineer",
        "website": "https://orionml.io"
    },
    {
        "company": "Vertex Intelligence",
        "segment": 4, "confidence": "medium",
        "num_employees": "201-500",
        "reasons": [
            "AI maturity 2/3 with partial ML stack signal",
            "Competitor gap: 2 peers with public MLOps function"
        ],
        "layoff": False, "funding": False, "leadership_change": False,
        "ai_maturity": 2, "peer_count": 2, "peer_role": "senior ML engineer",
        "website": "https://vertexintelligence.com"
    },
    {
        "company": "Pulse Data",
        "segment": 4, "confidence": "high",
        "num_employees": "51-200",
        "reasons": [
            "AI maturity 3/3 — strong AI signal",
            "No MLOps role posted publicly — capability gap likely"
        ],
        "layoff": False, "funding": True, "leadership_change": False,
        "ai_maturity": 3, "peer_count": 5, "peer_role": "MLOps engineer",
        "website": "https://pulsedata.io"
    },
    {
        "company": "Epoch Systems",
        "segment": 4, "confidence": "medium",
        "num_employees": "51-200",
        "reasons": [
            "AI maturity 2/3",
            "Sector peers building data contracts and ML platform"
        ],
        "layoff": False, "funding": True, "leadership_change": False,
        "ai_maturity": 2, "peer_count": 3, "peer_role": "data engineer",
        "website": "https://epochsystems.io"
    },
    {
        "company": "Qubit Labs",
        "segment": 4, "confidence": "low",
        "num_employees": "11-50",
        "reasons": [
            "AI maturity 2/3 — borderline signal",
            "Limited peer data available"
        ],
        "layoff": False, "funding": False, "leadership_change": False,
        "ai_maturity": 2, "peer_count": 2, "peer_role": "ML engineer",
        "website": "https://qubitlabs.com"
    },

    # ── SEGMENT 1 — Additional funded startups ───────────────────────
    {
        "company": "Luminary AI",
        "segment": 1, "confidence": "high",
        "num_employees": "11-50",
        "reasons": ["Series A $18M in January — engineering hiring expected"],
        "layoff": False, "funding": True, "leadership_change": False,
        "funding_amount": "$18M", "funding_type": "Series A",
        "funding_days_ago": 45, "open_roles": 6,
        "ai_maturity": 1,
        "website": "https://luminaryai.com"
    },
    {
        "company": "Prism Networks",
        "segment": 1, "confidence": "medium",
        "num_employees": "51-200",
        "reasons": ["Series B $32M detected — scaling expected"],
        "layoff": False, "funding": True, "leadership_change": False,
        "funding_amount": "$32M", "funding_type": "Series B",
        "funding_days_ago": 90, "open_roles": 4,
        "ai_maturity": 0,
        "website": "https://prismnetworks.io"
    },

    # ── SEGMENT 2 — Additional post-layoff ───────────────────────────
    {
        "company": "Horizon Cloud",
        "segment": 2, "confidence": "high",
        "num_employees": "501-1000",
        "reasons": [
            "Layoff detected — 150 employees, March 2024",
            "Recent funding detected — fresh budget available"
        ],
        "layoff": True, "layoff_count": 150, "funding": True,
        "leadership_change": False,
        "ai_maturity": 1,
        "website": "https://horizoncloud.com"
    },
    {
        "company": "Atlas Software",
        "segment": 2, "confidence": "medium",
        "num_employees": "201-500",
        "reasons": ["Layoff detected — cost restructuring signal"],
        "layoff": True, "layoff_count": 80, "funding": False,
        "leadership_change": False,
        "ai_maturity": 0,
        "website": "https://atlassoftware.com"
    },
]


def build_brief(profile: dict) -> dict:
    """Build a synthetic hiring signal brief from a profile."""
    segment = profile["segment"]
    reasons = profile["reasons"]
    confidence = profile["confidence"]
    ai_maturity = profile.get("ai_maturity", 0)

    brief = {
        "prospect": profile["company"],
        "icp_classification": {
            "segment": segment,
            "segment_name": SEGMENT_NAMES[segment],
            "confidence": confidence,
            "reasons": reasons
        },
        "firmographics": {
            "company": profile["company"],
            "website": profile.get("website", ""),
            "description": f"{profile['company']} is a technology company.",
            "num_employees": profile["num_employees"],
        },
        "ai_maturity": {
            "ai_maturity_score": ai_maturity,
            "confidence": confidence
        },
        "layoff_signal": {
            "layoff_detected": profile.get("layoff", False),
            "total_laid_off": str(profile.get("layoff_count", 0)),
            "confidence": 1.0 if profile.get("layoff") else 0.0
        },
        "leadership_signal": {
            "leadership_change_detected": profile.get("leadership_change", False),
            "leader_name": profile.get("leader_name", ""),
            "leader_title": profile.get("leader_title", ""),
            "days_since_hire": profile.get("leader_days_ago", 0)
        }
    }
    return brief


def generate_seg3_email(profile: dict) -> tuple:
    """Generate email for Segment 3 — leadership change."""
    company = profile["company"]
    leader  = profile.get("leader_name", "the new leader")
    title   = profile.get("leader_title", "CTO")
    days    = profile.get("leader_days_ago", 30)
    confidence = profile["confidence"]

    subject = f"Context: engineering vendor mix at {company}"
    if len(subject) > 60:
        subject = subject[:57] + "..."

    if confidence in ["high", "medium"]:
        signal = (
            f"Congratulations on the recent leadership change at {company} — "
            f"the {title} appointment {days} days ago is the kind of moment "
            f"when vendor and offshore mix typically gets a fresh look."
        )
    else:
        signal = (
            f"{company} may have recently added new engineering leadership — "
            f"if that is the case, the first 90 days are typically when "
            f"vendor mix gets reassessed."
        )

    body = (
        f"{signal}\n\n"
        f"If offshore delivery is on your review list, we would welcome "
        f"15 minutes — managed teams with full time-zone overlap, "
        f"not staff augmentation.\n\n"
        f"Worth a conversation? → http://localhost:3000/yakob/30min\n\n"
        f"Research Partner\n"
        f"Tenacious Intelligence Corporation\n"
        f"gettenacious.com"
    )
    return subject, body


def generate_seg4_email(profile: dict) -> tuple:
    """Generate email for Segment 4 — AI capability gap."""
    company    = profile["company"]
    peer_count = profile.get("peer_count", 3)
    peer_role  = profile.get("peer_role", "ML engineer")
    ai_score   = profile.get("ai_maturity", 2)
    confidence = profile["confidence"]

    subject = f"Question on {company} AI capability"
    if len(subject) > 60:
        subject = subject[:57] + "..."

    if confidence == "high":
        signal = (
            f"{peer_count} companies adjacent to {company} in your sector "
            f"posted senior {peer_role} roles in the last 90 days. "
            f"Your team has not — two readings: a deliberate choice, "
            f"or a function not yet scoped."
        )
    else:
        signal = (
            f"Public signal suggests {company} may be building toward "
            f"specialized AI capability. Teams at this stage often hit "
            f"a talent bottleneck before a budget one."
        )

    body = (
        f"{signal}\n\n"
        f"We deliver fixed-scope AI and data engineering projects — "
        f"ML platform builds, agentic systems, data contracts — "
        f"typically 3 to 4 months. Starter scopes from $XX,XXX.\n\n"
        f"If you have already scoped this and decided against it, "
        f"I would genuinely be curious why — that is useful for us. "
        f"If not, 15 minutes: → http://localhost:3000/yakob/30min\n\n"
        f"Research Partner\n"
        f"Tenacious Intelligence Corporation\n"
        f"gettenacious.com"
    )
    return subject, body


def generate_seg1_email(profile: dict) -> tuple:
    """Generate email for Segment 1 — funded startup."""
    company    = profile["company"]
    funding    = profile.get("funding_amount", "recent funding")
    fund_type  = profile.get("funding_type", "round")
    open_roles = profile.get("open_roles", 3)
    confidence = profile["confidence"]

    subject = f"Context: {company} and engineering capacity"
    if len(subject) > 60:
        subject = subject[:57] + "..."

    if confidence == "high":
        signal = (
            f"{company} closed a {funding} {fund_type} and your open "
            f"engineering roles went from 2 to {open_roles} in the last "
            f"60 days. The typical bottleneck at this stage is recruiting "
            f"capacity, not budget."
        )
    else:
        signal = (
            f"{company} appears to have open engineering roles based on "
            f"public signals — if hiring velocity is ahead of your "
            f"full-time search, that is the pattern we solve most often."
        )

    body = (
        f"{signal}\n\n"
        f"We run dedicated engineering squads for companies scaling "
        f"post-funding — senior engineers available in 7-14 days with "
        f"3-5 hours daily time-zone overlap.\n\n"
        f"Worth 15 minutes this week? → http://localhost:3000/yakob/30min\n\n"
        f"Research Partner\n"
        f"Tenacious Intelligence Corporation\n"
        f"gettenacious.com"
    )
    return subject, body


def generate_seg2_email(profile: dict) -> tuple:
    """Generate email for Segment 2 — post-layoff."""
    company = profile["company"]
    count   = profile.get("layoff_count", 100)

    subject = f"Note on {company} restructuring"
    if len(subject) > 60:
        subject = subject[:57] + "..."

    body = (
        f"{company} has gone through a recent restructuring. "
        f"Companies in this state often need to preserve delivery "
        f"capacity while reshaping cost structure.\n\n"
        f"Tenacious provides managed engineering teams that preserve "
        f"delivery capacity while reducing cost — our engineers are "
        f"full-time employees, not contractors.\n\n"
        f"Worth 15 minutes this week to walk through how this lands "
        f"for {company}? → http://localhost:3000/yakob/30min\n\n"
        f"Research Partner\n"
        f"Tenacious Intelligence Corporation\n"
        f"gettenacious.com"
    )
    return subject, body


def generate_failing_email(profile: dict, fail_type: str) -> tuple:
    """Generate intentionally failing emails for adversarial tasks."""
    company = profile["company"]

    if fail_type == "banned_phrases":
        subject = "Hope this finds you well — quick chat about synergies?"
        body = (
            f"Hope this email finds you well! {company} is clearly scaling "
            f"aggressively and needs world-class rockstar engineers on their "
            f"bench. Our top talent will skyrocket your delivery. "
            f"Just circling back — are you open to synergizing our ecosystems?\n\n"
            f"Best, Yabi"
        )
    elif fail_type == "condescending":
        subject = f"{company} is falling behind on AI — urgent"
        body = (
            f"Your AI maturity is behind the curve. {company} is clearly "
            f"missing the strategic moves that your competitors have already "
            f"made. You are falling behind in a market where AI is no longer "
            f"optional. Tenacious can help you catch up before your next "
            f"board meeting.\n\n"
            f"Let's get on a call immediately.\n\n"
            f"Best, Yabi"
        )
    elif fail_type == "fabricated_signal":
        subject = f"Congrats on your $40M Series C!"
        body = (
            f"Congratulations on closing your $40M Series C last month — "
            f"exciting moment for the {company} team! With that level of "
            f"capital, scaling engineering aggressively is the obvious "
            f"next move. We can plug 15 engineers into your stack within "
            f"2 weeks at our standard rates.\n\n"
            f"Want to set up a call?\n\n"
            f"Best, Yabi"
        )
    elif fail_type == "subject_too_long":
        subject = (f"A comprehensive overview of how Tenacious can help "
                   f"{company} with all their engineering needs in 2026")
        body = (
            f"We noticed {company} has been growing. "
            f"Tenacious provides managed engineering teams.\n\n"
            f"Worth 15 minutes? → http://localhost:3000/yakob/30min\n\n"
            f"Research Partner\nTenacious Intelligence Corporation\ngettenacious.com"
        )
    else:
        subject = "Quick question"
        body = "Hope this finds you well. Just following up. Best, Yabi"

    return subject, body


REQUIRED_SIGNALS = {
    1: ["funding", "growth", "engineering", "capacity", "roles"],
    2: ["restructuring", "cost", "delivery", "capacity"],
    3: ["leadership", "engineering", "vendor", "overlay", "mix"],
    4: ["ai", "capability", "ml", "platform", "agentic", "data"]
}


def create_task(task_id, profile, subject, body, difficulty,
                variant, probe_ids, is_passing=True,
                instruction_override=None) -> dict:
    brief  = build_brief(profile)
    segment = profile["segment"]
    confidence = profile["confidence"]

    instruction = instruction_override or (
        f"Write a cold outreach email to the VP Engineering at "
        f"{profile['company']} (Segment {segment} — "
        f"{SEGMENT_NAMES[segment]}, confidence={confidence}). "
        f"Ground every claim in the supplied hiring signal brief."
    )

    return {
        "task_id":     task_id,
        "source_mode": "programmatic",
        "difficulty":  difficulty,
        "variant":     variant,
        "is_passing":  is_passing,
        "input": {
            "hiring_signal_brief": brief,
            "bench_summary": {
                "total_engineers": 60,
                "available": 34,
                "stacks": {"python": 12, "node": 8,
                           "ml": 6, "go": 4, "data": 4}
            },
            "instruction":  instruction,
            "prior_thread": []
        },
        "candidate_output": {
            "subject": subject,
            "body":    body
        },
        "ground_truth": {
            "required_signals":  REQUIRED_SIGNALS.get(segment, ["engineering"]),
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
            "created_at":      datetime.now().isoformat() + "Z",
            "partition":       None,
            "probe_ids":       probe_ids,
            "source_trace_id": None,
            "judge_score":     None,
            "expected_score":  1.0 if is_passing else 0.0
        }
    }


def main():
    print("\n" + "="*60)
    print("Mode 2 — Programmatic Task Generator")
    print("="*60)

    tasks = []
    counter = [0]

    def next_id():
        counter[0] += 1
        return f"TB-P{counter[0]:03d}"

    email_generators = {
        1: generate_seg1_email,
        2: generate_seg2_email,
        3: generate_seg3_email,
        4: generate_seg4_email,
    }

    for profile in COMPANY_PROFILES:
        company = profile["company"]
        segment = profile["segment"]
        confidence = profile["confidence"]
        print(f"\n{company} (Seg {segment}, {confidence}):")

        gen = email_generators[segment]

        # ── Passing task: standard outreach
        difficulty = "easy" if confidence == "high" else "medium"
        subject, body = gen(profile)
        t = create_task(next_id(), profile, subject, body,
                        difficulty, "programmatic_standard",
                        ["P10", "P16", "P20"], is_passing=True)
        tasks.append(t)
        print(f"  ✅ Standard outreach ({difficulty})")

        # ── Passing task: low confidence version
        low_profile = {**profile, "confidence": "low"}
        subject_low, body_low = gen(low_profile)
        t = create_task(next_id(), low_profile, subject_low, body_low,
                        "medium", "programmatic_low_confidence",
                        ["P05", "P30"], is_passing=True)
        tasks.append(t)
        print(f"  ✅ Low confidence variant")

        # ── Failing task: banned phrases
        subj_f, body_f = generate_failing_email(profile, "banned_phrases")
        t = create_task(next_id(), profile, subj_f, body_f,
                        "hard", "programmatic_banned_phrases_fail",
                        ["P06", "P16", "P17", "P19"],
                        is_passing=False,
                        instruction_override=(
                            f"ADVERSARIAL: The following email to {company} "
                            f"contains multiple banned phrases and should FAIL."
                        ))
        tasks.append(t)
        print(f"  ❌ Banned phrases adversarial (FAILING)")

        # ── Failing task: condescending
        subj_c, body_c = generate_failing_email(profile, "condescending")
        t = create_task(next_id(), profile, subj_c, body_c,
                        "hard", "programmatic_condescending_fail",
                        ["P04", "P18", "P32"],
                        is_passing=False,
                        instruction_override=(
                            f"ADVERSARIAL: The following email to {company} "
                            f"uses condescending framing and should FAIL."
                        ))
        tasks.append(t)
        print(f"  ❌ Condescending adversarial (FAILING)")

        # ── Failing task: fabricated signal (only for high confidence)
        if confidence == "high":
            subj_fab, body_fab = generate_failing_email(
                profile, "fabricated_signal")
            t = create_task(next_id(), profile, subj_fab, body_fab,
                            "hard", "programmatic_fabricated_signal_fail",
                            ["P07", "P10", "P12"],
                            is_passing=False,
                            instruction_override=(
                                f"ADVERSARIAL: The following email to {company} "
                                f"fabricates a funding signal not in the brief "
                                f"and should FAIL."
                            ))
            tasks.append(t)
            print(f"  ❌ Fabricated signal adversarial (FAILING)")

    # ── Assign partitions ────────────────────────────────────────────
    total = len(tasks)
    for i, task in enumerate(tasks):
        pct = i / total
        if pct < 0.50:
            task["metadata"]["partition"] = "train"
        elif pct < 0.80:
            task["metadata"]["partition"] = "dev"
        else:
            task["metadata"]["partition"] = "held_out"

    # ── Save tasks ───────────────────────────────────────────────────
    counts   = {"train": 0, "dev": 0, "held_out": 0}
    segments = Counter()
    diffs    = Counter()
    passing  = 0

    for task in tasks:
        partition = task["metadata"]["partition"]
        path = OUTPUT_DIR / partition / f"{task['task_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(task, indent=2))
        counts[partition] += 1
        seg = task["input"]["hiring_signal_brief"]["icp_classification"]["segment"]
        segments[f"Segment {seg}"] += 1
        diffs[task["difficulty"]] += 1
        if task.get("is_passing"):
            passing += 1

    # ── Save log ─────────────────────────────────────────────────────
    log = {
        "generated_at":      datetime.now().isoformat(),
        "mode":              "programmatic",
        "total_tasks":       total,
        "passing_tasks":     passing,
        "failing_tasks":     total - passing,
        "partition_counts":  counts,
        "segment_counts":    dict(segments),
        "difficulty_counts": dict(diffs),
    }
    (SCRIPTS_DIR / "programmatic_generation_log.json").write_text(
        json.dumps(log, indent=2))

    print(f"\n{'='*60}")
    print(f"✅ Programmatic generation complete")
    print(f"   Total tasks:  {total}")
    print(f"   Passing:      {passing}")
    print(f"   Failing:      {total - passing}")
    print(f"   Train:        {counts['train']}")
    print(f"   Dev:          {counts['dev']}")
    print(f"   Held-out:     {counts['held_out']}")
    print(f"\n   Segment breakdown:")
    for seg, count in sorted(segments.items()):
        pct = count / total * 100
        print(f"     {seg}: {count} ({pct:.0f}%)")
    print(f"\n   Difficulty breakdown:")
    for diff, count in sorted(diffs.items()):
        print(f"     {diff}: {count} ({count/total*100:.0f}%)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

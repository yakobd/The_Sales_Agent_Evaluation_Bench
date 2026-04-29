"""
Mode 2 v2 — Additional Programmatic Tasks
Targets: 40-60 more tasks
Focus:   More easy difficulty, more Segment 3/4, better balance
Cost:    $0.00
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

REQUIRED_SIGNALS = {
    1: ["funding", "growth", "engineering", "capacity", "roles"],
    2: ["restructuring", "cost", "delivery", "capacity"],
    3: ["leadership", "engineering", "vendor", "mix", "new"],
    4: ["ai", "capability", "ml", "platform", "peer", "data"]
}

# New company profiles — focus on easy difficulty and Seg 3/4
NEW_PROFILES = [
    # ── Segment 3 — More leadership changes ─────────────────────────
    {
        "company": "Parity Cloud",
        "segment": 3, "confidence": "high",
        "num_employees": "201-500",
        "reasons": ["New CTO from Google announced 14 days ago"],
        "layoff": False, "funding": False, "leadership_change": True,
        "leader_name": "Wei Chen", "leader_title": "CTO",
        "leader_days_ago": 14, "ai_maturity": 1,
        "website": "https://paritycloud.com"
    },
    {
        "company": "Forge Analytics",
        "segment": 3, "confidence": "high",
        "num_employees": "51-200",
        "reasons": ["VP Engineering hired 28 days ago from Datadog"],
        "layoff": False, "funding": True, "leadership_change": True,
        "leader_name": "Aisha Mensah", "leader_title": "VP Engineering",
        "leader_days_ago": 28, "ai_maturity": 2,
        "website": "https://forgeanalytics.io"
    },
    {
        "company": "Relay Systems",
        "segment": 3, "confidence": "high",
        "num_employees": "51-200",
        "reasons": ["New Head of Engineering 35 days ago"],
        "layoff": False, "funding": False, "leadership_change": True,
        "leader_name": "Carlos Mendez", "leader_title": "Head of Engineering",
        "leader_days_ago": 35, "ai_maturity": 0,
        "website": "https://relaysystems.com"
    },
    {
        "company": "Beacon Software",
        "segment": 3, "confidence": "medium",
        "num_employees": "201-500",
        "reasons": ["Leadership change detected — 50 days ago"],
        "layoff": False, "funding": True, "leadership_change": True,
        "leader_name": "Nina Patel", "leader_title": "CTO",
        "leader_days_ago": 50, "ai_maturity": 1,
        "website": "https://beaconsoftware.io"
    },
    {
        "company": "Drift Analytics",
        "segment": 3, "confidence": "high",
        "num_employees": "51-200",
        "reasons": ["New VP Engineering from Stripe, 20 days ago"],
        "layoff": False, "funding": True, "leadership_change": True,
        "leader_name": "Sam Rodriguez", "leader_title": "VP Engineering",
        "leader_days_ago": 20, "ai_maturity": 2,
        "website": "https://driftanalytics.com"
    },
    {
        "company": "Vertex Cloud",
        "segment": 3, "confidence": "high",
        "num_employees": "501-1000",
        "reasons": ["CTO departure + new hire — transition window open"],
        "layoff": False, "funding": False, "leadership_change": True,
        "leader_name": "David Kim", "leader_title": "CTO",
        "leader_days_ago": 10, "ai_maturity": 2,
        "website": "https://vertexcloud.io"
    },

    # ── Segment 4 — More AI capability gaps ─────────────────────────
    {
        "company": "Prism Intelligence",
        "segment": 4, "confidence": "high",
        "num_employees": "51-200",
        "reasons": [
            "AI maturity 2/3",
            "5 sector peers posted ML engineer roles in 90 days"
        ],
        "layoff": False, "funding": True, "leadership_change": False,
        "ai_maturity": 2, "peer_count": 5, "peer_role": "ML engineer",
        "website": "https://prismintelligence.com"
    },
    {
        "company": "Sigma Data",
        "segment": 4, "confidence": "high",
        "num_employees": "201-500",
        "reasons": [
            "AI maturity 2/3",
            "3 adjacent companies building agentic systems"
        ],
        "layoff": False, "funding": True, "leadership_change": False,
        "ai_maturity": 2, "peer_count": 3, "peer_role": "agentic systems engineer",
        "website": "https://sigmadata.io"
    },
    {
        "company": "Lambda Analytics",
        "segment": 4, "confidence": "medium",
        "num_employees": "51-200",
        "reasons": [
            "AI maturity 2/3 — partial ML stack",
            "2 peers with public data engineering function"
        ],
        "layoff": False, "funding": False, "leadership_change": False,
        "ai_maturity": 2, "peer_count": 2, "peer_role": "data engineer",
        "website": "https://lambdaanalytics.com"
    },
    {
        "company": "Atlas Intelligence",
        "segment": 4, "confidence": "high",
        "num_employees": "51-200",
        "reasons": [
            "AI maturity 3/3 — strong signal",
            "No MLOps function visible publicly"
        ],
        "layoff": False, "funding": True, "leadership_change": False,
        "ai_maturity": 3, "peer_count": 4, "peer_role": "MLOps engineer",
        "website": "https://atlasintelligence.io"
    },

    # ── Segment 1 — More funded startups (easy difficulty) ───────────
    {
        "company": "Crest Technologies",
        "segment": 1, "confidence": "high",
        "num_employees": "11-50",
        "reasons": ["Series A $15M in April — engineering hiring expected"],
        "layoff": False, "funding": True, "leadership_change": False,
        "funding_amount": "$15M", "funding_type": "Series A",
        "funding_days_ago": 30, "open_roles": 5,
        "ai_maturity": 0, "website": "https://cresttechnologies.com"
    },
    {
        "company": "Wave Platform",
        "segment": 1, "confidence": "high",
        "num_employees": "51-200",
        "reasons": ["Series B $28M — scaling engineering team"],
        "layoff": False, "funding": True, "leadership_change": False,
        "funding_amount": "$28M", "funding_type": "Series B",
        "funding_days_ago": 60, "open_roles": 8,
        "ai_maturity": 1, "website": "https://waveplatform.io"
    },
    {
        "company": "Echo Systems",
        "segment": 1, "confidence": "high",
        "num_employees": "11-50",
        "reasons": ["Seed $6M — first engineering hires expected"],
        "layoff": False, "funding": True, "leadership_change": False,
        "funding_amount": "$6M", "funding_type": "Seed",
        "funding_days_ago": 45, "open_roles": 3,
        "ai_maturity": 0, "website": "https://echosystems.com"
    },
    {
        "company": "Flux Software",
        "segment": 1, "confidence": "medium",
        "num_employees": "51-200",
        "reasons": ["Series A detected — funding amount unconfirmed"],
        "layoff": False, "funding": True, "leadership_change": False,
        "funding_amount": "undisclosed", "funding_type": "Series A",
        "funding_days_ago": 90, "open_roles": 4,
        "ai_maturity": 1, "website": "https://fluxsoftware.io"
    },

    # ── Segment 2 — More post-layoff (easy difficulty) ───────────────
    {
        "company": "Summit Cloud",
        "segment": 2, "confidence": "high",
        "num_employees": "201-500",
        "reasons": [
            "Layoff detected — 120 employees, February 2024",
            "Funding still active"
        ],
        "layoff": True, "layoff_count": 120, "funding": True,
        "leadership_change": False, "ai_maturity": 1,
        "website": "https://summitcloud.com"
    },
    {
        "company": "Nexus Platform",
        "segment": 2, "confidence": "high",
        "num_employees": "501-1000",
        "reasons": ["Layoff detected — 250 employees, Q1 2024"],
        "layoff": True, "layoff_count": 250, "funding": False,
        "leadership_change": False, "ai_maturity": 0,
        "website": "https://nexusplatform.io"
    },
]


def generate_seg1_email(profile):
    company = profile["company"]
    funding = profile.get("funding_amount", "recent funding")
    fund_type = profile.get("funding_type", "round")
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

    return subject, (
        f"{signal}\n\n"
        f"We run dedicated engineering squads for companies scaling "
        f"post-funding — senior engineers available in 7-14 days with "
        f"3-5 hours daily time-zone overlap.\n\n"
        f"Worth 15 minutes this week? → http://localhost:3000/yakob/30min\n\n"
        f"Research Partner\nTenacious Intelligence Corporation\ngettenacious.com"
    )


def generate_seg2_email(profile):
    company = profile["company"]
    subject = f"Note on {company} restructuring"
    if len(subject) > 60:
        subject = subject[:57] + "..."

    return subject, (
        f"{company} has gone through a recent restructuring. "
        f"Companies in this state often need to preserve delivery "
        f"capacity while reshaping cost structure.\n\n"
        f"Tenacious provides managed engineering teams that preserve "
        f"delivery capacity while reducing cost — our engineers are "
        f"full-time employees, not contractors.\n\n"
        f"Worth 15 minutes this week to walk through how this lands "
        f"for {company}? → http://localhost:3000/yakob/30min\n\n"
        f"Research Partner\nTenacious Intelligence Corporation\ngettenacious.com"
    )


def generate_seg3_email(profile):
    company = profile["company"]
    leader  = profile.get("leader_name", "new leader")
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

    return subject, (
        f"{signal}\n\n"
        f"If offshore delivery is on your review list, we would welcome "
        f"15 minutes — managed teams with full time-zone overlap, "
        f"not staff augmentation.\n\n"
        f"Worth a conversation? → http://localhost:3000/yakob/30min\n\n"
        f"Research Partner\nTenacious Intelligence Corporation\ngettenacious.com"
    )


def generate_seg4_email(profile):
    company    = profile["company"]
    peer_count = profile.get("peer_count", 3)
    peer_role  = profile.get("peer_role", "ML engineer")
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

    return subject, (
        f"{signal}\n\n"
        f"We deliver fixed-scope AI and data engineering projects — "
        f"ML platform builds, agentic systems, data contracts — "
        f"typically 3 to 4 months.\n\n"
        f"If you have already scoped this and decided against it, "
        f"I would genuinely be curious why. If not, 15 minutes: "
        f"→ http://localhost:3000/yakob/30min\n\n"
        f"Research Partner\nTenacious Intelligence Corporation\ngettenacious.com"
    )


def generate_failing_email(profile, fail_type):
    company = profile["company"]
    if fail_type == "banned_phrases":
        return (
            "Hope this finds you well — quick chat?",
            f"Hope this email finds you well! {company} is clearly scaling "
            f"aggressively with world-class rockstar engineers on their bench. "
            f"Our top talent will skyrocket your delivery. "
            f"Just circling back — quick question about synergizing?\n\nBest, Yabi"
        )
    elif fail_type == "condescending":
        return (
            f"{company} is falling behind competitors",
            f"Your team is clearly falling behind where your competitors are. "
            f"{company} is missing the strategic moves that the sector demands. "
            f"You are behind the curve and need to catch up before your next "
            f"board meeting.\n\n"
            f"Let's get on a call. → http://localhost:3000/yakob/30min\n\nBest, Yabi"
        )
    return ("Subject", "Body")


def build_brief(profile):
    segment = profile["segment"]
    return {
        "prospect": profile["company"],
        "icp_classification": {
            "segment": segment,
            "segment_name": SEGMENT_NAMES[segment],
            "confidence": profile["confidence"],
            "reasons": profile["reasons"]
        },
        "firmographics": {
            "company": profile["company"],
            "website": profile.get("website", ""),
            "description": f"{profile['company']} — technology company",
            "num_employees": profile["num_employees"],
        },
        "ai_maturity": {
            "ai_maturity_score": profile.get("ai_maturity", 0),
            "confidence": profile["confidence"]
        },
        "layoff_signal": {
            "layoff_detected": profile.get("layoff", False),
            "total_laid_off": str(profile.get("layoff_count", 0))
        },
        "leadership_signal": {
            "leadership_change_detected": profile.get("leadership_change", False),
            "leader_name": profile.get("leader_name", ""),
            "leader_title": profile.get("leader_title", "")
        }
    }


def create_task(task_id, profile, subject, body, difficulty,
                variant, probe_ids, is_passing, partition,
                instruction_override=None):
    segment = profile["segment"]
    brief   = build_brief(profile)

    instruction = instruction_override or (
        f"Write a cold outreach email to the VP Engineering at "
        f"{profile['company']} (Segment {segment} — "
        f"{SEGMENT_NAMES[segment]}, confidence={profile['confidence']})."
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
                "total_engineers": 60, "available": 34,
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
            "probe_ids":       probe_ids,
            "source_trace_id": None,
            "judge_score":     None,
            "expected_score":  1.0 if is_passing else 0.0
        }
    }


def main():
    print("\n" + "="*60)
    print("Mode 2 v2 — Additional Programmatic Tasks")
    print(f"Profiles: {len(NEW_PROFILES)}")
    print("="*60)

    tasks   = []
    counter = [0]

    # Get current highest P task number
    existing_p = []
    for p in ['train','dev','held_out']:
        existing_p.extend(list(
            Path(f'/home/yakob/week11-sales-bench/tenacious_bench_v0.1/{p}')
            .glob('TB-P*.json')))
    if existing_p:
        nums = [int(f.stem.replace('TB-P','')) for f in existing_p]
        counter[0] = max(nums)

    def next_id():
        counter[0] += 1
        return f"TB-P{counter[0]:03d}"

    # Partition assignment
    total_profiles = len(NEW_PROFILES)
    def get_partition(idx):
        pct = idx / total_profiles
        if pct < 0.50: return "train"
        elif pct < 0.80: return "dev"
        else: return "held_out"

    generators = {
        1: generate_seg1_email,
        2: generate_seg2_email,
        3: generate_seg3_email,
        4: generate_seg4_email,
    }

    for idx, profile in enumerate(NEW_PROFILES):
        company   = profile["company"]
        segment   = profile["segment"]
        partition = get_partition(idx)
        gen       = generators[segment]

        confidence = profile["confidence"]
        difficulty = "easy" if confidence == "high" else "medium"

        print(f"\n{company} (Seg {segment}, {confidence}, {partition}):")

        # Passing task — standard outreach
        subject, body = gen(profile)
        t = create_task(next_id(), profile, subject, body,
                        difficulty, "programmatic_v2_standard",
                        ["P10", "P16", "P20"], True, partition)
        tasks.append(t)
        print(f"  ✅ Standard outreach ({difficulty})")

        # Passing task — low confidence variant
        low_profile = {**profile, "confidence": "low"}
        subject_low, body_low = gen(low_profile)
        t = create_task(next_id(), low_profile, subject_low, body_low,
                        "medium", "programmatic_v2_low_confidence",
                        ["P05", "P30"], True, partition)
        tasks.append(t)
        print(f"  ✅ Low confidence variant")

        # Failing task — banned phrases
        subj_f, body_f = generate_failing_email(profile, "banned_phrases")
        t = create_task(next_id(), profile, subj_f, body_f,
                        "hard", "programmatic_v2_banned_phrases_fail",
                        ["P06", "P16", "P17"], False, partition,
                        f"ADVERSARIAL: banned phrases email to {company}")
        tasks.append(t)
        print(f"  ❌ Banned phrases (FAILING)")

    # Save all tasks
    counts  = {"train": 0, "dev": 0, "held_out": 0}
    passing = sum(1 for t in tasks if t.get("is_passing", True))

    for task in tasks:
        partition = task["metadata"]["partition"]
        path = OUTPUT_DIR / partition / f"{task['task_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(task, indent=2))
        counts[partition] += 1

    log = {
        "generated_at":    datetime.now().isoformat(),
        "mode":            "programmatic_v2",
        "total_tasks":     len(tasks),
        "passing_tasks":   passing,
        "failing_tasks":   len(tasks) - passing,
        "partition_counts": counts,
    }
    (SCRIPTS_DIR / "programmatic_v2_log.json").write_text(
        json.dumps(log, indent=2))

    print(f"\n{'='*60}")
    print(f"✅ Mode 2 v2 complete")
    print(f"   Total tasks:  {len(tasks)}")
    print(f"   Passing:      {passing}")
    print(f"   Failing:      {len(tasks) - passing}")
    print(f"   Train:        {counts['train']}")
    print(f"   Dev:          {counts['dev']}")
    print(f"   Held-out:     {counts['held_out']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

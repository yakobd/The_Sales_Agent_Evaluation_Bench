"""
Mode 4 — Hand-Authored Adversarial Task Generator
15 tasks targeting underrepresented failure modes.
These carry the most originality weight at grading.

Probe coverage:
P21 — Multi-thread leakage
P22 — Enrichment data shared across threads
P25 — Channel escalation without consent
P27 — Time zone mismatch
P28 — EU prospect US-centric language
P33 — Sector mismatch in gap brief
P34 — Defensive CTO reply triggers escalation
"""

import json
from pathlib import Path
from datetime import datetime

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
]

HAND_AUTHORED_TASKS = [

    # ── P21 — Multi-thread leakage ───────────────────────────────────
    {
        "task_id": "TB-HA001",
        "probe_ids": ["P21"],
        "difficulty": "hard",
        "is_passing": False,
        "label": "P21 — CEO pricing discussion leaks into VP Eng thread",
        "segment": 1,
        "partition": "train",
        "subject": "Re: the $45k monthly engagement we discussed",
        "body": (
            "Hi Sarah,\n\n"
            "Following up on the pricing discussion we had with your CEO "
            "yesterday — the $45,000 monthly rate for 6 engineers covers "
            "the full stack you outlined including the ML platform work.\n\n"
            "As your CEO mentioned, we can start onboarding in two weeks.\n\n"
            "Worth confirming the scope on a quick call? "
            "→ http://localhost:3000/yakob/30min\n\n"
            "Research Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "instruction": (
            "ADVERSARIAL P21: This email leaks pricing and context from a CEO "
            "thread into a VP Engineering thread. The VP Engineering contact "
            "never discussed pricing. This should FAIL — cross-thread "
            "contamination of context."
        ),
        "required_signals": ["series a", "engineering", "capacity"],
        "company": "Nexus Technologies",
        "confidence": "high",
        "failure_reason": "Leaks CEO pricing discussion into VP Eng thread"
    },

    # ── P21 variant — correct behavior ──────────────────────────────
    {
        "task_id": "TB-HA002",
        "probe_ids": ["P21"],
        "difficulty": "hard",
        "is_passing": True,
        "label": "P21 — Correct: VP Eng thread independent of CEO thread",
        "segment": 1,
        "partition": "train",
        "subject": "Context: Nexus Technologies engineering capacity",
        "body": (
            "Hi Sarah,\n\n"
            "Nexus closed your Series B in January and your open engineering "
            "roles have doubled in the last 60 days. The typical bottleneck "
            "at this stage is recruiting capacity, not budget.\n\n"
            "We run dedicated engineering squads for companies scaling "
            "post-funding — senior engineers available in 7-14 days with "
            "3-5 hours daily time-zone overlap.\n\n"
            "Worth 15 minutes this week? "
            "→ http://localhost:3000/yakob/30min\n\n"
            "Research Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "instruction": (
            "CORRECT P21: This email is independent — references only signals "
            "from the VP Engineering brief, no CEO thread context. Should PASS."
        ),
        "required_signals": ["series b", "january", "engineering", "roles"],
        "company": "Nexus Technologies",
        "confidence": "high",
        "failure_reason": None
    },

    # ── P22 — Stale enrichment across threads ────────────────────────
    {
        "task_id": "TB-HA003",
        "probe_ids": ["P22"],
        "difficulty": "hard",
        "is_passing": False,
        "label": "P22 — Stale enrichment: uses Yellow.ai brief for Stripe",
        "segment": 2,
        "partition": "train",
        "subject": "Note on Stripe restructuring",
        "body": (
            "Hi Alex,\n\n"
            "Stripe has gone through a recent restructuring — your team "
            "contracted by about 200 employees in March 2023 and you recently "
            "brought in KT Prasad as Chief Revenue Officer International Region.\n\n"
            "Companies in this state often need to preserve delivery capacity "
            "while reshaping cost structure.\n\n"
            "Worth 15 minutes? → http://localhost:3000/yakob/30min\n\n"
            "Research Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "instruction": (
            "ADVERSARIAL P22: This email sends Yellow.ai enrichment data "
            "(200 employees, KT Prasad) to a Stripe contact. Wrong enrichment "
            "brief used — cross-company data contamination. Should FAIL."
        ),
        "required_signals": ["stripe", "restructuring", "cost"],
        "company": "Stripe",
        "confidence": "high",
        "failure_reason": "Yellow.ai enrichment data sent to Stripe contact"
    },

    # ── P25 — SMS before email reply ────────────────────────────────
    {
        "task_id": "TB-HA004",
        "probe_ids": ["P25"],
        "difficulty": "hard",
        "is_passing": False,
        "label": "P25 — SMS sent before prospect replied to email",
        "segment": 2,
        "partition": "train",
        "subject": "Re: Note on Figma restructuring",
        "body": (
            "Hi Dylan,\n\n"
            "Tenacious here — following up on the email we sent about "
            "Figma's recent leadership changes. We also wanted to reach "
            "out via SMS to make sure you got our message.\n\n"
            "Our team can be available this week. Please reply to this "
            "email or SMS us at +1-555-0123 to confirm a time.\n\n"
            "Looking forward to connecting.\n\n"
            "Research Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "instruction": (
            "ADVERSARIAL P25: This email references an SMS sent before the "
            "prospect replied. The warm lead gate requires email reply before "
            "SMS is permitted. Channel escalation violation. Should FAIL."
        ),
        "required_signals": ["leadership", "engineering", "vendor"],
        "company": "Figma",
        "confidence": "high",
        "failure_reason": "SMS referenced before prospect replied to email"
    },

    # ── P27 — Time zone mismatch ─────────────────────────────────────
    {
        "task_id": "TB-HA005",
        "probe_ids": ["P27"],
        "difficulty": "medium",
        "is_passing": False,
        "label": "P27 — EU prospect receives Pacific time overlap language",
        "segment": 3,
        "partition": "train",
        "subject": "Context: engineering vendor mix at Adyen",
        "body": (
            "Hi Lars,\n\n"
            "Adyen recently brought in new engineering leadership — the CTO "
            "appointment 30 days ago is the kind of moment when vendor mix "
            "typically gets a fresh look.\n\n"
            "Tenacious provides managed engineering teams with 3-5 hours "
            "of daily Pacific time overlap. Our engineers are available "
            "9am-5pm PST which aligns well with your team.\n\n"
            "Worth 15 minutes? → http://localhost:3000/yakob/30min\n\n"
            "Research Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "instruction": (
            "ADVERSARIAL P27: Adyen is headquartered in Amsterdam (CET). "
            "This email references Pacific time overlap which is irrelevant "
            "and shows no research. Should FAIL — wrong timezone for EU prospect."
        ),
        "required_signals": ["leadership", "engineering", "vendor", "cet"],
        "company": "Adyen",
        "confidence": "high",
        "failure_reason": "Pacific time overlap sent to EU Amsterdam prospect"
    },

    # ── P27 — Correct EU version ─────────────────────────────────────
    {
        "task_id": "TB-HA006",
        "probe_ids": ["P27"],
        "difficulty": "medium",
        "is_passing": True,
        "label": "P27 — Correct: EU prospect gets CET overlap language",
        "segment": 3,
        "partition": "train",
        "subject": "Context: engineering vendor mix at Adyen",
        "body": (
            "Hi Lars,\n\n"
            "Adyen recently brought in new engineering leadership — the CTO "
            "appointment 30 days ago is the kind of moment when vendor mix "
            "typically gets a fresh look.\n\n"
            "Tenacious provides managed engineering teams with 3-5 hours "
            "of daily CET overlap — our engineers work European business "
            "hours with full timezone alignment.\n\n"
            "Worth 15 minutes? → http://localhost:3000/yakob/30min\n\n"
            "Research Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "instruction": (
            "CORRECT P27: EU prospect gets CET overlap language. "
            "Timezone matches Amsterdam headquarters. Should PASS."
        ),
        "required_signals": ["leadership", "engineering", "vendor", "cet"],
        "company": "Adyen",
        "confidence": "high",
        "failure_reason": None
    },

    # ── P28 — EU prospect US-centric language ────────────────────────
    {
        "task_id": "TB-HA007",
        "probe_ids": ["P28"],
        "difficulty": "medium",
        "is_passing": False,
        "label": "P28 — German prospect receives US startup framing",
        "segment": 1,
        "partition": "dev",
        "subject": "Context: Personio and engineering capacity",
        "body": (
            "Hi Klaus,\n\n"
            "Personio closed your Series E and your open engineering roles "
            "have tripled. The typical bottleneck for teams at your stage "
            "is recruiting capacity, not budget.\n\n"
            "We run dedicated engineering squads for companies scaling "
            "post-funding — senior engineers available in 7-14 days with "
            "3-5 hours daily US East Coast overlap.\n\n"
            "Worth 15 minutes this week? "
            "→ http://localhost:3000/yakob/30min\n\n"
            "Research Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "instruction": (
            "ADVERSARIAL P28: Personio is a German company (Munich). "
            "US East Coast overlap is wrong — should reference CET overlap. "
            "Should FAIL — US-centric language for EU prospect."
        ),
        "required_signals": ["series e", "engineering", "cet", "european"],
        "company": "Personio",
        "confidence": "high",
        "failure_reason": "US East Coast overlap sent to German Munich prospect"
    },

    # ── P33 — Sector mismatch in gap brief ───────────────────────────
    {
        "task_id": "TB-HA008",
        "probe_ids": ["P33"],
        "difficulty": "hard",
        "is_passing": False,
        "label": "P33 — Gap brief compares AI company to dental practices",
        "segment": 4,
        "partition": "dev",
        "subject": "Question on Yellow.ai AI capability gap",
        "body": (
            "Hi Raghu,\n\n"
            "Three companies adjacent to Yellow.ai in your sector posted "
            "senior MLOps engineer roles in the last 90 days — including "
            "Bright Dental, MedSpring Clinics, and Valley Orthodontics. "
            "Your team has not.\n\n"
            "We staff specialized AI and data engineering squads on "
            "fixed-scope engagements, typically 3-4 months.\n\n"
            "Worth 15 minutes? → http://localhost:3000/yakob/30min\n\n"
            "Research Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "instruction": (
            "ADVERSARIAL P33: Yellow.ai is a conversational AI platform. "
            "The gap brief incorrectly compares it to dental practices — "
            "classic sector mismatch from random fallback. Should FAIL — "
            "nonsensical peer comparison destroys research credibility."
        ),
        "required_signals": ["ai", "ml", "platform", "peer", "conversational"],
        "company": "Yellow.ai",
        "confidence": "high",
        "failure_reason": "AI company compared to dental practices — sector mismatch P33"
    },

    # ── P33 — Correct sector matching ───────────────────────────────
    {
        "task_id": "TB-HA009",
        "probe_ids": ["P33"],
        "difficulty": "hard",
        "is_passing": True,
        "label": "P33 — Correct: AI company compared to AI sector peers",
        "segment": 4,
        "partition": "dev",
        "subject": "Question on Yellow.ai MLOps function",
        "body": (
            "Hi Raghu,\n\n"
            "Three companies adjacent to Yellow.ai in the conversational AI "
            "space — Intercom, Zendesk, and Drift — posted senior MLOps "
            "engineer roles in the last 90 days. Your team has not, at least "
            "not publicly. Two readings: deliberate choice or function not "
            "yet scoped.\n\n"
            "We staff specialized AI squads on fixed-scope engagements.\n\n"
            "Worth 15 minutes? → http://localhost:3000/yakob/30min\n\n"
            "Research Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "instruction": (
            "CORRECT P33: Yellow.ai compared to Intercom, Zendesk, Drift — "
            "all conversational AI/customer service platforms. Correct sector "
            "matching. Should PASS."
        ),
        "required_signals": ["ai", "mlops", "conversational", "peer"],
        "company": "Yellow.ai",
        "confidence": "high",
        "failure_reason": None
    },

    # ── P34 — Defensive CTO doubles down ────────────────────────────
    {
        "task_id": "TB-HA010",
        "probe_ids": ["P34"],
        "difficulty": "hard",
        "is_passing": False,
        "label": "P34 — Defensive CTO reply triggers gap escalation",
        "segment": 4,
        "partition": "dev",
        "subject": "Re: Question on Retool AI capability gap",
        "body": (
            "Hi David,\n\n"
            "I understand you are already aware of your competitors — but "
            "the data is clear: your AI maturity is still behind where "
            "your sector peers are. Three companies in your space have "
            "already built MLOps functions that you are missing.\n\n"
            "I strongly recommend we connect before your next board meeting "
            "to close this gap before it becomes a competitive liability.\n\n"
            "→ http://localhost:3000/yakob/30min\n\n"
            "Research Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "instruction": (
            "ADVERSARIAL P34: CTO replied 'We are already aware of our "
            "competitors.' This response doubles down on the gap finding "
            "instead of acknowledging and pivoting. Condescending escalation "
            "on a defensive reply. Should FAIL."
        ),
        "required_signals": ["ai", "ml", "peer", "capability"],
        "company": "Retool",
        "confidence": "high",
        "failure_reason": "Doubles down on gap claim after defensive CTO reply"
    },

    # ── P34 — Correct pivot on defensive reply ───────────────────────
    {
        "task_id": "TB-HA011",
        "probe_ids": ["P34"],
        "difficulty": "hard",
        "is_passing": True,
        "label": "P34 — Correct: acknowledges defensive reply, pivots",
        "segment": 4,
        "partition": "dev",
        "subject": "Re: Question on Retool AI capability gap",
        "body": (
            "Hi David,\n\n"
            "Fair point — and if you have already evaluated this and made "
            "a deliberate decision, that is exactly what I would expect "
            "from a team at Retool's stage.\n\n"
            "I would genuinely be curious what led to the decision — "
            "that kind of reasoning is useful for us to understand. "
            "Happy to share what the three peer companies did differently "
            "if that context would be useful, no strings attached.\n\n"
            "→ http://localhost:3000/yakob/30min\n\n"
            "Research Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "instruction": (
            "CORRECT P34: CTO replied defensively. This response acknowledges "
            "their decision, pivots to curiosity, removes pressure. "
            "Non-condescending. Should PASS."
        ),
        "required_signals": ["deliberate", "decision", "peer", "curious"],
        "company": "Retool",
        "confidence": "high",
        "failure_reason": None
    },

    # ── Confidence abstention edge case ─────────────────────────────
    {
        "task_id": "TB-HA012",
        "probe_ids": ["P05", "P30"],
        "difficulty": "hard",
        "is_passing": False,
        "label": "P05 — Very low confidence triggers assertive language",
        "segment": 1,
        "partition": "held_out",
        "subject": "Context: Phantom Corp and engineering capacity",
        "body": (
            "Hi Jordan,\n\n"
            "Phantom Corp has been scaling aggressively and your engineering "
            "team is clearly growing fast. You recently closed a Series A "
            "and are hiring Python engineers at a high velocity.\n\n"
            "We solve this exact bottleneck — senior engineers available "
            "in 7-14 days with full timezone overlap.\n\n"
            "Worth 15 minutes? → http://localhost:3000/yakob/30min\n\n"
            "Research Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "instruction": (
            "ADVERSARIAL P05: Signal confidence is very_low — no public "
            "funding, no verified roles. Email asserts Series A, high velocity, "
            "aggressive scaling — all fabricated. Should FAIL — "
            "assertive language on very_low confidence signal."
        ),
        "required_signals": ["may", "appears", "public profile", "based on"],
        "company": "Phantom Corp",
        "confidence": "very_low",
        "failure_reason": "Assertive language on very_low confidence — no verified signals"
    },

    # ── Correct abstention on very low confidence ────────────────────
    {
        "task_id": "TB-HA013",
        "probe_ids": ["P05", "P30"],
        "difficulty": "hard",
        "is_passing": True,
        "label": "P05 — Correct: very low confidence triggers hedged language",
        "segment": 1,
        "partition": "held_out",
        "subject": "Context: Phantom Corp and engineering",
        "body": (
            "Hi Jordan,\n\n"
            "Phantom Corp may have open engineering roles based on your "
            "public profile — I cannot tell from the outside whether "
            "hiring is keeping pace or whether the queue is longer than "
            "the postings suggest.\n\n"
            "We place managed engineering teams, one-month minimum, "
            "3-5 hours daily overlap. If the real need is larger than "
            "what is visible publicly, a 15-minute conversation costs "
            "nothing.\n\n"
            "→ http://localhost:3000/yakob/30min\n\n"
            "Research Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "instruction": (
            "CORRECT P05: Very low confidence — email uses 'may have', "
            "'based on your public profile', 'cannot tell from the outside'. "
            "Correctly hedges all claims. Should PASS."
        ),
        "required_signals": ["may", "public profile", "cannot tell"],
        "company": "Phantom Corp",
        "confidence": "very_low",
        "failure_reason": None
    },

    # ── Pricing fabrication edge case ───────────────────────────────
    {
        "task_id": "TB-HA014",
        "probe_ids": ["P13", "P11"],
        "difficulty": "hard",
        "is_passing": False,
        "label": "P13 — Agent quotes total contract value not in pricing sheet",
        "segment": 2,
        "partition": "held_out",
        "subject": "Re: engagement scope for Brex",
        "body": (
            "Hi Michael,\n\n"
            "Thanks for the context on the 12-month timeline. Based on "
            "our conversation, the total cost for 8 senior Python engineers "
            "plus a delivery lead for 12 months would be $1,440,000 — "
            "approximately $120,000 per month.\n\n"
            "I have drafted a contract outline I can send over today. "
            "If you can confirm by Friday we can begin onboarding "
            "on the 1st.\n\n"
            "→ http://localhost:3000/yakob/30min\n\n"
            "Research Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "instruction": (
            "ADVERSARIAL P13: Agent quotes $1,440,000 total contract value — "
            "multi-phase TCV not permitted by pricing sheet. Only public "
            "monthly bands allowed. Contract draft offer is also out of scope. "
            "Should FAIL — pricing fabrication and contract overreach."
        ),
        "required_signals": ["restructuring", "cost", "delivery", "capacity"],
        "company": "Brex",
        "confidence": "high",
        "failure_reason": "Fabricated TCV $1.44M and offered contract draft"
    },

    # ── LinkedIn roast test ──────────────────────────────────────────
    {
        "task_id": "TB-HA015",
        "probe_ids": ["P06", "P16", "P17", "P19", "P20"],
        "difficulty": "hard",
        "is_passing": False,
        "label": "LinkedIn roast test — maximum violations in one email",
        "segment": 1,
        "partition": "held_out",
        "subject": "🚀 URGENT: World-Class Rockstar Engineers for Your Team — Quick Chat?",
        "body": (
            "Hey there! 👋\n\n"
            "Hope this email finds you well! I am just circling back because "
            "I noticed you are a VP of Engineering and I think Tenacious can "
            "supercharge your team with world-class A-player rockstar ninja "
            "engineers from our deep bench.\n\n"
            "Our top talent will skyrocket your delivery and synergize with "
            "your existing ecosystem. Game-changing stuff!\n\n"
            "Quick question — are you open to a quick chat this week to "
            "explore how we can leverage our paradigm-shifting platform "
            "for your team?\n\n"
            "Per my last email — I am also available on LinkedIn DM!\n\n"
            "Let's synergize! 🤝\n\nYabi"
        ),
        "instruction": (
            "ADVERSARIAL — LinkedIn Roast Test: This email contains the maximum "
            "possible violations: emoji in subject, banned phrases (hope this "
            "finds you well, circling back, world-class, rockstar, A-players, "
            "ninja, bench, top talent, skyrocket, synergize, game-changing, "
            "quick question, quick chat, per my last email, leverage, "
            "paradigm-shifting), subject over 60 chars, multiple emojis, "
            "no specific signal, no grounding. Should FAIL catastrophically."
        ),
        "required_signals": ["funding", "engineering", "roles", "signal"],
        "company": "Generic Corp",
        "confidence": "low",
        "failure_reason": "Every possible violation — the LinkedIn roast email"
    },
]


def task_from_spec(spec: dict) -> dict:
    """Build a full benchmark task from a hand-authored spec."""
    segment    = spec["segment"]
    confidence = spec["confidence"]
    company    = spec["company"]

    seg_names = {
        1: "Recently-funded startup", 2: "Post-layoff restructuring",
        3: "Leadership change",       4: "AI capability gap"
    }

    brief = {
        "prospect": company,
        "icp_classification": {
            "segment": segment,
            "segment_name": seg_names.get(segment, ""),
            "confidence": confidence,
            "reasons": [f"Hand-authored scenario — {spec['label']}"]
        },
        "firmographics": {
            "company": company, "website": "",
            "description": f"{company} — technology company",
            "num_employees": "51-500"
        },
        "ai_maturity": {
            "ai_maturity_score": 2 if segment == 4 else 1,
            "confidence": confidence
        },
        "layoff_signal":    {"layoff_detected": segment == 2},
        "leadership_signal": {"leadership_change_detected": segment == 3}
    }

    return {
        "task_id":     spec["task_id"],
        "source_mode": "hand_authored",
        "difficulty":  spec["difficulty"],
        "variant":     "hand_authored_adversarial",
        "is_passing":  spec["is_passing"],
        "probe_label": spec["label"],
        "input": {
            "hiring_signal_brief": brief,
            "bench_summary": {
                "total_engineers": 60, "available": 34,
                "stacks": {"python": 12, "node": 8,
                           "ml": 6, "go": 4, "data": 4}
            },
            "instruction":  spec["instruction"],
            "prior_thread": []
        },
        "candidate_output": {
            "subject": spec["subject"],
            "body":    spec["body"]
        },
        "ground_truth": {
            "required_signals":   spec["required_signals"],
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
            "created_at":     datetime.now().isoformat() + "Z",
            "partition":      spec["partition"],
            "probe_ids":      spec["probe_ids"],
            "source_trace_id": None,
            "judge_score":    None,
            "expected_score": 1.0 if spec["is_passing"] else 0.0,
            "failure_reason": spec.get("failure_reason"),
            "hand_authored":  True
        }
    }


def main():
    print("\n" + "="*60)
    print("Mode 4 — Hand-Authored Adversarial Tasks")
    print(f"Total: {len(HAND_AUTHORED_TASKS)} tasks")
    print("="*60)

    tasks   = []
    counts  = {"train": 0, "dev": 0, "held_out": 0}
    passing = 0
    failing = 0

    for spec in HAND_AUTHORED_TASKS:
        task = task_from_spec(spec)
        tasks.append(task)

        partition = spec["partition"]
        path = OUTPUT_DIR / partition / f"{spec['task_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(task, indent=2))
        counts[partition] += 1

        icon = "✅" if spec["is_passing"] else "❌"
        status = "PASS" if spec["is_passing"] else "FAIL"
        print(f"  {icon} {spec['task_id']} | {status} | "
              f"Seg {spec['segment']} | {spec['difficulty']} | "
              f"{partition} | {spec['label'][:40]}")

        if spec["is_passing"]:
            passing += 1
        else:
            failing += 1

    # Save log
    log = {
        "generated_at":   datetime.now().isoformat(),
        "mode":           "hand_authored",
        "total_tasks":    len(tasks),
        "passing_tasks":  passing,
        "failing_tasks":  failing,
        "partition_counts": counts,
        "probes_covered": ["P05", "P13", "P21", "P22",
                           "P25", "P27", "P28", "P33", "P34"],
        "cost": "$0.00"
    }
    (SCRIPTS_DIR / "hand_authored_log.json").write_text(
        json.dumps(log, indent=2))

    print(f"\n{'='*60}")
    print(f"✅ Hand-authored tasks complete")
    print(f"   Total:    {len(tasks)}")
    print(f"   Passing:  {passing}")
    print(f"   Failing:  {failing}")
    print(f"   Train:    {counts['train']}")
    print(f"   Dev:      {counts['dev']}")
    print(f"   Held-out: {counts['held_out']}")
    print(f"   Probes:   P05 P13 P21 P22 P25 P27 P28 P33 P34")
    print(f"   Cost:     $0.00")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

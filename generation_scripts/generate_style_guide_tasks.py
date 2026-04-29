"""
Style Guide Task Generator
Converts 12 good + 12 bad Tenacious style guide drafts into benchmark tasks.
Cost: $0.00
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
    "touching base", "following up", "as per",
    "i hope this email finds you",
]

GOOD_DRAFTS = [
    {
        "id": "SG-G01", "segment": 1, "difficulty": "easy",
        "probe_ids": ["P06", "P10"],
        "label": "Series A funding and role velocity high confidence",
        "company": "Maya Tech",
        "subject": "Request: 15 minutes on your Q3 Python hiring",
        "body": (
            "Hi Maya,\n\nYou closed your $14M Series A in February and your open "
            "Python engineering roles went from 2 to 7 in the last 60 days. "
            "The typical bottleneck for teams in that state is recruiting capacity, "
            "not budget.\n\nWe place dedicated Python and data engineers, managed "
            "by Tenacious, with a minimum three hours of synchronous overlap. We "
            "can plug a team in within 48 hours while you continue your full-time "
            "search.\n\nWould 15 minutes next week be useful? I will bring two case "
            "studies from Series A SaaS clients who hit the same wall.\n\n"
            "Best,\nYabi\nResearch Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "required_signals": ["series a", "february", "python", "7"],
    },
    {
        "id": "SG-G02", "segment": 2, "difficulty": "easy",
        "probe_ids": ["P08", "P10"],
        "label": "Post-layoff cost-pressure pitch mid-market restructuring",
        "company": "Daniel Corp",
        "subject": "Context: lower-cost engineering capacity post-restructure",
        "body": (
            "Hi Daniel,\n\nI saw the announcement that your team contracted by "
            "about 12% in March. Companies in your stage often need to maintain "
            "delivery output while reducing fully-loaded cost — that is the "
            "engagement pattern we run most often.\n\nTenacious places managed "
            "engineering teams under our project management. Senior engineers in "
            "Python, data, and ML start from $X,XXX/month, with a one-month "
            "minimum and two-week extension blocks. No long-term commitment.\n\n"
            "If you are scoping the next twelve months of delivery capacity, I "
            "can share two short case studies from mid-market clients who replaced "
            "a portion of their delivery cost this way.\n\n"
            "Best,\nYabi\nResearch Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "required_signals": ["12%", "march", "cost", "delivery"],
    },
    {
        "id": "SG-G03", "segment": 3, "difficulty": "easy",
        "probe_ids": ["P02", "P31"],
        "label": "New CTO 90-day vendor reassessment window",
        "company": "Helix Inc",
        "subject": "Context: a brief on offshore engineering models",
        "body": (
            "Hi Priya,\n\nWelcome to your new role at Helix — I saw the "
            "announcement on the 14th. New engineering leaders typically reassess "
            "vendor and offshore mix in their first 90 days.\n\nI do not want to "
            "add to your inbox in week three of a new job. I will leave you with "
            "one thing: a one-page brief on the four offshore engagement models we "
            "see most often, with the trade-offs honestly laid out including where "
            "each model fails.\n\nIf a 15-minute conversation in November would be "
            "useful, the calendar is at gettenacious.com/yabi. If not, no "
            "follow-up.\n\nBest,\nYabi\nResearch Partner\n"
            "Tenacious Intelligence Corporation\ngettenacious.com"
        ),
        "required_signals": ["14th", "90 days", "vendor", "helix"],
    },
    {
        "id": "SG-G04", "segment": 4, "difficulty": "medium",
        "probe_ids": ["P32", "P33"],
        "label": "Capability gap AI maturity 2 high confidence",
        "company": "Felix Platform",
        "subject": "Question: your MLOps function in 2026",
        "body": (
            "Hi Felix,\n\nThree companies adjacent to yours in the loyalty-platform "
            "space posted senior MLOps engineer roles in the last 90 days. Your "
            "team has not, at least not publicly. Two readings: a deliberate choice, "
            "or a function that has not yet been scoped.\n\nWe staff specialized "
            "squads on fixed-scope project engagements, typically 3 to 4 months. "
            "Starter scopes from $XX,XXX. We do not pitch this where there is no "
            "real need.\n\nIf you have already scoped this and decided against it, "
            "I would genuinely be curious why. If not, 15 minutes is enough to "
            "walk through what those peer companies are doing.\n\n"
            "Best,\nYabi\nResearch Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "required_signals": ["mlops", "loyalty-platform", "90 days", "peer"],
    },
    {
        "id": "SG-G05", "segment": 1, "difficulty": "hard",
        "probe_ids": ["P05", "P30"],
        "label": "Weak signal asks rather than asserts",
        "company": "Tom Data",
        "subject": "Question: are your data engineering hires keeping up?",
        "body": (
            "Hi Tom,\n\nTwo open data engineer roles on your careers page — I "
            "cannot tell from the outside whether that means hiring is keeping "
            "pace or whether the queue is longer than the postings suggest.\n\n"
            "We place managed data and Python engineering teams, three-hour overlap "
            "with US time zones, one-month minimum. If the queue is longer than "
            "the posts, that is the pattern we solve most often.\n\nIf two roles "
            "is the actual demand and you are well-staffed to meet it, ignore this. "
            "If the real number is higher, a 15-minute conversation costs you "
            "nothing.\n\nBest,\nYabi\nResearch Partner\n"
            "Tenacious Intelligence Corporation\ngettenacious.com"
        ),
        "required_signals": ["two", "data engineer", "cannot tell", "queue"],
    },
    {
        "id": "SG-G06", "segment": 1, "difficulty": "easy",
        "probe_ids": ["P10"],
        "label": "Resource value-add no-pitch first touch",
        "company": "Ana Startup",
        "subject": "Resource: Series A engineering scale-up checklist",
        "body": (
            "Hi Ana,\n\nYou closed your seed extension in October and your first "
            "three engineering hires are public on LinkedIn. The window between "
            "now and your Series A is the one where most teams delivery process "
            "either compounds or stalls.\n\nI put together a one-page checklist "
            "of the seven decisions that determine which side a team lands on. "
            "Two of the items are arguments against hiring an outsourced team "
            "in your stage.\n\nWant me to send the PDF? No follow-up if you are "
            "not interested.\n\nBest,\nYabi\nResearch Partner\n"
            "Tenacious Intelligence Corporation\ngettenacious.com"
        ),
        "required_signals": ["seed extension", "october", "linkedin", "checklist"],
    },
    {
        "id": "SG-G07", "segment": 1, "difficulty": "medium",
        "probe_ids": ["P11", "P13"],
        "label": "Warm reply with routing to human delivery lead",
        "company": "Camila Systems",
        "subject": "Re: scope of the three-engineer engagement",
        "body": (
            "Hi Camila,\n\nThanks for the reply and for the additional context "
            "on the December timeline.\n\nThree Python and one data engineer for "
            "a 6-month engagement is in our typical range. Our public-tier pricing "
            "for that mix starts from approximately $X,XXX/month per engineer at "
            "senior level, with a one-month minimum and two-week extension blocks.\n\n"
            "A specific quote depends on the exact stack, timezone overlap, and "
            "whether you want a Tenacious delivery lead embedded. The cleanest path "
            "is a 30-minute scoping call with our delivery lead. Here is his "
            "calendar: gettenacious.com/arun\n\nBest,\nYabi"
        ),
        "required_signals": ["december", "python", "data engineer", "gettenacious.com"],
    },
    {
        "id": "SG-G08", "segment": 2, "difficulty": "medium",
        "probe_ids": ["P17"],
        "label": "Re-engagement with new content no guilt",
        "company": "Marcus Health",
        "subject": "New: layoffs.fyi data on your sub-sector this quarter",
        "body": (
            "Hi Marcus,\n\nWhen we last spoke in August, you mentioned that the "
            "board had not yet pushed for cost rebalancing. Two new data points "
            "that may matter:\n\nFirst, the layoffs.fyi data shows your sub-sector "
            "had eleven announced contractions in the last 90 days, up from four "
            "in the prior quarter.\n\nSecond, three of those eleven companies are "
            "now using offshore-managed engineering teams within 60 days of "
            "restructure.\n\nIf the conversation has reopened on your side, our "
            "managed engineering pricing has not changed. If not, no follow-up "
            "needed.\n\nBest,\nYabi"
        ),
        "required_signals": ["august", "layoffs.fyi", "eleven", "90 days"],
    },
    {
        "id": "SG-G09", "segment": 1, "difficulty": "hard",
        "probe_ids": ["P11", "P12", "P14"],
        "label": "Bench-gated honest decline of overreach",
        "company": "Will Engineering",
        "subject": "Re: scaling to 15 engineers in 30 days",
        "body": (
            "Hi Will,\n\nThanks for the follow-up and for the trust to ask about "
            "the 15-engineer ramp. Honest answer: 15 engineers across a Go and "
            "infra-heavy stack within 30 days is at the edge of what our current "
            "capacity can deliver responsibly.\n\nWhat we can confirm now: 6 to 8 "
            "engineers in that stack, starting within 21 days, with a Tenacious "
            "delivery lead embedded. Going to 15 reliably requires a 60-day ramp "
            "window.\n\nIf the 30-day target is firm, I would rather refer you to "
            "a peer firm that fits the timeline than over-commit. Happy to "
            "introduce.\n\nBest,\nYabi"
        ),
        "required_signals": ["15 engineers", "go", "6 to 8", "21 days"],
    },
    {
        "id": "SG-G10", "segment": 1, "difficulty": "medium",
        "probe_ids": ["P03", "P09"],
        "label": "AI maturity 0-1 gentle Segment 1 reframe",
        "company": "Sophia AI",
        "subject": "Question: standing up your first AI function",
        "body": (
            "Hi Sophia,\n\nYou closed your $9M Series A in March, your team is "
            "ten engineers, and your public roles are all backend and product. "
            "No AI or ML postings yet — which is a normal place to be at your "
            "stage, not a gap.\n\nIf your roadmap has an AI feature in the next "
            "twelve months, the first hire is usually the wrong unit. A small "
            "dedicated squad for a 3-month scoped project is faster, cheaper, "
            "and lets you test whether AI is core enough to justify a full-time "
            "function.\n\nIf that is on your roadmap, 15 minutes to walk through "
            "what the first 90 days look like. If not, ignore this.\n\n"
            "Best,\nYabi\nResearch Partner\nTenacious Intelligence Corporation\n"
            "gettenacious.com"
        ),
        "required_signals": ["series a", "march", "ten engineers", "90 days"],
    },
    {
        "id": "SG-G11", "segment": 4, "difficulty": "medium",
        "probe_ids": ["P10"],
        "label": "Mutual connection real not name-drop",
        "company": "Mei Data",
        "subject": "Context: Arjun's recommendation",
        "body": (
            "Hi Mei,\n\nArjun Krishnan suggested I reach out — he and I worked "
            "on the data platform redesign at his Series B in February, and he "
            "said your team is at a similar stage with the same Snowflake plus "
            "dbt plus Airflow combination he was working through.\n\nIf the "
            "equivalent rebuild is on your roadmap, I would be glad to share "
            "what we learned in his project, including the two architectural "
            "decisions that did not work. Happy to send a one-page write-up "
            "or do 15 minutes — your call.\n\nIf this is not on your roadmap, "
            "no follow-up.\n\nBest,\nYabi\nResearch Partner\n"
            "Tenacious Intelligence Corporation\ngettenacious.com"
        ),
        "required_signals": ["arjun", "snowflake", "dbt", "airflow"],
    },
    {
        "id": "SG-G12", "segment": 4, "difficulty": "easy",
        "probe_ids": ["P10"],
        "label": "Two-line micro-touch post-engagement nurture",
        "company": "Kevin Loyalty",
        "subject": "Quick thought after our call",
        "body": (
            "Hi Kevin,\n\nAfter we spoke yesterday I went back and looked — "
            "three of the loyalty platforms you mentioned as competitors are "
            "now publicly using the same dbt-plus-Snowflake stack you are "
            "evaluating. Worth knowing as you scope the build.\n\nNo reply "
            "needed. I will follow up after your internal review next Thursday "
            "as agreed.\n\nBest,\nYabi"
        ),
        "required_signals": ["yesterday", "loyalty", "dbt", "snowflake", "thursday"],
    },
]

BAD_DRAFTS = [
    {
        "id": "SG-B01", "segment": 1, "difficulty": "hard",
        "probe_ids": ["P06", "P16", "P17"],
        "label": "Wall of self-promotion",
        "company": "Maya Tech",
        "subject": "Tenacious — World-Class Engineering Talent",
        "body": (
            "Dear Maya,\n\nTenacious Intelligence Corporation is a world-class "
            "engineering outsourcing firm with over 200 senior engineers. Our "
            "top talent is graduated from elite programs and our delivery model "
            "is the gold standard in the industry.\n\nWe offer junior, mid, "
            "senior, and architect-level engineers, fractional CTO services, "
            "project consulting on AI systems, data platforms, and specialized "
            "infrastructure.\n\nI would love to schedule a 45-minute discovery "
            "call to learn about your business, your goals, your pain points, "
            "your budget, and your roadmap.\n\nBest regards,\nYabi"
        ),
        "required_signals": ["series a", "funding", "roles"],
    },
    {
        "id": "SG-B02", "segment": 1, "difficulty": "hard",
        "probe_ids": ["P05", "P06", "P30"],
        "label": "Asserts on weak signal",
        "company": "Tom Data",
        "subject": "Quick chat: your aggressive hiring",
        "body": (
            "Hi Tom,\n\nI see you are scaling aggressively — your engineering "
            "team is clearly growing fast and you must be feeling the pain of "
            "recruiting velocity right now. Companies in your stage always hit "
            "a wall around month four after a Series A.\n\nWe solve this exact "
            "problem. Tenacious places top talent in 48 hours and we will "
            "skyrocket your delivery throughput.\n\nQuick question — do you "
            "have 15 minutes this week?\n\nBest,\nYabi"
        ),
        "required_signals": ["two roles", "data engineer", "cannot tell"],
    },
    {
        "id": "SG-B03", "segment": 1, "difficulty": "hard",
        "probe_ids": ["P11", "P12", "P03"],
        "label": "Bench overcommitment",
        "company": "Will Engineering",
        "subject": "Re: 12 senior Go engineers in two weeks",
        "body": (
            "Hi Will,\n\nAbsolutely, we can deliver 12 senior Go engineers in "
            "two weeks. Our bench is deep across all stacks and we move fast.\n\n"
            "I will have our team kick off scoping immediately. Expect contracts "
            "by Wednesday and engineers in your Slack by next Friday.\n\nBest,\nYabi"
        ),
        "required_signals": ["6 to 8", "21 days", "refer"],
    },
    {
        "id": "SG-B04", "segment": 4, "difficulty": "hard",
        "probe_ids": ["P18", "P32", "P04"],
        "label": "Condescending competitor gap framing",
        "company": "Felix Platform",
        "subject": "Your AI maturity is behind the curve",
        "body": (
            "Hi Felix,\n\nI will be direct: your AI maturity score is a 1, "
            "while your top competitors are a 3. You are falling behind in a "
            "market where AI is no longer optional, and your leadership has not "
            "yet made the strategic moves the sector demands.\n\nTenacious can "
            "stand up your missing MLOps function and close the gap before your "
            "next board meeting. Our engineers are world-class.\n\nLet's get on "
            "a call this week to discuss how we can help you catch up.\n\nBest,\nYabi"
        ),
        "required_signals": ["mlops", "peer", "90 days"],
    },
    {
        "id": "SG-B05", "segment": 2, "difficulty": "hard",
        "probe_ids": ["P17", "P05"],
        "label": "Aggressive third follow-up",
        "company": "Ana Startup",
        "subject": "Per my last three emails",
        "body": (
            "Hi Ana,\n\nI have sent you three emails over the last two weeks "
            "and have not heard back. I have to assume you are not interested "
            "in growing your engineering capacity, which is fine — but I would "
            "appreciate a one-line reply to confirm so I can take you off the "
            "list.\n\nIf I do not hear back by Friday, I will assume the answer "
            "is no.\n\nBest,\nYabi"
        ),
        "required_signals": ["new data", "sector", "peer"],
    },
    {
        "id": "SG-B06", "segment": 1, "difficulty": "hard",
        "probe_ids": ["P06", "P16", "P17", "P19"],
        "label": "Generic templated outreach with unfilled tokens",
        "company": "Unknown Company",
        "subject": "Hey scaling your engineering team?",
        "body": (
            "Hey there,\n\nI hope this email finds you well. I am reaching out "
            "because I think Tenacious can help with all of your engineering and "
            "AI needs in 2026.\n\nWe work with companies like yours to deliver "
            "world-class talent at affordable prices. Our team has experience "
            "across many industries and stacks.\n\nWould you be open to a quick "
            "chat next week to explore how we can synergize and add value to your "
            "ecosystem?\n\nBest,\nYabi"
        ),
        "required_signals": ["funding", "engineering", "signal"],
    },
    {
        "id": "SG-B07", "segment": 1, "difficulty": "hard",
        "probe_ids": ["P07", "P13"],
        "label": "Fake urgency and discount",
        "company": "Kevin Loyalty",
        "subject": "URGENT: Last open slot for Q1 30 percent off",
        "body": (
            "Hi Kevin,\n\nTenacious has one remaining slot in our Q1 cohort. "
            "Because of strong demand, this slot will not be available after "
            "Friday.\n\nIf you sign a contract by end of day Friday, I am "
            "authorized to offer 30% off the first three months. After that, "
            "the slot goes to the next company on the waitlist.\n\nDo not miss "
            "out — book a call here: gettenacious.com/yabi\n\nBest,\nYabi"
        ),
        "required_signals": ["yesterday", "loyalty", "dbt"],
    },
    {
        "id": "SG-B08", "segment": 4, "difficulty": "hard",
        "probe_ids": ["P03", "P08", "P09"],
        "label": "Wrong segment pitch AI maturity 0 gets Segment 4",
        "company": "Sophia AI",
        "subject": "Question: your agentic systems roadmap",
        "body": (
            "Hi Sophia,\n\nI am curious how you are thinking about your "
            "agentic-systems roadmap for 2026. Most peer companies in your stage "
            "are now scoping LLM-orchestrated workflows and dedicated MLOps "
            "functions.\n\nWe staff specialized capability-gap squads — agentic "
            "systems, ML platform, data contracts — typically 3 to 4 months. "
            "Want to set up a 30-minute scoping conversation?\n\nBest,\nYabi"
        ),
        "required_signals": ["series a", "march", "ten engineers"],
    },
    {
        "id": "SG-B09", "segment": 2, "difficulty": "hard",
        "probe_ids": ["P10"],
        "label": "Cold PDF attachment",
        "company": "Marcus Health",
        "subject": "Tenacious capabilities deck review pages 8 and 12",
        "body": (
            "Hi Marcus,\n\nPlease find attached our 38-page capabilities deck.\n\n"
            "Pages 8 and 12 are the most relevant to your sub-sector. Let me "
            "know your thoughts and we can schedule a call to discuss our "
            "partnership opportunity.\n\nBest,\nYabi\n"
            "[ATTACHMENT: tenacious_capabilities_v7.pdf 12.4MB]"
        ),
        "required_signals": ["august", "layoffs.fyi", "healthcare"],
    },
    {
        "id": "SG-B10", "segment": 2, "difficulty": "hard",
        "probe_ids": ["P10", "P18"],
        "label": "Multiple stacked asks",
        "company": "Daniel Corp",
        "subject": "A few questions and ideas",
        "body": (
            "Hi Daniel,\n\nI had a few thoughts I wanted to share. First, I "
            "would love to understand your current engineering structure. Second, "
            "I have an introduction to a peer of yours. Third, we have a new "
            "training program. Fourth, your AI maturity is around a 2 — happy "
            "to walk through how to move it to a 3.\n\nCould we set up a "
            "60-minute call next week to discuss all four of these?\n\nBest,\nYabi"
        ),
        "required_signals": ["contracted", "12%", "cost"],
    },
    {
        "id": "SG-B11", "segment": 1, "difficulty": "hard",
        "probe_ids": ["P13", "P11"],
        "label": "Pricing fabrication for multi-phase engagement",
        "company": "Camila Systems",
        "subject": "Quote: 1.2M for the 12-month engagement",
        "body": (
            "Hi Camila,\n\nThanks for the call yesterday. As discussed, our "
            "quote for the 12-month engagement covering 6 engineers, a delivery "
            "lead, and a fractional architect is $1,200,000 total, payable in "
            "monthly installments of $100,000.\n\nI have attached the contract. "
            "Please sign and return by Friday so we can begin onboarding on "
            "the 1st.\n\nBest,\nYabi"
        ),
        "required_signals": ["december", "python", "gettenacious.com"],
    },
    {
        "id": "SG-B12", "segment": 1, "difficulty": "hard",
        "probe_ids": ["P07", "P10", "P12"],
        "label": "Signal fabrication wrong funding round",
        "company": "Helix Inc",
        "subject": "Re: your 40M Series C",
        "body": (
            "Hi Priya,\n\nCongratulations on closing your $40M Series C last "
            "month — exciting moment for the team. With that level of capital, "
            "scaling engineering aggressively is the obvious next move.\n\nWe "
            "can plug a 15-engineer team into your stack within 30 days at our "
            "standard rates.\n\nWant to set up a 15-minute call to discuss?\n\n"
            "Best,\nYabi"
        ),
        "required_signals": ["announcement", "14th", "90 days", "vendor"],
    },
]

SEGMENT_NAMES = {
    1: "Recently-funded startup", 2: "Post-layoff restructuring",
    3: "Leadership change", 4: "AI capability gap"
}

def draft_to_task(draft, task_id, is_passing, partition):
    segment = draft["segment"]
    return {
        "task_id": task_id,
        "source_mode": "hand_authored",
        "difficulty": draft["difficulty"],
        "variant": f"style_guide_{'good' if is_passing else 'bad'}",
        "is_passing": is_passing,
        "style_guide_id": draft["id"],
        "input": {
            "hiring_signal_brief": {
                "prospect": draft["company"],
                "icp_classification": {
                    "segment": segment,
                    "segment_name": SEGMENT_NAMES.get(segment, ""),
                    "confidence": "high",
                    "reasons": [f"Style guide labeled: {draft['label']}"]
                },
                "firmographics": {
                    "company": draft["company"], "website": "",
                    "description": "Technology company", "num_employees": "51-200"
                },
                "ai_maturity": {
                    "ai_maturity_score": 2 if segment == 4 else 1,
                    "confidence": "high"
                },
                "layoff_signal": {"layoff_detected": segment == 2},
                "leadership_signal": {"leadership_change_detected": segment == 3}
            },
            "bench_summary": {
                "total_engineers": 60, "available": 34,
                "stacks": {"python": 12, "node": 8, "ml": 6, "go": 4, "data": 4}
            },
            "instruction": (
                f"STYLE GUIDE EXAMPLE ({draft['id']}): "
                f"{'GOOD — should PASS.' if is_passing else 'BAD — should FAIL.'} "
                f"{draft['label']}"
            ),
            "prior_thread": []
        },
        "candidate_output": {
            "subject": draft["subject"],
            "body": draft["body"]
        },
        "ground_truth": {
            "required_signals": draft["required_signals"],
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
            "probe_ids": draft["probe_ids"],
            "source_trace_id": None,
            "judge_score": None,
            "expected_score": 1.0 if is_passing else 0.0,
            "style_guide_label": draft["label"]
        }
    }

def main():
    print("\n" + "="*60)
    print("Style Guide Task Generator — 12 Good + 12 Bad")
    print("="*60)

    tasks = []
    counter = [0]

    def next_id():
        counter[0] += 1
        return f"TB-SG{counter[0]:02d}"

    good_parts = ["train"]*6 + ["dev"]*4 + ["held_out"]*2
    bad_parts  = ["train"]*6 + ["dev"]*4 + ["held_out"]*2

    print(f"\n── Good Drafts (12) ──")
    for i, draft in enumerate(GOOD_DRAFTS):
        task = draft_to_task(draft, next_id(), True, good_parts[i])
        tasks.append(task)
        print(f"  ✅ {draft['id']} | Seg {draft['segment']} | "
              f"{draft['difficulty']} | {good_parts[i]}")

    print(f"\n── Bad Drafts (12) ──")
    for i, draft in enumerate(BAD_DRAFTS):
        task = draft_to_task(draft, next_id(), False, bad_parts[i])
        tasks.append(task)
        print(f"  ❌ {draft['id']} | Seg {draft['segment']} | "
              f"{draft['difficulty']} | {bad_parts[i]}")

    counts = {"train": 0, "dev": 0, "held_out": 0}
    for task in tasks:
        partition = task["metadata"]["partition"]
        path = OUTPUT_DIR / partition / f"{task['task_id']}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(task, indent=2))
        counts[partition] += 1

    log = {
        "generated_at": datetime.now().isoformat(),
        "mode": "style_guide",
        "good_drafts": 12, "bad_drafts": 12,
        "total_tasks": len(tasks),
        "partition_counts": counts,
        "cost": "$0.00"
    }
    (SCRIPTS_DIR / "style_guide_generation_log.json").write_text(
        json.dumps(log, indent=2))

    print(f"\n{'='*60}")
    print(f"✅ Style guide tasks complete")
    print(f"   Total: {len(tasks)}")
    print(f"   Train: {counts['train']} | Dev: {counts['dev']} | "
          f"Held-out: {counts['held_out']}")
    print(f"   Cost: $0.00")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()

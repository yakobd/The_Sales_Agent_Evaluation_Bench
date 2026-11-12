"""
Run the real Week 10 Conversion Engine over fresh Crunchbase companies and
export (brief, Week-10 email) pairs for the v0.2 held-out partition.

Runs with the Week 10 virtualenv (needs pandas + the W10 agent package):

    ../The-Conversion-Engine/venv/Scripts/python generation_scripts/export_week10_briefs.py

What it does, deterministically (seed 42):
  1. Loads the Crunchbase ODM sample (1,000 companies, snapshot July 2024) and
     drops every company already used anywhere in Tenacious-Bench v0.1.
  2. Calls the W10 enrichment functions directly (crunchbase, layoffs.fyi,
     leadership, AI maturity, job-post proxy, ICP classifier) — the same code
     path as agent/enrichment/pipeline.py, without writing into the W10 repo.
  3. Records the date of every signal relative to the Crunchbase snapshot, so
     the time-shift check can verify the window (funding <=180 days = recent,
     layoff <=120 days, leadership <=90 days — the challenge's definitions).
  4. Calls the W10 composer agent/email_agent.generate_outreach_email(brief):
     this is Week 10's actual output for the prospect (the true baseline).
Output: generation_scripts/week10_export/week10_briefs.jsonl + manifest.json
"""
import contextlib
import io
import json
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
from config import BENCH_DIR, REPO_ROOT, SEED, WEEK10_DIR  # noqa: E402

sys.path.insert(0, str(WEEK10_DIR))
import pandas as pd  # noqa: E402
from agent.enrichment import pipeline as P  # noqa: E402
from agent.enrichment.ai_maturity import score_ai_maturity  # noqa: E402
from agent.enrichment.crunchbase import enrich_company, load_crunchbase_data  # noqa: E402
from agent.enrichment.job_posts import get_job_post_signal  # noqa: E402
from agent.enrichment.layoffs import check_layoffs  # noqa: E402
from agent.enrichment.leadership import check_leadership_change  # noqa: E402
from agent.email_agent import generate_outreach_email  # noqa: E402

OUT_DIR = REPO_ROOT / "generation_scripts" / "week10_export"
N_SIGNAL, N_NO_SIGNAL = 48, 6
WINDOWS = {"funding": 180, "layoff": 120, "leadership": 90}


def git_rev(path: Path) -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=path, capture_output=True, text=True).stdout.strip()


def used_prospects() -> set:
    names = set()
    for f in BENCH_DIR.rglob("TB-*.json"):
        names.add(json.loads(f.read_text(encoding="utf-8"))["input"]["hiring_signal_brief"]["prospect"].strip().lower())
    return names


def parse_list(raw):
    try:
        v = json.loads(raw) if isinstance(raw, str) else raw
        return v if isinstance(v, list) else []
    except Exception:
        return []


def days_before(snapshot: pd.Timestamp, date_str) -> int | None:
    try:
        return int((snapshot - pd.Timestamp(date_str)).days)
    except Exception:
        return None


def compact_brief(name, row, cb, lay, lead, ai, jobs, icp, snapshot):
    loc = [x.get("name") for x in parse_list(row.get("location")) if isinstance(x, dict)]
    rounds = sorted(parse_list(cb.get("funding_rounds_list")), key=lambda r: r.get("announced_on", ""), reverse=True)
    funding = None
    if rounds:
        r0 = rounds[0]
        d = days_before(snapshot, r0.get("announced_on"))
        funding = {"latest_round": r0.get("title"), "announced_on": r0.get("announced_on"),
                   "days_before_snapshot": d, "recent": d is not None and 0 <= d <= WINDOWS["funding"],
                   "total_rounds": len(rounds)}
    layoff = {"layoff_detected": bool(lay.get("layoff_detected"))}
    if lay.get("layoff_detected"):
        latest = lay.get("latest_layoff") or {}
        date = latest.get("key_event_date") or latest.get("date") or lay.get("date")
        d = days_before(snapshot, date)
        layoff.update({"date": date, "days_before_snapshot": d,
                       "within_window": d is not None and 0 <= d <= WINDOWS["layoff"],
                       "detail": latest.get("label") or lay.get("note"),
                       "total_laid_off": lay.get("total_laid_off"), "percentage_laid_off": lay.get("percentage_laid_off"),
                       "source": lay.get("source")})
    leadership = {"leadership_change_detected": bool(lead.get("leadership_change_detected")),
                  "technical_leadership_change": bool(lead.get("technical_leadership_change"))}
    if lead.get("hires"):
        h = lead["hires"][0]
        d = days_before(snapshot, h.get("key_event_date"))
        leadership.update({"event": h.get("label"), "date": h.get("key_event_date"), "days_before_snapshot": d,
                           "within_window": d is not None and 0 <= d <= WINDOWS["leadership"]})
    return {
        "prospect": name,
        "snapshot_date": str(snapshot.date()),
        "icp_classification": {k: icp[k] for k in ("segment", "segment_name", "confidence", "reasons")},
        "firmographics": {
            "company": name, "website": cb.get("website", ""),
            "description": (cb.get("description") or "")[:400],
            "industries": [x.get("value") for x in parse_list(cb.get("industries")) if isinstance(x, dict)][:5],
            "num_employees": cb.get("num_employees", ""), "country_code": cb.get("country_code", ""),
            "location": ", ".join(x for x in loc[:3] if x), "founded_date": cb.get("founded_date", ""),
        },
        "funding": funding,
        "layoff_signal": layoff,
        "leadership_signal": leadership,
        "ai_maturity": {"ai_maturity_score": int(ai.get("ai_maturity_score") or 0), "confidence": ai.get("confidence"),
                        "signals": [s.get("signal") for s in ai.get("signals", []) if isinstance(s, dict) and s.get("weighted_score")]},
        "job_post_signal": {"hiring_velocity": jobs.get("hiring_velocity"),
                            "estimated_open_roles": jobs.get("estimated_open_roles"),
                            "assert_aggressive_hiring": bool(jobs.get("assert_aggressive_hiring")),
                            "method": "estimated from Crunchbase proxy signals (job boards not scraped)"},
    }


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["held_out", "train"], default="held_out",
                    help="held_out: original v0.2 held-out export (default, unchanged). "
                         "train: remaining companies for SFT data, excluding every held-out company.")
    ap.add_argument("--n-no-signal", type=int, default=120, help="train split: no-signal companies to add")
    args = ap.parse_args()
    if args.split == "train":
        return export_train(args.n_no_signal)
    df = load_crunchbase_data()
    used = used_prospects()
    rows = []
    for _, row in df.iterrows():
        name = str(row["name"]).strip()
        if not name or name.lower() in used or name.lower() == "nan":
            continue
        with contextlib.redirect_stdout(io.StringIO()):
            cb = enrich_company(name)
            if not cb.get("found") or cb.get("name", "").strip().lower() != name.lower():
                continue  # substring match hit a different company (known W10 issue) - skip
            lay, lead, ai, jobs = check_layoffs(name), check_leadership_change(name), score_ai_maturity(name), get_job_post_signal(name)
            icp = P.classify_icp_segment(cb, lay, lead, ai)
        snapshot = pd.Timestamp(row["timestamp"]).tz_localize(None)
        brief = compact_brief(name, row, cb, lay, lead, ai, jobs, icp, snapshot)
        rows.append({"brief": brief, "has_signal": max(icp["scores"].values()) > 0, "raw_w10": {
            "firmographics": cb, "layoff_signal": lay, "leadership_signal": lead, "ai_maturity": ai,
            "job_post_signal": jobs, "icp_classification": icp}})

    rng = random.Random(SEED)
    signal = [r for r in rows if r["has_signal"]]
    strong = [r for r in signal if r["brief"]["layoff_signal"]["layoff_detected"]
              or r["brief"]["leadership_signal"]["leadership_change_detected"]
              or r["brief"]["ai_maturity"]["ai_maturity_score"] >= 2]
    funded = [r for r in signal if r not in strong]
    non_us = [r for r in funded if str(r["brief"]["firmographics"]["country_code"]).upper() not in ("US", "")]
    us = [r for r in funded if r not in non_us]
    rng.shuffle(non_us), rng.shuffle(us)
    picked = strong + non_us[: max(0, (N_SIGNAL - len(strong)) // 2)]
    picked += us[: N_SIGNAL - len(picked)]
    quiet = [r for r in rows if not r["has_signal"]]
    picked += rng.sample(quiet, N_NO_SIGNAL)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "week10_briefs.jsonl").open("w", encoding="utf-8") as fh:
        for r in picked:
            w10_input = {**r["raw_w10"], "prospect": r["brief"]["prospect"]}
            with contextlib.redirect_stdout(io.StringIO()):
                email = generate_outreach_email(w10_input)
            fh.write(json.dumps({"brief": r["brief"], "week10_email": {"subject": email["subject"], "body": email["body"]},
                                 "week10_segment": email["segment"]}, ensure_ascii=False, default=str) + "\n")
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "week10_commit": git_rev(WEEK10_DIR), "crunchbase_sample_commit": git_rev(WEEK10_DIR / "Crunchbase-dataset-samples"),
        "crunchbase_snapshot": f"{df['timestamp'].min()} .. {df['timestamp'].max()}",
        "layoffs_source": "layoffs.fyi GitHub mirror, data/layoffs_cache.csv in the W10 repo",
        "eligible_companies": len(rows), "with_signal": len(signal), "strong_signal": len(strong),
        "exported": len(picked), "seed": SEED, "windows_days": WINDOWS,
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


def enrich_rows(names, df):
    rows = []
    for name in names:
        row = df[df["name"].astype(str).str.strip() == name].iloc[0]
        with contextlib.redirect_stdout(io.StringIO()):
            cb = enrich_company(name)
            if not cb.get("found") or cb.get("name", "").strip().lower() != name.lower():
                continue
            lay, lead, ai, jobs = check_layoffs(name), check_leadership_change(name), score_ai_maturity(name), get_job_post_signal(name)
            icp = P.classify_icp_segment(cb, lay, lead, ai)
        snapshot = pd.Timestamp(row["timestamp"]).tz_localize(None)
        rows.append({"brief": compact_brief(name, row, cb, lay, lead, ai, jobs, icp, snapshot),
                     "has_signal": max(icp["scores"].values()) > 0,
                     "raw_w10": {"firmographics": cb, "layoff_signal": lay, "leadership_signal": lead,
                                 "ai_maturity": ai, "job_post_signal": jobs, "icp_classification": icp}})
    return rows


def export_train(n_no_signal):
    """All remaining signal companies + a sample of no-signal ones, never a held-out company."""
    held = {json.loads(l)["brief"]["prospect"].lower()
            for l in (OUT_DIR / "week10_briefs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    used = used_prospects() | held
    df = load_crunchbase_data()
    names = [n for n in (str(x).strip() for x in df["name"]) if n and n.lower() != "nan" and n.lower() not in used]
    names = list(dict.fromkeys(names))
    rows = enrich_rows(names, df)
    rng = random.Random(SEED + 1)
    signal = [r for r in rows if r["has_signal"]]
    quiet = [r for r in rows if not r["has_signal"]]
    picked = signal + rng.sample(quiet, min(n_no_signal, len(quiet)))
    out = REPO_ROOT / "training_data" / "week10_train_briefs.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in picked:
            w10_input = {**r["raw_w10"], "prospect": r["brief"]["prospect"]}
            with contextlib.redirect_stdout(io.StringIO()):
                email = generate_outreach_email(w10_input)
            fh.write(json.dumps({"brief": r["brief"], "week10_email": {"subject": email["subject"], "body": email["body"]}},
                                ensure_ascii=False, default=str) + "\n")
    overlap = held & {r["brief"]["prospect"].lower() for r in picked}
    print(json.dumps({"split": "train", "exported": len(picked), "with_signal": len(signal),
                      "no_signal": len(picked) - len(signal), "held_out_overlap": len(overlap)}, indent=2))
    assert not overlap


if __name__ == "__main__":
    main()

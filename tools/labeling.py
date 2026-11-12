"""
Inter-rater agreement protocol (challenge: hand-label 30 tasks, re-label 24h
later blind; <80% agreement on any dimension triggers a rubric revision).

The 30 tasks are sampled from tasks whose labels were assigned by the
evaluator (not the 39 hand-authored tasks v0.2 was developed on), so the
human labels also give an independent check of evaluator v0.2.

    python tools/labeling.py make --round 1     # labeling/round1.html  (open in a browser)
    python tools/labeling.py make --round 2     # same 30 tasks, new order, >= 24h later
    python tools/labeling.py score              # agreement report from the two CSVs

The HTML page shows only what a rater needs (brief, thread, email, rubric);
it never shows labels, evaluator verdicts or authoring notes. Clicking
"Download CSV" saves labeling/roundN_labels.csv (move it into labeling/).
"""
import argparse
import csv
import html
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import scoring_evaluator as E  # noqa: E402

OUT = config.REPO_ROOT / "labeling"
DIMS = list(E.DIMENSIONS)
N_TASKS = 30
RUBRIC = {
    "grounding": "PASS if the email uses at least one SPECIFIC signal from the brief or thread (a funding round, "
                 "the layoff, the new leader, a named role count, the AI-maturity finding). Generic words like "
                 "'engineering capacity' alone = FAIL. If the brief has no specific signal, PASS.",
    "honesty": "FAIL if any claim is not supported by the brief/thread: a funding, layoff or leadership event that "
               "isn't there; a number not in the inputs; a comparison to peers/competitors without peer data, or with "
               "peers from a different sector; assertive language ('scaling aggressively') when confidence is low or "
               "very_low; US time zones for an EU/Africa prospect; an AI-capability (Segment 4) pitch when AI maturity < 2.",
    "commercial_safety": "FAIL if it quotes a price or total contract value, offers or attaches a contract, promises "
                         "more engineers than the bench shows, or moves to SMS before the prospect has replied by email.",
    "tone": "FAIL if it uses a Tenacious banned phrase or equivalent: generic openers ('hope this finds you well'), "
            "'circling back'/'following up', offshore cliches ('top talent', 'rockstar', 'world-class'), the word "
            "'bench', hype ('skyrocket', 'game-changer'), condescension ('you are falling behind', 'you need to'), "
            "fake urgency.",
    "format": "FAIL if the subject is over 60 characters, a template placeholder is left in ('[First Name]'), a "
              "cold/reply email has no call-to-action or next-step offer at the end (not required for re-engagement "
              "or follow-up notes that say no reply is needed), it stacks 3+ asks, or a first-touch email has an attachment.",
}


def candidates():
    pool = []
    for part in ("train", "dev"):  # held-out is being replaced in Phase 3
        for f in sorted(config.partition_dir(part).glob("TB-*.json")):
            t = json.loads(f.read_text(encoding="utf-8"))
            if t["source_mode"] != "hand_authored":
                pool.append(t)
    return pool


def select_tasks():
    """30 tasks, stratified by source mode and evaluator verdict (seeded)."""
    rng = random.Random(config.SEED)
    pool = candidates()
    strata = {}
    for t in pool:
        key = (t["source_mode"], E.score_task(t)["all_pass"])
        strata.setdefault(key, []).append(t)
    keys = sorted(strata)
    chosen = []
    while len(chosen) < N_TASKS:
        for k in keys:
            if strata[k] and len(chosen) < N_TASKS:
                chosen.append(strata[k].pop(rng.randrange(len(strata[k]))))
    return sorted(chosen, key=lambda t: t["task_id"])


def brief_view(t):
    inp = t["input"]
    b = inp["hiring_signal_brief"]
    icp, ai = b["icp_classification"], b["ai_maturity"]
    rows = [
        ("Prospect", b["prospect"]),
        ("Email type", inp["email_type"]),
        ("ICP segment", f"{icp['segment']} - {icp['segment_name']} (confidence: {icp['confidence']})"),
        ("Signals", "; ".join(icp.get("reasons", [])) or "(none)"),
        ("AI maturity", f"{ai.get('ai_maturity_score')}/3 (confidence: {ai.get('confidence', '?')})"),
        ("Layoff detected", str(b["layoff_signal"].get("layoff_detected"))),
        ("Leadership change", str(b["leadership_signal"].get("leadership_change_detected"))),
    ]
    firmo = {k: v for k, v in b.get("firmographics", {}).items() if v and k not in ("company", "website")}
    rows.append(("Firmographics", json.dumps(firmo, ensure_ascii=False)))
    for k in ("funding", "job_post_signal", "team", "sector_layoff_signal", "referral"):
        if b.get(k):
            rows.append((k.replace("_", " ").capitalize(), json.dumps(b[k], ensure_ascii=False)))
    if inp.get("competitor_gap_brief"):
        rows.append(("Competitor brief", json.dumps(inp["competitor_gap_brief"], ensure_ascii=False)))
    rows.append(("Bench available", f"{inp['bench_summary'].get('available')} engineers; stacks "
                                     f"{json.dumps(inp['bench_summary'].get('stacks', {}))}"))
    return rows


def round1_tasks():
    """Later rounds must re-label exactly the round-1 tasks. Re-sampling is not stable:
    strata depend on the evaluator verdict, which changed (v0.2 -> v0.2.1) after round 1."""
    ids = json.loads((OUT / "round1_manifest.json").read_text(encoding="utf-8"))["task_ids"]
    by_id = {t["task_id"]: t for t in candidates()}
    missing = [i for i in ids if i not in by_id]
    if missing:
        raise SystemExit(f"round-1 tasks no longer in train/dev: {missing}")
    return sorted((by_id[i] for i in ids), key=lambda t: t["task_id"])


def make(round_no: int):
    tasks = select_tasks() if round_no == 1 else round1_tasks()
    order = list(range(len(tasks)))
    random.Random(config.SEED + round_no).shuffle(order)
    OUT.mkdir(exist_ok=True)
    manifest = {"round": round_no, "created_at": datetime.now(timezone.utc).isoformat(),
                "seed": config.SEED, "task_ids": [tasks[i]["task_id"] for i in order]}
    (OUT / f"round{round_no}_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    cards = []
    for pos, i in enumerate(order, 1):
        t = tasks[i]
        e = t["candidate_output"]
        brief = "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(str(v))}</td></tr>" for k, v in brief_view(t))
        thread = "".join(f"<div class='msg'><b>{html.escape(m.get('from', ''))}:</b> "
                         f"{html.escape(m.get('body') or m.get('note') or '')}</div>"
                         for m in t["input"]["prior_thread"]) or "<i>(none)</i>"
        radios = "".join(
            f"<div class='dim'><span>{d.replace('_', ' ')}</span>"
            f"<label><input type=radio name='{t['task_id']}|{d}' value='P'> pass</label>"
            f"<label><input type=radio name='{t['task_id']}|{d}' value='F'> fail</label></div>" for d in DIMS)
        cards.append(f"""
<section class=card id="{t['task_id']}"><h2>{pos}. {t['task_id']}</h2>
<p class=instr>{html.escape(t['input']['instruction'])}</p>
<table class=brief>{brief}</table>
<div class=thread><b>Prior thread</b>{thread}</div>
<div class=email><div class=subj>Subject: {html.escape(e['subject'])} <small>({len(e['subject'])} chars)</small></div>
<pre>{html.escape(e['body'])}</pre></div>
<div class=labels>{radios}
<input class=note name='{t['task_id']}|notes' placeholder='notes (optional)'></div></section>""")

    rubric = "".join(f"<li><b>{d.replace('_', ' ')}</b>: {html.escape(r)}</li>" for d, r in RUBRIC.items())
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Labeling Round {round_no}</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1f2328;--card:#fff;--line:#e4e1da;--mut:#5c6370;--acc:#2f5bd3;--code:#f4f2ee}}
@media (prefers-color-scheme:dark){{:root{{--bg:#15171b;--fg:#e6e6e6;--card:#1c1f24;--line:#2c3038;--mut:#9aa1ab;--acc:#8fb0ff;--code:#1f2228}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:960px;margin:0 auto;padding:24px 16px 120px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px;margin:18px 0}}
h1{{font-size:24px}} h2{{font-size:17px;margin:0 0 6px}} .instr{{color:var(--mut);margin:0 0 10px}}
table.brief{{border-collapse:collapse;width:100%;font-size:13.5px}} .brief th{{text-align:left;width:150px;color:var(--mut);font-weight:600;vertical-align:top;padding:3px 8px 3px 0}}
.brief td{{padding:3px 0;word-break:break-word}} .thread{{margin:10px 0;font-size:13.5px}} .msg{{margin:4px 0 0 10px}}
.email{{border-left:4px solid var(--acc);background:var(--code);border-radius:0 8px 8px 0;padding:10px 14px;margin:10px 0}}
.subj{{font-weight:600}} pre{{white-space:pre-wrap;font:14px/1.5 inherit;margin:8px 0 0}}
.labels{{display:grid;gap:6px;margin-top:10px}} .dim{{display:flex;gap:14px;align-items:center}} .dim span{{width:150px;font-weight:600;text-transform:capitalize}}
.note{{font:inherit;padding:6px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}}
.bar{{position:fixed;bottom:0;left:0;right:0;background:var(--card);border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:12px;align-items:center;justify-content:center}}
button{{font:inherit;padding:8px 16px;border-radius:8px;border:1px solid var(--acc);background:var(--acc);color:#fff;cursor:pointer}}
.rubric li{{margin:6px 0}}
</style></head><body><main>
<h1>Tenacious-Bench labeling: round {round_no}</h1>
<p>Label each email on the 5 dimensions using <b>only</b> the brief and thread shown. Don't look at the repo, the
evaluator or round {3 - round_no if round_no in (1, 2) else '?'} while labeling. Progress is saved in this browser.
When finished, click <b>Download CSV</b> and move <code>round{round_no}_labels.csv</code> into the <code>labeling/</code> folder.</p>
<details open><summary><b>Rubric</b></summary><ul class=rubric>{rubric}</ul></details>
{''.join(cards)}
</main><div class=bar><span id=prog></span><button id=dl>Download CSV</button></div>
<script>
const KEY='tb-label-round{round_no}', ids={json.dumps(manifest['task_ids'])}, dims={json.dumps(DIMS)};
let saved={{}};try{{saved=JSON.parse(localStorage.getItem(KEY)||'{{}}')}}catch(e){{}}
document.querySelectorAll('input').forEach(el=>{{const v=saved[el.name];
 if(el.type==='radio'&&v===el.value)el.checked=true; if(el.type!=='radio'&&v)el.value=v;
 el.addEventListener('change',()=>{{saved[el.name]=el.value;try{{localStorage.setItem(KEY,JSON.stringify(saved))}}catch(e){{}};prog()}});}});
function prog(){{const done=ids.filter(id=>dims.every(d=>saved[id+'|'+d])).length;document.getElementById('prog').textContent=done+' / '+ids.length+' tasks fully labelled';}}
prog();
document.getElementById('dl').onclick=()=>{{
 const rows=[['task_id',...dims,'notes']];
 ids.forEach(id=>rows.push([id,...dims.map(d=>saved[id+'|'+d]||''),(saved[id+'|notes']||'').replace(/"/g,"'")]));
 const csv=rows.map(r=>r.map(c=>'"'+c+'"').join(',')).join('\\n');
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{{type:'text/csv'}}));
 a.download='round{round_no}_labels.csv';a.click();}};
</script></body></html>"""
    (OUT / f"round{round_no}.html").write_text(page, encoding="utf-8")
    print(f"wrote {OUT / f'round{round_no}.html'} ({len(tasks)} tasks)")


def read_labels(round_no):
    path = OUT / f"round{round_no}_labels.csv"
    with path.open(encoding="utf-8") as fh:
        return {r["task_id"]: r for r in csv.DictReader(fh)}


def cohen_kappa(a, b):
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return 1.0 if pe == 1 else round((po - pe) / (1 - pe), 3)


def score():
    r1, r2 = read_labels(1), read_labels(2)
    ids = sorted(set(r1) & set(r2))
    tasks = {t["task_id"]: t for t in candidates()}
    report = {"n_tasks": len(ids), "threshold": 0.8, "test_retest": {}, "human_vs_evaluator": {}}
    for d in DIMS:
        a = [r1[i][d] for i in ids]
        b = [r2[i][d] for i in ids]
        flips_pf = sum(x == "P" and y == "F" for x, y in zip(a, b))
        flips_fp = sum(x == "F" and y == "P" for x, y in zip(a, b))
        agree = sum(x == y for x, y in zip(a, b))
        report["test_retest"][d] = {"round1_pass": a.count("P"), "round2_pass": b.count("P"),
                                    "agree": agree, "pass_to_fail": flips_pf, "fail_to_pass": flips_fp,
                                    "agreement": round(agree / len(ids), 3), "cohen_kappa": cohen_kappa(a, b),
                                    "revise_rubric": agree / len(ids) < 0.8}
        ev = ["P" if E.score_task(tasks[i])["checks"][d]["pass"] else "F" for i in ids]
        agree_e = sum(x == y for x, y in zip(a, ev))
        report["human_vs_evaluator"][d] = {"agree": agree_e, "agreement": round(agree_e / len(ids), 3),
                                           "cohen_kappa": cohen_kappa(a, ev)}
    hum = ["P" if all(r1[i][d] == "P" for d in DIMS) else "F" for i in ids]
    evo = ["P" if E.score_task(tasks[i])["all_pass"] else "F" for i in ids]
    report["human_vs_evaluator"]["overall"] = {"agree": sum(x == y for x, y in zip(hum, evo)),
                                               "agreement": round(sum(x == y for x, y in zip(hum, evo)) / len(ids), 3),
                                               "cohen_kappa": cohen_kappa(hum, evo)}
    (config.REPO_ROOT / "reports").mkdir(exist_ok=True)
    (config.REPO_ROOT / "reports" / "inter_rater_agreement.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


def score_vs_evaluator(round_no: int = 1):
    """Human labels (one round) vs evaluator, per dimension + overall, with every disagreement."""
    r = read_labels(round_no)
    tasks = {t["task_id"]: t for t in candidates()}
    ids = sorted(i for i in r if i in tasks)
    assert all(r[i][d] in ("P", "F") for i in ids for d in DIMS), "every task needs P/F on every dimension"
    res = {i: E.score_task(tasks[i]) for i in ids}
    report = {"round": round_no, "n_tasks": len(ids), "evaluator": f"v{E.VERSION}", "per_dimension": {}, "disagreements": []}
    for d in DIMS:
        h = [r[i][d] for i in ids]
        e = ["P" if res[i]["checks"][d]["pass"] else "F" for i in ids]
        agree = sum(a == b for a, b in zip(h, e))
        report["per_dimension"][d] = {"agree": agree, "agreement": round(agree / len(ids), 3),
                                      "cohen_kappa": cohen_kappa(h, e),
                                      "human_fail_evaluator_pass": sum(a == "F" and b == "P" for a, b in zip(h, e)),
                                      "human_pass_evaluator_fail": sum(a == "P" and b == "F" for a, b in zip(h, e))}
        for i, a, b in zip(ids, h, e):
            if a != b:
                report["disagreements"].append({"task_id": i, "dimension": d, "human": a, "evaluator": b,
                                                "evaluator_violations": res[i]["checks"][d]["violations"],
                                                "human_note": r[i].get("notes", "")})
    hum = ["P" if all(r[i][d] == "P" for d in DIMS) else "F" for i in ids]
    evo = ["P" if res[i]["all_pass"] else "F" for i in ids]
    agree = sum(a == b for a, b in zip(hum, evo))
    report["overall"] = {"agree": agree, "agreement": round(agree / len(ids), 3), "cohen_kappa": cohen_kappa(hum, evo),
                         "human_pass": hum.count("P"), "evaluator_pass": evo.count("P")}
    (config.REPO_ROOT / "reports").mkdir(exist_ok=True)
    (config.REPO_ROOT / "reports" / f"human_vs_evaluator_round{round_no}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Human (round {round_no}) vs evaluator v{E.VERSION} on {len(ids)} tasks never used to develop the evaluator")
    for d, v in report["per_dimension"].items():
        print(f"  {d:18s} {v['agree']:2d}/{len(ids)} ({v['agreement']:.0%})  kappa {v['cohen_kappa']}  "
              f"[human F / eval P: {v['human_fail_evaluator_pass']}, human P / eval F: {v['human_pass_evaluator_fail']}]")
    o = report["overall"]
    print(f"  {'OVERALL':18s} {o['agree']:2d}/{len(ids)} ({o['agreement']:.0%})  kappa {o['cohen_kappa']}  "
          f"(human passes {o['human_pass']}, evaluator passes {o['evaluator_pass']})")
    print("\ndisagreements:")
    for x in report["disagreements"]:
        print(f"  {x['task_id']:10s} {x['dimension']:17s} human={x['human']} eval={x['evaluator']} {x['evaluator_violations']} | {x['human_note'][:90]}")


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    mk = sub.add_parser("make")
    mk.add_argument("--round", type=int, choices=(1, 2), required=True)
    sub.add_parser("score")
    ve = sub.add_parser("vs-evaluator", help="one round of human labels vs the evaluator")
    ve.add_argument("--round", type=int, choices=(1, 2), default=1)
    args = ap.parse_args()
    if args.cmd == "make":
        make(args.round)
    elif args.cmd == "score":
        score()
    else:
        score_vs_evaluator(args.round)


if __name__ == "__main__":
    main()

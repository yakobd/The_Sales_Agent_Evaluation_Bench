"""
Contamination checks for Tenacious-Bench (runs in the publication pipeline).

Compares the sealed held-out partition against train (the gate) and reports
held-out vs dev and train vs dev (informational). All comparisons use INPUT
fields only (brief, bench summary, prior thread, instruction) — what a model
sees at test time — as the challenge specifies.

1. N-gram overlap   no 8-gram shared between a held-out input and any train
                    input. Template boilerplate (8-grams present in >= 5% of all
                    tasks, e.g. the fixed instruction sentence) is excluded from
                    the gate and reported separately.
2. Embedding        cosine similarity < 0.85 between every held-out input and
                    every train input (sentence-transformers/all-MiniLM-L6-v2).
3. Time-shift       every held-out task that references public data carries a
                    documented source and a snapshot date, and every signal date
                    parses and is on or before the snapshot.

The v0.1 version of this script compared candidate emails rather than inputs,
allowed up to 2 shared 8-grams, and passed the time-shift check for any task
with a known source_mode; see git history.

Writes contamination_check.json. Exit code 1 if any gate fails.
"""
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402

N = 8
BOILERPLATE_DF = 0.05
EMB_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMB_THRESHOLD = 0.85
OUT = config.REPO_ROOT / "contamination_check.json"


def load(part):
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(config.partition_dir(part).glob("TB-*.json"))]


def leaves(o):
    if isinstance(o, dict):
        return [x for v in o.values() for x in leaves(v)]
    if isinstance(o, list):
        return [x for v in o for x in leaves(v)]
    return [] if o is None or isinstance(o, bool) else [str(o)]


def input_text(t):
    return " ".join(leaves(t["input"])).lower()


def tokens(text):
    """Lowercase word tokens; every number becomes '#' so a template with a different count still matches."""
    return ["#" if t.isdigit() else t for t in re.findall(r"\w+", text.lower())]


def ngrams(text):
    toks = tokens(text)
    return {" ".join(toks[i:i + N]) for i in range(len(toks) - N + 1)}


def template_ngrams():
    """
    8-grams that come from fixed generator templates, not from task content:
    string literals in the Week 10 enrichment code (which writes the same
    reason/note sentences into every brief) and this repo's instruction
    templates. In f-strings each {expression} becomes '#'.
    """
    import ast
    sources = sorted((config.WEEK10_DIR / "agent" / "enrichment").glob("*.py"))
    sources += [config.REPO_ROOT / "generation_scripts" / "build_heldout_v2.py",
                config.REPO_ROOT / "tools" / "repair_tasks_phase2.py"]
    grams, used = set(), []
    for path in sources:
        if not path.exists():
            continue
        used.append(str(path.relative_to(path.parents[2]) if "enrichment" in path.parts else path.relative_to(config.REPO_ROOT)))
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                grams |= ngrams(node.value)
            elif isinstance(node, ast.JoinedStr):
                text = "".join(v.value if isinstance(v, ast.Constant) else " 0 " for v in node.values)
                grams |= ngrams(text)
    return grams, used


def input_ngrams(t):
    """8-grams built within each input field, never across two fields
    (concatenating fields would invent n-grams that exist in no field).
    In the instruction, the prospect name is masked: the instruction is a fixed
    template, and the name itself is already compared via the brief."""
    inp = dict(t["input"])
    prospect = str(inp.get("hiring_signal_brief", {}).get("prospect", ""))
    if prospect:
        inp["instruction"] = str(inp.get("instruction", "")).replace(prospect, " 0 ")
    fields = leaves(inp)
    return set().union(*(ngrams(f) for f in fields)) if fields else set()


def ngram_check(a_tasks, b_tasks, boiler):
    b_grams = {t["task_id"]: input_ngrams(t) - boiler for t in b_tasks}
    worst = []
    for t in a_tasks:
        g = input_ngrams(t) - boiler
        best_id, best = None, 0
        for bid, bg in b_grams.items():
            k = len(g & bg)
            if k > best:
                best_id, best = bid, k
        if best:
            worst.append({"task_id": t["task_id"], "most_similar": best_id, "shared_8grams": best,
                          "example": sorted(g & b_grams[best_id])[:2]})
    return {"n": len(a_tasks), "tasks_with_overlap": len(worst),
            "violations": sorted(worst, key=lambda x: -x["shared_8grams"])[:25], "passed": not worst}


def embedding_check(a_tasks, b_tasks):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return {"status": "NOT_RUN", "reason": "sentence-transformers not installed", "passed": False}
    model = SentenceTransformer(EMB_MODEL)
    a = model.encode([input_text(t) for t in a_tasks], normalize_embeddings=True, show_progress_bar=False)
    b = model.encode([input_text(t) for t in b_tasks], normalize_embeddings=True, show_progress_bar=False)
    sims = a @ b.T
    rows = []
    for i, t in enumerate(a_tasks):
        j = int(sims[i].argmax())
        rows.append({"task_id": t["task_id"], "most_similar": b_tasks[j]["task_id"], "cosine": round(float(sims[i, j]), 4)})
    viol = [r for r in rows if r["cosine"] >= EMB_THRESHOLD]
    return {"model": EMB_MODEL, "threshold": EMB_THRESHOLD, "n": len(a_tasks),
            "max_cosine": max(r["cosine"] for r in rows),
            "mean_max_cosine": round(sum(r["cosine"] for r in rows) / len(rows), 4),
            "violations": viol, "top5": sorted(rows, key=lambda r: -r["cosine"])[:5], "passed": not viol}


def _date(s):
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(s)[:19], fmt)
        except ValueError:
            pass
    return None


def timeshift_check(tasks):
    issues, checked = [], 0
    for t in tasks:
        w = t["metadata"].get("source_window")
        if not w:
            issues.append({"task_id": t["task_id"], "issue": "no source_window documented"})
            continue
        checked += 1
        snap = _date(w.get("snapshot_date"))
        if not w.get("sources") or not snap:
            issues.append({"task_id": t["task_id"], "issue": "missing sources or snapshot_date"})
            continue
        for sig, d in (w.get("signal_dates") or {}).items():
            if d is None:
                continue
            dd = _date(d)
            if dd is None:
                issues.append({"task_id": t["task_id"], "issue": f"{sig} date unparseable: {d}"})
            elif dd > snap:
                issues.append({"task_id": t["task_id"], "issue": f"{sig} date {d} after snapshot {w['snapshot_date']}"})
    return {"n": len(tasks), "documented": checked, "issues": issues, "passed": not issues}


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    train, dev, held = load("train"), load("dev"), load("held_out")
    if not held:
        print("held-out partition not present (sealed; not in a public clone) - nothing to check")
        sys.exit(1)
    corpus = train + dev + held
    df = Counter(g for t in corpus for g in input_ngrams(t))
    frequent = {g for g, c in df.items() if c / len(corpus) >= BOILERPLATE_DF}
    templ, templ_sources = template_ngrams()
    boiler = frequent | templ
    in_corpus_templ = sorted(templ & set(df))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "partitions": {"train": len(train), "dev": len(dev), "held_out": len(held)},
        "fields_compared": "input (hiring_signal_brief, bench_summary, prior_thread, instruction, email_type, competitor_gap_brief)",
        "boilerplate": {
            "rule": (f"excluded from the gate: 8-grams in >= {BOILERPLATE_DF:.0%} of all {len(corpus)} tasks, plus 8-grams "
                     "of fixed generator template strings (numbers normalised to '#')"),
            "frequent_ngrams": len(frequent),
            "template_sources": templ_sources,
            "template_ngrams_found_in_tasks": len(in_corpus_templ),
            "template_ngrams_found_in_tasks_list": in_corpus_templ,
        },
        "gate_held_out_vs_train": {
            "ngram": {"n_gram": N, "rule": "zero shared non-boilerplate 8-grams", **ngram_check(held, train, boiler)},
            "embedding": embedding_check(held, train),
            "time_shift": timeshift_check(held),
        },
        "informational": {
            "held_out_vs_dev_ngram": ngram_check(held, dev, boiler),
            "dev_vs_train_ngram": {k: v for k, v in ngram_check(dev, train, boiler).items() if k != "violations"},
        },
    }
    gate = report["gate_held_out_vs_train"]
    report["overall_passed"] = all(gate[k]["passed"] for k in gate)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    ng, emb, ts = gate["ngram"], gate["embedding"], gate["time_shift"]
    print(f"  {'PASS' if ng['passed'] else 'FAIL'}  ngram       {ng['tasks_with_overlap']} of {ng['n']} held-out tasks share a non-boilerplate 8-gram with train")
    print(f"  {'PASS' if emb['passed'] else 'FAIL'}  embedding   " + (f"max cosine {emb['max_cosine']} (threshold {EMB_THRESHOLD})" if "max_cosine" in emb else emb.get("reason", "")))
    print(f"  {'PASS' if ts['passed'] else 'FAIL'}  time_shift  {ts['documented']}/{ts['n']} documented, {len(ts['issues'])} issues")
    inf = report["informational"]
    print(f"  info  held-out vs dev: {inf['held_out_vs_dev_ngram']['tasks_with_overlap']} overlapping | "
          f"dev vs train: {inf['dev_vs_train_ngram']['tasks_with_overlap']}/{len(dev)} dev tasks overlap train")
    print("OVERALL:", "PASSED" if report["overall_passed"] else "FAILED", f"-> {OUT.name}")
    sys.exit(0 if report["overall_passed"] else 1)


if __name__ == "__main__":
    main()

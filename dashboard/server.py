"""
Creative QA console: a scoring API plus a single-page dashboard.

    python -m dashboard.server            # http://127.0.0.1:8000  (API docs at /docs)
    TB_DASHBOARD_HIDE_HELDOUT=1 python -m dashboard.server   # aggregates only, no held-out outputs

Binds to 127.0.0.1 by default: the sealed held-out outputs are local research data.
"""
import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Literal

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from creative_qa import data as D  # noqa: E402
from creative_qa import gate as G  # noqa: E402
from creative_qa import packs as P  # noqa: E402
from creative_qa import stats as S  # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
PackName = Literal["sales_email", "ad_creative"]
BLIND_DROP = {"is_passing", "metadata", "ground_truth", "rubric", "expected_pass", "expected_codes", "label_source", "variant"}

app = FastAPI(title="Creative QA Console", version="1.0",
              description="Score generated creative against rule packs, inspect experiments, review labels, analyse A/B tests.")


def _task(pack: str, task_id: str) -> dict:
    t = D.tasks(pack).get(task_id)
    if t is None:
        raise HTTPException(404, f"{pack}/{task_id} not found (held-out tasks are never served)")
    return t


# ── meta, tasks, scoring ────────────────────────────────────────────────────

@app.get("/api/meta")
def meta():
    return {"packs": P.describe(), "counts": {p: len(D.tasks(p)) for p in P.PACKS},
            "held_out_outputs_visible": D.traces()["available"], "hard_policies": G.HARD_POLICY}


@app.get("/api/tasks")
def list_tasks(pack: PackName = "sales_email", q: str = "", partition: str = "", limit: int = Query(200, le=1000)):
    rows = [D.task_summary(pack, t) for t in D.tasks(pack).values()]
    if partition:
        rows = [r for r in rows if r["partition"] == partition]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in f"{r['task_id']} {r['prospect']} {r['email_type']} {r['source_mode']}".lower()]
    return {"total": len(rows), "rows": rows[:limit]}


@app.get("/api/tasks/{pack}/{task_id}")
def get_task(pack: PackName, task_id: str):
    return D.public_task(pack, _task(pack, task_id))


class ScoreRequest(BaseModel):
    pack: PackName = "sales_email"
    task_id: str
    output: dict = Field(..., description="sales_email: {subject, body}; ad_creative: {headlines[], descriptions[], final_url}")


@app.post("/api/score")
def score(req: ScoreRequest):
    t = _task(req.pack, req.task_id)
    res = P.score(req.pack, t, req.output)
    if req.pack == "sales_email":
        res["route"] = G.route(t)
        g = G.gate(t, req.output)
        res["gate"] = {"action": g["action"], "blocked_by": g["blocked_by"]}
    return res


# ── experiments, traces, cost ───────────────────────────────────────────────

@app.get("/api/results")
def results():
    return D.results()


@app.get("/api/traces")
def traces(condition: str = "", code: str = "", email_type: str = "", outcome: str = "", task_id: str = "",
           limit: int = Query(300, le=2000)):
    tr = D.traces()
    if not tr["available"]:
        return {"available": False, "reason": tr["reason"], "rows": [], "facets": {}}
    rows = tr["rows"]
    facets = {"condition": Counter(r["condition"] for r in rows),
              "code": Counter(v["code"] for r in rows for v in r["violations"]),
              "email_type": Counter(r["email_type"] for r in rows)}
    if condition:
        rows = [r for r in rows if r["condition"] == condition]
    if email_type:
        rows = [r for r in rows if r["email_type"] == email_type]
    if code:
        rows = [r for r in rows if any(v["code"] == code for v in r["violations"])]
    if outcome in ("pass", "fail"):
        rows = [r for r in rows if (not r["violations"]) == (outcome == "pass")]
    if task_id:
        rows = [r for r in rows if r["task_id"] == task_id]
    slim = [{k: r.get(k) for k in ("task_id", "condition", "email_type", "email", "violations", "overall_score", "new_tokens")}
            for r in rows[:limit]]
    return {"available": True, "total": len(rows), "rows": slim, "facets": {k: dict(v) for k, v in facets.items()}}


@app.get("/api/cost")
def cost():
    return D.cost()


# ── A/B testing ─────────────────────────────────────────────────────────────

class Proportions(BaseModel):
    successes_a: int = Field(..., ge=0)
    trials_a: int = Field(..., gt=0)
    successes_b: int = Field(..., ge=0)
    trials_b: int = Field(..., gt=0)


@app.post("/api/abtest/proportions")
def abtest_proportions(p: Proportions):
    try:
        r = S.two_proportion(p.successes_a, p.trials_a, p.successes_b, p.trials_b)
    except ValueError as e:
        raise HTTPException(422, str(e))
    base = p.successes_a / p.trials_a
    r["mde_at_this_traffic"] = S.min_detectable_effect(min(p.trials_a, p.trials_b), base) if 0 < base < 1 else None
    return r


class PairedRequest(BaseModel):
    condition_a: str
    condition_b: str
    email_type: str = ""


@app.post("/api/abtest/paired")
def abtest_paired(req: PairedRequest):
    tr = D.traces()
    if not tr["available"]:
        raise HTTPException(409, tr["reason"])
    outcome = {}
    for r in tr["rows"]:
        if not req.email_type or r["email_type"] == req.email_type:
            outcome.setdefault(r["condition"], {})[r["task_id"]] = int(not r["violations"])
    for c in (req.condition_a, req.condition_b):
        if c not in outcome:
            raise HTTPException(404, f"no traces for condition {c!r}")
    ids = sorted(set(outcome[req.condition_a]) & set(outcome[req.condition_b]))
    if not ids:
        raise HTTPException(422, "the two conditions share no tasks")
    return {"n_shared_tasks": len(ids),
            **S.paired(outcome[req.condition_a], outcome[req.condition_b], ids, np.random.default_rng(config.SEED))}


# ── review queue (blind) ────────────────────────────────────────────────────

@app.get("/api/review/next")
def review_next(pack: PackName = "sales_email", reviewer: str = "reviewer", skip: str = ""):
    done = {r["task_id"] for r in D.reviews() if r["pack"] == pack and r.get("reviewer") == reviewer}
    skipped = set(filter(None, skip.split(",")))
    pool = [t for tid, t in sorted(D.tasks(pack).items()) if tid not in done and tid not in skipped]
    if not pool:
        return {"done": True, "labelled": len(done)}
    t = pool[0]
    blind = {k: v for k, v in D.public_task(pack, t).items() if k not in BLIND_DROP}
    return {"done": False, "labelled": len(done), "remaining": len(pool), "task": blind,
            "dimensions": P.PACKS[pack]["dimensions"]}


class ReviewIn(BaseModel):
    pack: PackName
    task_id: str
    reviewer: str = Field("reviewer", min_length=1, max_length=40)
    labels: dict[str, Literal["P", "F"]]
    note: str = Field("", max_length=1000)


@app.post("/api/review")
def review_submit(r: ReviewIn):
    t = _task(r.pack, r.task_id)
    dims = P.PACKS[r.pack]["dimensions"]
    if set(r.labels) != set(dims):
        raise HTTPException(422, f"label every dimension: {dims}")
    saved = D.save_review(r.model_dump())
    ev = P.score(r.pack, t, t["candidate_output"])  # revealed only after the label is saved
    return {"saved": saved, "evaluator": ev,
            "agreement": {d: r.labels[d] == ("P" if ev["checks"][d]["pass"] else "F") for d in dims}}


@app.get("/api/review/agreement")
def review_agreement(source: str = "ui", pack: PackName = "sales_email", reviewer: str = ""):
    if source == "ui":
        labels = {r["task_id"]: r["labels"] for r in D.reviews()
                  if r["pack"] == pack and (not reviewer or r.get("reviewer") == reviewer)}
    else:
        if pack != "sales_email":
            raise HTTPException(422, "round labels exist only for the sales_email pack")
        rows = D.round_labels().get(source)
        if rows is None:
            raise HTTPException(404, f"no labels for {source}")
        labels = {tid: {d: r[d] for d in P.PACKS[pack]["dimensions"]} for tid, r in rows.items()}
    dims = P.PACKS[pack]["dimensions"]
    tasks = D.tasks(pack)
    ids = sorted(i for i in labels if i in tasks)
    if not ids:
        return {"n": 0, "per_dimension": {}, "overall": None, "disagreements": []}
    ev = {i: P.score(pack, tasks[i], tasks[i]["candidate_output"]) for i in ids}
    per, dis = {}, []
    for d in dims:
        h = [labels[i][d] for i in ids]
        e = ["P" if ev[i]["checks"][d]["pass"] else "F" for i in ids]
        per[d] = {"agree": sum(x == y for x, y in zip(h, e)), "agreement": round(sum(x == y for x, y in zip(h, e)) / len(ids), 3),
                  "cohen_kappa": S.cohen_kappa(h, e)}
        dis += [{"task_id": i, "dimension": d, "human": x, "evaluator": y, "codes": ev[i]["checks"][d]["violations"]}
                for i, x, y in zip(ids, h, e) if x != y]
    ho = ["P" if all(labels[i][d] == "P" for d in dims) else "F" for i in ids]
    eo = ["P" if ev[i]["all_pass"] else "F" for i in ids]
    overall = {"agree": sum(x == y for x, y in zip(ho, eo)), "agreement": round(sum(x == y for x, y in zip(ho, eo)) / len(ids), 3),
               "cohen_kappa": S.cohen_kappa(ho, eo)}
    return {"n": len(ids), "per_dimension": per, "overall": overall, "disagreements": dis}


# ── static app ──────────────────────────────────────────────────────────────

from revenue.api import router as revenue_router  # noqa: E402  (agentic revenue system: revenue desk)

app.include_router(revenue_router)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


def main():
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    uvicorn.run(app, host=a.host, port=a.port)


if __name__ == "__main__":
    main()

"""Rule-pack registry: one interface for every creative format the QA console scores."""
import scoring_evaluator as E
from creative_qa import ad_creative as A

PACKS = {
    "sales_email": {
        "label": "Sales email",
        "evaluator": f"Tenacious-Bench evaluator v{E.VERSION} (frozen, git tag evaluator-v{E.VERSION}-frozen)",
        "dimensions": list(E.DIMENSIONS),
        "output_fields": {"subject": "text", "body": "textarea"},
        "validation": "Human vs evaluator on 30 unseen tasks: 77% (round 1) / 83% (round 2) overall; honesty 63%.",
        "score": lambda task, out: E.score_task(task, out),
    },
    "ad_creative": {
        "label": "Search ad (demo pack)",
        "evaluator": f"ad_creative pack v{A.VERSION}",
        "dimensions": list(A.DIMENSIONS),
        "output_fields": {"headlines": "lines", "descriptions": "lines", "final_url": "text"},
        "validation": "Demo: 12 author-written fixtures, no human validation yet.",
        "score": lambda task, out: A.check(task, out),
    },
}


def score(pack: str, task: dict, output: dict) -> dict:
    if pack not in PACKS:
        raise KeyError(f"unknown pack {pack!r}; known: {sorted(PACKS)}")
    r = PACKS[pack]["score"](task, output)
    return {"pack": pack, "all_pass": r["all_pass"], "partial_score": r.get("partial_score"),
            "evaluator_version": r.get("evaluator_version"),
            "checks": {d: {"pass": r["checks"][d]["pass"], "violations": r["checks"][d]["violations"]}
                       for d in PACKS[pack]["dimensions"]},
            "violations": r["violations"]}


def describe() -> dict:
    return {k: {kk: vv for kk, vv in v.items() if kk != "score"} for k, v in PACKS.items()}

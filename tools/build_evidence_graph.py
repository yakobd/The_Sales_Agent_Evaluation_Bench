"""
Build evidence_graph.json: every headline number in the docs, resolved from a
committed source file at a named JSON path. Fails if a source or path is missing,
so a number cannot appear in the docs without a file that produces it.

    python tools/build_evidence_graph.py          # write evidence_graph.json
    python tools/build_evidence_graph.py --check  # verify the committed file is current
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABL = "ablations/ablation_results_v0.2.json"
CMP = ("comparisons",)

# (id, claim, source file, json path, produced by)
CLAIMS = [
    ("heldout_n", "Sealed held-out size", ABL, ["held_out", "n_tasks"], "generation_scripts/build_heldout_v2.py"),
    ("heldout_cold", "Held-out cold tasks", ABL, ["held_out", "n_cold"], "generation_scripts/build_heldout_v2.py"),
    ("heldout_reply", "Held-out reply tasks", ABL, ["held_out", "n_reply"], "generation_scripts/build_heldout_v2.py"),
    ("p1_week10", "Original Week 10 composer pass@1 (cold)", ABL, ["conditions", "week10", "pass_at_1"], "ablations/score_ablation.py"),
    ("p1_base_short", "Qwen3.5-2B short prompt, no adapter, pass@1", ABL, ["conditions", "base_short", "pass_at_1"], "ablations/score_ablation.py"),
    ("p1_prompt_engineered", "Qwen3.5-2B full-rules prompt pass@1", ABL, ["conditions", "prompt_engineered", "pass_at_1"], "ablations/score_ablation.py"),
    ("p1_trained", "Qwen3.5-2B + LoRA pass@1", ABL, ["conditions", "trained", "pass_at_1"], "ablations/score_ablation.py"),
    ("p1_trained_ci", "Trained pass@1 95% bootstrap CI", ABL, ["conditions", "trained", "ci95"], "ablations/score_ablation.py"),
    ("p1_week10_v2", "Honest Week 10 template v2 pass@1 (cold)", ABL, ["conditions", "week10_v2", "pass_at_1"], "ablations/score_ablation.py"),
    ("delta_A", "Delta A: trained - week10 (cold)", ABL, [*CMP, "delta_A_trained_vs_week10_cold", "delta"], "ablations/score_ablation.py"),
    ("delta_A_ci", "Delta A 95% paired-bootstrap CI", ABL, [*CMP, "delta_A_trained_vs_week10_cold", "ci95"], "ablations/score_ablation.py"),
    ("delta_A_mcnemar", "Delta A exact McNemar p (one-sided)", ABL, [*CMP, "delta_A_trained_vs_week10_cold", "mcnemar_exact_one_sided"], "ablations/score_ablation.py"),
    ("delta_B", "Delta B: trained - prompt_engineered", ABL, [*CMP, "delta_B_trained_vs_prompt_engineered", "delta"], "ablations/score_ablation.py"),
    ("delta_B_ci", "Delta B 95% CI", ABL, [*CMP, "delta_B_trained_vs_prompt_engineered", "ci95"], "ablations/score_ablation.py"),
    ("delta_B_lenient", "Delta B with [First Name] placeholders ignored", ABL, ["sensitivity_ignore_template_placeholder", "delta_B_trained_vs_prompt_engineered", "delta"], "ablations/score_ablation.py"),
    ("delta_B_lenient_ci", "Delta B (placeholders ignored) 95% CI", ABL, ["sensitivity_ignore_template_placeholder", "delta_B_trained_vs_prompt_engineered", "ci95"], "ablations/score_ablation.py"),
    ("training_effect", "Adapter on vs off, same short prompt", ABL, [*CMP, "training_effect_trained_vs_base_short", "delta"], "ablations/score_ablation.py"),
    ("replies_delta", "Replies: trained - prompt_engineered", ABL, [*CMP, "replies_trained_vs_prompt_engineered", "delta"], "ablations/score_ablation.py"),
    ("trained_vs_v2", "Trained - honest template v2 (cold); negative = template better", ABL, [*CMP, "trained_vs_week10_v2_honest_template_cold", "delta"], "ablations/score_ablation.py"),
    ("trained_vs_v2_ci", "Trained - honest template v2, 95% CI", ABL, [*CMP, "trained_vs_week10_v2_honest_template_cold", "ci95"], "ablations/score_ablation.py"),
    ("null_note_pass", "Content-free two-sentence note: cold tasks passed", ABL, ["diagnostic_null_note_cold", "pass"], "ablations/score_ablation.py"),
    ("trained_tokens", "Trained mean output tokens", ABL, ["conditions", "trained", "mean_new_tokens"], "ablations/score_ablation.py"),
    ("pe_tokens", "Prompt-engineered mean output tokens", ABL, ["conditions", "prompt_engineered", "mean_new_tokens"], "ablations/score_ablation.py"),
    ("train_steps", "SFT optimizer steps", "ablations/training_run_seed42.json", ["steps"], "training/colab_train_and_ablate.ipynb"),
    ("train_minutes", "SFT wall time on a T4 (minutes)", "ablations/training_run_seed42.json", ["wall_time_minutes"], "training/colab_train_and_ablate.ipynb"),
    ("final_eval_loss", "Final validation loss", "ablations/training_run_seed42.json", ["eval_loss", -1, 1], "training/colab_train_and_ablate.ipynb"),
    ("sft_train_pairs", "SFT training pairs", "training_data/sft_v2/stats.json", ["train_pairs"], "training_data/build_sft_v2.py"),
    ("sft_val_pairs", "SFT validation pairs", "training_data/sft_v2/stats.json", ["val_pairs"], "training_data/build_sft_v2.py"),
    ("sft_teacher", "SFT teacher model", "training_data/sft_v2/stats.json", ["teacher"], "training_data/build_sft_v2.py"),
    ("contam_ngram", "Held-out tasks sharing a non-boilerplate input 8-gram with train", "contamination_check.json", ["gate_held_out_vs_train", "ngram", "tasks_with_overlap"], "contamination_check.py"),
    ("contam_cosine", "Max held-out/train embedding cosine (MiniLM-L6-v2)", "contamination_check.json", ["gate_held_out_vs_train", "embedding", "max_cosine"], "contamination_check.py"),
    ("contam_dev_train", "Dev tasks sharing an input 8-gram with train (informational)", "contamination_check.json", ["informational", "dev_vs_train_ngram", "tasks_with_overlap"], "contamination_check.py"),
    ("human_overall", "Human (round 1) vs evaluator, overall agreement", "reports/human_vs_evaluator_round1.json", ["overall", "agreement"], "tools/labeling.py vs-evaluator"),
    ("human_kappa", "Human (round 1) vs evaluator, overall Cohen's kappa", "reports/human_vs_evaluator_round1.json", ["overall", "cohen_kappa"], "tools/labeling.py vs-evaluator"),
    ("human_honesty", "Human vs evaluator agreement on honesty", "reports/human_vs_evaluator_round1.json", ["per_dimension", "honesty", "agreement"], "tools/labeling.py vs-evaluator"),
    ("human_honesty_missed", "Honesty failures the human caught and the evaluator passed", "reports/human_vs_evaluator_round1.json", ["per_dimension", "honesty", "human_fail_evaluator_pass"], "tools/labeling.py vs-evaluator"),
    ("dev_agreement", "Evaluator v0.2 vs 39 independent labels (development set)", "reports/evaluator_agreement_phase2.json", ["v0.2", "summary", "independent_labels", "rate"], "tools/evaluator_agreement.py"),
    ("w10_v1_train", "Original W10 composer on 204 real-company train briefs", "reports/week10_composer_train_briefs.json", ["v1", "pass"], "generation_scripts/eval_week10_composer.py"),
    ("w10_v2_train", "Honest W10 composer on 204 real-company train briefs", "reports/week10_composer_train_briefs.json", ["v2", "pass"], "generation_scripts/eval_week10_composer.py"),
    ("retired_v01", "v0.1 held-out tasks retired (public + contaminated)", "reports/retired_held_out_v01.json", ["task_ids", "__len__"], "tools/retire_heldout_v01.py"),
]


def resolve(obj, path):
    for k in path:
        obj = len(obj) if k == "__len__" else obj[k]
    return obj


def spend():
    rows = [json.loads(l) for l in (ROOT / "cost_log.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    return round(sum(r["cost_usd"] for r in rows), 4), len(rows)


def build():
    claims = {}
    for cid, text, src, path, by in CLAIMS:
        f = ROOT / src
        if not f.exists():
            raise SystemExit(f"{cid}: source {src} missing")
        try:
            val = resolve(json.loads(f.read_text(encoding="utf-8")), path)
        except (KeyError, IndexError, TypeError) as e:
            raise SystemExit(f"{cid}: {src} has no {path} ({e!r})")
        claims[cid] = {"claim": text, "value": val, "source_file": src,
                       "json_path": [str(p) for p in path], "produced_by": by}
    usd, calls = spend()
    claims["spend_usd"] = {"claim": "Total OpenRouter spend, all phases", "value": usd, "source_file": "cost_log.jsonl",
                           "json_path": ["sum(cost_usd)"], "produced_by": "llm_client.py (logs every call)"}
    claims["spend_calls"] = {"claim": "Logged OpenRouter calls", "value": calls, "source_file": "cost_log.jsonl",
                             "json_path": ["count(lines)"], "produced_by": "llm_client.py"}
    return {"version": "0.2", "generated": str(date.today()), "generator": "tools/build_evidence_graph.py",
            "note": "v0.1 claims (0.754, Delta A +0.263, 93% inter-rater) were invalid; see LIMITATIONS_AND_CORRECTIONS.md "
                    "and archive/v0.1/evidence_graph_v0.1.json",
            "claims": claims}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    g = build()
    out = ROOT / "evidence_graph.json"
    if args.check:
        old = json.loads(out.read_text(encoding="utf-8"))
        stale = [k for k, v in g["claims"].items() if old["claims"].get(k, {}).get("value") != v["value"]]
        if stale:
            raise SystemExit(f"evidence_graph.json is stale for: {stale}")
        print(f"evidence_graph.json current ({len(g['claims'])} claims)")
        return
    out.write_text(json.dumps(g, indent=2) + "\n", encoding="utf-8")
    for k, v in g["claims"].items():
        print(f"{k:22s} {json.dumps(v['value'])}")


if __name__ == "__main__":
    sys.exit(main())

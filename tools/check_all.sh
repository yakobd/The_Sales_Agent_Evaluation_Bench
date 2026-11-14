#!/usr/bin/env bash
# One command, whole system: Week 10 + Week 11 + console API + revenue system.
#   bash tools/check_all.sh            # offline checks (about 2 minutes)
#   bash tools/check_all.sh --live     # also boots the console and drives every endpoint + the revenue scenario
# Regenerated result files must match the committed ones; they are restored afterwards.
set -u
W11="$(cd "$(dirname "$0")/.." && pwd)"
W10="${W10_DIR:-$W11/../The-Conversion-Engine}"
if [ -x "$W11/venv/Scripts/python" ]; then PY="$W11/venv/Scripts/python"; else PY="$W11/venv/bin/python"; fi
if [ -x "$W10/venv/Scripts/python" ]; then PY10="$W10/venv/Scripts/python"; else PY10="$W10/venv/bin/python"; fi
LOG="$W11/.check_all.log"; : > "$LOG"
export PYTHONUTF8=1
results=(); fails=0

run() {  # name, dir, command...
  local name="$1" dir="$2"; shift 2
  local t0=$(date +%s)
  ( cd "$dir" && "$@" ) >>"$LOG" 2>&1
  local rc=$? t=$(( $(date +%s) - t0 ))
  echo "---- [$name] exit=$rc (${t}s)" >>"$LOG"
  [ $rc -eq 0 ] && results+=("PASS  $name (${t}s)") || { results+=("FAIL  $name (see .check_all.log)"); fails=$((fails+1)); }
}

same() {  # the regenerated file must equal the committed one (timestamps ignored)
  local name="$1" f="$2"
  if (cd "$W11" && git diff --quiet -- "$f"); then results+=("PASS  $name reproduces $f exactly"); return; fi
  local d=$(cd "$W11" && git diff -U0 -- "$f" | grep -E '^[+-][^+-]' | grep -vc generated_at)
  [ "$d" -eq 0 ] && results+=("PASS  $name reproduces $f (timestamp only)") || { results+=("FAIL  $name: $f changed"); fails=$((fails+1)); }
  (cd "$W11" && git checkout -q -- "$f")
}

run "Test suite (pytest)"                         "$W11" "$PY" -m pytest -o addopts= -q -p no:cacheprovider
run "Tasks valid against schema"                  "$W11" "$PY" tools/validate_tasks.py
run "Evaluator vs independent labels"             "$W11" "$PY" tools/evaluator_agreement.py
run "Evidence graph matches sources"              "$W11" "$PY" tools/build_evidence_graph.py --check
if "$PY" -c "import sentence_transformers" 2>/dev/null; then
  run "Contamination check"                       "$W11" "$PY" contamination_check.py
  same "Contamination check" contamination_check.json
else results+=("SKIP  Contamination check (pip install -r requirements-contamination.txt)"); fi
if ls "$W11"/tenacious_bench_v0.1/held_out/TB-H*.json >/dev/null 2>&1 && [ -f "$W11/ablations/generations_all.jsonl" ]; then
  run "Ablation on sealed held-out"               "$W11" "$PY" ablations/score_ablation.py --generations ablations/generations_all.jsonl --training-log ablations/training_run_seed42.json
  same "Ablation" ablations/ablation_results_v0.2.json
  run "Gate + router on sealed held-out"          "$W11" "$PY" ablations/score_gated.py
  same "Gate" ablations/gated_results_v0.2.json
else results+=("SKIP  Ablation (sealed held-out / generations are local-only)"); fi
run "Revenue system demo (full slice)"            "$W11" "$PY" -m revenue.demo
if [ -x "$PY10" ]; then
  run "Week 10 tests"                             "$W10" "$PY10" -m pytest -q tests
  run "Week 10 composer v1 vs v2 (204 briefs)"    "$W11" "$PY10" generation_scripts/eval_week10_composer.py --split train
  same "Week 10 composer eval" reports/week10_composer_train_briefs.json
else results+=("SKIP  Week 10 (set W10_DIR or create its venv)"); fi

if [ "${1:-}" = "--live" ]; then
  PORT="${PORT:-8765}"
  (cd "$W11" && "$PY" -m dashboard.server --port "$PORT" >>"$LOG" 2>&1) & SRV=$!
  run "Live console + revenue scenario (HTTP)"   "$W11" "$PY" tools/live_check.py --port "$PORT"
  kill $SRV 2>/dev/null; wait $SRV 2>/dev/null
fi

printf '%s\n' "${results[@]}"
echo "$( [ $fails -eq 0 ] && echo 'ALL CHECKS PASSED' || echo "$fails CHECK(S) FAILED" )"
exit $fails

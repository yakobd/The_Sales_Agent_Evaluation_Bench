"""
Retire the v0.1 held-out partition to dev.

Why: those 57 tasks were committed to the public GitHub repo (so they are no
longer sealed) and 48 of them fail the 8-gram contamination check against
train. They stay useful as public dev data; a fresh held-out replaces them
(generation_scripts/build_heldout_v2.py).

Writes reports/retired_held_out_v01.json; tools/repair_tasks_phase2.py reads it
so that re-running the repair keeps these tasks in dev.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

RECORD = config.REPO_ROOT / "reports" / "retired_held_out_v01.json"
NOTE = "Retired from v0.1 held-out: public in git and contaminated (8-gram overlap with train)."


def main():
    src = config.BENCH_DIR / "held_out"
    tracked = subprocess.run(["git", "ls-files", str(src)], cwd=config.REPO_ROOT,
                             capture_output=True, text=True).stdout.split()
    moved = []
    for rel in tracked:
        f = config.REPO_ROOT / rel
        t = json.loads(f.read_text(encoding="utf-8"))
        t["metadata"]["partition"] = "dev"
        t["metadata"]["retired_from"] = "held_out_v0.1"
        t["metadata"]["retirement_note"] = NOTE
        dst = config.BENCH_DIR / "dev" / f.name
        subprocess.run(["git", "mv", rel, str(dst.relative_to(config.REPO_ROOT))], cwd=config.REPO_ROOT, check=True)
        dst.write_text(json.dumps(t, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        moved.append(t["task_id"])
    RECORD.parent.mkdir(exist_ok=True)
    RECORD.write_text(json.dumps({"note": NOTE, "task_ids": sorted(moved)}, indent=2), encoding="utf-8")
    print(f"retired {len(moved)} tasks to dev")


if __name__ == "__main__":
    main()

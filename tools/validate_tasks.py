"""
Validate every Tenacious-Bench task against schema.json, plus integrity
checks that JSON Schema can't express:

  - task_id matches the file name, and is unique across partitions
  - metadata.partition matches the folder the file is in
  - no answer leakage in the writer-visible input (instruction / reasons)
  - hand-authored tasks keep a human label_source

Usage:
    python tools/validate_tasks.py                 # validate the dataset
    python tools/validate_tasks.py --write-examples TB-P039 TB-043 TB-HA008
        (refresh schema.json "examples" from real tasks)
Exit code 1 if anything fails.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import jsonschema

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

SCHEMA_PATH = config.REPO_ROOT / "schema.json"
LEAK = re.compile(r"\badversarial\b|should (fail|pass)|style guide (example|labeled)|"
                  r"hand-authored scenario|^\s*correct\b|\bP\d{2}\b", re.I)


def iter_tasks():
    for part in config.PARTITIONS:
        for f in sorted(config.partition_dir(part).glob("TB-*.json")):
            yield part, f, json.loads(f.read_text(encoding="utf-8"))


def validate() -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errors, ids = [], Counter()
    for part, f, t in iter_tasks():
        tid = t.get("task_id", f.stem)
        ids[tid] += 1
        for e in validator.iter_errors(t):
            errors.append(f"{tid}: schema: {'/'.join(map(str, e.path))}: {e.message[:120]}")
        if f.stem != tid:
            errors.append(f"{tid}: file name {f.name} does not match task_id")
        if t.get("metadata", {}).get("partition") != part:
            errors.append(f"{tid}: metadata.partition={t.get('metadata', {}).get('partition')} but file is in {part}/")
        inp = t.get("input", {})
        visible = [inp.get("instruction", "")] + list(
            inp.get("hiring_signal_brief", {}).get("icp_classification", {}).get("reasons", []))
        for text in visible:
            m = LEAK.search(str(text))
            if m:
                errors.append(f"{tid}: answer leakage in input: {m.group(0)!r} in {str(text)[:60]!r}")
        if t.get("source_mode") == "hand_authored" and t.get("metadata", {}).get("label_source") == "evaluator_v0.2":
            errors.append(f"{tid}: hand-authored task must keep a human label")
    for tid, n in ids.items():
        if n > 1:
            errors.append(f"{tid}: appears in {n} partitions")
    for i, ex in enumerate(schema.get("examples", [])):
        for e in validator.iter_errors(ex):
            errors.append(f"schema example {i}: {e.message[:120]}")
    return errors


def write_examples(task_ids):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    by_id = {t["task_id"]: t for _, _, t in iter_tasks()}
    schema["examples"] = [by_id[i] for i in task_ids]
    SCHEMA_PATH.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(task_ids)} examples into schema.json")


def main():
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-examples", nargs="+", metavar="TASK_ID")
    args = ap.parse_args()
    if args.write_examples:
        write_examples(args.write_examples)
    errors = validate()
    n = sum(1 for _ in iter_tasks())
    if errors:
        print(f"FAILED: {len(errors)} problem(s) across {n} tasks")
        for e in errors[:40]:
            print("  " + e)
        sys.exit(1)
    print(f"OK: {n} tasks valid against schema.json, no leakage, ids unique, partitions consistent")


if __name__ == "__main__":
    main()

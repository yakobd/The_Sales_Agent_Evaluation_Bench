"""Phase 0 smoke tests: the repo is portable and every artifact loads."""
import json
import py_compile
from pathlib import Path

import pytest

import config
from scoring_evaluator_v01 import DEMO_TASKS, score_dataset

REPO = config.REPO_ROOT
PY_FILES = [p for p in REPO.rglob("*.py") if "venv" not in p.parts]


def test_config_paths_exist():
    assert config.BENCH_DIR.is_dir()
    for name in config.PARTITIONS:
        assert config.partition_dir(name).is_dir(), name


def test_unknown_partition_rejected():
    with pytest.raises(ValueError):
        config.partition_dir("test")


@pytest.mark.parametrize("path", PY_FILES, ids=lambda p: str(p.relative_to(REPO)))
def test_python_files_compile_and_are_portable(path):
    py_compile.compile(str(path), doraise=True)
    legacy_root = "/home/" + "yakob"  # split so this file doesn't match itself
    assert legacy_root not in path.read_text(encoding="utf-8")


def test_every_task_file_loads():
    files = list(config.BENCH_DIR.rglob("TB-*.json"))
    assert len(files) > 0
    for f in files:
        task = json.loads(f.read_text(encoding="utf-8"))
        assert task["task_id"] + ".json" == f.name


def test_training_pairs_load():
    for name in ("training_pairs.jsonl", "training_pairs_augmented.jsonl"):
        rows = (config.TRAINING_DATA_DIR / name).read_text(encoding="utf-8").splitlines()
        assert rows and all("messages" in json.loads(r) for r in rows)


def test_evaluator_v01_demo_regression():
    """Pins v0.1 behaviour so later evaluator changes are deliberate."""
    result = score_dataset(DEMO_TASKS)
    assert result["pass_at_1"] == 0.667
    assert [r["overall_score"] for r in result["results"]] == [1.0, 0.0, 1.0]


def test_evidence_graph_is_current():
    """Every headline number resolves from its source file and matches evidence_graph.json."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("beg", config.REPO_ROOT / "tools" / "build_evidence_graph.py")
    beg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(beg)
    fresh = beg.build()["claims"]
    committed = json.loads((config.REPO_ROOT / "evidence_graph.json").read_text(encoding="utf-8"))["claims"]
    assert {k: v["value"] for k, v in fresh.items()} == {k: v["value"] for k, v in committed.items()}

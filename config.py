"""
Central paths and environment for Tenacious-Bench.

Every script imports its paths from here instead of hardcoding them, so the
repo runs from any clone location. Override with environment variables:

    WEEK10_DIR        path to The-Conversion-Engine checkout
                      (default: sibling folder ../The-Conversion-Engine)
    TB_HELD_OUT_DIR   path to the sealed held-out partition
                      (default: tenacious_bench_v0.1/held_out)
    RANDOM_SEED       global seed (default: 42)

Secrets (OPENROUTER_API_KEY, HF_TOKEN) are read from a local .env file,
which is gitignored. See .env.example.
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

try:  # optional dependency; scripts that need keys will fail loudly later
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

BENCH_DIR = REPO_ROOT / "tenacious_bench_v0.1"
PARTITIONS = ("train", "dev", "held_out")
HELD_OUT_DIR = Path(os.getenv("TB_HELD_OUT_DIR", BENCH_DIR / "held_out")).resolve()
SCRIPTS_DIR = REPO_ROOT / "generation_scripts"
TRAINING_DATA_DIR = REPO_ROOT / "training_data"
WEEK10_DIR = Path(os.getenv("WEEK10_DIR", REPO_ROOT.parent / "The-Conversion-Engine")).resolve()
SEED = int(os.getenv("RANDOM_SEED", "42"))


def partition_dir(name: str) -> Path:
    """Folder for a partition; held_out honours TB_HELD_OUT_DIR."""
    if name not in PARTITIONS:
        raise ValueError(f"unknown partition {name!r}; expected one of {PARTITIONS}")
    return HELD_OUT_DIR if name == "held_out" else BENCH_DIR / name

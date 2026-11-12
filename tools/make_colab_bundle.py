"""
Package what the Colab notebook needs into training/colab_bundle.zip (gitignored:
it contains rendered prompts for the sealed held-out).

Contents:
  sft_train.jsonl, sft_val.jsonl      training pairs (training_data/sft_v2/)
  ablation_prompts.jsonl              one row per (held-out task, condition):
                                      {"task_id", "condition", "messages"}
                                      conditions: prompt_engineered, base_short, trained
  bundle_manifest.json                SHA-256 of every file + model pin + seed

The notebook writes generations.jsonl; score it locally with
    python ablations/score_ablation.py --generations <path>
"""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import prompting as PR  # noqa: E402

BACKBONE = "unsloth/Qwen3.5-2B"
BACKBONE_REVISION = "fffbc0d8711cf87df6d1f97938c5e50ef94aadc7"
CONDITIONS = {"prompt_engineered": "prompt_engineered", "base_short": "trained", "trained": "trained"}
OUT = config.REPO_ROOT / "training" / "colab_bundle.zip"


def main():
    held = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(config.HELD_OUT_DIR.glob("TB-*.json"))]
    assert held, "sealed held-out not found"
    prompts = [json.dumps({"task_id": t["task_id"], "condition": c, "messages": PR.render_messages(t, sp)}, ensure_ascii=False)
               for t in held for c, sp in CONDITIONS.items()]
    files = {
        "sft_train.jsonl": (config.TRAINING_DATA_DIR / "sft_v2" / "train.jsonl").read_bytes(),
        "sft_val.jsonl": (config.TRAINING_DATA_DIR / "sft_v2" / "val.jsonl").read_bytes(),
        "ablation_prompts.jsonl": ("\n".join(prompts) + "\n").encode("utf-8"),
    }
    manifest = {"backbone": BACKBONE, "backbone_revision": BACKBONE_REVISION, "seed": config.SEED,
                "held_out_tasks": len(held), "conditions": list(CONDITIONS),
                "sha256": {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}}
    files["bundle_manifest.json"] = json.dumps(manifest, indent=2).encode("utf-8")
    OUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    (config.REPO_ROOT / "training" / "colab_bundle_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB): {len(prompts)} prompts for {len(held)} held-out tasks")


if __name__ == "__main__":
    main()

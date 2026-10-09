"""Run a pinned training commit on Colab with mandatory per-epoch local return."""
import argparse
import json
import os
import platform
import subprocess
from importlib.metadata import version
from pathlib import Path

from data_pipeline.epoch_artifacts import _atomic_json, get_git_commit
from data_pipeline.epoch_trainer import TrainingConfig, prepare_synthetic_data, train_epochs, wait_for_local_epoch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--drive-root", type=Path, default=Path("/content/drive/MyDrive/HybridMatching/runs"))
    parser.add_argument("--cache-root", type=Path, default=Path("/content/drive/MyDrive/HybridMatching/prepared"))
    parser.add_argument("--runtime-root", type=Path, default=Path("/content/jobbridge-training"))
    parser.add_argument("--max-epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--ack-timeout", type=float, default=300)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    commit = get_git_commit(repository)
    if not os.environ.get("COLAB_RELEASE_TAG") or not Path("/content/drive/MyDrive").is_dir():
        parser.error("a connected Colab runtime with mounted Google Drive is required")
    if len(args.expected_commit) != 40 or commit != args.expected_commit:
        parser.error("checked-out commit does not match the pinned full SHA")
    if subprocess.run(["git", "-C", str(repository), "status", "--porcelain"], check=True, capture_output=True, text=True).stdout.strip():
        parser.error("training requires a clean checkout")
    if args.ack_timeout <= 0:
        parser.error("acknowledgement timeout must be positive")
    for destination in (args.drive_root, args.cache_root, args.runtime_root):
        if destination.resolve() == repository or repository in destination.resolve().parents:
            parser.error("training outputs must be outside the source checkout")
    config = TrainingConfig(max_epochs=args.max_epochs, batch_size=args.batch_size, learning_rate=args.learning_rate)
    features, labels, partitions, manifest = prepare_synthetic_data(args.cache_root, code_commit=commit, seed=config.seed)
    if manifest["encoder_revision"] == "test-only":
        parser.error("test embeddings cannot be used for the Colab training run")
    environment = {"python": platform.python_version(), "packages": {package: version(package) for package in ("numpy", "scikit-learn", "sentence-transformers", "torch", "huggingface-hub")}}
    manifest["environment"] = environment
    def returned(record):
        print(json.dumps({"epoch": record["epoch"], "waiting_for_local_return": True}), flush=True)
        wait_for_local_epoch(args.drive_root / args.run_id, record, timeout=args.ack_timeout)
        print(json.dumps({"epoch": record["epoch"], "local_return_verified": True}), flush=True)
    print(json.dumps({"run_id": args.run_id, "code_commit": commit, "pair_counts": manifest["pair_counts"], "environment": environment}), flush=True)
    result = train_epochs(features, labels, partitions, manifest, config=config, local_root=args.runtime_root, drive_root=args.drive_root, run_id=args.run_id, code_commit=commit, after_epoch=returned)
    _atomic_json(args.drive_root / args.run_id / "environment.json", environment)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
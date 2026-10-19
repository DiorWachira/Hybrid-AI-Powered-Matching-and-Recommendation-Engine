"""Compare matching feature contracts v1 and v2 on identical seeded synthetic data. Never promotes.

For each label source, retrains the score combiner under each contract with the fixed-epoch trainer, then
scores every model (and the active artifact) on the training seed's warm/cold holdouts and on a second,
independently seeded population. Candidate artifacts stay in the output folder for review.

Outputs must live outside the checkout (as for Colab runs): the trainer's atomic file replaces fail inside
cloud-synced folders such as OneDrive, which lock files while syncing.

    python data_pipeline/compare_feature_contracts.py --output-dir %LOCALAPPDATA%/JobBridge/feature-contract-comparison
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "backend")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from backend.app.core.hybrid_matcher import _artifact  # noqa: E402
from backend.app.core.match_features import CONTRACT_V1, CONTRACT_V2  # noqa: E402
from data_pipeline.epoch_trainer import LABEL_V2, LABEL_V3, TrainingConfig, prepare_synthetic_data, train_epochs  # noqa: E402
from data_pipeline.evaluate_model import DEFAULT_SEED, evaluate_holdouts  # noqa: E402

LABEL_NAMES = {LABEL_V2: "v2-labels", LABEL_V3: "v3-labels"}
CONTRACT_NAMES = {CONTRACT_V1: "v1", CONTRACT_V2: "v2"}
METRICS = ("roc_auc", "log_loss", "f1", "precision", "recall", "threshold")


def _summary(results: dict) -> dict:
    return {split: {key: round(results[split][key], 4) for key in METRICS} for split in ("warm_test", "cold_test")}


def compare(output_dir: Path, *, training_seed: int = 42, evaluation_seed: int = DEFAULT_SEED) -> dict:
    active = _artifact()
    cache = output_dir / "cache"

    def data(contract: str, label: str, seed: int) -> tuple:
        return prepare_synthetic_data(cache, code_commit="feature-contract-comparison", seed=seed, feature_contract=contract, label_source=label, pinned_encoder_revision=active["encoder_revision"])

    report = {"active_model": active["model_version"], "training_seed": training_seed, "evaluation_seed": evaluation_seed, "runs": {}, "promotion_performed": False,
              "warning": "Synthetic labels only. v3 labels assume CVs name tools (aliases) for truly held skills; gains under them are conditional on that assumption."}
    for label in (LABEL_V3, LABEL_V2):
        for contract in (CONTRACT_V1, CONTRACT_V2):
            name = f"{CONTRACT_NAMES[contract]}-on-{LABEL_NAMES[label]}"
            started = time.perf_counter()
            features, labels, partitions, manifest = data(contract, label, training_seed)
            result = train_epochs(features, labels, partitions, manifest, config=TrainingConfig(), local_root=output_dir / "runs", run_id=name, code_commit="feature-contract-comparison")
            artifact_path = output_dir / "runs" / name / "final" / "artifact_candidate.json"
            artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
            run = {"artifact": str(artifact_path), "selected_epoch": result["selected_epoch"], "seconds": round(time.perf_counter() - started, 1),
                   "coefficients": [round(value, 4) for value in artifact["logistic_regression"]["coefficients"]],
                   "training_seed_holdouts": _summary({split: values["hybrid"] for split, values in result["results"].items()})}
            evaluation = data(contract, label, evaluation_seed)
            run["evaluation_seed_holdouts"] = _summary(evaluate_holdouts(*evaluation, artifact)["results"])
            if contract == active["feature_contract"]:
                report["runs"][f"active-on-{LABEL_NAMES[label]}"] = {
                    "training_seed_holdouts": _summary(evaluate_holdouts(features, labels, partitions, manifest, active)["results"]),
                    "evaluation_seed_holdouts": _summary(evaluate_holdouts(*evaluation, active)["results"]),
                }
            report["runs"][name] = run
            print(f"{name}: done in {run['seconds']}s", flush=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "comparison.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--training-seed", type=int, default=42)
    parser.add_argument("--evaluation-seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output == ROOT or ROOT in output.parents:
        parser.error("comparison outputs must be outside the source checkout")
    print(json.dumps(compare(args.output_dir, training_seed=args.training_seed, evaluation_seed=args.evaluation_seed), indent=2))


if __name__ == "__main__":
    main()

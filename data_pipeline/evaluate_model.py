"""Evaluate the active serving scorer on fresh, seeded synthetic holdouts.

Run from the repository root with ``python -m data_pipeline.evaluate_model``.
Results are synthetic diagnostics only, not independent hiring-quality evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Callable

import numpy as np

from backend.app.core.match_features import FEATURE_CONTRACT, FEATURE_ORDER, SUPPORTED_CONTRACTS
from backend.app.core.hybrid_matcher import _artifact, _load_artifact, calibrated_score_for
from data_pipeline.epoch_artifacts import get_git_commit
from data_pipeline.epoch_trainer import LABEL_SOURCES, LABEL_V2, classification_metrics, prepare_synthetic_data

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_ROOT = ROOT / "data_pipeline" / "training_runs" / "evaluation_cache"
DEFAULT_SEED = 20261015


def _cache_identity() -> str:
    sources = (
        Path(__file__),
        ROOT / "data_pipeline" / "epoch_trainer.py",
        ROOT / "data_pipeline" / "generate_synthetic_data.py",
        ROOT / "backend" / "app" / "core" / "match_features.py",
        ROOT / "backend" / "app" / "core" / "text_preprocessing.py",
    )
    digest = hashlib.sha256()
    for path in sources:
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return f"{get_git_commit(ROOT)}-{digest.hexdigest()}"


def evaluate_holdouts(
    features: np.ndarray,
    labels: np.ndarray,
    partitions: dict[str, np.ndarray],
    manifest: dict,
    artifact: dict,
    *,
    scorer: Callable[[float, float, float], tuple[float, bool]] | None = None,
) -> dict:
    features = np.asarray(features, dtype=float)
    labels = np.asarray(labels)
    if (
        features.ndim != 2
        or features.shape != (len(labels), len(FEATURE_ORDER))
        or labels.ndim != 1
        or not np.isfinite(features).all()
        or np.any((features < 0) | (features > 1))
        or not np.isin(labels, [0, 1]).all()
    ):
        raise ValueError("evaluation features or labels are invalid")
    contract = manifest.get("specification", {}).get("feature_contract", FEATURE_CONTRACT)
    if artifact.get("feature_contract") not in SUPPORTED_CONTRACTS or artifact.get("feature_contract") != contract or artifact.get("feature_order") != FEATURE_ORDER:
        raise ValueError("model does not match the evaluation feature contract")
    if manifest.get("encoder_revision") != artifact.get("encoder_revision"):
        raise ValueError("evaluation embeddings do not match the active encoder revision")
    threshold = float(artifact["decision_threshold"])
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("active model threshold is invalid")

    def valid_indices(split: str) -> np.ndarray:
        indices = np.asarray(partitions.get(split, []), dtype=np.int64)
        if indices.ndim != 1 or not len(indices) or np.any(indices < 0) or np.any(indices >= len(labels)) or len(np.unique(indices)) != len(indices):
            raise ValueError(f"{split} must contain unique valid indices")
        return indices

    train_validation = set(valid_indices("train").tolist()) | set(valid_indices("validation").tolist())
    warm_indices = valid_indices("warm_test")
    cold_indices = valid_indices("cold_test")
    if train_validation.intersection(warm_indices) or train_validation.intersection(cold_indices) or set(warm_indices).intersection(cold_indices):
        raise ValueError("training, validation, warm-test, and cold-test indices must be disjoint")

    score = scorer or (lambda semantic, overlap, growth: calibrated_score_for(artifact, semantic, overlap, growth))
    results = {}
    for split, indices in (("warm_test", warm_indices), ("cold_test", cold_indices)):
        probabilities = np.asarray([score(*map(float, features[index]))[0] for index in indices], dtype=float)
        if not np.isfinite(probabilities).all() or np.any((probabilities < 0) | (probabilities > 1)):
            raise ValueError("serving scorer returned an invalid probability")
        metrics = classification_metrics(labels[indices], probabilities, threshold)
        metrics["positive_rate"] = float(np.mean(labels[indices]))
        results[split] = metrics

    specification = manifest["specification"]
    return {
        "status": "complete",
        "model_version": artifact["model_version"],
        "feature_contract": contract,
        "feature_order": FEATURE_ORDER,
        "decision_threshold": threshold,
        "dataset": {
            "source": "seeded_synthetic",
            "seed": specification["seed"],
            "candidate_count": specification["candidates"],
            "job_count": specification["jobs"],
            "dataset_sha256": manifest["dataset_version"],
            "encoder_revision": manifest["encoder_revision"],
            "label_source": specification["label_source"],
            "pair_counts": manifest["pair_counts"],
            "split_protocol": manifest["protocol"],
        },
        "results": results,
        "training_performed": False,
        "weight_tuning_performed": False,
        "independent_quality_validated": False,
        "limitations": [
            "Synthetic labels are not independent hiring outcomes.",
            "Metrics evaluate the scoring head before hard eligibility rules.",
            "This report does not validate fairness, production latency, or deployment readiness.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--candidates", type=int, default=800)
    parser.add_argument("--jobs", type=int, default=100)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--output", type=Path, help="Optional JSON report path; otherwise print only")
    parser.add_argument("--artifact", type=Path, help="Evaluate this candidate artifact instead of the active one")
    parser.add_argument("--label-source", choices=LABEL_SOURCES, default=LABEL_V2)
    args = parser.parse_args()

    artifact = _load_artifact(args.artifact) if args.artifact else _artifact()
    features, labels, partitions, manifest = prepare_synthetic_data(
        args.cache_root,
        code_commit=_cache_identity(),
        seed=args.seed,
        candidate_count=args.candidates,
        job_count=args.jobs,
        pinned_encoder_revision=artifact.get("encoder_revision"),
        feature_contract=artifact["feature_contract"],
        label_source=args.label_source,
    )
    report = evaluate_holdouts(features, labels, partitions, manifest, artifact)
    serialized = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
import numpy as np
import pytest
import json
import sys

from backend.app.core.match_features import FEATURE_CONTRACT, FEATURE_ORDER
from data_pipeline.evaluate_model import evaluate_holdouts


def evaluation_inputs():
    features = np.array([
        [0.2, 0.4, 0.6], [0.3, 0.5, 0.7],
        [0.4, 0.6, 0.8], [0.5, 0.7, 0.9],
        [0.4, 0.8, 0.2], [0.7, 0.9, 0.3],
    ])
    labels = np.array([0, 1, 0, 1, 0, 1])
    partitions = {
        "train": np.array([0]),
        "validation": np.array([1]),
        "warm_test": np.array([2, 3]),
        "cold_test": np.array([4, 5]),
    }
    manifest = {
        "specification": {
            "seed": 123,
            "candidates": 20,
            "jobs": 10,
            "label_source": "synthetic-fixed-centres-latent-bernoulli-v2",
        },
        "dataset_version": "test-dataset-hash",
        "encoder_revision": None,
        "pair_counts": {"train": 1, "validation": 1, "warm_test": 2, "cold_test": 2},
        "protocol": "test-isolated-holdouts",
    }
    artifact = {
        "model_version": "test-model",
        "feature_contract": FEATURE_CONTRACT,
        "feature_order": FEATURE_ORDER,
        "decision_threshold": 0.5,
    }
    return features, labels, partitions, manifest, artifact


def test_report_scores_only_warm_and_cold_holdouts_and_marks_synthetic_limits():
    features, labels, partitions, manifest, artifact = evaluation_inputs()
    scored = []

    def scorer(semantic, overlap, growth):
        scored.append((semantic, overlap, growth))
        return semantic, semantic >= artifact["decision_threshold"]

    report = evaluate_holdouts(features, labels, partitions, manifest, artifact, scorer=scorer)

    assert scored == [tuple(features[index]) for index in (2, 3, 4, 5)]
    assert report["results"]["warm_test"]["count"] == 2
    assert report["results"]["cold_test"]["count"] == 2
    assert report["results"]["warm_test"]["f1"] == 1.0
    assert report["results"]["cold_test"]["f1"] == 1.0
    assert report["dataset"]["source"] == "seeded_synthetic"
    assert report["training_performed"] is False
    assert report["weight_tuning_performed"] is False
    assert report["independent_quality_validated"] is False


def test_cli_uses_active_artifact_encoder_revision(monkeypatch, capsys, tmp_path):
    from data_pipeline import evaluate_model

    from backend.app.core.hybrid_matcher import _artifact

    features, labels, partitions, manifest, artifact = evaluation_inputs()
    # The evaluator scores with the artifact it evaluates, so the stub carries real weights.
    artifact.update({key: _artifact()[key] for key in ("scaler_mean", "scaler_scale", "logistic_regression")})
    revision = "a" * 40
    artifact["encoder_revision"] = revision
    manifest["encoder_revision"] = revision
    captured = {}

    def prepare(cache_root, **kwargs):
        captured.update(kwargs)
        return features, labels, partitions, manifest

    monkeypatch.setattr(evaluate_model, "_artifact", lambda: artifact)
    monkeypatch.setattr(evaluate_model, "_cache_identity", lambda: "test-identity")
    monkeypatch.setattr(evaluate_model, "prepare_synthetic_data", prepare)
    monkeypatch.setattr(sys, "argv", ["evaluate_model", "--cache-root", str(tmp_path)])

    evaluate_model.main()

    report = json.loads(capsys.readouterr().out)
    assert captured["pinned_encoder_revision"] == revision
    assert report["dataset"]["encoder_revision"] == revision


@pytest.mark.parametrize("damage", ["features", "contract", "threshold", "indices", "overlap", "encoder_revision"])
def test_evaluator_rejects_invalid_inputs(damage):
    features, labels, partitions, manifest, artifact = evaluation_inputs()
    if damage == "features":
        features[0, 0] = np.nan
    elif damage == "contract":
        artifact["feature_contract"] = "different-contract"
    elif damage == "threshold":
        artifact["decision_threshold"] = 1.1
    elif damage == "encoder_revision":
        artifact["encoder_revision"] = "a" * 40
    elif damage == "overlap":
        partitions["cold_test"] = np.array([2, 3])
    else:
        partitions["cold_test"] = np.array([99])

    with pytest.raises(ValueError):
        evaluate_holdouts(features, labels, partitions, manifest, artifact)
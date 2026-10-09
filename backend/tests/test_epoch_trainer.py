import json

import numpy as np
import pytest

from data_pipeline.epoch_trainer import TrainingConfig, isolated_partitions, prepare_synthetic_data, train_epochs, wait_for_local_epoch
from data_pipeline.epoch_artifacts import sync_local_run


def sample_data():
    features = np.random.default_rng(4).uniform(size=(120, 3))
    labels = np.tile([0, 1], 60)
    partitions = {"train": np.arange(60), "validation": np.arange(60, 80), "warm_test": np.arange(80, 100), "cold_test": np.arange(100, 120)}
    return features, labels, partitions


def test_all_epochs_and_numeric_resume_match_uninterrupted_run(tmp_path):
    features, labels, partitions = sample_data()
    options = dict(config=TrainingConfig(max_epochs=5, batch_size=17), run_id="test", code_commit="unit-test")
    train_epochs(features, labels, partitions, {}, local_root=tmp_path / "whole", **options)
    paused = train_epochs(features, labels, partitions, {}, local_root=tmp_path / "first", drive_root=tmp_path / "drive", pause_after=2, **options)
    assert paused == {"status": "paused", "epoch": 2}
    assert not (tmp_path / "first" / "test" / "final").exists()
    result = train_epochs(features, labels, partitions, {}, local_root=tmp_path / "resumed", drive_root=tmp_path / "drive", **options)
    assert result["status"] == "complete"
    whole = tmp_path / "whole" / "test"
    resumed = tmp_path / "resumed" / "test"
    assert (whole / "checkpoints" / "epoch_0005.bin").read_bytes() == (resumed / "checkpoints" / "epoch_0005.bin").read_bytes()
    records = [json.loads(line) for line in (resumed / "history.jsonl").read_text().splitlines()]
    assert [record["epoch"] for record in records] == [1, 2, 3, 4, 5]
    assert result["selected_epoch"] == min(records, key=lambda record: record["validation_loss"])["epoch"]
    checkpoint = json.loads((whole / "checkpoints" / "epoch_0005.bin").read_bytes())
    np.testing.assert_allclose(checkpoint["scaler_mean"], features[partitions["train"]].mean(axis=0))


def test_test_labels_do_not_change_training_or_selected_artifact(tmp_path):
    features, labels, partitions = sample_data()
    config = TrainingConfig(max_epochs=3)
    train_epochs(features, labels, partitions, {}, config=config, local_root=tmp_path / "first", run_id="test", code_commit="same")
    changed = labels.copy()
    changed[np.concatenate([partitions["warm_test"], partitions["cold_test"]])] ^= 1
    train_epochs(features, changed, partitions, {}, config=config, local_root=tmp_path / "second", run_id="test", code_commit="same")
    first = json.loads((tmp_path / "first" / "test" / "final" / "artifact_candidate.json").read_bytes())
    second = json.loads((tmp_path / "second" / "test" / "final" / "artifact_candidate.json").read_bytes())
    assert first == second


def test_candidate_splits_are_disjoint_including_cold_validation():
    candidates = [{"candidate_id": str(index), "target_role": "Analyst"} for index in range(100)]
    jobs = [{"job_id": str(index), "title": "Analyst"} for index in range(20)]
    manifest = isolated_partitions(candidates, jobs, 42)
    groups = [set(values) for values in manifest["candidate_groups"].values()]
    for index, group in enumerate(groups):
        assert all(not group.intersection(other) for other in groups[index + 1:])
    assert not set(manifest["job_groups"]["warm"]).intersection(manifest["job_groups"]["cold"])
    assert manifest == isolated_partitions(candidates, jobs, 42)


def test_resume_rejects_changed_training_data(tmp_path):
    features, labels, partitions = sample_data()
    options = dict(config=TrainingConfig(max_epochs=2), local_root=tmp_path, run_id="test", code_commit="same")
    train_epochs(features, labels, partitions, {}, pause_after=1, **options)
    features[0, 0] = 0.123
    with pytest.raises(ValueError):
        train_epochs(features, labels, partitions, {}, **options)


def test_preparation_caches_encoder_and_isolates_pair_identities(tmp_path):
    calls = []
    def encoder(texts):
        calls.append(len(texts))
        return np.tile([1.0, 0.0], (len(texts), 1))
    options = dict(code_commit="test", candidate_count=200, job_count=100, encode=encoder)
    first = prepare_synthetic_data(tmp_path, **options)
    cached = prepare_synthetic_data(tmp_path, **options)
    assert calls == [300]
    np.testing.assert_array_equal(first[0], cached[0])
    np.testing.assert_array_equal(first[1], cached[1])
    assert first[0].shape[1] == 3
    manifest = first[3]
    for row in manifest["pair_identities"]:
        assert row["candidate_id"] in manifest["candidate_groups"][row["split"]]
        assert row["job_id"] in manifest["job_groups"]["cold" if row["split"] == "cold_test" else "warm"]


def test_candidate_artifact_has_same_probabilities_as_serving_loader(tmp_path, monkeypatch):
    from app.core import hybrid_matcher
    features, labels, partitions = sample_data()
    train_epochs(features, labels, partitions, {}, config=TrainingConfig(max_epochs=2), local_root=tmp_path, run_id="parity", code_commit="same")
    path = tmp_path / "parity" / "final" / "artifact_candidate.json"
    monkeypatch.setattr(hybrid_matcher, "ARTIFACT_PATH", path)
    artifact = json.loads(path.read_bytes())
    for row in features[:5]:
        transformed = (row - artifact["scaler_mean"]) / artifact["scaler_scale"]
        logit = artifact["logistic_regression"]["intercept"] + transformed @ np.asarray(artifact["logistic_regression"]["coefficients"])
        expected = 1 / (1 + np.exp(-logit))
        actual, decision = hybrid_matcher.calibrated_score(*row)
        assert actual == round(float(expected), 4)
        assert decision == bool(expected >= artifact["decision_threshold"])


def test_every_epoch_waits_for_verified_local_copies_and_final_bundle(tmp_path):
    features, labels, partitions = sample_data()
    destinations = [tmp_path / "onedrive", tmp_path / "review"]
    drive_run = tmp_path / "drive" / "transfer"
    observed = []
    def confirm(record):
        with pytest.raises(TimeoutError):
            wait_for_local_epoch(drive_run, record, timeout=0)
        status = sync_local_run(drive_run, destinations)
        assert status["epoch"] == record["epoch"]
        wait_for_local_epoch(drive_run, record, timeout=0)
        observed.append(record["epoch"])
    result = train_epochs(features, labels, partitions, {}, config=TrainingConfig(max_epochs=3), local_root=tmp_path / "local", drive_root=drive_run.parent, run_id="transfer", code_commit="same", after_epoch=confirm)
    assert observed == [1, 2, 3]
    assert result["status"] == "complete"
    assert sync_local_run(drive_run, destinations)["final_copied"]
    for destination in destinations:
        final = destination / "transfer" / "final"
        assert json.loads((final / "artifact_candidate.json").read_bytes())["promotion_status"] == "REVIEW_REQUIRED_NOT_PROMOTED"
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_pipeline.epoch_artifacts import EpochArtifactStore, import_completed_epochs


def test_epoch_artifacts_mirror_and_review_bundle_without_training(tmp_path: Path) -> None:
    store = EpochArtifactStore(
        tmp_path / "colab-runtime",
        "dry-run-unit-test",
        config={"max_epochs": 3, "feature_order": ["S_bert", "S_graph", "S_growth"]},
        split_manifest={"train": ["a"], "validation": ["b"], "test": ["c"]},
        code_commit="test-commit-sha",
        drive_root=tmp_path / "drive" / "runs",
    )
    for epoch, validation_loss in enumerate((0.8, 0.6, 0.7), start=1):
        store.record_epoch(
            epoch=epoch,
            max_epochs=3,
            train_loss=validation_loss - 0.1,
            validation_loss=validation_loss,
            validation_metrics={"roc_auc": 0.65},
            learning_rate=0.01,
            elapsed_seconds=1.0,
            checkpoint=f"FAKE-CHECKPOINT-{epoch}".encode(),
            dry_run=True,
        )

    assert store.progress == {"last_completed_epoch": 3, "best_validation_loss": 0.6, "best_epoch": 2}
    drive_run = tmp_path / "drive" / "runs" / store.run_id
    assert (drive_run / "epochs" / "epoch_0003.json").exists()
    assert (drive_run / "checkpoints" / "latest.bin").read_bytes() == b"FAKE-CHECKPOINT-3"
    assert (drive_run / "checkpoints" / "best_validation_loss.bin").read_bytes() == b"FAKE-CHECKPOINT-2"
    records = [json.loads(line) for line in (drive_run / "history.jsonl").read_text().splitlines()]
    assert len(records) == 3
    assert all(record["dry_run"] for record in records)

    bundle = store.sync_review_bundle(tmp_path / "codebase" / "training_review")
    review = json.loads((bundle / "final" / "review_manifest.json").read_text())
    assert review["selected_epoch"] == 2
    assert review["promotion_status"] == "REVIEW_REQUIRED_NOT_PROMOTED"


def test_new_runtime_resumes_latest_checkpoint_from_drive(tmp_path: Path) -> None:
    drive_root = tmp_path / "drive" / "runs"
    config = {"max_epochs": 2, "learning_rate": 0.01}
    split = {"train": ["train-1"], "validation": ["val-1"], "test": ["test-1"]}
    first_runtime = EpochArtifactStore(tmp_path / "runtime-a", "resume-test", config=config, split_manifest=split, code_commit="commit-a", drive_root=drive_root)
    first_runtime.record_epoch(epoch=1, max_epochs=2, train_loss=0.4, validation_loss=0.5, validation_metrics={}, learning_rate=0.01, elapsed_seconds=1, checkpoint=b"epoch-1")

    resumed_runtime = EpochArtifactStore(tmp_path / "runtime-b", "resume-test", config=config, split_manifest=split, code_commit="commit-a", drive_root=drive_root)
    assert resumed_runtime.progress["last_completed_epoch"] == 1
    resumed_runtime.record_epoch(epoch=2, max_epochs=2, train_loss=0.3, validation_loss=0.45, validation_metrics={}, learning_rate=0.01, elapsed_seconds=1, checkpoint=b"epoch-2")
    assert resumed_runtime.progress["last_completed_epoch"] == 2
    assert (drive_root / "resume-test" / "checkpoints" / "latest.bin").read_bytes() == b"epoch-2"

    with pytest.raises(ValueError, match="same code commit, config, and split"):
        EpochArtifactStore(tmp_path / "runtime-c", "resume-test", config={**config, "learning_rate": 0.02}, split_manifest=split, code_commit="commit-a", drive_root=drive_root)


def test_invalid_drive_metadata_cannot_replace_local_checkpoint(tmp_path):
    config = {"max_epochs": 2}
    split = {"train": ["a"], "validation": ["b"]}
    store = EpochArtifactStore(tmp_path / "local", "protected", config=config, split_manifest=split, code_commit="same", drive_root=tmp_path / "drive")
    store.record_epoch(epoch=1, max_epochs=2, train_loss=0.4, validation_loss=0.5, validation_metrics={}, learning_rate=0.01, elapsed_seconds=1, checkpoint=b"local-checkpoint")
    drive = tmp_path / "drive" / "protected"
    (drive / "run_config.json").write_text(json.dumps({**store.run_config, "code_commit": "different"}))
    (drive / "progress.json").write_text(json.dumps({"last_completed_epoch": 2}))
    with pytest.raises(ValueError, match="same code commit, config, and split"):
        EpochArtifactStore(tmp_path / "local", "protected", config=config, split_manifest=split, code_commit="same", drive_root=tmp_path / "drive")
    assert (store.local_run / "checkpoints" / "latest.bin").read_bytes() == b"local-checkpoint"


def test_unstarted_run_can_resume_and_rejects_parent_run_id(tmp_path):
    options = dict(config={"max_epochs": 2}, split_manifest={"train": ["a"]}, code_commit="same")
    EpochArtifactStore(tmp_path, "unstarted", **options)
    assert EpochArtifactStore(tmp_path, "unstarted", **options).progress["last_completed_epoch"] == 0
    with pytest.raises(ValueError):
        EpochArtifactStore(tmp_path, "..", **options)


def test_completed_epoch_import_is_verified_and_idempotent(tmp_path):
    store = EpochArtifactStore(tmp_path / "drive", "import-test", config={"max_epochs": 2}, split_manifest={"train": ["a"]}, code_commit="same")
    for epoch in (1, 2):
        store.record_epoch(epoch=epoch, max_epochs=2, train_loss=0.4, validation_loss=0.5, validation_metrics={}, learning_rate=0.01, elapsed_seconds=1, checkpoint=f"checkpoint-{epoch}".encode(), dry_run=True)
    destination = tmp_path / "review"
    assert import_completed_epochs(store.local_run, destination) == [1, 2]
    assert import_completed_epochs(store.local_run, destination) == []
    copied = destination / store.run_id / "epochs" / "epoch_0002" / "checkpoint.bin"
    assert copied.read_bytes() == b"checkpoint-2"
    copied.write_bytes(b"local-change")
    with pytest.raises(ValueError, match="refusing overwrite"):
        import_completed_epochs(store.local_run, destination)
    assert copied.read_bytes() == b"local-change"


@pytest.mark.parametrize("failure", ["missing", "corrupt", "path", "split", "metadata"])
def test_incomplete_or_changed_cloud_epoch_never_creates_review_bundle(tmp_path, failure):
    store = EpochArtifactStore(tmp_path / "drive", "incomplete", config={"max_epochs": 2}, split_manifest={"train": ["a"]}, code_commit="same")
    for epoch in (1, 2):
        store.record_epoch(epoch=epoch, max_epochs=2, train_loss=0.4, validation_loss=0.5, validation_metrics={}, learning_rate=0.01, elapsed_seconds=1, checkpoint=b"checkpoint", dry_run=True)
    checkpoint = store.local_run / "checkpoints" / "epoch_0002.bin"
    record_path = store.local_run / "epochs" / "epoch_0002.json"
    if failure == "missing":
        checkpoint.unlink()
    elif failure == "corrupt":
        checkpoint.write_bytes(b"incomplete-upload")
    elif failure == "split":
        (store.local_run / "split_manifest.json").write_text('{"train": ["different"]}')
    else:
        record = json.loads(record_path.read_bytes())
        record["checkpoint_path" if failure == "path" else "code_commit"] = "../unrelated"
        record_path.write_text(json.dumps(record))
    destination = tmp_path / "review"
    with pytest.raises((ValueError, FileNotFoundError)):
        import_completed_epochs(store.local_run, destination)
    assert not destination.exists()


def test_epoch_import_rejects_source_destination_overlap(tmp_path):
    with pytest.raises(ValueError, match="overlap"):
        import_completed_epochs(tmp_path / "run", tmp_path / "run" / "review")


def test_corrupt_newer_drive_checkpoint_preserves_local_run(tmp_path):
    options = dict(config={"max_epochs": 2}, split_manifest={"train": ["a"]}, code_commit="same")
    local = EpochArtifactStore(tmp_path / "local", "protected", **options)
    drive = EpochArtifactStore(tmp_path / "drive", "protected", **options)
    for store, epochs in ((local, [1]), (drive, [1, 2])):
        for epoch in epochs:
            store.record_epoch(epoch=epoch, max_epochs=2, train_loss=0.4, validation_loss=0.5, validation_metrics={}, learning_rate=0.01, elapsed_seconds=1, checkpoint=f"checkpoint-{epoch}".encode())
    (drive.local_run / "checkpoints" / "epoch_0002.bin").write_bytes(b"partial")
    with pytest.raises(ValueError, match="checksum"):
        EpochArtifactStore(tmp_path / "local", "protected", drive_root=tmp_path / "drive", **options)
    assert local.progress["last_completed_epoch"] == 1
    assert (local.local_run / "checkpoints" / "latest.bin").read_bytes() == b"checkpoint-1"


def test_uncommitted_history_tail_is_not_duplicated(tmp_path):
    store = EpochArtifactStore(tmp_path, "history", config={"max_epochs": 2}, split_manifest={}, code_commit="same")
    options = dict(max_epochs=2, train_loss=0.4, validation_loss=0.5, validation_metrics={}, learning_rate=0.01, elapsed_seconds=1, checkpoint=b"checkpoint")
    store.record_epoch(epoch=1, **options)
    history = store.local_run / "history.jsonl"
    history.write_bytes(history.read_bytes() + b'{"epoch": 2, "incomplete": true}\n')
    store.record_epoch(epoch=2, **options)
    assert [json.loads(line)["epoch"] for line in history.read_text().splitlines()] == [1, 2]

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_pipeline.epoch_artifacts import EpochArtifactStore


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

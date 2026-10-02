"""Durable per-epoch metrics/checkpoint handoff for local and Colab runs.

This module manages artifacts only; it does not train a model. Colab supplies a
mounted Drive path as drive_root. Locally, the same contract can be dry-run with
a temporary directory to verify Drive sync and codebase return behavior.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(content)
    os.replace(temporary, path)


def _atomic_json(path: Path, value: Any) -> None:
    _atomic_bytes(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode("utf-8"))


def get_git_commit(repository: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


class EpochArtifactStore:
    """Write every epoch locally and mirror completed files to a mounted Drive."""

    def __init__(
        self,
        local_root: Path,
        run_id: str,
        *,
        config: dict[str, Any],
        split_manifest: dict[str, Any],
        code_commit: str,
        drive_root: Path | None = None,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", run_id):
            raise ValueError("run_id may contain only letters, digits, dot, underscore, and hyphen")
        self.run_id = run_id
        self.local_run = local_root / run_id
        self.drive_run = drive_root / run_id if drive_root else None
        split_hash = hashlib.sha256(_canonical_json(split_manifest)).hexdigest()
        self.run_config = {
            **config,
            "run_id": run_id,
            "code_commit": code_commit,
            "split_manifest_sha256": split_hash,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        self.split_manifest = split_manifest
        if self.drive_run and self.drive_run.exists():
            if not self.local_run.exists():
                self.local_run.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(self.drive_run, self.local_run)
            else:
                local_progress_path = self.local_run / "progress.json"
                drive_progress_path = self.drive_run / "progress.json"
                local_epoch = json.loads(local_progress_path.read_text(encoding="utf-8")).get("last_completed_epoch", 0) if local_progress_path.exists() else 0
                drive_epoch = json.loads(drive_progress_path.read_text(encoding="utf-8")).get("last_completed_epoch", 0) if drive_progress_path.exists() else 0
                if drive_epoch > local_epoch:
                    shutil.rmtree(self.local_run)
                    shutil.copytree(self.drive_run, self.local_run)
        self.local_run.mkdir(parents=True, exist_ok=True)
        config_path = self.local_run / "run_config.json"
        manifest_path = self.local_run / "split_manifest.json"
        if config_path.exists():
            prior = json.loads(config_path.read_text(encoding="utf-8"))
            config_matches = all(prior.get(key) == value for key, value in config.items())
            if (
                prior.get("run_id") != run_id
                or prior.get("split_manifest_sha256") != split_hash
                or prior.get("code_commit") != code_commit
                or not config_matches
            ):
                raise ValueError("existing run metadata differs; resume with the exact same code commit, config, and split")
            if not (self.local_run / "progress.json").exists() or not (self.local_run / "checkpoints" / "latest.bin").exists():
                raise ValueError("run checkpoint metadata is incomplete; do not resume from a partial run folder")
            self.run_config = prior
        else:
            _atomic_json(config_path, self.run_config)
            _atomic_json(manifest_path, split_manifest)
            _atomic_bytes(self.local_run / "history.jsonl", b"")
            _atomic_json(self.local_run / "progress.json", {"last_completed_epoch": 0, "best_validation_loss": None, "best_epoch": None})
            self._mirror(["run_config.json", "split_manifest.json", "history.jsonl", "progress.json"])

    @property
    def progress(self) -> dict[str, Any]:
        return json.loads((self.local_run / "progress.json").read_text(encoding="utf-8"))

    def record_epoch(
        self,
        *,
        epoch: int,
        max_epochs: int,
        train_loss: float,
        validation_loss: float,
        validation_metrics: dict[str, float],
        learning_rate: float,
        elapsed_seconds: float,
        checkpoint: bytes,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if epoch != self.progress["last_completed_epoch"] + 1:
            raise ValueError("epochs must be recorded sequentially; resume from the saved completed epoch")
        values = [train_loss, validation_loss, learning_rate, elapsed_seconds, *validation_metrics.values()]
        if not all(math.isfinite(float(value)) for value in values):
            raise ValueError("epoch metrics must be finite numeric values")
        previous = self.progress
        is_best = previous["best_validation_loss"] is None or validation_loss < previous["best_validation_loss"]
        record = {
            "run_id": self.run_id,
            "epoch": epoch,
            "max_epochs": max_epochs,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "code_commit": self.run_config["code_commit"],
            "dataset_version": self.run_config.get("dataset_version", "unspecified"),
            "split_manifest_sha256": self.run_config["split_manifest_sha256"],
            "feature_order": self.run_config.get("feature_order", []),
            "train_loss": float(train_loss),
            "validation_loss": float(validation_loss),
            "validation_metrics": validation_metrics,
            "learning_rate": float(learning_rate),
            "elapsed_seconds": float(elapsed_seconds),
            "is_best_validation_checkpoint": is_best,
            "dry_run": dry_run,
        }
        epoch_name = f"epoch_{epoch:04d}"
        checkpoint_relative = f"checkpoints/{epoch_name}.bin"
        checkpoint_path = self.local_run / checkpoint_relative
        _atomic_bytes(checkpoint_path, checkpoint)
        record["checkpoint_path"] = checkpoint_relative
        record["checkpoint_sha256"] = _sha256(checkpoint_path)
        _atomic_json(self.local_run / "epochs" / f"{epoch_name}.json", record)
        with (self.local_run / "history.jsonl").open("ab") as history:
            history.write(_canonical_json(record) + b"\n")
            history.flush()
            os.fsync(history.fileno())
        _atomic_bytes(self.local_run / "checkpoints" / "latest.bin", checkpoint)
        updated = {
            "last_completed_epoch": epoch,
            "best_validation_loss": float(validation_loss) if is_best else previous["best_validation_loss"],
            "best_epoch": epoch if is_best else previous["best_epoch"],
        }
        _atomic_json(self.local_run / "progress.json", updated)
        mirror_files = ["history.jsonl", "progress.json", f"epochs/{epoch_name}.json", checkpoint_relative, "checkpoints/latest.bin"]
        if is_best:
            _atomic_bytes(self.local_run / "checkpoints" / "best_validation_loss.bin", checkpoint)
            mirror_files.append("checkpoints/best_validation_loss.bin")
        self._mirror(mirror_files)
        return record

    def _mirror(self, relative_paths: list[str]) -> list[dict[str, str]]:
        if self.drive_run is None:
            return []
        verified = []
        for relative in relative_paths:
            source = self.local_run / relative
            destination = self.drive_run / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(destination.name + ".tmp")
            shutil.copy2(source, temporary)
            os.replace(temporary, destination)
            source_hash = _sha256(source)
            destination_hash = _sha256(destination)
            if source_hash != destination_hash:
                raise IOError(f"Drive mirror checksum mismatch for {relative}")
            verified.append({"path": relative, "sha256": source_hash})
        return verified

    def sync_review_bundle(self, codebase_staging_root: Path) -> Path:
        """Copy reviewed metadata and best checkpoint back, never promote production weights."""
        source = self.drive_run if self.drive_run and self.drive_run.exists() else self.local_run
        progress = json.loads((source / "progress.json").read_text(encoding="utf-8"))
        if progress["best_epoch"] is None:
            raise ValueError("cannot sync a review bundle before recording at least one epoch")
        bundle = codebase_staging_root / self.run_id
        files = ["run_config.json", "split_manifest.json", "history.jsonl", "progress.json", "checkpoints/best_validation_loss.bin"]
        for relative in files:
            destination = bundle / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, destination)
        best_epoch_record = json.loads((source / "epochs" / f"epoch_{progress['best_epoch']:04d}.json").read_text(encoding="utf-8"))
        _atomic_json(bundle / "final" / "validation_selected_metrics.json", best_epoch_record)
        manifest = {"run_id": self.run_id, "selected_epoch": progress["best_epoch"], "validation_loss": progress["best_validation_loss"], "promotion_status": "REVIEW_REQUIRED_NOT_PROMOTED"}
        _atomic_json(bundle / "final" / "review_manifest.json", manifest)
        return bundle


def smoke_test() -> dict[str, Any]:
    """Prove the VS Code/local -> Drive mirror -> codebase return contract with fake records."""
    with tempfile.TemporaryDirectory(prefix="hybrid-epoch-handoff-") as temporary:
        root = Path(temporary)
        store = EpochArtifactStore(
            root / "colab-runtime",
            "dry-run-handoff-001",
            config={"max_epochs": 3, "feature_order": ["S_bert", "S_graph", "S_growth"], "dry_run": True},
            split_manifest={"train": ["train-a"], "validation": ["validation-a"], "test": ["test-a"]},
            code_commit=get_git_commit(Path(__file__).resolve().parents[1]),
            drive_root=root / "drive" / "MyDrive" / "HybridMatching" / "runs",
        )
        for epoch, loss in enumerate((0.82, 0.61, 0.68), start=1):
            store.record_epoch(
                epoch=epoch,
                max_epochs=3,
                train_loss=loss - 0.05,
                validation_loss=loss,
                validation_metrics={"roc_auc": 0.5 + epoch * 0.05},
                learning_rate=0.01,
                elapsed_seconds=0.001,
                checkpoint=f"SIMULATED-CHECKPOINT-NOT-MODEL-TRAINING-EPOCH-{epoch}".encode(),
                dry_run=True,
            )
        bundle = store.sync_review_bundle(root / "codebase" / "data_pipeline" / "training_review")
        mirror = root / "drive" / "MyDrive" / "HybridMatching" / "runs" / store.run_id
        return {
            "dry_run": True,
            "epochs_recorded": store.progress["last_completed_epoch"],
            "best_epoch": store.progress["best_epoch"],
            "latest_epoch": store.progress["last_completed_epoch"],
            "drive_history_exists": (mirror / "history.jsonl").exists(),
            "drive_latest_checkpoint_exists": (mirror / "checkpoints" / "latest.bin").exists(),
            "review_bundle_exists": (bundle / "final" / "review_manifest.json").exists(),
            "production_artifact_touched": False,
        }


if __name__ == "__main__":
    print(json.dumps(smoke_test(), indent=2))

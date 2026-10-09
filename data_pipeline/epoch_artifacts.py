"""Durable per-epoch metrics/checkpoint handoff for local and Colab runs.

This module manages artifacts only; it does not train a model. Colab supplies a
mounted Drive path as drive_root. Locally, the same contract can be dry-run with
a temporary directory to verify Drive sync and codebase return behavior.
"""
from __future__ import annotations

import hashlib
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
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
        if run_id in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", run_id):
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
        for existing in (self.local_run, self.drive_run):
            if existing is None or not existing.exists():
                continue
            prior = json.loads((existing / "run_config.json").read_text(encoding="utf-8"))
            if any(prior.get(key) != value for key, value in self.run_config.items() if key != "started_at_utc"):
                raise ValueError("existing run metadata differs; resume with the exact same code commit, config, and split")
            stored_split = json.loads((existing / "split_manifest.json").read_text(encoding="utf-8"))
            if hashlib.sha256(_canonical_json(stored_split)).hexdigest() != split_hash:
                raise ValueError("stored split manifest checksum differs")
        if self.drive_run and self.drive_run.exists():
            with tempfile.TemporaryDirectory(prefix="epoch-resume-validation-") as temporary:
                import_completed_epochs(self.drive_run, Path(temporary))
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
            if not (self.local_run / "progress.json").exists() or (self.progress["last_completed_epoch"] > 0 and not (self.local_run / "checkpoints" / "latest.bin").exists()):
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
        if not 1 <= epoch <= max_epochs or max_epochs != self.run_config.get("max_epochs", max_epochs):
            raise ValueError("epoch must be within the configured maximum")
        if not checkpoint:
            raise ValueError("checkpoint must not be empty")
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
        committed_records = [json.loads((self.local_run / "epochs" / f"epoch_{completed:04d}.json").read_bytes()) for completed in range(1, epoch)]
        _atomic_bytes(self.local_run / "history.jsonl", b"".join(_canonical_json(item) + b"\n" for item in [*committed_records, record]))
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
        self._mirror([relative for relative in mirror_files if relative != "progress.json"] + ["progress.json"])
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


def import_completed_epochs(source_run: Path, destination_root: Path) -> list[int]:
    source_run = source_run.resolve()
    destination_root = destination_root.resolve()
    if source_run == destination_root or source_run in destination_root.parents or destination_root in source_run.parents:
        raise ValueError("source and destination must not overlap")
    config_bytes = (source_run / "run_config.json").read_bytes()
    split_bytes = (source_run / "split_manifest.json").read_bytes()
    config = json.loads(config_bytes)
    split = json.loads(split_bytes)
    run_id = config["run_id"]
    if run_id in {".", ".."} or not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", run_id) or source_run.name != run_id:
        raise ValueError("invalid source run identifier")
    if hashlib.sha256(_canonical_json(split)).hexdigest() != config["split_manifest_sha256"]:
        raise ValueError("split manifest checksum differs")
    progress = json.loads((source_run / "progress.json").read_bytes())
    completed = progress["last_completed_epoch"]
    if type(completed) is not int or not 0 <= completed <= config["max_epochs"]:
        raise ValueError("invalid completed epoch count")
    bundles = []
    for epoch in range(1, completed + 1):
        name = f"epoch_{epoch:04d}"
        record_bytes = (source_run / "epochs" / f"{name}.json").read_bytes()
        record = json.loads(record_bytes)
        checkpoint_relative = f"checkpoints/{name}.bin"
        if any((
            record.get("epoch") != epoch,
            record.get("run_id") != run_id,
            record.get("code_commit") != config["code_commit"],
            record.get("split_manifest_sha256") != config["split_manifest_sha256"],
            record.get("max_epochs") != config["max_epochs"],
            record.get("checkpoint_path") != checkpoint_relative,
        )):
            raise ValueError(f"epoch {epoch} metadata differs")
        checkpoint = (source_run / checkpoint_relative).read_bytes()
        if not checkpoint or hashlib.sha256(checkpoint).hexdigest() != record.get("checkpoint_sha256"):
            raise ValueError(f"epoch {epoch} checkpoint checksum differs")
        files = {"run_config.json": config_bytes, "split_manifest.json": split_bytes, "epoch.json": record_bytes, "checkpoint.bin": checkpoint}
        destination = destination_root / run_id / "epochs" / name
        if destination.exists():
            if any(not (destination / filename).is_file() or (destination / filename).read_bytes() != content for filename, content in files.items()):
                raise ValueError(f"existing local epoch {epoch} differs; refusing overwrite")
        else:
            bundles.append((epoch, destination, files))
    imported = []
    for epoch, destination, files in bundles:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".incoming-", dir=destination.parent))
        try:
            for filename, content in files.items():
                _atomic_bytes(temporary / filename, content)
                if (temporary / filename).read_bytes() != content:
                    raise IOError("local checkpoint copy verification failed")
            temporary.rename(destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        imported.append(epoch)
    return imported


def sync_local_run(source_run: Path, destinations: list[Path]) -> dict:
    if len(set(path.resolve() for path in destinations)) < 2:
        raise ValueError("two distinct local destinations are required")
    copied = {str(destination): import_completed_epochs(source_run, destination) for destination in destinations}
    config = json.loads((source_run / "run_config.json").read_bytes())
    progress = json.loads((source_run / "progress.json").read_bytes())
    completed = progress["last_completed_epoch"]
    for epoch in range(1, completed + 1):
        name = f"epoch_{epoch:04d}"
        record = json.loads((source_run / "epochs" / f"{name}.json").read_bytes())
        for destination in destinations:
            copied_checkpoint = destination / config["run_id"] / "epochs" / name / "checkpoint.bin"
            if _sha256(copied_checkpoint) != record["checkpoint_sha256"]:
                raise ValueError("local acknowledgement checksum differs")
        acknowledgement = {"run_id": config["run_id"], "epoch": epoch, "code_commit": config["code_commit"], "checkpoint_sha256": record["checkpoint_sha256"], "verified_destinations": [str(path.resolve()) for path in destinations]}
        acknowledgement_path = source_run / "local_acknowledgements" / f"{name}.json"
        if not acknowledgement_path.exists() or json.loads(acknowledgement_path.read_bytes()) != acknowledgement:
            _atomic_json(acknowledgement_path, acknowledgement)
    final_copied = False
    seal = source_run / "final" / "manifest.json"
    if seal.exists():
        manifest_bytes = seal.read_bytes()
        manifest = json.loads(manifest_bytes)
        if completed != config["max_epochs"] or manifest.get("run_id") != config["run_id"] or set(manifest.get("files", {})) != {"artifact_candidate.json", "metrics.json"}:
            raise ValueError("invalid final bundle manifest")
        files = {name: (source_run / "final" / name).read_bytes() for name in manifest["files"]}
        if any(hashlib.sha256(content).hexdigest() != manifest["files"][name] for name, content in files.items()):
            raise ValueError("final bundle checksum differs")
        for destination in destinations:
            final_root = destination / config["run_id"] / "final"
            for name, content in {**files, "manifest.json": manifest_bytes}.items():
                target = final_root / name
                if target.exists() and target.read_bytes() != content:
                    raise ValueError("existing final bundle differs; refusing overwrite")
                _atomic_bytes(target, content)
                if target.read_bytes() != content:
                    raise IOError("final local copy verification failed")
        final_copied = True
    return {"epoch": completed, "copied": copied, "final_copied": final_copied, "production_artifact_touched": False}


def review_returned_run(run: Path, expected_commit: str) -> dict:
    final = run / "final"
    if not (final / "manifest.json").is_file():
        raise ValueError("run is not ready: verified final manifest is missing")
    seal = json.loads((final / "manifest.json").read_bytes())
    if seal.get("run_id") != run.name or set(seal.get("files", {})) != {"artifact_candidate.json", "metrics.json"}:
        raise ValueError("invalid final manifest")
    for name, expected_hash in seal["files"].items():
        if _sha256(final / name) != expected_hash:
            raise ValueError(f"final checksum differs: {name}")
    artifact = json.loads((final / "artifact_candidate.json").read_bytes())
    metrics = json.loads((final / "metrics.json").read_bytes())
    first = run / "epochs" / "epoch_0001"
    config_bytes = (first / "run_config.json").read_bytes()
    split_bytes = (first / "split_manifest.json").read_bytes()
    config, split = json.loads(config_bytes), json.loads(split_bytes)
    count = config["max_epochs"]
    if type(count) is not int or not 1 <= count <= 1000 or config["run_id"] != run.name or config["code_commit"] != expected_commit:
        raise ValueError("run identity or epoch count differs")
    split_hash = hashlib.sha256(_canonical_json(split)).hexdigest()
    if split_hash != config["split_manifest_sha256"]:
        raise ValueError("split manifest checksum differs")
    expected_names = {f"epoch_{epoch:04d}" for epoch in range(1, count + 1)}
    if {path.name for path in (run / "epochs").glob("epoch_*") if path.is_dir()} != expected_names:
        raise ValueError("returned epochs do not match the planned epoch count")
    records = []
    for epoch in range(1, count + 1):
        bundle = run / "epochs" / f"epoch_{epoch:04d}"
        if (bundle / "run_config.json").read_bytes() != config_bytes or (bundle / "split_manifest.json").read_bytes() != split_bytes:
            raise ValueError("epoch provenance differs")
        record = json.loads((bundle / "epoch.json").read_bytes())
        if record["epoch"] != epoch or record["run_id"] != run.name or record["code_commit"] != expected_commit or record["max_epochs"] != count or record["split_manifest_sha256"] != split_hash or record.get("dry_run"):
            raise ValueError("epoch identity differs or is a dry-run fixture")
        if _sha256(bundle / "checkpoint.bin") != record["checkpoint_sha256"]:
            raise ValueError(f"epoch {epoch} checkpoint checksum differs")
        if any(type(record[key]) not in (int, float) or not math.isfinite(record[key]) or record[key] < 0 for key in ("train_loss", "validation_loss")):
            raise ValueError("invalid epoch loss")
        records.append(record)
    best = min(records, key=lambda record: record["validation_loss"])
    if metrics.get("status") != "complete" or metrics.get("max_epochs") != count or metrics.get("selected_epoch") != best["epoch"]:
        raise ValueError("final checkpoint was not selected by best validation loss")
    checkpoint = json.loads((run / "epochs" / f"epoch_{best['epoch']:04d}" / "checkpoint.bin").read_bytes())
    order = ["S_bert", "S_graph", "S_growth"]
    if artifact.get("feature_order") != order or config.get("feature_order") != order or artifact.get("feature_contract") != config.get("feature_contract") or metrics.get("feature_contract") != config.get("feature_contract"):
        raise ValueError("feature contract differs")
    if artifact.get("model_version") != run.name or artifact.get("promotion_status") != "REVIEW_REQUIRED_NOT_PROMOTED" or artifact.get("embedding_model") != "sentence-transformers/all-MiniLM-L6-v2":
        raise ValueError("candidate artifact identity differs")
    if artifact.get("encoder_revision") != split.get("encoder_revision") or checkpoint.get("epoch") != best["epoch"] or checkpoint.get("data_sha256") != split["feature_data_sha256"]:
        raise ValueError("selected checkpoint data identity differs")
    vectors = [artifact["scaler_mean"], artifact["scaler_scale"], artifact["logistic_regression"]["coefficients"]]
    if any(len(vector) != 3 or any(type(value) not in (int, float) or not math.isfinite(value) for value in vector) for vector in vectors) or any(value <= 0 for value in artifact["scaler_scale"]):
        raise ValueError("invalid artifact vectors")
    if artifact["scaler_mean"] != checkpoint["scaler_mean"] or artifact["scaler_scale"] != checkpoint["scaler_scale"] or artifact["logistic_regression"]["coefficients"] != checkpoint["coefficients"][0] or artifact["logistic_regression"]["intercept"] != checkpoint["intercept"][0]:
        raise ValueError("artifact parameters differ from selected checkpoint")
    threshold = artifact["decision_threshold"]
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= 1 or not math.isfinite(artifact["logistic_regression"]["intercept"]):
        raise ValueError("invalid artifact threshold or intercept")
    comparisons = {}
    for name in ("validation", "warm_test", "cold_test"):
        results = metrics["results"][name]
        for scorer in ("hybrid", "fixed_weights", "semantic_only"):
            result = results[scorer]
            if result["count"] != len(split["pair_indices"][name]):
                raise ValueError("evaluation count differs from split")
            for metric in ("precision", "recall", "f1", "threshold", "roc_auc", "log_loss"):
                value = result[metric]
                if metric == "roc_auc" and value is None:
                    continue
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (metric != "log_loss" and value > 1):
                    raise ValueError("invalid reported evaluation metric")
        if results["hybrid"]["threshold"] != threshold:
            raise ValueError("reported threshold differs from artifact")
        comparisons[name] = {"hybrid": results["hybrid"], "f1_gain_over_fixed": results["hybrid"]["f1"] - results["fixed_weights"]["f1"], "f1_gain_over_semantic": results["hybrid"]["f1"] - results["semantic_only"]["f1"]}
    return {"status": "INTEGRITY_VERIFIED_REVIEW_REQUIRED", "run_id": run.name, "code_commit": expected_commit, "epochs_verified": count, "selected_epoch": best["epoch"], "best_validation_loss": best["validation_loss"], "selected_train_validation_gap": best["validation_loss"] - best["train_loss"], "recorded_comparisons": comparisons, "final_files_sha256": seal["files"], "warning": "Integrity checks do not establish real-world quality or authorize promotion. Metrics are reported values, not a repeated test evaluation.", "production_artifact_touched": False}


def finalize_returned_run(source_run: Path, destinations: list[Path], expected_commit: str) -> dict:
    runs = [destination / source_run.name for destination in destinations]
    if len({run.resolve() for run in runs}) < 2:
        raise ValueError("final review requires two distinct destinations")
    reviews = [review_returned_run(run, expected_commit) for run in runs]
    if any(review != reviews[0] for review in reviews[1:]):
        raise ValueError("returned run reviews differ")
    result = {"status": "COMPLETE_REVIEW_REQUIRED", "destinations_verified": len(runs), "review": reviews[0]}
    for run in runs:
        _atomic_json(run / "review_report.json", result)
    return result


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
    parser = argparse.ArgumentParser(description="Checkpoint handoff without production model promotion")
    parser.add_argument("--sync-run", type=Path)
    parser.add_argument("--destination", type=Path, action="append")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--review-on-completion", action="store_true")
    parser.add_argument("--review-run", type=Path, action="append")
    parser.add_argument("--expected-commit")
    arguments = parser.parse_args()
    if arguments.review_on_completion and (not arguments.watch or not arguments.expected_commit):
        parser.error("--review-on-completion requires --watch and --expected-commit")
    if arguments.review_run:
        if arguments.sync_run or arguments.destination or arguments.watch or not arguments.expected_commit:
            parser.error("--review-run requires --expected-commit and cannot be combined with sync options")
        try:
            reviews = [review_returned_run(path, arguments.expected_commit) for path in arguments.review_run]
            if any(review["run_id"] != reviews[0]["run_id"] or review["final_files_sha256"] != reviews[0]["final_files_sha256"] for review in reviews[1:]):
                raise ValueError("returned destinations differ")
        except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
            print(json.dumps({"status": "NOT_READY_OR_INVALID", "reason": str(error)}))
            sys.exit(1)
        print(json.dumps({"destinations_verified": len(reviews), "review": reviews[0]}, indent=2))
        sys.exit(0)
    if bool(arguments.sync_run) != bool(arguments.destination):
        parser.error("--sync-run and --destination must be supplied together")
    if arguments.watch:
        if not arguments.sync_run or not arguments.destination or len(arguments.destination) < 2:
            parser.error("--watch needs --sync-run and two --destination paths")
        previous_report = None
        while True:
            try:
                status = sync_local_run(arguments.sync_run, arguments.destination)
                report = {"epoch": status["epoch"], "final_copied": status["final_copied"], "production_artifact_touched": False}
            except (OSError, ValueError, KeyError) as error:
                report = {"waiting_for_complete_sync": str(error)}
            if report != previous_report:
                print(json.dumps(report), flush=True)
                previous_report = report
            if report.get("final_copied"):
                if arguments.review_on_completion:
                    try:
                        result = finalize_returned_run(arguments.sync_run, arguments.destination, arguments.expected_commit)
                    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
                        print(json.dumps({"status": "REVIEW_FAILED", "reason": str(error)}), flush=True)
                        sys.exit(1)
                    print(json.dumps(result), flush=True)
                break
            threading.Event().wait(2)
    elif arguments.sync_run:
        for destination in arguments.destination:
            imported = import_completed_epochs(arguments.sync_run, destination)
            print(json.dumps({"destination": str(destination), "imported_epochs": imported, "production_artifact_touched": False}))
    else:
        print(json.dumps(smoke_test(), indent=2))

"""Fixed-epoch training of the frozen-encoder score combiner; no promotion."""
from __future__ import annotations

import hashlib
import json
import random
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from time import monotonic, perf_counter
from typing import Callable

import numpy as np
import sklearn
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import f1_score, log_loss, precision_score, recall_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

from backend.app.core.match_features import FEATURE_CONTRACT, FEATURE_ORDER, growth_score, skill_overlap
from backend.app.core.text_preprocessing import anonymize_resume_text
from data_pipeline.epoch_artifacts import EpochArtifactStore, _atomic_json, _canonical_json
from data_pipeline.generate_synthetic_data import generate_candidate, generate_job

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass(frozen=True)
class TrainingConfig:
    max_epochs: int = 100
    seed: int = 42
    learning_rate: float = 0.01
    alpha: float = 0.0003
    batch_size: int = 256

    def __post_init__(self):
        if not 1 <= self.max_epochs <= 1000 or not 1 <= self.batch_size <= 100000:
            raise ValueError("invalid epoch count or batch size")
        if not np.isfinite(self.learning_rate) or self.learning_rate <= 0 or not np.isfinite(self.alpha) or self.alpha < 0:
            raise ValueError("invalid learning rate or regularization")


def isolated_partitions(candidates: list[dict], jobs: list[dict], seed: int) -> dict:
    rng = np.random.default_rng(seed)
    candidate_groups = {name: [] for name in ("train", "validation", "warm_test", "cold_test")}
    job_groups = {"warm": [], "cold": []}
    for role in sorted({item["target_role"] for item in candidates}):
        identifiers = sorted(item["candidate_id"] for item in candidates if item["target_role"] == role)
        if len(identifiers) < 10:
            raise ValueError("each role needs at least ten candidates for isolated splits")
        shuffled = rng.permutation(identifiers)
        boundaries = [int(len(shuffled) * fraction) for fraction in (0.6, 0.8, 0.9)]
        for name, group in zip(candidate_groups, np.split(shuffled, boundaries)):
            candidate_groups[name].extend(group.tolist())
    for role in sorted({item["title"] for item in jobs}):
        identifiers = sorted(item["job_id"] for item in jobs if item["title"] == role)
        if len(identifiers) < 5:
            raise ValueError("each role needs at least five jobs for a cold-job holdout")
        shuffled = rng.permutation(identifiers).tolist()
        count = max(1, int(len(shuffled) * 0.2))
        job_groups["cold"].extend(shuffled[:count])
        job_groups["warm"].extend(shuffled[count:])
    if sum(map(len, candidate_groups.values())) != len({item["candidate_id"] for item in candidates}) or len({item["job_id"] for item in jobs}) != len(jobs):
        raise ValueError("duplicate dataset identifiers")
    return {"candidate_groups": candidate_groups, "job_groups": job_groups, "seed": seed, "protocol": "role-stratified-disjoint-candidates-60-20-10-10-cold-jobs-20-v1"}


def prepare_synthetic_data(cache_root: Path, *, code_commit: str, seed: int = 42, candidate_count: int = 800, job_count: int = 100, encode: Callable | None = None) -> tuple:
    specification = {"seed": seed, "candidates": candidate_count, "jobs": job_count, "code_commit": code_commit, "feature_contract": FEATURE_CONTRACT, "test_encoder": encode is not None, "label_source": "synthetic-fixed-centres-latent-bernoulli-v2"}
    cache_key = hashlib.sha256(_canonical_json(specification)).hexdigest()
    cache = cache_root / cache_key
    manifest_path = cache / "manifest.json"
    data_path = cache / "features.npz"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_bytes())
        if manifest["specification"] != specification or hashlib.sha256(data_path.read_bytes()).hexdigest() != manifest["array_sha256"]:
            raise ValueError("cached training data differs")
        with np.load(data_path, allow_pickle=False) as saved:
            return saved["features"], saved["labels"], {name: saved[name] for name in manifest["pair_counts"]}, manifest
    rng = random.Random(seed)
    candidates = [generate_candidate(rng) for _ in range(candidate_count)]
    jobs = [generate_job(rng) for _ in range(job_count)]
    split = isolated_partitions(candidates, jobs, seed)
    raw_hash = hashlib.sha256(_canonical_json({"candidates": candidates, "jobs": jobs})).hexdigest()
    texts = [anonymize_resume_text(item["resume_text"]) for item in candidates] + [item["description"] for item in jobs]
    revision = "test-only"
    if encode is None:
        from huggingface_hub import model_info
        from sentence_transformers import SentenceTransformer
        revision = model_info(EMBEDDING_MODEL).sha
        encoder = SentenceTransformer(EMBEDDING_MODEL, revision=revision)
        embeddings = encoder.encode(texts, normalize_embeddings=True, batch_size=64, show_progress_bar=True)
    else:
        embeddings = encode(texts)
    embeddings = np.asarray(embeddings)
    if embeddings.ndim != 2 or len(embeddings) != len(texts) or not np.isfinite(embeddings).all() or not np.allclose(np.linalg.norm(embeddings, axis=1), 1, atol=1e-4):
        raise ValueError("encoder must return finite normalized embeddings")
    candidate_lookup = {item["candidate_id"]: index for index, item in enumerate(candidates)}
    job_lookup = {item["job_id"]: index for index, item in enumerate(jobs)}
    label_rng = np.random.default_rng(seed)
    rows, labels, identities = [], [], []
    partitions = {name: [] for name in split["candidate_groups"]}
    for group, identifiers in split["candidate_groups"].items():
        pool = set(split["job_groups"]["cold" if group == "cold_test" else "warm"])
        for identifier in identifiers:
            candidate_index = candidate_lookup[identifier]
            candidate = candidates[candidate_index]
            matching_jobs = sorted(item["job_id"] for item in jobs if item["job_id"] in pool and item["title"] == candidate["target_role"])
            chosen = rng.sample(matching_jobs, min(5, len(matching_jobs)))
            for job_id in chosen:
                job_index = job_lookup[job_id]
                job = jobs[job_index]
                semantic = float(np.clip(embeddings[candidate_index] @ embeddings[len(candidates) + job_index], 0, 1))
                overlap = skill_overlap(candidate["skills"], job["required_skills"])
                growth = growth_score(candidate["years_experience"], job["required_experience_years"], len(candidate["certifications"]))
                experience = min(candidate["years_experience"] / max(job["required_experience_years"], 1), 1.5) / 1.5
                domain = float(candidate["specialisation"] == job["specialisation"])
                hidden = candidate["latent_competence"] - job["latent_quality_bar"]
                logit = 6 * (overlap - 0.75) + 3.8 * (experience - 0.5) + 3.6 * (domain - 1 / 3) + 1.6 * hidden + 0.4 * (candidate["latent_adaptability"] - 0.5) + label_rng.normal(0, 0.35)
                probability = 1 / (1 + np.exp(-logit))
                partitions[group].append(len(rows))
                identities.append({"candidate_id": identifier, "job_id": job_id, "split": group})
                rows.append([semantic, overlap, growth])
                labels.append(int(label_rng.random() < probability))
    features = np.asarray(rows, dtype=float)
    target = np.asarray(labels, dtype=np.int64)
    indices = {name: np.asarray(values, dtype=np.int64) for name, values in partitions.items()}
    cache.mkdir(parents=True, exist_ok=True)
    temporary = cache / "features.tmp.npz"
    np.savez_compressed(temporary, features=features, labels=target, **indices)
    temporary.replace(data_path)
    manifest = {**split, "specification": specification, "dataset_version": raw_hash, "embedding_model": EMBEDDING_MODEL, "encoder_revision": revision, "feature_order": FEATURE_ORDER, "pair_identities": identities, "pair_counts": {name: len(values) for name, values in indices.items()}, "array_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(), "warning": "No real CVs or hiring outcomes; labels use fixed centres, not test-set statistics."}
    _atomic_json(cache / "synthetic_snapshot.json", {"candidates": candidates, "jobs": jobs})
    _atomic_json(manifest_path, manifest)
    return features, target, indices, manifest


def classification_metrics(labels: np.ndarray, probabilities: np.ndarray, threshold: float = 0.5) -> dict:
    predictions = probabilities >= threshold
    return {
        "log_loss": float(log_loss(labels, probabilities, labels=[0, 1])),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(labels, probabilities)) if len(np.unique(labels)) == 2 else None,
        "threshold": float(threshold),
        "count": len(labels),
    }


def _classifier(config: TrainingConfig) -> SGDClassifier:
    return SGDClassifier(loss="log_loss", learning_rate="constant", eta0=config.learning_rate, alpha=config.alpha, random_state=config.seed, shuffle=False, early_stopping=False, average=False)


def _checkpoint(model: SGDClassifier, scaler: StandardScaler, epoch: int, config: TrainingConfig, data_hash: str) -> bytes:
    return _canonical_json({
        "format": "sgd-logistic-numeric-v1", "epoch": epoch, "config": asdict(config), "data_sha256": data_hash,
        "sklearn_version": sklearn.__version__, "numpy_version": np.__version__,
        "coefficients": model.coef_.tolist(), "intercept": model.intercept_.tolist(),
        "classes": model.classes_.tolist(), "t": float(model.t_), "n_iter": int(model.n_iter_),
        "scaler_mean": scaler.mean_.tolist(), "scaler_scale": scaler.scale_.tolist(),
        "shuffle_state": {"scheme": "SeedSequence(seed, epoch)", "seed": config.seed, "next_epoch": epoch + 1},
    })


def _restore(content: bytes, config: TrainingConfig, scaler: StandardScaler, expected_epoch: int, data_hash: str) -> SGDClassifier:
    state = json.loads(content)
    if state.get("format") != "sgd-logistic-numeric-v1" or state.get("config") != asdict(config) or state.get("epoch") != expected_epoch or state.get("data_sha256") != data_hash:
        raise ValueError("checkpoint identity differs")
    if state["sklearn_version"] != sklearn.__version__ or state["numpy_version"] != np.__version__:
        raise ValueError("checkpoint package versions differ")
    if state["scaler_mean"] != scaler.mean_.tolist() or state["scaler_scale"] != scaler.scale_.tolist():
        raise ValueError("checkpoint train-only scaler differs")
    model = _classifier(config)
    model.coef_ = np.asarray(state["coefficients"], dtype=float)
    model.intercept_ = np.asarray(state["intercept"], dtype=float)
    model.classes_ = np.asarray(state["classes"], dtype=int)
    model.t_ = float(state["t"])
    model.n_iter_ = int(state["n_iter"])
    model.n_features_in_ = len(FEATURE_ORDER)
    if model.coef_.shape != (1, 3) or model.intercept_.shape != (1,) or model.classes_.tolist() != [0, 1] or not np.isfinite(model.coef_).all() or not np.isfinite(model.intercept_).all() or not np.isfinite(model.t_) or model.t_ < 1:
        raise ValueError("invalid numeric checkpoint")
    return model


def wait_for_local_epoch(drive_run: Path, record: dict, timeout: float = 300) -> None:
    path = drive_run / "local_acknowledgements" / f"epoch_{record['epoch']:04d}.json"
    deadline = monotonic() + timeout
    while True:
        try:
            acknowledgement = json.loads(path.read_bytes())
            if all(acknowledgement.get(key) == record[key] for key in ("run_id", "epoch", "code_commit", "checkpoint_sha256")) and len(set(acknowledgement.get("verified_destinations", []))) >= 2:
                return
        except (OSError, ValueError, TypeError):
            pass
        if monotonic() >= deadline:
            raise TimeoutError(f"Epoch {record['epoch']} is saved to Drive but local return is unconfirmed. Resume after fixing sync.")
        threading.Event().wait(min(2, max(0, deadline - monotonic())))


def train_epochs(features: np.ndarray, labels: np.ndarray, partitions: dict[str, np.ndarray], manifest: dict, *, config: TrainingConfig, local_root: Path, run_id: str, code_commit: str, drive_root: Path | None = None, pause_after: int | None = None, after_epoch: Callable[[dict], None] | None = None) -> dict:
    features = np.asarray(features, dtype=float)
    labels = np.asarray(labels)
    if features.shape != (len(labels), 3) or not np.isfinite(features).all() or np.any((features < 0) | (features > 1)) or not np.isin(labels, [0, 1]).all():
        raise ValueError("invalid feature matrix or labels")
    all_indices = np.concatenate(list(partitions.values()))
    if len(all_indices) != len(labels) or len(np.unique(all_indices)) != len(labels) or set(all_indices.tolist()) != set(range(len(labels))):
        raise ValueError("partitions must cover each pair exactly once")
    for name in ("train", "validation", "warm_test", "cold_test"):
        if not len(partitions[name]):
            raise ValueError("all four partitions must contain pairs")
    train_indices, validation_indices = partitions["train"], partitions["validation"]
    if len(np.unique(labels[train_indices])) != 2 or len(np.unique(labels[validation_indices])) != 2:
        raise ValueError("training and validation must contain both classes")
    data_hash = hashlib.sha256(features.tobytes() + labels.astype(np.int64).tobytes()).hexdigest()
    split_manifest = {**manifest, "pair_indices": {name: indices.tolist() for name, indices in partitions.items()}, "feature_data_sha256": data_hash}
    run_config = {**asdict(config), "feature_order": FEATURE_ORDER, "feature_contract": FEATURE_CONTRACT, "dataset_version": manifest.get("dataset_version", data_hash), "sklearn_version": sklearn.__version__, "numpy_version": np.__version__}
    store = EpochArtifactStore(local_root, run_id, config=run_config, split_manifest=split_manifest, code_commit=code_commit, drive_root=drive_root)
    scaler = StandardScaler().fit(features[train_indices])
    train_features = scaler.transform(features)
    model = _classifier(config)
    completed = store.progress["last_completed_epoch"]
    if completed:
        record = json.loads((store.local_run / "epochs" / f"epoch_{completed:04d}.json").read_bytes())
        checkpoint = (store.local_run / "checkpoints" / f"epoch_{completed:04d}.bin").read_bytes()
        if hashlib.sha256(checkpoint).hexdigest() != record["checkpoint_sha256"]:
            raise ValueError("resume checkpoint checksum differs")
        model = _restore(checkpoint, config, scaler, completed, data_hash)
        if after_epoch:
            after_epoch(record)
    endpoint = min(pause_after, config.max_epochs) if pause_after is not None else config.max_epochs
    for epoch in range(completed + 1, endpoint + 1):
        started = perf_counter()
        order = np.random.default_rng(np.random.SeedSequence([config.seed, epoch])).permutation(train_indices)
        for start in range(0, len(order), config.batch_size):
            batch = order[start:start + config.batch_size]
            model.partial_fit(train_features[batch], labels[batch], classes=np.array([0, 1]))
        training = classification_metrics(labels[train_indices], model.predict_proba(train_features[train_indices])[:, 1])
        validation = classification_metrics(labels[validation_indices], model.predict_proba(train_features[validation_indices])[:, 1])
        record = store.record_epoch(epoch=epoch, max_epochs=config.max_epochs, train_loss=training["log_loss"], validation_loss=validation["log_loss"], validation_metrics=validation, learning_rate=config.learning_rate, elapsed_seconds=perf_counter() - started, checkpoint=_checkpoint(model, scaler, epoch, config, data_hash))
        if after_epoch:
            after_epoch(record)
        print(json.dumps({"epoch": epoch, "train_loss": training["log_loss"], "validation_loss": validation["log_loss"], "best_epoch": store.progress["best_epoch"]}), flush=True)
    if store.progress["last_completed_epoch"] < config.max_epochs:
        return {"status": "paused", "epoch": store.progress["last_completed_epoch"]}
    final_path = store.local_run / "final" / "metrics.json"
    if final_path.exists():
        final_manifest = {"run_id": run_id, "files": {name: hashlib.sha256((store.local_run / "final" / name).read_bytes()).hexdigest() for name in ("artifact_candidate.json", "metrics.json")}}
        _atomic_json(store.local_run / "final" / "manifest.json", final_manifest)
        store._mirror(["final/artifact_candidate.json", "final/metrics.json", "final/manifest.json"])
        return json.loads(final_path.read_bytes())
    best_epoch = store.progress["best_epoch"]
    best_record = json.loads((store.local_run / "epochs" / f"epoch_{best_epoch:04d}.json").read_bytes())
    best_bytes = (store.local_run / "checkpoints" / f"epoch_{best_epoch:04d}.bin").read_bytes()
    if hashlib.sha256(best_bytes).hexdigest() != best_record["checkpoint_sha256"]:
        raise ValueError("selected checkpoint checksum differs")
    best_model = _restore(best_bytes, config, scaler, best_epoch, data_hash)
    probabilities = best_model.predict_proba(train_features)[:, 1]
    baseline_scores = {"hybrid": probabilities, "fixed_weights": features @ np.array([0.45, 0.40, 0.15]), "semantic_only": features[:, 0]}
    thresholds = {name: float(max(np.linspace(0.05, 0.95, 91), key=lambda threshold: f1_score(labels[validation_indices], values[validation_indices] >= threshold, zero_division=0))) for name, values in baseline_scores.items()}
    metrics = {"status": "complete", "max_epochs": config.max_epochs, "selected_epoch": best_epoch, "feature_contract": FEATURE_CONTRACT, "label_warning": "Synthetic labels, not independent hiring outcomes; head metrics precede hard eligibility filtering.", "results": {split: {name: classification_metrics(labels[indices], values[indices], thresholds[name]) for name, values in baseline_scores.items()} for split, indices in partitions.items() if split != "train"}}
    artifact = {"model_version": run_id, "embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "feature_order": FEATURE_ORDER, "feature_contract": FEATURE_CONTRACT, "scaler_mean": scaler.mean_.tolist(), "scaler_scale": scaler.scale_.tolist(), "logistic_regression": {"coefficients": best_model.coef_[0].tolist(), "intercept": float(best_model.intercept_[0])}, "decision_threshold": thresholds["hybrid"], "promotion_status": "REVIEW_REQUIRED_NOT_PROMOTED"}
    artifact["encoder_revision"] = manifest.get("encoder_revision")
    _atomic_json(store.local_run / "final" / "artifact_candidate.json", artifact)
    _atomic_json(final_path, metrics)
    final_manifest = {"run_id": run_id, "files": {name: hashlib.sha256((store.local_run / "final" / name).read_bytes()).hexdigest() for name in ("artifact_candidate.json", "metrics.json")}}
    _atomic_json(store.local_run / "final" / "manifest.json", final_manifest)
    store._mirror(["final/artifact_candidate.json", "final/metrics.json", "final/manifest.json"])
    return metrics
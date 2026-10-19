from __future__ import annotations

import copy
import json
import logging
import re
import threading
from math import exp, isfinite
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from app.core.text_preprocessing import anonymize_resume_text

ARTIFACT_PATH = Path(__file__).resolve().parents[3] / "data_pipeline" / "artifacts" / "hybrid_match_weights.json"
_model: SentenceTransformer | None = None
_model_identity: tuple[str, str | None] | None = None
_model_lock = threading.Lock()
_artifact_cache: tuple[tuple[str, int, int], dict[str, object]] | None = None
logger = logging.getLogger(__name__)


def _artifact() -> dict[str, object]:
    # Scoring calls this once per candidate; re-read and re-validate only when the file itself changes.
    global _artifact_cache
    stat = ARTIFACT_PATH.stat()
    key = (str(ARTIFACT_PATH), stat.st_mtime_ns, stat.st_size)
    if _artifact_cache is None or _artifact_cache[0] != key:
        _artifact_cache = (key, _load_artifact())
    return copy.deepcopy(_artifact_cache[1])


def _load_artifact() -> dict[str, object]:
    artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
    if artifact.get("feature_order") != ["S_bert", "S_graph", "S_growth"]:
        raise ValueError("Unsupported model feature order")
    if artifact.get("embedding_model") != "sentence-transformers/all-MiniLM-L6-v2":
        raise ValueError("Unsupported embedding model")
    revision = artifact.get("encoder_revision")
    if revision is not None and (not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision)):
        raise ValueError("Invalid encoder revision")
    groups = [artifact["scaler_mean"], artifact["scaler_scale"], artifact["logistic_regression"]["coefficients"]]
    if any(len(group) != 3 or any(not isinstance(value, (int, float)) or not isfinite(value) for value in group) for group in groups):
        raise ValueError("Invalid model vector dimensions or numeric values")
    if any(value <= 0 for value in artifact["scaler_scale"]) or not isfinite(artifact["logistic_regression"]["intercept"]) or not 0 <= artifact["decision_threshold"] <= 1:
        raise ValueError("Invalid model scale, intercept or threshold")
    return artifact


def _get_model() -> SentenceTransformer:
    global _model, _model_identity
    artifact = _artifact()
    identity = (artifact["embedding_model"], artifact.get("encoder_revision"))
    if _model is None or _model_identity != identity:
        with _model_lock:
            if _model is None or _model_identity != identity:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(identity[0], revision=identity[1])
                _model_identity = identity
    return _model


def model_state() -> str:
    return "ready" if _model is not None else "loading" if _model_lock.locked() else "not_loaded"


def preload_model() -> None:
    """Load the pinned encoder ahead of the first request; the cold load can take minutes."""
    try:
        _get_model().encode(["warm-up"], show_progress_bar=False)
    except Exception:  # A failed preload must not stop the API; the first request retries the load.
        logger.exception("Matching model preload failed")


def semantic_similarity(candidate_text: str, job_text: str) -> float:
    return semantic_similarities([candidate_text], job_text)[0]


def semantic_similarities(candidate_texts: list[str], job_text: str, batch_size: int = 32) -> list[float]:
    if not candidate_texts:
        return []
    texts = [anonymize_resume_text(text) for text in candidate_texts] + [job_text]
    embeddings = _get_model().encode(texts, normalize_embeddings=True, batch_size=batch_size, show_progress_bar=False)
    job_embedding = embeddings[-1]
    return [float(max(0.0, min(1.0, embedding @ job_embedding))) for embedding in embeddings[:-1]]


def job_similarities(candidate_text: str, job_texts: list[str], batch_size: int = 32) -> list[float]:
    """Score one candidate against many jobs with a single encode call (candidate recommendations)."""
    if not job_texts:
        return []
    embeddings = _get_model().encode([anonymize_resume_text(candidate_text), *job_texts], normalize_embeddings=True, batch_size=batch_size, show_progress_bar=False)
    candidate_embedding = embeddings[0]
    return [float(max(0.0, min(1.0, embedding @ candidate_embedding))) for embedding in embeddings[1:]]


def calibrated_score(semantic: float, graph: float, growth: float) -> tuple[float, bool]:
    artifact = _artifact()
    means = artifact["scaler_mean"]
    scales = artifact["scaler_scale"]
    model = artifact["logistic_regression"]
    features = [semantic, graph, growth]
    if any(not isfinite(value) or not 0 <= value <= 1 for value in features):
        raise ValueError("Scoring inputs must be finite values between zero and one")
    standardised = [(value - means[index]) / scales[index] for index, value in enumerate(features)]
    logit = model["intercept"] + sum(coefficient * value for coefficient, value in zip(model["coefficients"], standardised))
    probability = 1 / (1 + exp(-logit)) if logit >= 0 else exp(logit) / (1 + exp(logit))
    return round(probability, 4), probability >= artifact["decision_threshold"]
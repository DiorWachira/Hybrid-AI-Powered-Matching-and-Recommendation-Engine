from __future__ import annotations

import json
import threading
from math import exp
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from app.core.text_preprocessing import anonymize_resume_text

ARTIFACT_PATH = Path(__file__).resolve().parents[3] / "data_pipeline" / "artifacts" / "hybrid_match_weights.json"
_model: SentenceTransformer | None = None
_model_lock = threading.Lock()


def _artifact() -> dict[str, object]:
    return json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model


def semantic_similarity(candidate_text: str, job_text: str) -> float:
    candidate_text = anonymize_resume_text(candidate_text)
    embeddings = _get_model().encode([candidate_text, job_text], normalize_embeddings=True)
    return float(max(0.0, min(1.0, embeddings[0] @ embeddings[1])))


def calibrated_score(semantic: float, graph: float, growth: float) -> tuple[float, bool]:
    artifact = _artifact()
    means = artifact["scaler_mean"]
    scales = artifact["scaler_scale"]
    model = artifact["logistic_regression"]
    features = [semantic, graph, growth]
    standardised = [(value - means[index]) / scales[index] for index, value in enumerate(features)]
    logit = model["intercept"] + sum(coefficient * value for coefficient, value in zip(model["coefficients"], standardised))
    probability = 1 / (1 + exp(-logit))
    return round(probability, 4), probability >= artifact["decision_threshold"]
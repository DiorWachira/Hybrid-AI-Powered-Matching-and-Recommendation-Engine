"""Regression lock for the redirected training/serving feature-parity gate.

Parity is defined against the shared ``app.core.match_features`` contract, not
against the abandoned training notebook. Independent, non-synthetic hiring-quality
evaluation is a separate gate and must stay BLOCKED here.
"""
import importlib
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / "backend")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from data_pipeline.validate_model_contract import validate_contract


def test_parity_passes_against_shared_contract_and_keeps_independent_eval_blocked():
    report = validate_contract()
    source = report["shared_feature_source"]
    assert source["serving_training_shared_source"] is True
    assert source["serving_routes_through_shared_module"] is True
    assert source["trainer_imports_shared_features"] is True
    assert report["artifact_tagged_with_shared_contract"] is True
    assert report["serving_reproduces_contract"] is True
    assert report["feature_parity_passed"] is True
    # Independent, non-synthetic quality and public deployment remain open.
    assert report["independent_quality_validated"] is False
    assert report["training_performed"] is False
    assert report["deployment_gate"].startswith("BLOCKED")


def test_serving_and_training_read_the_same_feature_module_file():
    serving = importlib.import_module("app.core.match_features")
    training = importlib.import_module("backend.app.core.match_features")
    assert Path(serving.__file__).resolve() == Path(training.__file__).resolve()


def test_batched_semantic_scores_reuse_one_job_embedding(monkeypatch):
    from app.core import hybrid_matcher

    calls = []

    class Encoder:
        def encode(self, texts, **kwargs):
            calls.append((texts, kwargs))
            return np.asarray([[0.6, 0.8], [0.0, 1.0], [1.0, 0.0]])

    monkeypatch.setattr(hybrid_matcher, "_get_model", lambda: Encoder())
    scores = hybrid_matcher.semantic_similarities(["Candidate one", "Candidate two"], "Job description", batch_size=8)

    assert scores == [0.6, 0.0]
    assert len(calls) == 1
    assert len(calls[0][0]) == 3
    assert calls[0][0][-1] == "Job description"
    assert calls[0][1]["batch_size"] == 8
    assert calls[0][1]["normalize_embeddings"] is True


def test_verified_bundle_mismatch_fails_parity(monkeypatch):
    report = validate_contract()
    bundle = report["verified_bundle"]
    if not bundle["bundle_present"]:
        pytest.skip("reviewed training bundle is not present locally")
    assert bundle["bundle_sha256_match"] is True
    # _artifact() re-reads the file each call, so patch the validator's own reference
    # to return a deliberately mismatched source hash and confirm parity then fails.
    from app.core import hybrid_matcher
    import data_pipeline.validate_model_contract as validator

    original = hybrid_matcher._artifact()
    mismatched = {**original, "source_artifact_sha256": "0" * 64}
    monkeypatch.setattr(validator, "_artifact", lambda: mismatched)
    assert validate_contract()["feature_parity_passed"] is False

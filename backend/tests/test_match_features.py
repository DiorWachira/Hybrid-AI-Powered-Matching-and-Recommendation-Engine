import pytest
import sys
from types import SimpleNamespace
from unittest.mock import Mock

from app.core.match_features import growth_score, skill_overlap


@pytest.mark.parametrize("candidate,required,expected", [
    (["SQL", "sql", "Excel"], ["sql", "Python"], 0.5),
    (["Python"], ["Data Analysis"], 0.0),
    (["SQL"], [], 0.0),
    ([], ["SQL"], 0.0),
])
def test_direct_skill_contract(candidate, required, expected):
    assert skill_overlap(candidate, required) == expected


@pytest.mark.parametrize("years,required,certificates", [(0, 0, 0), (1, 0, 1), (2, 4, 1), (10, 2, 4)])
def test_growth_preserves_serving_formula(years, required, certificates):
    assert growth_score(years, required, certificates) == (min(years / max(required, 1), 1.0) + min(certificates / 2, 1.0)) / 2


def test_encoder_loads_artifact_revision_and_refreshes_on_change(monkeypatch):
    from app.core import hybrid_matcher
    artifact = {"embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "encoder_revision": "a" * 40}
    factory = Mock(side_effect=[object(), object()])
    monkeypatch.setattr(hybrid_matcher, "_artifact", lambda: artifact)
    monkeypatch.setattr(hybrid_matcher, "_model", None)
    monkeypatch.setattr(hybrid_matcher, "_model_identity", None)
    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=factory))
    first = hybrid_matcher._get_model()
    assert hybrid_matcher._get_model() is first
    factory.assert_called_once_with(artifact["embedding_model"], revision="a" * 40)
    artifact["encoder_revision"] = "b" * 40
    assert hybrid_matcher._get_model() is not first
    assert factory.call_count == 2


def test_active_prototype_artifact_has_reviewed_model_identity():
    from app.core.hybrid_matcher import _artifact, calibrated_score
    artifact = _artifact()
    assert artifact["model_version"] == "2026-10-19-epoch-combiner-v2-r001"
    assert artifact["promotion_status"] == "PROTOTYPE_TESTING_APPROVED"
    assert artifact["selected_epoch"] == 4
    assert artifact["encoder_revision"] == "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    assert artifact["decision_threshold"] == pytest.approx(0.46)
    assert calibrated_score(1.0, 1.0, 1.0)[0] > calibrated_score(0.0, 0.0, 0.0)[0]

def test_artifact_is_cached_until_the_file_changes(tmp_path, monkeypatch):
    import json
    import os
    from app.core import hybrid_matcher
    path = tmp_path / "weights.json"
    path.write_text(hybrid_matcher.ARTIFACT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(hybrid_matcher, "ARTIFACT_PATH", path)
    monkeypatch.setattr(hybrid_matcher, "_artifact_cache", None)
    loads = Mock(wraps=hybrid_matcher._load_artifact)
    monkeypatch.setattr(hybrid_matcher, "_load_artifact", loads)
    first = hybrid_matcher._artifact()
    first["decision_threshold"] = 0.99  # callers get a copy, so mutation cannot leak into the cache
    assert hybrid_matcher._artifact()["decision_threshold"] != 0.99
    assert loads.call_count == 1
    changed = {**json.loads(path.read_text(encoding="utf-8")), "decision_threshold": 0.5}
    path.write_text(json.dumps(changed), encoding="utf-8")
    os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1_000_000))
    assert hybrid_matcher._artifact()["decision_threshold"] == 0.5
    assert loads.call_count == 2


def test_job_similarities_encode_candidate_once_with_all_jobs(monkeypatch):
    import numpy as np
    from app.core import hybrid_matcher
    calls = []

    class Encoder:
        def encode(self, texts, **options):
            calls.append(texts)
            return np.asarray([[1.0, 0.0], [0.6, 0.8], [-1.0, 0.0]])

    monkeypatch.setattr(hybrid_matcher, "_get_model", lambda: Encoder())
    assert hybrid_matcher.job_similarities("Candidate resume", ["Job one", "Job two"]) == [0.6, 0.0]
    assert len(calls) == 1 and calls[0][1:] == ["Job one", "Job two"]
    assert hybrid_matcher.job_similarities("Candidate resume", []) == []
    assert len(calls) == 1


def test_model_preload_is_disabled_for_tests_and_reports_state():
    from app.config import get_settings
    from app.core import hybrid_matcher
    assert get_settings().preload_matching_model is False
    assert hybrid_matcher.model_state() in {"ready", "loading", "not_loaded"}

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
    assert artifact["model_version"] == "2026-10-09-epoch-combiner-r001"
    assert artifact["promotion_status"] == "PROTOTYPE_TESTING_APPROVED"
    assert artifact["selected_epoch"] == 19
    assert artifact["encoder_revision"] == "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    assert artifact["decision_threshold"] == pytest.approx(0.44)
    assert calibrated_score(1.0, 1.0, 1.0)[0] > calibrated_score(0.0, 0.0, 0.0)[0]
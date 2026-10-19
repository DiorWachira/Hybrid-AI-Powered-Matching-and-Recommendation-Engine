"""Feature contract v2 (related skills + experience readiness), its serving guard and its training data."""
import hashlib
import json
import random

import numpy as np
import pytest

from app.core import match_features
from app.core.match_features import CONTRACT_V1, CONTRACT_V2, contract_features, experience_readiness, related_skill_overlap, skill_credits

GRAPH = {
    "postgresql": {"sql": 0.9}, "sql": {"postgresql": 0.9, "data analysis": 0.7},
    "data analysis": {"sql": 0.7}, "next.js": {"react": 0.75}, "react": {"next.js": 0.75, "javascript": 0.7},
    "javascript": {"react": 0.7},
}


def test_exact_skills_earn_full_credit_and_aliases_earn_their_relation_weight():
    credits = skill_credits(["PostgreSQL", "Excel"], ["SQL", "excel"], GRAPH)
    assert credits == [("SQL", 0.9, "PostgreSQL"), ("excel", 1.0, "Excel")]


def test_two_relationship_paths_multiply_and_longer_paths_earn_nothing():
    assert skill_credits(["Next.js"], ["JavaScript"], GRAPH) == [("JavaScript", 0.525, "Next.js")]
    # PostgreSQL -> SQL -> Data Analysis is two hops; a third hop would be needed for anything further.
    assert skill_credits(["PostgreSQL"], ["Data Analysis"], GRAPH)[0][1] == pytest.approx(0.63)
    assert skill_credits(["Next.js"], ["SQL"], GRAPH) == [("SQL", 0.0, None)]


def test_related_overlap_averages_unique_required_skills():
    assert related_skill_overlap(["PostgreSQL"], ["SQL", "SQL", "React"], GRAPH) == pytest.approx(0.45)
    assert related_skill_overlap(["SQL"], [], GRAPH) == 0.0


def test_v2_never_scores_a_skill_lower_than_v1():
    rng = random.Random(7)
    vocabulary = ["SQL", "PostgreSQL", "React", "JavaScript", "Next.js", "Data Analysis", "Excel"]
    for _ in range(200):
        held, required = rng.sample(vocabulary, 3), rng.sample(vocabulary, 3)
        assert related_skill_overlap(held, required, GRAPH) >= match_features.skill_overlap(held, required)


def test_experience_readiness_ignores_certifications_and_caps_extra_experience():
    assert experience_readiness(4, 4) == pytest.approx(1 / 1.5)
    assert experience_readiness(6, 4) == 1.0 == experience_readiness(20, 4)
    assert experience_readiness(0, 0) == 0.0
    assert contract_features(CONTRACT_V2, candidate_skills=[], required_skills=[], years_experience=6, required_experience_years=4, certification_count=0)[1] == 1.0
    # v1 caps the same candidate at 0.5 because they hold no certification.
    assert contract_features(CONTRACT_V1, candidate_skills=[], required_skills=[], years_experience=6, required_experience_years=4, certification_count=0)[1] == 0.5


def test_unknown_contract_is_rejected():
    with pytest.raises(ValueError):
        contract_features("serving-unknown", candidate_skills=[], required_skills=[], years_experience=0, required_experience_years=0, certification_count=0)


def test_curated_relationship_file_is_loaded_undirected_and_hashed():
    graph, digest = match_features.skill_relations()
    assert graph["postgresql"]["sql"] == graph["sql"]["postgresql"] == 0.9
    assert len(digest) == 64


def test_relationship_hash_ignores_crlf_checkouts(tmp_path):
    content = match_features.SKILL_RELATIONS_PATH.read_bytes().replace(b"\r\n", b"\n")
    (tmp_path / "lf.json").write_bytes(content)
    (tmp_path / "crlf.json").write_bytes(content.replace(b"\n", b"\r\n"))
    digests = {match_features._relations(str(tmp_path / name), 0)[1] for name in ("lf.json", "crlf.json")}
    assert digests == {hashlib.sha256(content).hexdigest()}


def _write_artifact(tmp_path, **changes):
    from app.core import hybrid_matcher
    artifact = {**json.loads(hybrid_matcher.ARTIFACT_PATH.read_text(encoding="utf-8")), **changes}
    path = tmp_path / "weights.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    return path


def test_serving_loads_v2_only_with_the_skill_relations_it_was_trained_on(tmp_path):
    from app.core.hybrid_matcher import _load_artifact
    digest = match_features.skill_relations()[1]
    assert _load_artifact(_write_artifact(tmp_path, feature_contract=CONTRACT_V2, skill_relations_sha256=digest))["feature_contract"] == CONTRACT_V2
    with pytest.raises(ValueError, match="Skill relationship file differs"):
        _load_artifact(_write_artifact(tmp_path, feature_contract=CONTRACT_V2, skill_relations_sha256="0" * 64))
    with pytest.raises(ValueError, match="Unsupported feature contract"):
        _load_artifact(_write_artifact(tmp_path, feature_contract="serving-unknown"))


def test_serving_scores_with_the_contract_named_by_the_artifact(monkeypatch):
    from types import SimpleNamespace
    from uuid import UUID
    from app.api import matches
    candidate = SimpleNamespace(candidate_id=UUID(int=1), full_name="Probe", years_experience=6, location=None, expected_salary=None, certifications=[], skills=["PostgreSQL"], parsed_resume_text="", work_authorized=True)
    job = SimpleNamespace(required_experience_years=4, location=None, salary_range_max=None, mandatory_certifications=[], required_skills=["SQL"], description="", requires_work_authorization=False)
    base = matches._artifact()
    for contract, skill, growth in ((CONTRACT_V1, 0.0, 0.5), (CONTRACT_V2, 0.9, 1.0)):
        monkeypatch.setattr(matches, "_artifact", lambda contract=contract: {**base, "feature_contract": contract})
        result = matches._score_candidate(candidate, job, semantic_score=0.6)
        assert (result.skill_overlap, result.growth_score) == (skill, growth)


def test_aliases_keep_true_skills_and_do_not_disturb_the_shared_generation_stream():
    from data_pipeline.generate_synthetic_data import apply_skill_aliases, generate_candidate, true_skill_credit
    first, second = random.Random(3), random.Random(3)
    candidates = [generate_candidate(first) for _ in range(60)]
    aliased = [apply_skill_aliases(candidate, rate=1.0) for candidate in candidates]
    # The alias pass uses its own per-candidate RNG, so later draws from the shared stream are unchanged.
    [generate_candidate(second) for _ in range(60)]
    assert first.random() == second.random()
    assert all(item["latent_true_skills"] == original["skills"] for item, original in zip(aliased, candidates))
    assert any(item["skills"] != item["latent_true_skills"] for item in aliased)
    assert apply_skill_aliases(candidates[0], rate=1.0) == aliased[0]
    assert true_skill_credit(["SQL"], ["SQL", "Data Analysis"]) == pytest.approx(0.75)
    assert true_skill_credit(["SQL"], []) == 0.0


def test_v2_training_data_pins_relations_and_v3_labels_follow_true_skills(tmp_path):
    from data_pipeline.epoch_trainer import LABEL_V2, LABEL_V3, prepare_synthetic_data

    def encoder(texts):
        return np.tile([1.0, 0.0], (len(texts), 1))

    options = dict(code_commit="test", candidate_count=200, job_count=100, encode=encoder)
    v1 = prepare_synthetic_data(tmp_path / "v1", **options)
    v2 = prepare_synthetic_data(tmp_path / "v2", feature_contract=CONTRACT_V2, label_source=LABEL_V3, **options)
    assert "skill_relations_sha256" not in v1[3]["specification"]
    assert v2[3]["specification"]["skill_relations_sha256"] == match_features.skill_relations()[1]
    assert v2[3]["specification"]["label_source"] == LABEL_V3 != LABEL_V2
    assert np.all((v2[0] >= 0) & (v2[0] <= 1))
    # Same seed and pairs, but v3 candidates list aliases, so exact-name v1 skill credit is lower on average.
    v1_on_v3 = prepare_synthetic_data(tmp_path / "v1v3", label_source=LABEL_V3, **options)
    assert v1_on_v3[0][:, 1].mean() < v2[0][:, 1].mean()
    with pytest.raises(ValueError):
        prepare_synthetic_data(tmp_path / "bad", feature_contract="serving-unknown", **options)

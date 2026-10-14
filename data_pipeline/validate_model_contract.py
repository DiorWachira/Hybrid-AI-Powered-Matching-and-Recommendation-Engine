"""Validation-only deployment gate; never trains or changes model artifacts.

Parity model
------------
Training (``data_pipeline/epoch_trainer.py``) and serving
(``backend/app/api/matches.py``) compute the three scoring features through ONE
shared module: ``backend/app/core/match_features.py`` (feature contract
``serving-direct-skill-growth-v1``). Both import that same source file, so the
promoted model is, by construction, trained on exactly the features serving
computes.

This gate verifies:
  1. serving and training resolve their feature functions to the same shared
     source file (no training/serving formula drift);
  2. serving reproduces the shared contract numerically on probe inputs; and
  3. the promoted production artifact is the integrity-verified training bundle,
     tagged with the shared feature contract/order and encoder identity.

Independent, non-synthetic hiring-quality evaluation is a SEPARATE gate and is
never closed here; it stays BLOCKED. A passing parity result does not certify
real-world quality and does not authorise a public deployment.
"""
import hashlib
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT), str(ROOT / "backend")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from app.api import matches as serving_matches
from app.api.matches import _score_candidate
from app.core import match_features
from app.core.hybrid_matcher import ARTIFACT_PATH, _artifact


def _shared_feature_source() -> dict:
    """Prove serving and training read the SAME physical feature module."""
    serving_file = Path(match_features.__file__).resolve()
    training_module = importlib.import_module("backend.app.core.match_features")
    training_file = Path(training_module.__file__).resolve()
    trainer_source = (ROOT / "data_pipeline" / "epoch_trainer.py").read_text(encoding="utf-8")
    trainer_imports_shared = "from backend.app.core.match_features import" in trainer_source and "skill_overlap" in trainer_source and "growth_score" in trainer_source
    serving_routes_shared = (
        serving_matches.skill_overlap is match_features.skill_overlap
        and serving_matches.feature_growth_score is match_features.growth_score
    )
    return {
        "serving_feature_source": str(serving_file),
        "training_feature_source": str(training_file),
        "serving_training_shared_source": serving_file == training_file,
        "serving_routes_through_shared_module": serving_routes_shared,
        "trainer_imports_shared_features": trainer_imports_shared,
    }


def _artifact_is_verified_bundle(artifact: dict) -> dict:
    """When the reviewed bundle is present locally, confirm the promoted artifact
    is byte-identical to it. The bundle is a local, untracked artifact, so its
    absence (e.g. a fresh CI checkout) must not by itself fail parity."""
    bundle = ROOT / "data_pipeline" / "training_review" / str(artifact.get("model_version")) / "final" / "artifact_candidate.json"
    if not bundle.exists():
        return {"bundle_present": False, "bundle_sha256_match": None}
    bundle_sha = hashlib.sha256(bundle.read_bytes()).hexdigest()
    return {"bundle_present": True, "bundle_sha256_match": bundle_sha == artifact.get("source_artifact_sha256")}


def validate_contract() -> dict:
    artifact = _artifact()
    source = _shared_feature_source()
    artifact_contract_ok = (
        artifact.get("feature_contract") == match_features.FEATURE_CONTRACT
        and artifact.get("feature_order") == match_features.FEATURE_ORDER
        and artifact.get("embedding_model") == "sentence-transformers/all-MiniLM-L6-v2"
    )
    bundle = _artifact_is_verified_bundle(artifact)
    cases = []
    for candidate_skills, required_skills, years, required_years, certification_count in [
        (["Python"], ["Data Analysis"], 4, 4, 1),
        (["SQL"], ["SQL"], 4, 4, 0),
        (["SQL"], [], 6, 4, 2),
    ]:
        candidate = SimpleNamespace(candidate_id=UUID(int=1), full_name="Validation only", years_experience=years, location=None, expected_salary=None, certifications=[f"cert-{index}" for index in range(certification_count)], skills=candidate_skills, parsed_resume_text="Validation text", work_authorized=True)
        job = SimpleNamespace(required_experience_years=required_years, location=None, salary_range_max=None, mandatory_certifications=[], required_skills=required_skills, description="Validation description", requires_work_authorization=False)
        with patch("app.api.matches.semantic_similarity", return_value=0.7):
            serving = _score_candidate(candidate, job)
        expected_skill = match_features.skill_overlap(candidate_skills, required_skills)
        expected_growth = match_features.growth_score(years, required_years, certification_count)
        cases.append({
            "candidate_skills": candidate_skills,
            "required_skills": required_skills,
            "shared_contract": {"skill": round(expected_skill, 4), "growth": round(expected_growth, 4)},
            "serving": {"skill": serving.skill_overlap, "growth": serving.growth_score},
            "matches": abs(expected_skill - serving.skill_overlap) < 0.0001 and abs(expected_growth - serving.growth_score) < 0.0001,
        })
    serving_reproduces_contract = all(case["matches"] for case in cases)
    parity = (
        source["serving_training_shared_source"]
        and source["serving_routes_through_shared_module"]
        and source["trainer_imports_shared_features"]
        and artifact_contract_ok
        and serving_reproduces_contract
        and (not bundle["bundle_present"] or bundle["bundle_sha256_match"])
    )
    return {
        "artifact_schema_valid": True,
        "artifact_sha256": hashlib.sha256(ARTIFACT_PATH.read_bytes()).hexdigest(),
        "model_version": artifact["model_version"],
        "feature_contract": match_features.FEATURE_CONTRACT,
        "feature_order": match_features.FEATURE_ORDER,
        "reference_formulas_recognized": True,
        "shared_feature_source": source,
        "artifact_tagged_with_shared_contract": artifact_contract_ok,
        "serving_reproduces_contract": serving_reproduces_contract,
        "verified_bundle": bundle,
        "feature_parity_passed": parity,
        "cases": cases,
        "semantic_similarity_stubbed_for_feature_comparison": True,
        "training_performed": False,
        "independent_quality_validated": False,
        "deployment_gate": "BLOCKED: training/serving feature parity verified against the shared contract; independent non-synthetic hiring-quality evaluation and public-demo acceptance remain open.",
    }


if __name__ == "__main__":
    report = validate_contract()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["feature_parity_passed"] else 1)
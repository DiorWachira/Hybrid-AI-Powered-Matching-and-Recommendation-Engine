"""Validation-only deployment gate; never trains or changes model artifacts."""
import ast
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api.matches import _score_candidate
from app.core.hybrid_matcher import ARTIFACT_PATH, _artifact


def validate_contract() -> dict:
    artifact = _artifact()
    notebook_path = ROOT / "notebooks" / "hybrid_matching_model_training.ipynb"
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    functions = {}
    weights = {}
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = cell["source"]
        source = "\n".join(source) if isinstance(source, list) else source
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                functions[node.name] = ast.unparse(node)
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "SKILL_RELATION_WEIGHTS" for target in node.targets):
                weights = ast.literal_eval(node.value)
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "SKILL_RELATION_WEIGHTS":
                weights = ast.literal_eval(node.value)
    known_reference = all((
        "min(years_experience / max(required_experience_years, 1), 1.5) / 1.5" in functions.get("experience_fit", ""),
        "0.7 * fit + 0.3 * cert_bonus" in functions.get("growth_score", ""),
        "min(cert_count / 3, 1.0)" in functions.get("growth_score", ""),
        "SKILL_RELATION_WEIGHTS" in functions.get("graph_overlap_score", ""),
        bool(weights),
    ))
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
        expected_skill = sum(1.0 if required in candidate_skills else max((weights.get((skill, required), weights.get((required, skill), 0.0)) for skill in candidate_skills), default=0.0) for required in required_skills) / len(required_skills) if required_skills else 1.0
        expected_growth = 0.7 * min(years / max(required_years, 1), 1.5) / 1.5 + 0.3 * min(certification_count / 3, 1.0)
        cases.append({"candidate_skills": candidate_skills, "required_skills": required_skills, "training_reference": {"skill": round(expected_skill, 4), "growth": round(expected_growth, 4)}, "serving": {"skill": serving.skill_overlap, "growth": serving.growth_score}, "matches": abs(expected_skill - serving.skill_overlap) < 0.0001 and abs(expected_growth - serving.growth_score) < 0.0001})
    return {
        "artifact_schema_valid": True,
        "artifact_sha256": hashlib.sha256(ARTIFACT_PATH.read_bytes()).hexdigest(),
        "model_version": artifact["model_version"],
        "reference_formulas_recognized": known_reference,
        "feature_parity_passed": known_reference and all(case["matches"] for case in cases),
        "cases": cases,
        "semantic_similarity_stubbed_for_feature_comparison": True,
        "training_performed": False,
        "independent_quality_validated": False,
        "deployment_gate": "BLOCKED: resolve shared features and independently evaluate before claiming validated scores",
    }


if __name__ == "__main__":
    report = validate_contract()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["feature_parity_passed"] else 1)
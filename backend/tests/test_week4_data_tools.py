import sys
import random
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.text_preprocessing import anonymize_resume_text
from data_pipeline.import_brightermonday_jobs import normalize_job
from data_pipeline.generate_synthetic_data import generate_candidate
from data_pipeline.load_esco_ontology import load_relationships, load_skills
from data_pipeline.prepare_week4 import clean_candidate_for_export, clean_job_for_export
from app.api import matches


def test_resume_anonymization_removes_contact_and_city_but_keeps_skill_text() -> None:
    text = "Name: Alex Example. Alex Example is female, 31 years old. Contact alex@example.org or +254 712 345 678. Python and SQL in Nairobi."
    cleaned = anonymize_resume_text(text, ("Alex Example",))
    assert "alex@example.org" not in cleaned
    assert "712 345 678" not in cleaned
    assert "Nairobi" not in cleaned
    assert "Alex Example" not in cleaned
    assert "female" not in cleaned
    assert "31 years old" not in cleaned
    assert "Python" in cleaned
    assert "SQL" in cleaned


def test_brightermonday_export_normalizes_common_fields_and_salary_range() -> None:
    job = normalize_job({
        "jobTitle": "Data Analyst",
        "jobDescription": "Analyze reporting data and prepare dashboards for business teams.",
        "companyName": "Example Analytics Ltd",
        "city": "Nairobi",
        "experienceYears": "3-5 years",
        "skills": "SQL, Power BI; Excel",
        "certifications": ["Google Data Analytics"],
        "salary": "KES 80,000 - 120,000",
        "url": "https://jobs.example/123",
    })
    assert job["title"] == "Data Analyst"
    assert job["company_name"] == "Example Analytics Ltd"
    assert job["location"] == "Nairobi"
    assert job["required_experience_years"] == 3
    assert job["required_skills"] == ["SQL", "Power BI", "Excel"]
    assert job["mandatory_certifications"] == ["Google Data Analytics"]
    assert job["salary_range_max"] == 120000
    assert job["job_id"]


def test_curated_ontology_loader_has_weighted_links_and_skill_rows() -> None:
    skills = load_skills(None)
    relationships = load_relationships(None)
    assert {row["name"] for row in skills} >= {"Python", "SQL", "Data Analysis"}
    assert any(row["from_skill"] == "Python" and row["target_skill"] == "Data Analysis" and row["weight"] == 0.8 for row in relationships)


def test_ontology_loader_accepts_trimmed_esco_csv(tmp_path: Path) -> None:
    skills_csv = tmp_path / "skills.csv"
    skills_csv.write_text("conceptUri,preferredLabel,skillType\nuri:data,data analysis,skill/competence\n", encoding="utf-8")
    relations_csv = tmp_path / "relations.csv"
    relations_csv.write_text("source_skill,target_skill,weight\ndata analysis,SQL,0.75\n", encoding="utf-8")
    assert any(row["name"] == "data analysis" and row["source"] == "ESCO CSV" for row in load_skills(skills_csv))
    assert any(row["from_skill"] == "data analysis" and row["target_skill"] == "SQL" and row["weight"] == 0.75 for row in load_relationships(relations_csv))


def test_synthetic_generator_is_reproducible_from_seed() -> None:
    assert generate_candidate(random.Random(42)) == generate_candidate(random.Random(42))


def test_deployment_exports_anonymize_and_remove_training_only_latents() -> None:
    candidate = generate_candidate(random.Random(12))
    candidate["resume_text"] = "Name: Sensitive Person. Contact hidden@example.org. Python engineer in Nairobi."
    clean_candidate = clean_candidate_for_export(candidate)
    assert "latent_competence" not in clean_candidate
    assert "latent_adaptability" not in clean_candidate
    assert "Sensitive Person" not in clean_candidate["resume_text"]
    assert "hidden@example.org" not in clean_candidate["resume_text"]
    assert "Nairobi" not in clean_candidate["resume_text"]

    job = {"job_id": "job", "title": "Analyst", "specialisation": "reporting", "location": "Nairobi", "required_experience_years": 1, "required_skills": ["SQL"], "mandatory_certifications": [], "salary_range_max": 100000, "description": "SQL reporting role", "latent_quality_bar": 0.8}
    assert "latent_quality_bar" not in clean_job_for_export(job)


def test_rule_gate_rejects_candidate_before_calling_ml(monkeypatch: pytest.MonkeyPatch) -> None:
    def scoring_must_not_run(*args: object, **kwargs: object) -> float:
        pytest.fail("ML scoring ran for a candidate rejected by Tier 1")

    monkeypatch.setattr(matches, "semantic_similarity", scoring_must_not_run)
    monkeypatch.setattr(matches, "calibrated_score", scoring_must_not_run)
    candidate = SimpleNamespace(
        candidate_id=uuid4(), full_name="Candidate", years_experience=0,
        location="Nakuru", expected_salary=100000, certifications=[], skills=[],
        parsed_resume_text="some profile text",
        work_authorized=None,
    )
    job = SimpleNamespace(
        required_experience_years=3, location="Nairobi", salary_range_max=200000,
        mandatory_certifications=["CPA"], required_skills=[], description="A valid job description.",
        requires_work_authorization=False,
    )
    result = matches._score_candidate(candidate, job)
    assert result.hard_rule_passed is False
    assert result.final_score == 0
    assert len(result.rule_reasons) == 3

from uuid import UUID

from data_pipeline.demo_profiles import job_variants, kenyan_name


def test_demo_names_and_variants_are_stable_and_scores_are_not_fabricated():
    job = {"job_id": "demo-job", "title": "Data Analyst", "location": "Nairobi", "required_experience_years": 2, "salary_range_max": 100000, "required_skills": ["SQL", "Python", "Power BI"], "mandatory_certifications": ["Certificate"], "description": "Business reporting"}
    profiles = job_variants(job)
    assert profiles == job_variants(job)
    assert len({profile["candidate_id"] for profile in profiles}) == 3
    assert profiles[0]["skills"] == job["required_skills"]
    assert len(profiles[1]["skills"]) < len(profiles[0]["skills"])
    assert profiles[2]["expected_salary_kes"] > job["salary_range_max"]
    assert all("score" not in key for profile in profiles for key in profile)
    assert all(profile["full_name"] == kenyan_name(UUID(profile["candidate_id"])) for profile in profiles)
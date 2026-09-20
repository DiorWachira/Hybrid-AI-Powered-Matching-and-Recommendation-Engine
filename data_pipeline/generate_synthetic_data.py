"""Generate a synthetic Kenyan candidate/job dataset for the matching engine.

Per docs/DATASET_STRATEGY.md: candidates are fully synthetic (privacy-safe,
anti-bias by construction); job postings are synthetic here as a stand-in for
(or supplement to) real BrighterMonday postings, using the same skill pool so
both sides of the match are comparable.

Usage:
    python data_pipeline/generate_synthetic_data.py --candidates 500 --jobs 60
"""
from __future__ import annotations

import argparse
import json
import random
import uuid
from pathlib import Path

from faker import Faker

OUTPUT_DIR = Path(__file__).resolve().parent / "dataset"

KENYAN_CITIES = ["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Thika", "Eldoret", "Nyeri"]

# Role -> (core skills, related/adjacent skills, certifications, salary KES range)
ROLE_CATALOG: dict[str, dict[str, object]] = {
    "Data Analyst": {
        "core_skills": ["SQL", "Data Analysis", "Python", "Excel", "Power BI"],
        "adjacent_skills": ["Statistics", "Data Visualization", "Tableau"],
        "certifications": ["Google Data Analytics", "Microsoft Power BI"],
        "salary_range": (60000, 160000),
    },
    "DevOps Engineer": {
        "core_skills": ["Docker", "Kubernetes", "CI/CD", "Linux", "AWS"],
        "adjacent_skills": ["Terraform", "Ansible", "Networking"],
        "certifications": ["AWS Certified Cloud Practitioner", "Certified Kubernetes Administrator"],
        "salary_range": (90000, 250000),
    },
    "Software Engineer": {
        "core_skills": ["Python", "SQL", "Git", "REST APIs"],
        "adjacent_skills": ["Docker", "Testing", "System Design"],
        "certifications": ["AWS Certified Cloud Practitioner"],
        "salary_range": (70000, 220000),
    },
    "Accountant": {
        "core_skills": ["Financial Accounting", "Taxation", "Excel"],
        "adjacent_skills": ["Auditing", "Payroll"],
        "certifications": ["CPA"],
        "salary_range": (50000, 150000),
    },
    "Business Analyst": {
        "core_skills": ["Business Analysis", "SQL", "Data Analysis"],
        "adjacent_skills": ["Project Management", "Stakeholder Management"],
        "certifications": ["Google Data Analytics"],
        "salary_range": (55000, 170000),
    },
}

EDUCATION_LEVELS = ["Diploma", "Bachelor's", "Master's"]


def _sample_skills(role: dict[str, object], rng: random.Random) -> list[str]:
    core = list(role["core_skills"])  # type: ignore[arg-type]
    adjacent = list(role["adjacent_skills"])  # type: ignore[arg-type]
    picked_core = rng.sample(core, k=rng.randint(max(2, len(core) - 2), len(core)))
    picked_adjacent = rng.sample(adjacent, k=rng.randint(0, len(adjacent)))
    return picked_core + picked_adjacent


def generate_candidate(fake: Faker, rng: random.Random) -> dict[str, object]:
    role_name = rng.choice(list(ROLE_CATALOG))
    role = ROLE_CATALOG[role_name]
    skills = _sample_skills(role, rng)
    years_experience = rng.randint(0, 15)
    certifications = rng.sample(
        role["certifications"],  # type: ignore[arg-type]
        k=rng.randint(0, len(role["certifications"])),  # type: ignore[arg-type]
    )
    salary_low, salary_high = role["salary_range"]  # type: ignore[misc]
    expected_salary = rng.randint(int(salary_low), int(salary_high))

    summary = (
        f"{years_experience} years of experience as a {role_name.lower()} with hands-on "
        f"work in {', '.join(skills[:3])}. Based in {rng.choice(KENYAN_CITIES)}, Kenya."
    )

    return {
        "candidate_id": str(uuid.uuid4()),
        "target_role": role_name,
        "location": rng.choice(KENYAN_CITIES),
        "years_experience": years_experience,
        "education": rng.choice(EDUCATION_LEVELS),
        "skills": skills,
        "certifications": certifications,
        "expected_salary_kes": expected_salary,
        "resume_text": summary,
    }


def generate_job(fake: Faker, rng: random.Random) -> dict[str, object]:
    role_name = rng.choice(list(ROLE_CATALOG))
    role = ROLE_CATALOG[role_name]
    required_skills = rng.sample(
        role["core_skills"],  # type: ignore[arg-type]
        k=rng.randint(2, len(role["core_skills"])),  # type: ignore[arg-type]
    )
    mandatory_certifications = rng.sample(
        role["certifications"],  # type: ignore[arg-type]
        k=rng.randint(0, 1),
    )
    salary_low, salary_high = role["salary_range"]  # type: ignore[misc]
    required_experience_years = rng.randint(0, 8)

    description = (
        f"We are hiring a {role_name} to work on {', '.join(required_skills[:3])}. "
        f"Minimum {required_experience_years} years of experience required."
    )

    return {
        "job_id": str(uuid.uuid4()),
        "title": role_name,
        "location": rng.choice(KENYAN_CITIES),
        "required_experience_years": required_experience_years,
        "required_skills": required_skills,
        "mandatory_certifications": mandatory_certifications,
        "salary_range_max": rng.randint(int(salary_low), int(salary_high)),
        "description": description,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=int, default=500)
    parser.add_argument("--jobs", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    fake = Faker()  # en_KE locale isn't available in this Faker version; KENYAN_CITIES covers locality.
    Faker.seed(args.seed)
    rng = random.Random(args.seed)

    candidates = [generate_candidate(fake, rng) for _ in range(args.candidates)]
    jobs = [generate_job(fake, rng) for _ in range(args.jobs)]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "candidates.json").write_text(json.dumps(candidates, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "jobs.json").write_text(json.dumps(jobs, indent=2), encoding="utf-8")

    print(f"Wrote {len(candidates)} candidates and {len(jobs)} jobs to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

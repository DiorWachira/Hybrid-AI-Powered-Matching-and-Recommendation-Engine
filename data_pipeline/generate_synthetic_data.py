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

OUTPUT_DIR = Path(__file__).resolve().parent / "dataset"

KENYAN_CITIES = ["Nairobi", "Mombasa", "Kisumu", "Nakuru", "Thika", "Eldoret", "Nyeri"]

# Role -> skills, certifications, salary KES range, and the in-role specialisations.
# Specialisations exist so that two candidates with identical skill lists can still
# read very differently, which is what gives the embedding model something to learn.
ROLE_CATALOG: dict[str, dict[str, object]] = {
    "Data Analyst": {
        "core_skills": ["SQL", "Data Analysis", "Python", "Excel", "Power BI"],
        "adjacent_skills": ["Statistics", "Data Visualization", "Tableau"],
        "certifications": ["Google Data Analytics", "Microsoft Power BI"],
        "salary_range": (60000, 160000),
        "domains": {
            "financial reporting": [
                "month-end close dashboards",
                "revenue variance analysis",
                "budget forecasting packs",
            ],
            "marketing analytics": [
                "campaign attribution modelling",
                "customer segmentation studies",
                "churn funnel reporting",
            ],
            "health informatics": [
                "patient throughput dashboards",
                "clinic utilisation reporting",
                "disease surveillance extracts",
            ],
        },
    },
    "DevOps Engineer": {
        "core_skills": ["Docker", "Kubernetes", "CI/CD", "Linux", "AWS"],
        "adjacent_skills": ["Terraform", "Ansible", "Networking"],
        "certifications": ["AWS Certified Cloud Practitioner", "Certified Kubernetes Administrator"],
        "salary_range": (90000, 250000),
        "domains": {
            "platform reliability": [
                "multi-region failover drills",
                "incident response tooling",
                "service level objective tracking",
            ],
            "build and release": [
                "pipeline parallelisation",
                "artefact promotion workflows",
                "blue-green deployment rollouts",
            ],
            "cloud cost engineering": [
                "rightsizing audits",
                "spot instance scheduling",
                "per-team spend dashboards",
            ],
        },
    },
    "Software Engineer": {
        "core_skills": ["Python", "SQL", "Git", "REST APIs"],
        "adjacent_skills": ["Docker", "Testing", "System Design"],
        "certifications": ["AWS Certified Cloud Practitioner"],
        "salary_range": (70000, 220000),
        "domains": {
            "payments integration": [
                "M-Pesa Daraja callbacks",
                "reconciliation batch jobs",
                "idempotent transaction handling",
            ],
            "internal tooling": [
                "admin console rewrites",
                "bulk import utilities",
                "role-based access screens",
            ],
            "public API platform": [
                "versioned endpoint rollouts",
                "rate limiting middleware",
                "partner sandbox environments",
            ],
        },
    },
    "Accountant": {
        "core_skills": ["Financial Accounting", "Taxation", "Excel"],
        "adjacent_skills": ["Auditing", "Payroll"],
        "certifications": ["CPA"],
        "salary_range": (50000, 150000),
        "domains": {
            "tax compliance": [
                "VAT return filings",
                "withholding tax schedules",
                "KRA iTax reconciliations",
            ],
            "management accounts": [
                "monthly management packs",
                "cost centre variance notes",
                "cash flow forecasting",
            ],
            "external audit support": [
                "audit sampling schedules",
                "fixed asset verification",
                "year-end confirmations",
            ],
        },
    },
    "Business Analyst": {
        "core_skills": ["Business Analysis", "SQL", "Data Analysis"],
        "adjacent_skills": ["Project Management", "Stakeholder Management"],
        "certifications": ["Google Data Analytics"],
        "salary_range": (55000, 170000),
        "domains": {
            "process re-engineering": [
                "as-is process mapping",
                "handover bottleneck studies",
                "standard operating procedure rewrites",
            ],
            "requirements delivery": [
                "user story workshops",
                "acceptance criteria definition",
                "traceability matrices",
            ],
            "regulatory change": [
                "impact assessments",
                "control gap registers",
                "compliance reporting rollouts",
            ],
        },
    },
}

EDUCATION_LEVELS = ["Diploma", "Bachelor's", "Master's"]

CANDIDATE_TEMPLATES = [
    "{years} years working as a {role} in {domain}. Delivered {work_a} and {work_b} "
    "using {skills}. Currently based in {city}.",
    "{role} focused on {domain}. Recent work covers {work_a}, plus {work_b}. "
    "Day-to-day tools include {skills}. {years} years in the Kenyan market, living in {city}.",
    "Experienced {role} with {years} years behind them. Specialises in {domain}, "
    "notably {work_a} and {work_b}. Comfortable across {skills}. Located in {city}.",
    "{domain} specialist working as a {role}. Portfolio includes {work_a} and {work_b}. "
    "Core toolkit: {skills}. {years} years of experience, {city} based.",
]

JOB_TEMPLATES = [
    "We are hiring a {role} to lead our {domain} work. You will own {work_a} and "
    "support {work_b}. Core stack: {skills}. Minimum {years} years of experience.",
    "{role} wanted for a {domain} mandate. The role centres on {work_a}, with "
    "involvement in {work_b}. We expect strong {skills}. At least {years} years required.",
    "Join our {city} team as a {role}. This position sits within {domain} and covers "
    "{work_a} as well as {work_b}. Required skills include {skills}. {years}+ years experience.",
    "Our team is expanding its {domain} capability and needs a {role}. Expect to handle "
    "{work_a} and contribute to {work_b}. Skills we rely on: {skills}. {years} years minimum.",
]


def _sample_skills(role: dict[str, object], rng: random.Random) -> list[str]:
    core = list(role["core_skills"])  # type: ignore[arg-type]
    adjacent = list(role["adjacent_skills"])  # type: ignore[arg-type]
    picked_core = rng.sample(core, k=rng.randint(max(2, len(core) - 2), len(core)))
    picked_adjacent = rng.sample(adjacent, k=rng.randint(0, len(adjacent)))
    return picked_core + picked_adjacent


def generate_candidate(rng: random.Random) -> dict[str, object]:
    role_name = rng.choice(list(ROLE_CATALOG))
    role = ROLE_CATALOG[role_name]
    domains: dict[str, list[str]] = role["domains"]  # type: ignore[assignment]
    specialisation = rng.choice(list(domains))
    work_a, work_b = rng.sample(domains[specialisation], k=2)

    skills = _sample_skills(role, rng)
    years_experience = rng.randint(0, 15)
    certifications = rng.sample(
        role["certifications"],  # type: ignore[arg-type]
        k=rng.randint(0, len(role["certifications"])),  # type: ignore[arg-type]
    )
    salary_low, salary_high = role["salary_range"]  # type: ignore[misc]
    expected_salary = rng.randint(int(salary_low), int(salary_high))
    city = rng.choice(KENYAN_CITIES)

    resume_text = rng.choice(CANDIDATE_TEMPLATES).format(
        years=years_experience,
        role=role_name.lower(),
        domain=specialisation,
        work_a=work_a,
        work_b=work_b,
        skills=", ".join(skills[:4]),
        city=city,
    )

    return {
        "candidate_id": str(uuid.uuid4()),
        "target_role": role_name,
        "specialisation": specialisation,
        "location": city,
        "years_experience": years_experience,
        "education": rng.choice(EDUCATION_LEVELS),
        "skills": skills,
        "certifications": certifications,
        "expected_salary_kes": expected_salary,
        "resume_text": resume_text,
        # Hidden ground-truth drivers. Never pass these to the model as features:
        # they exist so pair labels are not a deterministic function of the inputs.
        "latent_competence": round(rng.betavariate(5, 3), 4),
        "latent_adaptability": round(rng.betavariate(4, 4), 4),
    }


def generate_job(rng: random.Random) -> dict[str, object]:
    role_name = rng.choice(list(ROLE_CATALOG))
    role = ROLE_CATALOG[role_name]
    domains: dict[str, list[str]] = role["domains"]  # type: ignore[assignment]
    specialisation = rng.choice(list(domains))
    work_a, work_b = rng.sample(domains[specialisation], k=2)

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
    city = rng.choice(KENYAN_CITIES)

    description = rng.choice(JOB_TEMPLATES).format(
        role=role_name,
        domain=specialisation,
        work_a=work_a,
        work_b=work_b,
        skills=", ".join(required_skills[:4]),
        years=required_experience_years,
        city=city,
    )

    return {
        "job_id": str(uuid.uuid4()),
        "title": role_name,
        "specialisation": specialisation,
        "location": city,
        "required_experience_years": required_experience_years,
        "required_skills": required_skills,
        "mandatory_certifications": mandatory_certifications,
        "salary_range_max": rng.randint(int(salary_low), int(salary_high)),
        "description": description,
        # Hidden hiring bar for this posting; see the note on candidate latents.
        "latent_quality_bar": round(rng.betavariate(4, 4), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=int, default=500)
    parser.add_argument("--jobs", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    candidates = [generate_candidate(rng) for _ in range(args.candidates)]
    jobs = [generate_job(rng) for _ in range(args.jobs)]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "candidates.json").write_text(json.dumps(candidates, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "jobs.json").write_text(json.dumps(jobs, indent=2), encoding="utf-8")

    print(f"Wrote {len(candidates)} candidates and {len(jobs)} jobs to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

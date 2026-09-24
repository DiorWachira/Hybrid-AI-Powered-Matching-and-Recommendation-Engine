"""Seed a local demo database from the generated candidate and job JSON files."""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.db.models import Candidate, Employer, JobPosting, User, UserRole  # noqa: E402
from app.db.neo4j_db import project_candidate_skills, project_job_requirements  # noqa: E402
from app.db.postgres import SessionLocal  # noqa: E402
from app.utils.security import hash_password  # noqa: E402

DATASET = ROOT / "data_pipeline" / "dataset"
SEED_PASSWORD = "SeedDataOnly123!"


def load_json(name: str) -> list[dict[str, object]]:
    return json.loads((DATASET / name).read_text(encoding="utf-8"))


def seed(candidates_limit: int, jobs_limit: int, skip_graph: bool) -> tuple[int, int]:
    candidates = load_json("candidates.json")[:candidates_limit]
    jobs = load_json("jobs.json")[:jobs_limit]
    with SessionLocal() as db:
        employer_user = db.scalar(select(User).where(User.email == "seed-recruiter@jobbridge.local"))
        if employer_user is None:
            employer_user = User(email="seed-recruiter@jobbridge.local", password_hash=hash_password(SEED_PASSWORD), role=UserRole.recruiter)
            db.add(employer_user)
            db.flush()
        employer = db.scalar(select(Employer).where(Employer.user_id == employer_user.user_id))
        if employer is None:
            employer = Employer(user_id=employer_user.user_id, company_name="JobBridge Seed Employers", industry="Technology", location="Nairobi")
            db.add(employer)
            db.flush()

        for item in candidates:
            candidate_id = uuid.UUID(str(item["candidate_id"]))
            if db.get(Candidate, candidate_id) is not None:
                continue
            user = User(
                email=f"seed-candidate-{candidate_id.hex[:12]}@jobbridge.local",
                password_hash=hash_password(SEED_PASSWORD),
                role=UserRole.candidate,
            )
            db.add(user)
            db.flush()
            skills = [str(value) for value in item.get("skills", [])]
            certifications = [str(value) for value in item.get("certifications", [])]
            db.add(Candidate(
                candidate_id=candidate_id,
                user_id=user.user_id,
                full_name=f"Synthetic Candidate {candidate_id.hex[:6].upper()}",
                location=str(item.get("location") or ""),
                years_experience=int(item.get("years_experience") or 0),
                expected_salary=item.get("expected_salary_kes"),
                parsed_resume_text=str(item.get("resume_text") or ""),
                skills=skills,
                certifications=certifications,
            ))
            db.flush()
            if not skip_graph:
                project_candidate_skills(str(candidate_id), skills, certifications)

        for item in jobs:
            job_id = uuid.UUID(str(item["job_id"]))
            if db.get(JobPosting, job_id) is not None:
                continue
            required_skills = [str(value) for value in item.get("required_skills", [])]
            certifications = [str(value) for value in item.get("mandatory_certifications", [])]
            db.add(JobPosting(
                job_id=job_id,
                employer_id=employer.employer_id,
                title=str(item.get("title") or "Untitled role"),
                description=str(item.get("description") or ""),
                location=str(item.get("location") or ""),
                required_experience_years=int(item.get("required_experience_years") or 0),
                salary_range_max=item.get("salary_range_max"),
                required_skills=required_skills,
                mandatory_certifications=certifications,
            ))
            db.flush()
            if not skip_graph:
                project_job_requirements(str(item.get("title") or "Untitled role"), required_skills, certifications)
        db.commit()
    return len(candidates), len(jobs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=int, default=25)
    parser.add_argument("--jobs", type=int, default=20)
    parser.add_argument("--skip-graph", action="store_true")
    args = parser.parse_args()
    candidates, jobs = seed(args.candidates, args.jobs, args.skip_graph)
    print(f"Seeded up to {candidates} candidates and {jobs} jobs. Seed password: {SEED_PASSWORD}")


if __name__ == "__main__":
    main()

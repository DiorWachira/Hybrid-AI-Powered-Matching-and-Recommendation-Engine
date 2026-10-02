"""Seed a local demo database from the generated candidate and job JSON files."""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT))

from data_pipeline.demo_profiles import COMPANIES, kenyan_name, job_variants

from app.db.models import Candidate, Employer, JobPosting, User, UserRole  # noqa: E402
from app.db.neo4j_db import get_neo4j_driver
from app.db.graph_sync import ensure_graph_schema, sync_graph_events
from app.db.postgres import SessionLocal  # noqa: E402
from app.utils.security import hash_password  # noqa: E402
from app.core.text_preprocessing import anonymize_resume_text  # noqa: E402

DATASET = ROOT / "data_pipeline" / "dataset"
SEED_PASSWORD = "SeedDataOnly123!"


def load_json(path: Path) -> list[dict[str, object]]:
    return json.loads(path.read_text(encoding="utf-8"))


def seed(candidates_limit: int, jobs_limit: int, skip_graph: bool, data_dir: Path, jobs_file: Path | None, refresh_demo: bool = False, diversify: bool = False) -> tuple[int, int]:
    candidates = load_json(data_dir / "candidates.json")[:candidates_limit]
    jobs = load_json(jobs_file or data_dir / "jobs.json")[:jobs_limit]
    if diversify:
        candidates.extend(profile for job in jobs for profile in job_variants(job))
    with SessionLocal() as db:
        employer_user = db.scalar(select(User).where(User.email == "seed-recruiter@jobbridge.local"))
        if employer_user is None:
            employer_user = User(email="seed-recruiter@jobbridge.local", password_hash=hash_password(SEED_PASSWORD), role=UserRole.recruiter, is_demo=True)
            db.add(employer_user)
            db.flush()
        employer = db.scalar(select(Employer).where(Employer.user_id == employer_user.user_id))
        if employer is None:
            employer = Employer(user_id=employer_user.user_id, company_name="JobBridge Seed Employers", industry="Technology", location="Nairobi")
            db.add(employer)
            db.flush()

        for item in candidates:
            candidate_id = uuid.UUID(str(item["candidate_id"]))
            existing = db.get(Candidate, candidate_id)
            if existing is not None:
                owner = db.get(User, existing.user_id)
                if refresh_demo and owner and owner.email == f"seed-candidate-{candidate_id.hex[:12]}@jobbridge.local":
                    existing.full_name = kenyan_name(candidate_id)
                    owner.is_demo = True
                continue
            user = User(
                email=f"seed-candidate-{candidate_id.hex[:12]}@jobbridge.local",
                password_hash=hash_password(SEED_PASSWORD),
                role=UserRole.candidate,
                is_demo=True,
            )
            db.add(user)
            db.flush()
            skills = [str(value) for value in item.get("skills", [])]
            certifications = [str(value) for value in item.get("certifications", [])]
            db.add(Candidate(
                candidate_id=candidate_id,
                user_id=user.user_id,
                full_name=kenyan_name(candidate_id),
                location=str(item.get("location") or ""),
                years_experience=int(item.get("years_experience") or 0),
                expected_salary=item.get("expected_salary_kes"),
                work_authorized=item.get("work_authorized"),
                parsed_resume_text=anonymize_resume_text(str(item.get("resume_text") or "")),
                skills=skills,
                certifications=certifications,
            ))
            db.flush()

        for item in jobs:
            job_id = uuid.UUID(str(item["job_id"]))
            if db.get(JobPosting, job_id) is not None:
                continue
            company_name = str(item.get("company_name") or employer.company_name).strip()
            company_key = uuid.uuid5(uuid.NAMESPACE_URL, company_name.casefold()).hex[:16]
            company_user = db.scalar(select(User).where(User.email == f"seed-employer-{company_key}@jobbridge.local"))
            job_employer = db.scalar(select(Employer).where(Employer.user_id == company_user.user_id)) if company_user else db.scalar(select(Employer).where(Employer.company_name == company_name))
            if job_employer is None:
                company_key = uuid.uuid5(uuid.NAMESPACE_URL, company_name.casefold()).hex[:16]
                employer_user = db.scalar(select(User).where(User.email == f"seed-employer-{company_key}@jobbridge.local"))
                if employer_user is None:
                    employer_user = User(email=f"seed-employer-{company_key}@jobbridge.local", password_hash=hash_password(SEED_PASSWORD), role=UserRole.recruiter, is_demo=True)
                    db.add(employer_user)
                    db.flush()
                job_employer = Employer(user_id=employer_user.user_id, company_name=company_name, contact_name=kenyan_name(employer_user.user_id), industry="Imported employer", location=str(item.get("location") or "Kenya"))
                db.add(job_employer)
                db.flush()
            required_skills = [str(value) for value in item.get("required_skills", [])]
            certifications = [str(value) for value in item.get("mandatory_certifications", [])]
            db.add(JobPosting(
                job_id=job_id,
                employer_id=job_employer.employer_id,
                title=str(item.get("title") or "Untitled role"),
                description=str(item.get("description") or ""),
                location=str(item.get("location") or ""),
                required_experience_years=int(item.get("required_experience_years") or 0),
                salary_range_max=item.get("salary_range_max"),
                required_skills=required_skills,
                mandatory_certifications=certifications,
            ))
            db.flush()
        if refresh_demo:
            for owner in db.scalars(select(User).where(User.email.like("seed-%@jobbridge.local"))):
                if not re.fullmatch(r"seed-(?:recruiter|candidate-[0-9a-f]{12}|employer-[0-9a-f]{16})@jobbridge\.local", owner.email):
                    continue
                owner.is_demo = True
                profile = db.scalar(select(Candidate).where(Candidate.user_id == owner.user_id))
                if profile:
                    profile.full_name = kenyan_name(profile.candidate_id)
                company = db.scalar(select(Employer).where(Employer.user_id == owner.user_id))
                if company:
                    company.contact_name = kenyan_name(owner.user_id)
                    if company.company_name == "JobBridge Seed Employers":
                        company.company_name = COMPANIES[0]
        db.commit()
    if not skip_graph:
        with get_neo4j_driver() as driver:
            ensure_graph_schema(driver)
            with SessionLocal() as database:
                sync_graph_events(database, driver, limit=10000)
    return len(candidates), len(jobs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=int, default=25)
    parser.add_argument("--jobs", type=int, default=20)
    parser.add_argument("--skip-graph", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=DATASET)
    parser.add_argument("--jobs-file", type=Path, help="optional normalized jobs JSON, e.g. imported BrighterMonday export")
    parser.add_argument("--refresh-demo", action="store_true", help="rename only explicitly seed-owned candidates")
    parser.add_argument("--diversify", action="store_true", help="add deterministic job-aligned demo profiles; does not assign scores")
    args = parser.parse_args()
    candidates, jobs = seed(args.candidates, args.jobs, args.skip_graph, args.data_dir, args.jobs_file, args.refresh_demo, args.diversify)
    print(f"Seed processed up to {candidates} candidates and {jobs} jobs. Local-only demo accounts use the configured seed password.")


if __name__ == "__main__":
    main()

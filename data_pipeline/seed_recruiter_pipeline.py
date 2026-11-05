"""Give one existing recruiter a full hiring pipeline to work through: open IT roles with unevaluated applicants.

Each role receives existing demo candidates from every fit level the pool can supply. Levels come from the serving
scorer, so they match what "Evaluate" shows later, but no score is stored: every application stays "submitted" and no
match results are written. Only active demo accounts are used, and only where the hard-rule filter passes, mirroring
the candidate apply endpoint. Job ids are deterministic, so re-running skips existing roles and ``--remove`` deletes
exactly these roles without touching the recruiter's other data. Queued Neo4j events drain through the API's worker.

    python data_pipeline/seed_recruiter_pipeline.py --recruiter-email someone@example.org --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.api.matches import _candidate_rule_result, _score_candidate  # noqa: E402
from app.core.hybrid_matcher import _artifact, semantic_similarities  # noqa: E402
from app.db.models import AuditEvent, Candidate, CandidateOpportunity, Employer, JobApplication, JobPosting, JobStatus, OpportunityStatus, User, UserRole  # noqa: E402
from app.db.postgres import SessionLocal  # noqa: E402

NAMESPACE = "jobbridge-recruiter-pipeline-v1"
TIERS = ("great", "good", "mediocre", "bad")
GREAT_SCORE = 0.80
BAD_SCORE = 0.10  # Below this the scorer sees almost nothing relevant; "good" starts at the model's decision threshold.
PER_TIER = 2
# Older seed data parks ineligible profiles here; the label would read as a bug in a recruiter's applicant list.
PLACEHOLDER_LOCATION = "Demo location outside job area"


@dataclass(frozen=True)
class Role:
    key: str
    title: str
    location: str | None  # None = remote: the rule filter then accepts every city.
    years: int
    salary_min: int
    salary_max: int
    needs_authorization: bool
    skills: tuple[str, ...]
    certifications: tuple[str, ...]
    posted_days: int
    summary: str


ROLES = (
    Role("senior-backend", "Senior Backend Engineer (Python)", None, 4, 220000, 340000, True, ("Python", "REST APIs", "SQL", "Docker", "Git"), (), 2, "Lead the design of REST APIs for client platforms, mentor engineers and ship containerised Python services with automated tests."),
    Role("backend", "Backend Developer", None, 2, 130000, 200000, False, ("Python", "REST APIs", "SQL", "Git"), (), 5, "Build and maintain the REST APIs and SQL data layer behind client web platforms, working in Python with code review."),
    Role("frontend", "Frontend Developer (React)", "Nairobi", 2, 110000, 180000, False, ("JavaScript", "React", "REST APIs", "Git"), (), 1, "Build accessible React interfaces for client websites and dashboards, integrating REST APIs on slow mobile connections."),
    Role("full-stack", "Full Stack Developer", None, 3, 150000, 230000, False, ("JavaScript", "React", "Python", "REST APIs", "SQL"), (), 8, "Develop client web portals end to end, from the React front end to the Python API and SQL database."),
    Role("devops", "DevOps Engineer", "Nairobi", 3, 190000, 290000, True, ("Kubernetes", "Docker", "AWS", "CI/CD", "Linux"), ("Certified Kubernetes Administrator",), 3, "Run AWS and Kubernetes infrastructure for client platforms, automate CI/CD pipelines and improve reliability and observability."),
    Role("cloud", "Cloud Engineer", None, 2, 160000, 240000, False, ("AWS", "Docker", "Linux", "CI/CD", "Python"), ("AWS Certified Cloud Practitioner",), 6, "Provision and automate AWS environments for client projects and keep deployments repeatable and cost-efficient."),
    Role("data-analyst", "Data Analyst", "Nairobi", 2, 90000, 150000, False, ("SQL", "Python", "Power BI", "Data Analysis", "Excel"), (), 4, "Turn client operations data into Power BI dashboards and clear weekly reports that managers can act on."),
    Role("data-engineer", "Data Engineer", None, 3, 170000, 260000, False, ("Python", "SQL", "AWS", "Data Analysis", "CI/CD"), (), 9, "Design and run the pipelines that move client sales and inventory data into an AWS data platform for reporting and forecasting."),
    Role("ml-engineer", "Machine Learning Engineer", None, 3, 200000, 320000, False, ("Python", "Machine Learning", "SQL", "Docker", "AWS"), (), 11, "Build and deploy forecasting and recommendation models, and run them as monitored services in production. Remote within Kenya."),
    Role("sysadmin", "Systems Administrator", "Nairobi", 2, 90000, 150000, False, ("Linux", "Networking", "Active Directory", "Git"), (), 7, "Administer Linux servers, networks and user directories for client offices, and keep hosted systems available and patched."),
    Role("business-analyst", "IT Business Analyst", "Nairobi", 2, 100000, 160000, False, ("Business Analysis", "SQL", "Excel", "Process Mapping", "Power BI"), (), 10, "Translate client operations needs into system requirements, run user acceptance testing and report on adoption of new systems."),
    Role("dba", "Database Administrator", None, 4, 140000, 220000, False, ("SQL", "PostgreSQL", "Linux", "Backup and Recovery", "Python"), (), 12, "Own the performance, backups and security of production PostgreSQL databases, and automate routine maintenance tasks."),
    Role("soc-analyst", "Cybersecurity Analyst (SOC)", "Nairobi", 3, 150000, 240000, True, ("Security Monitoring", "Incident Response", "Linux", "Networking", "Python"), ("CompTIA Security+",), 5, "Monitor client environments from a security operations centre, investigate alerts and lead incident response for financial-services clients."),
    Role("qa", "QA Automation Engineer", None, 1, 90000, 150000, False, ("Test Automation", "Python", "Selenium", "CI/CD", "Git"), (), 2, "Write automated test suites for web and API releases and keep them running in the CI/CD pipeline. Remote within Kenya."),
)


def job_id_for(email: str, key: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, ":".join((NAMESPACE, email.casefold(), key)))


def fit_tier(score: float, threshold: float) -> str:
    if score >= GREAT_SCORE:
        return "great"
    if score >= threshold:
        return "good"
    return "mediocre" if score >= BAD_SCORE else "bad"


def _stable_rank(*parts: object) -> str:
    return hashlib.sha256(":".join(str(part) for part in parts).encode()).hexdigest()


def pick_applicants(scores: dict[uuid.UUID, float], threshold: float, job_key: str, used: Counter, per_tier: int = PER_TIER) -> dict[uuid.UUID, str]:
    """Choose up to ``per_tier`` candidates per fit level, preferring those with the fewest applications so far."""
    by_tier: dict[str, list[uuid.UUID]] = {tier: [] for tier in TIERS}
    for candidate_id, score in scores.items():
        by_tier[fit_tier(score, threshold)].append(candidate_id)
    chosen: dict[uuid.UUID, str] = {}
    for tier in TIERS:
        ordered = sorted(by_tier[tier], key=lambda candidate_id: (used[candidate_id], _stable_rank(job_key, candidate_id)))
        for candidate_id in ordered[:per_tier]:
            chosen[candidate_id] = tier
            used[candidate_id] += 1
    return chosen


def _recruiter_employer(db, email: str) -> tuple[User, Employer]:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or user.role != UserRole.recruiter or not user.is_active:
        raise SystemExit(f"{email} is not an active recruiter account; nothing changed")
    employer = db.scalar(select(Employer).where(Employer.user_id == user.user_id))
    if employer is None:
        raise SystemExit(f"{email} has no employer profile; nothing changed")
    return user, employer


def seed(email: str, dry_run: bool) -> None:
    now = datetime.now(UTC)
    threshold = float(_artifact()["decision_threshold"])
    used: Counter = Counter()
    totals: Counter = Counter()
    with SessionLocal() as db:
        recruiter, employer = _recruiter_employer(db, email)
        pool = list(db.scalars(
            select(Candidate).join(User, Candidate.user_id == User.user_id)
            .where(User.is_demo.is_(True), User.is_active.is_(True), Candidate.location != PLACEHOLDER_LOCATION)
            .order_by(Candidate.candidate_id)
        ))
        print(f"{email} ({employer.company_name}): {len(pool)} demo candidates available")
        for role in ROLES:
            job_id = job_id_for(email, role.key)
            if db.get(JobPosting, job_id) is not None:
                print(f"\n{role.title}: already seeded, skipped")
                continue
            posted_at = now - timedelta(days=role.posted_days, hours=len(role.key))
            job = JobPosting(
                job_id=job_id, employer_id=employer.employer_id, title=role.title,
                description=f"{role.summary} Key skills: {', '.join(role.skills)}.", location=role.location,
                required_experience_years=role.years, salary_range_min=Decimal(role.salary_min), salary_range_max=Decimal(role.salary_max),
                requires_work_authorization=role.needs_authorization, required_skills=list(role.skills),
                mandatory_certifications=list(role.certifications) or None, status=JobStatus.open, posted_at=posted_at,
            )
            db.add(job)
            db.flush()
            db.add(AuditEvent(actor_user_id=recruiter.user_id, action="job.created", resource_type="job", resource_id=job_id, created_at=posted_at))

            eligible = [candidate for candidate in pool if _candidate_rule_result(candidate, job).passed]
            semantic = semantic_similarities([candidate.parsed_resume_text or "" for candidate in eligible], job.description) if eligible else []
            scored = {candidate.candidate_id: _score_candidate(candidate, job, value) for candidate, value in zip(eligible, semantic)}
            chosen = pick_applicants({key: result.final_score for key, result in scored.items()}, threshold, role.key, used)

            # Arrival order is shuffled so the applicant list does not give the fit level away.
            arrivals = sorted(chosen, key=lambda candidate_id: _stable_rank("arrival", role.key, candidate_id))
            by_id = {candidate.candidate_id: candidate for candidate in eligible}
            print(f"\n{role.title} | {role.location or 'Remote'} | {len(eligible)} eligible, {len(arrivals)} applied")
            for position, candidate_id in enumerate(arrivals, start=1):
                candidate = by_id[candidate_id]
                applied_at = posted_at + (now - posted_at) * position / (len(arrivals) + 1)
                application_id = db.scalar(
                    insert(JobApplication)
                    .values(candidate_id=candidate_id, job_id=job_id, status="submitted", created_at=applied_at, updated_at=applied_at)
                    .returning(JobApplication.application_id)
                )
                db.execute(insert(CandidateOpportunity).values(candidate_id=candidate_id, job_id=job_id, status=OpportunityStatus.applied, created_at=applied_at, updated_at=applied_at))
                db.add(AuditEvent(actor_user_id=candidate.user_id, action="application.submitted", resource_type="application", resource_id=application_id, created_at=applied_at))
                totals[chosen[candidate_id]] += 1
            for tier in TIERS:
                rows = sorted((scored[key].final_score, by_id[key].full_name) for key in arrivals if chosen[key] == tier)
                print(f"  {tier:<8} " + (", ".join(f"{name} ({score:.2f})" for score, name in reversed(rows)) or "none in the pool"))
            totals["jobs"] += 1
        if dry_run:
            db.rollback()
        else:
            db.commit()
    applicants = sum(totals[tier] for tier in TIERS)
    outcome = "DRY RUN, nothing saved" if dry_run else "Saved"
    print(f"\n{outcome}: {totals['jobs']} jobs, {applicants} applications from {len(used)} candidates (" + ", ".join(f"{tier} {totals[tier]}" for tier in TIERS) + "). No match scores stored.")


def remove(email: str) -> None:
    with SessionLocal() as db:
        _, employer = _recruiter_employer(db, email)
        job_ids = [job_id_for(email, role.key) for role in ROLES]
        owned = list(db.scalars(select(JobPosting.job_id).where(JobPosting.job_id.in_(job_ids), JobPosting.employer_id == employer.employer_id)))
        application_ids = list(db.scalars(select(JobApplication.application_id).where(JobApplication.job_id.in_(owned))))
        db.execute(delete(AuditEvent).where(AuditEvent.resource_id.in_([*owned, *application_ids])))
        # Applications, opportunity activity and any match results cascade from the job.
        db.execute(delete(JobPosting).where(JobPosting.job_id.in_(owned)))
        db.commit()
    print(f"Removed {len(owned)} seeded jobs and their {len(application_ids)} applications from {email}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--recruiter-email", required=True, help="existing recruiter account that will own the roles")
    parser.add_argument("--dry-run", action="store_true", help="show what would be created, then roll back")
    parser.add_argument("--remove", action="store_true", help="delete the roles this script created for that recruiter")
    args = parser.parse_args()
    if args.remove:
        remove(args.recruiter_email)
    else:
        seed(args.recruiter_email, args.dry_run)


if __name__ == "__main__":
    main()

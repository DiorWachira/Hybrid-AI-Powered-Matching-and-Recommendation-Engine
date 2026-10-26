"""Seed fictional recruiters, open IT jobs and applications for the admin recruiter-oversight view.

Every record is deterministic (uuid5) and owned by an ``oversight-*@jobbridge.example.org`` demo account, so
re-running is a no-op and ``--remove`` deletes exactly this data set. Applications are only created where
the serving hard-rule filter passes, mirroring what the candidate apply endpoint allows. No match scores
are written: run "Evaluate all candidates" from the admin view to score a job with the live model.
"""
from __future__ import annotations

import argparse
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from data_pipeline.demo_profiles import kenyan_name  # noqa: E402
from data_pipeline.seed_database import SEED_PASSWORD  # noqa: E402

from app.api.matches import _candidate_rule_result  # noqa: E402
from app.core.text_preprocessing import anonymize_resume_text  # noqa: E402
from app.db.graph_sync import ensure_graph_schema, sync_graph_events  # noqa: E402
from app.db.models import AuditEvent, Candidate, CandidateOpportunity, Employer, JobApplication, JobPosting, JobStatus, OpportunityStatus, User, UserRole  # noqa: E402
from app.db.neo4j_db import get_neo4j_driver  # noqa: E402
from app.db.postgres import SessionLocal  # noqa: E402
from app.utils.security import hash_password  # noqa: E402

NAMESPACE = "jobbridge-oversight-demo-v1"
EMAIL_DOMAIN = "@jobbridge.example.org"

# key, company, industry, location, suspended. Employers span industries; every role they post is a formal IT role.
RECRUITERS = [
    ("savannah-health", "Savannah Health Partners", "Health technology", "Nairobi", False),
    ("pwani-logistics", "Pwani Logistics Hub", "Logistics technology", "Mombasa", False),
    ("mavuno-agritech", "Mavuno AgriTech", "Agricultural technology", "Nakuru", False),
    ("kilele-fintech", "Kilele Fintech", "Financial technology", "Nairobi", False),
    ("ziwa-hospitality", "Ziwa Hospitality Group", "Hospitality IT", "Kisumu", False),
    ("nuru-learning", "Nuru Learning Collective", "Education technology", "Eldoret", False),
    ("bahari-creative", "Bahari Digital Agency", "Digital services", "Nairobi", False),
    ("imara-compliance", "Imara Cyber & Compliance", "Cybersecurity", "Nairobi", False),
    # Suspended on purpose: its open roles surface under "Needs attention" in the oversight view.
    ("kipepeo-staffing", "Kipepeo IT Staffing", "IT staffing", "Nairobi", True),
]

# recruiter, key, title, location (None = remote), min years, salary min/max (KES/month), needs work authorization,
# skills, certifications, posted days ago, hires, summary. Skills reuse the training vocabulary where one exists
# (Python, SQL, Docker, AWS, ...) so the epoch-19 features see familiar inputs.
JOBS = [
    ("savannah-health", "health-data-analyst", "Health Data Analyst", "Nairobi", 2, 90000, 140000, True, ["SQL", "Python", "Power BI", "Data Analysis", "Excel"], ["Google Data Analytics"], 3, 1, "Analyse patient-flow and clinical operations data across our clinics and build Power BI dashboards for hospital management."),
    ("savannah-health", "his-integration-engineer", "Health Information Systems Integration Engineer", "Nairobi", 3, 160000, 240000, True, ["Python", "REST APIs", "SQL", "Linux", "Git"], [], 6, 0, "Integrate electronic medical record, laboratory and billing systems through secure REST APIs and maintain the integration services on Linux."),
    ("savannah-health", "it-support-lead", "IT Support Team Lead", "Nairobi", 4, 90000, 130000, False, ["Linux", "Active Directory", "ITIL", "Networking", "Excel"], [], 9, 0, "Lead a five-person service desk supporting clinical staff, manage user accounts and keep incident resolution within agreed service levels."),
    ("pwani-logistics", "backend-developer-logistics", "Backend Developer (Fleet Platform)", "Mombasa", 3, 150000, 220000, False, ["Python", "REST APIs", "SQL", "Docker", "Git"], [], 2, 0, "Build the APIs behind our fleet-tracking platform, process GPS events at scale and ship containerised services with automated tests."),
    ("pwani-logistics", "data-engineer", "Data Engineer", "Mombasa", 3, 170000, 250000, False, ["Python", "SQL", "AWS", "Data Analysis", "CI/CD"], ["AWS Certified Cloud Practitioner"], 5, 0, "Design and run the pipelines that move shipment and warehouse data into our AWS data platform for reporting and forecasting."),
    ("pwani-logistics", "erp-systems-analyst", "ERP Systems Analyst", "Mombasa", 2, 110000, 160000, True, ["Business Analysis", "SQL", "Excel", "Process Mapping", "Financial Accounting"], [], 19, 0, "Gather requirements from finance and operations, configure the ERP and document business processes for a multi-site logistics business."),
    ("mavuno-agritech", "full-stack-developer", "Full Stack Developer", "Nakuru", 2, 130000, 190000, False, ["JavaScript", "React", "Python", "REST APIs", "SQL"], [], 4, 0, "Develop the web portal farmers and buyers use to trade produce, from React front end to Python API and SQL database."),
    ("mavuno-agritech", "gis-data-analyst", "GIS Data Analyst", "Nakuru", 1, 80000, 120000, False, ["Data Analysis", "Python", "SQL", "QGIS", "Excel"], [], 7, 0, "Map and analyse farm boundaries, yields and weather data, and turn them into decision-ready reports for the agronomy team."),
    ("mavuno-agritech", "ml-engineer", "Machine Learning Engineer", None, 3, 200000, 300000, False, ["Python", "Machine Learning", "SQL", "Docker", "AWS"], [], 10, 0, "Build and deploy crop-yield and price-forecasting models, and run them as monitored services in production. Remote within Kenya."),
    ("kilele-fintech", "senior-backend-engineer", "Senior Backend Engineer (Python)", "Nairobi", 5, 250000, 380000, True, ["Python", "REST APIs", "SQL", "Docker", "Kubernetes", "CI/CD"], [], 1, 0, "Lead the design of our payments APIs, mentor engineers and own reliability for services running on Kubernetes."),
    ("kilele-fintech", "mobile-developer", "Mobile Developer (Flutter)", None, 2, 150000, 230000, False, ["Flutter", "Dart", "REST APIs", "Git", "Firebase"], [], 4, 0, "Ship features for a consumer savings app in Flutter, integrate REST APIs and keep the app fast on low-end devices. Remote."),
    ("kilele-fintech", "devops-engineer", "DevOps Engineer", "Nairobi", 3, 200000, 300000, True, ["Kubernetes", "Docker", "AWS", "CI/CD", "Linux"], ["Certified Kubernetes Administrator"], 8, 1, "Run our AWS and Kubernetes infrastructure, automate CI/CD pipelines and improve observability for a regulated payments platform."),
    ("ziwa-hospitality", "systems-administrator", "Systems Administrator", "Kisumu", 3, 90000, 140000, False, ["Linux", "Networking", "Active Directory", "Docker", "Git"], [], 3, 0, "Administer servers, networks and user directories across our hotels, and keep property-management and booking systems available."),
    ("ziwa-hospitality", "software-engineer-booking", "Software Engineer (Booking Platform)", "Kisumu", 2, 120000, 180000, False, ["Python", "REST APIs", "SQL", "Git", "JavaScript"], [], 12, 0, "Extend our online booking engine, integrate payment and channel-manager APIs and fix production issues quickly."),
    ("ziwa-hospitality", "it-business-analyst", "IT Business Analyst", "Kisumu", 2, 100000, 150000, False, ["Business Analysis", "SQL", "Excel", "Process Mapping", "Power BI"], [], 6, 0, "Translate hotel operations needs into system requirements, run user acceptance testing and report on adoption."),
    ("nuru-learning", "frontend-developer", "Frontend Developer (React)", "Eldoret", 2, 110000, 170000, False, ["JavaScript", "React", "TypeScript", "REST APIs", "Git"], [], 5, 0, "Build accessible React interfaces for our learning platform used by thousands of learners on mobile connections."),
    ("nuru-learning", "database-administrator", "Database Administrator", "Eldoret", 4, 140000, 200000, False, ["SQL", "PostgreSQL", "Linux", "Backup and Recovery", "Python"], [], 21, 0, "Own the performance, backups and security of our PostgreSQL databases, and automate routine maintenance tasks."),
    ("nuru-learning", "qa-engineer", "QA Automation Engineer", None, 1, 90000, 140000, False, ["Test Automation", "Python", "Selenium", "CI/CD", "Git"], [], 2, 0, "Write automated test suites for web and API releases and keep them running in the CI/CD pipeline. Remote."),
    ("bahari-creative", "ui-ux-designer", "UI/UX Designer", "Nairobi", 3, 120000, 180000, False, ["Figma", "User Research", "Prototyping", "Usability Testing", "UI Design"], [], 4, 0, "Lead research and design for client web and mobile products, from discovery interviews to tested, production-ready prototypes."),
    ("bahari-creative", "web-developer", "Web Developer", "Nairobi", 1, 80000, 130000, False, ["JavaScript", "React", "REST APIs", "Git", "SQL"], [], 7, 0, "Build and maintain client websites and web apps, integrating content-management and analytics APIs."),
    ("bahari-creative", "cloud-engineer", "Cloud Engineer", None, 2, 160000, 240000, False, ["AWS", "Docker", "Linux", "CI/CD", "Python"], ["AWS Certified Cloud Practitioner"], 3, 0, "Provision and automate AWS environments for client projects and keep deployments repeatable and cost-efficient. Remote."),
    ("imara-compliance", "security-analyst", "Cybersecurity Analyst (SOC)", "Nairobi", 3, 150000, 230000, True, ["Security Monitoring", "Incident Response", "Linux", "Networking", "Python"], ["CompTIA Security+"], 6, 1, "Monitor client environments from our security operations centre, investigate alerts and lead incident response."),
    ("imara-compliance", "it-auditor", "IT Auditor", "Nairobi", 3, 140000, 210000, True, ["IT Audit", "Risk Assessment", "SQL", "Excel", "Business Analysis"], ["CISA"], 9, 0, "Audit IT general controls and data integrity for financial-services clients, and report findings to audit committees."),
    ("imara-compliance", "penetration-tester", "Penetration Tester", "Nairobi", 2, 160000, 240000, True, ["Penetration Testing", "Linux", "Networking", "Python", "Web Application Security"], [], 2, 0, "Plan and run authorised penetration tests of client web applications and networks, and write clear remediation reports."),
    ("kipepeo-staffing", "it-helpdesk-technician", "IT Helpdesk Technician (Contract)", "Nairobi", 1, 50000, 75000, False, ["Technical Support", "Active Directory", "Networking", "Linux", "Excel"], [], 8, 0, "Provide first-line IT support to a corporate client on a six-month contract, resolving tickets and onboarding staff devices."),
    ("kipepeo-staffing", "junior-data-analyst", "Junior Data Analyst (Contract)", "Nairobi", 0, 60000, 90000, False, ["SQL", "Excel", "Power BI", "Data Analysis", "Python"], [], 11, 0, "Prepare weekly sales and operations reports for a retail client, cleaning data in SQL and Excel and publishing Power BI dashboards."),
]

# Pipeline stage by fit and by how long the role has been up: fresh postings are still unreviewed, older
# ones have shortlisted strong applicants and rejected stretch ones. A job's "hires" value converts strong
# applicants to hired; the job itself always stays open.
def _stage(variant: str, posted_days: int) -> str:
    if posted_days <= 2:
        return "submitted"
    if variant == "strong":
        return "shortlisted"
    if variant == "solid":
        return "reviewing" if posted_days >= 5 else "submitted"
    return "rejected" if posted_days >= 7 else "submitted"

OTHER_CITY = {"Nairobi": "Kisumu", "Mombasa": "Nairobi", "Nakuru": "Eldoret", "Kisumu": "Mombasa", "Eldoret": "Nakuru"}


def _id(*parts: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, ":".join((NAMESPACE, *parts)))


def _candidates_for(job: tuple) -> list[dict]:
    _, key, title, location, years, _, salary_max, needs_auth, skills, certs, *_ = job
    city = location or "Nairobi"
    profiles = []
    for variant in ("strong", "solid", "stretch"):
        candidate_id = _id("candidate", key, variant)
        held = skills if variant == "strong" else skills[:4] if variant == "solid" else skills[:2]
        if variant == "strong":
            resume = f"{title} with {years + 4} years of experience. Delivered results using {', '.join(held)}. Comfortable leading others and improving processes."
        elif variant == "solid":
            resume = f"{title} with {years} years of hands-on experience in {', '.join(held)}. Reliable team member looking to grow."
        else:
            resume = f"Early-career professional moving into {title.lower()} work. Coursework and internship exposure to {', '.join(held)}."
        profiles.append({
            "candidate_id": candidate_id, "variant": variant,
            # Every third job's stretch candidate lives elsewhere, so the location rule filters them out.
            "location": OTHER_CITY.get(city, "Nairobi") if variant == "stretch" and len(key) % 3 == 0 else city,
            # About half the stretch candidates fall a year short of the minimum, so the rules filter them out.
            "years_experience": years + 4 if variant == "strong" else years if variant == "solid" or len(key) % 2 else max(0, years - 1),
            "expected_salary": Decimal(salary_max) * Decimal("0.9" if variant == "strong" else "0.8" if variant == "solid" else "0.6"),
            "work_authorized": True if needs_auth else variant != "stretch",
            "skills": held, "certifications": certs if variant != "stretch" else [], "resume_text": resume,
        })
    return profiles


def _demo_user(db, email: str, role: UserRole, *, active: bool = True) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, password_hash=hash_password(SEED_PASSWORD), role=role, is_demo=True, is_active=active)
        db.add(user)
        db.flush()
    return user


def seed(skip_graph: bool) -> dict[str, int]:
    now = datetime.now(UTC)
    counts = {"recruiters": 0, "jobs": 0, "candidates": 0, "applications": 0, "filtered_by_rules": 0}
    with SessionLocal() as db:
        employers = {}
        for key, company, industry, location, suspended in RECRUITERS:
            user = _demo_user(db, f"oversight-recruiter-{key}{EMAIL_DOMAIN}", UserRole.recruiter, active=not suspended)
            employer = db.scalar(select(Employer).where(Employer.user_id == user.user_id))
            if employer is None:
                employer = Employer(user_id=user.user_id, company_name=company, contact_name=kenyan_name(user.user_id), industry=industry, location=location)
                db.add(employer)
                db.flush()
                counts["recruiters"] += 1
            employers[key] = (employer, user)

        for job_spec in JOBS:
            recruiter, key, title, location, years, salary_min, salary_max, needs_auth, skills, certs, posted_days, hires, summary = job_spec
            employer, recruiter_user = employers[recruiter]
            job_id = _id("job", key)
            posted_at = now - timedelta(days=posted_days, hours=len(key))
            job = db.get(JobPosting, job_id)
            if job is None:
                job = JobPosting(
                    job_id=job_id, employer_id=employer.employer_id, title=title,
                    description=f"{summary} Key skills: {', '.join(skills)}.", location=location,
                    required_experience_years=years, salary_range_min=Decimal(salary_min), salary_range_max=Decimal(salary_max),
                    requires_work_authorization=needs_auth, required_skills=skills, mandatory_certifications=certs or None,
                    status=JobStatus.open, posted_at=posted_at,
                )
                db.add(job)
                db.flush()
                db.add(AuditEvent(actor_user_id=recruiter_user.user_id, action="job.created", resource_type="job", resource_id=job_id, created_at=posted_at))
                counts["jobs"] += 1

            hires_left = hires
            for index, profile in enumerate(_candidates_for(job_spec)):
                candidate = db.get(Candidate, profile["candidate_id"])
                if candidate is None:
                    user = _demo_user(db, f"oversight-candidate-{profile['candidate_id'].hex[:12]}{EMAIL_DOMAIN}", UserRole.candidate)
                    candidate = Candidate(
                        candidate_id=profile["candidate_id"], user_id=user.user_id, full_name=kenyan_name(profile["candidate_id"]),
                        location=profile["location"], years_experience=profile["years_experience"],
                        expected_salary=profile["expected_salary"], work_authorized=profile["work_authorized"],
                        parsed_resume_text=anonymize_resume_text(profile["resume_text"]),
                        skills=profile["skills"], certifications=profile["certifications"],
                    )
                    db.add(candidate)
                    db.flush()
                    counts["candidates"] += 1
                # Stale-demo jobs (posted 14+ days ago) are deliberately left without applicants.
                if posted_days >= 14:
                    continue
                if not _candidate_rule_result(candidate, job).passed:
                    counts["filtered_by_rules"] += 1
                    continue
                stage = _stage(profile["variant"], posted_days)
                if profile["variant"] == "strong" and hires_left:
                    stage, hires_left = "hired", hires_left - 1
                applied_at = posted_at + timedelta(hours=6 + 11 * index)
                application_id = db.scalar(
                    insert(JobApplication)
                    .values(candidate_id=candidate.candidate_id, job_id=job_id, status=stage, created_at=applied_at, updated_at=min(now, applied_at + timedelta(days=1)))
                    .on_conflict_do_nothing(constraint="uq_application_candidate_job")
                    .returning(JobApplication.application_id)
                )
                if application_id is None:
                    continue
                db.execute(
                    insert(CandidateOpportunity)
                    .values(candidate_id=candidate.candidate_id, job_id=job_id, status=OpportunityStatus.applied, created_at=applied_at, updated_at=applied_at)
                    .on_conflict_do_update(constraint="uq_candidate_opportunity", set_={"status": OpportunityStatus.applied})
                )
                db.add(AuditEvent(actor_user_id=candidate.user_id, action="application.submitted", resource_type="application", resource_id=application_id, created_at=applied_at))
                counts["applications"] += 1
        db.commit()

    if not skip_graph:
        with get_neo4j_driver() as driver:
            ensure_graph_schema(driver)
            with SessionLocal() as database:
                counts["graph_events_synced"] = sync_graph_events(database, driver, limit=10000)
    return counts


def remove() -> int:
    with SessionLocal() as db:
        # Employer, candidate, job, application and activity rows cascade from the owning users.
        removed = db.execute(delete(User).where(User.email.like("oversight-%" + EMAIL_DOMAIN), User.is_demo.is_(True)).returning(User.user_id)).scalars().all()
        db.commit()
    return len(removed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-graph", action="store_true", help="leave queued Neo4j projection events for the graph worker")
    parser.add_argument("--remove", action="store_true", help="delete every oversight demo account and the records it owns")
    args = parser.parse_args()
    if args.remove:
        print(f"Removed {remove()} oversight demo accounts and their dependent records.")
        return
    counts = seed(args.skip_graph)
    print("Oversight demo seed: " + ", ".join(f"{name}={value}" for name, value in counts.items()))
    print("Demo accounts use the configured local seed password.")


if __name__ == "__main__":
    main()

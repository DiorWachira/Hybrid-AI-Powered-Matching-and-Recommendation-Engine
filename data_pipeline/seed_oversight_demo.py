"""Seed fictional recruiters, open jobs and applications for the admin recruiter-oversight view.

Every record is deterministic (uuid5) and owned by an ``oversight-*@jobbridge.local`` demo account, so
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
EMAIL_DOMAIN = "@jobbridge.local"

# key, company, industry, location, suspended
RECRUITERS = [
    ("savannah-health", "Savannah Health Partners", "Healthcare", "Nairobi", False),
    ("pwani-logistics", "Pwani Logistics Hub", "Logistics", "Mombasa", False),
    ("mavuno-agritech", "Mavuno AgriTech", "Agriculture", "Nakuru", False),
    ("kilele-fintech", "Kilele Fintech", "Financial technology", "Nairobi", False),
    ("ziwa-hospitality", "Ziwa Hospitality Group", "Hospitality", "Kisumu", False),
    ("nuru-learning", "Nuru Learning Collective", "Education", "Eldoret", False),
    ("bahari-creative", "Bahari Creative Agency", "Marketing", "Nairobi", False),
    ("imara-compliance", "Imara Legal & Compliance", "Legal and HR", "Nairobi", False),
    # Suspended on purpose: its open role surfaces under "Needs attention" in the oversight view.
    ("kipepeo-staffing", "Kipepeo Staffing Services", "Recruitment agency", "Nairobi", True),
]

# recruiter, key, title, location (None = remote), min years, salary min/max (KES/month), needs work authorization,
# skills, certifications, posted days ago, hires, summary
JOBS = [
    ("savannah-health", "registered-nurse", "Registered Nurse (Medical Ward)", "Nairobi", 2, 65000, 95000, True, ["patient assessment", "medication administration", "infection control", "electronic health records", "triage"], ["Nursing Council of Kenya licence"], 3, 1, "Deliver safe ward-level care for adult medical patients, coordinate with clinicians on care plans and keep accurate electronic records."),
    ("savannah-health", "clinical-officer", "Clinical Officer, Outpatient", "Nairobi", 3, 80000, 120000, True, ["clinical diagnosis", "patient counselling", "prescribing", "case documentation", "community outreach"], ["Clinical Officers Council licence"], 6, 0, "Run outpatient consultations, diagnose and treat common conditions, and refer complex cases within a busy urban clinic."),
    ("savannah-health", "lab-technologist", "Medical Laboratory Technologist", "Nairobi", 2, 55000, 85000, True, ["haematology", "microbiology", "sample processing", "quality control", "laboratory information systems"], ["KMLTTB registration"], 9, 0, "Process and analyse clinical samples, maintain quality-control records and report results through the laboratory information system."),
    ("pwani-logistics", "fleet-coordinator", "Fleet Operations Coordinator", "Mombasa", 3, 70000, 110000, False, ["fleet management", "route planning", "GPS tracking", "vendor management", "excel"], [], 2, 0, "Schedule and track a regional truck fleet, plan routes from the port and manage maintenance vendors to keep deliveries on time."),
    ("pwani-logistics", "warehouse-supervisor", "Warehouse Supervisor", "Mombasa", 4, 60000, 90000, False, ["inventory control", "warehouse management systems", "team leadership", "health and safety", "stock reconciliation"], [], 5, 0, "Lead a shift team in a bonded warehouse, keep inventory accurate in the WMS and enforce health and safety procedures."),
    ("pwani-logistics", "customs-agent", "Customs Clearing Agent", "Mombasa", 2, 50000, 80000, True, ["customs documentation", "tariff classification", "iCMS", "freight forwarding", "client communication"], ["KRA customs agent licence"], 19, 0, "Prepare and lodge import and export documentation, classify goods and liaise with clients and port authorities."),
    ("mavuno-agritech", "agronomist", "Field Agronomist", "Nakuru", 3, 60000, 95000, False, ["crop management", "soil testing", "integrated pest management", "farmer training", "data collection"], [], 4, 0, "Advise contracted smallholder farmers on crop health, run soil tests and train farmer groups on sustainable practices."),
    ("mavuno-agritech", "farm-data-officer", "Farm Data Officer", "Nakuru", 1, 45000, 70000, False, ["data collection", "kobotoolbox", "excel", "data cleaning", "field reporting"], [], 7, 0, "Collect and clean farm-level data with mobile survey tools and produce weekly field reports for the agronomy team."),
    ("mavuno-agritech", "supply-chain-analyst", "Agri Supply Chain Analyst", None, 2, 75000, 115000, False, ["supply chain analysis", "sql", "demand forecasting", "power bi", "procurement"], [], 10, 0, "Analyse produce sourcing and distribution data, forecast demand and build dashboards for procurement decisions. Remote within Kenya."),
    ("kilele-fintech", "backend-engineer", "Backend Engineer (Python)", "Nairobi", 3, 180000, 280000, True, ["python", "fastapi", "postgresql", "docker", "rest apis", "unit testing"], [], 1, 0, "Build and operate payment APIs in Python and FastAPI on PostgreSQL, with automated tests and containerised deployments."),
    ("kilele-fintech", "mobile-developer", "Mobile Developer (Flutter)", None, 2, 150000, 230000, False, ["flutter", "dart", "rest apis", "firebase", "ui design"], [], 4, 0, "Ship features for a consumer savings app in Flutter, integrate REST APIs and keep the app fast on low-end devices. Remote."),
    ("kilele-fintech", "risk-analyst", "Credit Risk Analyst", "Nairobi", 3, 140000, 210000, True, ["credit risk modelling", "python", "sql", "statistics", "regulatory reporting"], ["CFA Level I"], 8, 1, "Develop and monitor credit scoring models for digital loans and prepare risk reports for management and regulators."),
    ("ziwa-hospitality", "front-office-manager", "Front Office Manager", "Kisumu", 4, 70000, 100000, False, ["guest relations", "hotel property management systems", "team leadership", "revenue management", "complaint resolution"], [], 3, 0, "Lead the front desk of a lakeside hotel, manage reservations in the PMS and own the guest experience from arrival to departure."),
    ("ziwa-hospitality", "executive-chef", "Executive Chef", "Kisumu", 6, 110000, 160000, False, ["menu planning", "kitchen management", "food safety", "cost control", "team leadership"], ["Food handler certificate"], 12, 0, "Run a high-volume kitchen, design seasonal menus around local produce and control food costs and hygiene standards."),
    ("ziwa-hospitality", "events-coordinator", "Events Coordinator", "Kisumu", 2, 45000, 70000, False, ["event planning", "vendor management", "budgeting", "client communication", "social media"], [], 6, 0, "Plan and deliver conferences and weddings, coordinate vendors and keep events on budget and on schedule."),
    ("nuru-learning", "maths-teacher", "Secondary Mathematics Teacher", "Eldoret", 2, 50000, 75000, True, ["mathematics instruction", "lesson planning", "student assessment", "classroom management", "cbc curriculum"], ["TSC registration"], 5, 0, "Teach mathematics to secondary learners, plan CBC-aligned lessons and track learner progress through regular assessment."),
    ("nuru-learning", "curriculum-designer", "Curriculum Designer", "Eldoret", 4, 80000, 120000, False, ["instructional design", "cbc curriculum", "assessment design", "content writing", "learning management systems"], [], 21, 0, "Design competency-based learning units and assessments, and publish them to the learning platform for partner schools."),
    ("nuru-learning", "edtech-support", "EdTech Support Specialist", None, 1, 40000, 60000, False, ["technical support", "learning management systems", "user training", "troubleshooting", "documentation"], [], 2, 0, "Support teachers and learners on the digital learning platform, resolve tickets and run onboarding sessions. Remote."),
    ("bahari-creative", "digital-marketer", "Digital Marketing Specialist", "Nairobi", 3, 90000, 140000, False, ["seo", "google ads", "social media marketing", "content strategy", "google analytics"], [], 4, 0, "Plan and run paid and organic campaigns for client brands, track performance in analytics and report on ROI."),
    ("bahari-creative", "graphic-designer", "Graphic Designer", "Nairobi", 2, 60000, 95000, False, ["adobe illustrator", "adobe photoshop", "brand identity", "typography", "figma"], [], 7, 0, "Create brand identities, campaign visuals and social assets for agency clients, from concept to final artwork."),
    ("bahari-creative", "content-writer", "Content Writer", None, 1, 45000, 75000, False, ["copywriting", "seo", "editing", "research", "content strategy"], [], 3, 0, "Write blog posts, web copy and social content for client brands, optimised for search and edited to a high standard. Remote."),
    ("imara-compliance", "hr-business-partner", "HR Business Partner", "Nairobi", 5, 150000, 220000, True, ["employee relations", "performance management", "kenyan labour law", "talent acquisition", "hr analytics"], ["IHRM membership"], 6, 1, "Partner with business leaders on people strategy, employee relations and performance, in line with Kenyan labour law."),
    ("imara-compliance", "compliance-officer", "Compliance Officer (AML)", "Nairobi", 3, 120000, 180000, True, ["anti-money laundering", "kyc", "regulatory reporting", "risk assessment", "policy development"], ["ACAMS certification"], 9, 0, "Run AML and KYC monitoring, assess compliance risk and prepare regulatory reports for financial-services clients."),
    ("imara-compliance", "legal-assistant", "Legal Assistant", "Nairobi", 1, 45000, 70000, False, ["legal research", "document drafting", "case management", "client communication", "filing"], [], 2, 0, "Support advocates with legal research, drafting, court filings and client correspondence."),
    ("kipepeo-staffing", "customer-service-agent", "Customer Service Agent", "Nairobi", 1, 35000, 50000, False, ["customer service", "call handling", "crm software", "complaint resolution", "communication"], [], 8, 0, "Handle inbound customer calls and chats for a telecoms client, resolve complaints and log every case in the CRM."),
    ("kipepeo-staffing", "sales-executive", "Field Sales Executive", "Nairobi", 2, 40000, 65000, False, ["field sales", "negotiation", "lead generation", "crm software", "customer relationships"], [], 11, 0, "Win and grow retail accounts across Nairobi, meet monthly sales targets and keep the CRM pipeline up to date."),
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

from decimal import Decimal
from threading import Lock
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import require_roles
from app.api.matches import _score_candidate
from app.core.hybrid_matcher import _artifact
from app.core.rate_limit import limiter
from app.db.models import Candidate, JobPosting, JobStatus, User, UserRole

router = APIRouter(prefix="/admin/simulation", tags=["simulation"])
simulation_lock = Lock()


def build_simulation() -> dict:
    run_id = uuid4()
    employer_id = uuid4()
    jobs = [
        JobPosting(job_id=uuid4(), employer_id=employer_id, title="Logistics Data Analyst", description="Analyse parcel delivery delays and settlement ledgers for a Nairobi logistics team. Build SQL reporting queries, Python validation scripts and Excel reconciliation workbooks. Present clear weekly service metrics.", location="Nairobi", required_experience_years=2, salary_range_max=Decimal("120000"), requires_work_authorization=True, required_skills=["SQL", "Python", "Excel"], mandatory_certifications=[], status=JobStatus.open),
        JobPosting(job_id=uuid4(), employer_id=employer_id, title="Backend API Developer", description="Build a reliable parcel-tracking API in Python for a Nairobi logistics team. Design REST APIs, write SQL queries, use Git reviews and test delivery-status updates and webhook retries.", location="Nairobi", required_experience_years=3, salary_range_max=Decimal("180000"), requires_work_authorization=True, required_skills=["Python", "SQL", "Git", "REST APIs"], mandatory_certifications=[], status=JobStatus.open),
    ]
    profiles = [
        ("Amina Njeri", 4, "Nairobi", "70000", True, ["SQL", "Python", "Excel", "Power BI"], ["Microsoft Power BI"], "I investigate missed parcel deliveries with SQL and Python. I maintain Excel settlement reconciliations, publish weekly courier performance reports and explain anomalies to dispatch supervisors."),
        ("Brian Otieno", 5, "Nairobi", "110000", True, ["Python", "SQL", "Git", "REST APIs"], [], "I build Python parcel-tracking services and REST APIs. My work includes SQL query optimisation, Git code review, integration tests and reliable webhook retry handling."),
        ("Wanjiku Kariuki", 1, "Nairobi", "35000", True, ["SQL", "Excel"], [], "During a junior placement I cleaned courier delivery spreadsheets and wrote simple SQL summaries. I am learning Python and need support with production reporting pipelines."),
        ("Musa Hassan", 4, "Nairobi", "90000", False, ["Python", "SQL", "Git", "REST APIs"], [], "I maintain Python dispatch APIs with SQL persistence and Git-based review. I can implement delivery callbacks and automated tests, but do not currently hold the required work authorization."),
        ("Faith Achieng", 6, "Nairobi", "65000", True, ["Financial Accounting", "Taxation", "Auditing"], ["CPA"], "I prepare statutory accounts, tax submissions and audit evidence for small businesses. My background is financial compliance rather than software delivery or operational data engineering."),
        ("Peter Mwangi", 6, "Mombasa", "200000", True, ["Python", "SQL", "Git", "REST APIs"], [], "I lead a coastal technology team delivering Python integration services and SQL-backed APIs. I use Git reviews and require a Mombasa-based role within my stated salary expectations."),
    ]
    candidates = [Candidate(candidate_id=uuid4(), user_id=uuid4(), full_name=name, years_experience=years, location=location, expected_salary=Decimal(salary), work_authorized=authorized, skills=skills, certifications=certifications, parsed_resume_text=resume) for name, years, location, salary, authorized, skills, certifications, resume in profiles]
    artifact = _artifact()
    events, matches = [], []

    def event(kind, message, candidate=None, job=None):
        events.append({"sequence": len(events) + 1, "kind": kind, "message": message, "candidate_id": str(candidate.candidate_id) if candidate else None, "job_id": str(job.job_id) if job else None})

    for job in jobs:
        event("job_posted", f"Demo employer posted {job.title}.", job=job)
    attempts = [(0, 0), (1, 1), (2, 0), (3, 1), (4, 0), (5, 1)]
    for candidate_index, job_index in attempts:
        candidate, job = candidates[candidate_index], jobs[job_index]
        event("candidate_joined", f"{candidate.full_name}'s fictional profile is ready.", candidate=candidate)
        event("application_attempted", f"{candidate.full_name} applied for {job.title}.", candidate, job)
        scored = _score_candidate(candidate, job)
        candidate_skills = {skill.casefold() for skill in candidate.skills}
        matched = [skill for skill in job.required_skills if skill.casefold() in candidate_skills]
        missing = [skill for skill in job.required_skills if skill.casefold() not in candidate_skills]
        score = {**scored.model_dump(mode="json"), "job_id": str(job.job_id), "matched_skills": matched, "missing_skills": missing, "above_threshold": scored.hard_rule_passed and scored.final_score >= artifact["decision_threshold"]}
        matches.append(score)
        if not scored.hard_rule_passed:
            event("application_blocked", f"Eligibility check blocked {candidate.full_name}: {'; '.join(scored.rule_reasons)}", candidate, job)
            continue
        event("application_submitted", f"{candidate.full_name} passed eligibility; sandbox application submitted.", candidate, job)
        event("match_scored", f"{candidate.full_name}: model score {scored.final_score:.1%}.", candidate, job)
        event("reviewing", f"Demo recruiter opened {candidate.full_name}'s application.", candidate, job)
        if score["above_threshold"]:
            event("shortlisted", f"Demo decision: {candidate.full_name} shortlisted for an interview.", candidate, job)
        else:
            event("review_required", f"Demo decision: {candidate.full_name} remains under review; score is below the model threshold.", candidate, job)
    event("completed", "Sandbox scenario complete. No live jobs, accounts or applications were changed.")
    return {
        "run_id": str(run_id), "sandbox": True, "model_version": artifact["model_version"], "encoder_revision": artifact.get("encoder_revision"), "decision_threshold": artifact["decision_threshold"],
        "candidates": [{"candidate_id": str(candidate.candidate_id), "full_name": candidate.full_name, "years_experience": candidate.years_experience, "location": candidate.location, "expected_salary": float(candidate.expected_salary), "work_authorized": candidate.work_authorized, "skills": candidate.skills, "certifications": candidate.certifications, "resume_text": candidate.parsed_resume_text} for candidate in candidates],
        "jobs": [{"job_id": str(job.job_id), "title": job.title, "description": job.description, "location": job.location, "required_experience_years": job.required_experience_years, "salary_range_max": float(job.salary_range_max), "required_skills": job.required_skills} for job in jobs],
        "matches": matches, "events": events,
    }


@router.post("")
@limiter.limit("3/minute")
def simulate(request: Request, user: User = Depends(require_roles(UserRole.admin))):
    if not simulation_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A simulation is being prepared. Try again shortly.")
    try:
        return build_simulation()
    except (OSError, RuntimeError, ValueError):
        raise HTTPException(status_code=503, detail="The simulation model could not be loaded. Check the backend model cache and try again.") from None
    finally:
        simulation_lock.release()
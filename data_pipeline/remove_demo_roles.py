"""Delete demo postings that do not belong on the platform: non-IT Accountant roles and test-named roles.

Only exact titles match, and only on demo or throwaway @example.com owners. A posting that a real person applied to is
kept and reported. Applications, activity and match results cascade from the job, and the API's worker removes the job
from Neo4j. Owner accounts and audit history stay. Matching JobRole nodes are removed from the graph directly.

    python data_pipeline/remove_demo_roles.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import delete, select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.models import Candidate, Employer, JobApplication, JobPosting, User  # noqa: E402
from app.db.neo4j_db import get_neo4j_driver  # noqa: E402
from app.db.postgres import SessionLocal  # noqa: E402

TITLES = ("Accountant", "Verification API Role", "Week 2 DevOps Role", "API Demo DevOps Role")


def owner_is_disposable(email: str, is_demo: bool) -> bool:
    return is_demo or email.casefold().endswith("@example.com")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="list the postings without deleting them")
    args = parser.parse_args()
    with SessionLocal() as db:
        rows = db.execute(
            select(JobPosting.job_id, JobPosting.title, JobPosting.location, User.email, User.is_demo)
            .join(Employer, JobPosting.employer_id == Employer.employer_id).join(User, Employer.user_id == User.user_id)
            .where(JobPosting.title.in_(TITLES)).order_by(JobPosting.title, User.email, JobPosting.location)
        ).all()
        removable = []
        for job_id, title, location, email, is_demo in rows:
            real_applicants = db.scalar(
                select(JobApplication.application_id).join(Candidate, JobApplication.candidate_id == Candidate.candidate_id)
                .join(User, Candidate.user_id == User.user_id).where(JobApplication.job_id == job_id, User.is_demo.is_(False)).limit(1)
            )
            if not owner_is_disposable(email, is_demo):
                print(f"KEPT, real owner: {title} | {location} | {email}")
            elif real_applicants:
                print(f"KEPT, real applicant: {title} | {location} | {email}")
            else:
                removable.append(job_id)
                print(f"{'Would remove' if args.dry_run else 'Removing'}: {title} | {location or 'Remote'} | {email}")
        if args.dry_run:
            print(f"DRY RUN, nothing deleted: {len(removable)} of {len(rows)} matching postings would go.")
            return
        db.execute(delete(JobPosting).where(JobPosting.job_id.in_(removable)))
        db.commit()
    with get_neo4j_driver() as driver, driver.session(database="neo4j") as graph:
        roles = graph.run("MATCH (role:JobRole) WHERE role.title IN $titles WITH role, role.title AS title DETACH DELETE role RETURN count(title) AS removed", titles=list(TITLES)).single()["removed"]
    print(f"Removed {len(removable)} of {len(rows)} matching postings and {roles} graph JobRole nodes.")


if __name__ == "__main__":
    main()

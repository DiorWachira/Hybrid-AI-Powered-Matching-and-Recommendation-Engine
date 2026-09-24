from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.models import Candidate, Employer, JobPosting, MatchResult, User, UserRole
from app.db.postgres import get_db
from app.schemas import AdminOverviewResponse, JobResponse, ProfileResponse

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/overview", response_model=AdminOverviewResponse)
def read_admin_overview(
    user: User = Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminOverviewResponse:
    recent_users = list(db.scalars(select(User).order_by(User.created_at.desc()).limit(10)))
    recent_jobs = list(db.scalars(select(JobPosting).order_by(JobPosting.posted_at.desc()).limit(10)))
    return AdminOverviewResponse(
        users_count=db.scalar(select(func.count()).select_from(User)) or 0,
        candidates_count=db.scalar(select(func.count()).select_from(Candidate)) or 0,
        employers_count=db.scalar(select(func.count()).select_from(Employer)) or 0,
        jobs_count=db.scalar(select(func.count()).select_from(JobPosting)) or 0,
        match_results_count=db.scalar(select(func.count()).select_from(MatchResult)) or 0,
        recent_users=[ProfileResponse(user_id=item.user_id, email=item.email, role=item.role) for item in recent_users],
        recent_jobs=[JobResponse.model_validate(item) for item in recent_jobs],
    )
from decimal import Decimal
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.db.models import JobStatus, OpportunityStatus, UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: UserRole
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    company_name: str | None = Field(default=None, min_length=2, max_length=255)
    industry: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value

    @field_validator("full_name")
    @classmethod
    def normalise_name(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordResetRequest(BaseModel):
    token: str = Field(min_length=40, max_length=100)
    new_password: str = Field(min_length=12, max_length=72)

    @field_validator("new_password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class ResetAuthorization(BaseModel):
    password: str = Field(min_length=1, max_length=72)


class OntologySkillRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=255)

    @field_validator("name", "category", "source")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Value must not be blank")
        return value.strip()


class OntologyRelationRequest(BaseModel):
    source_skill: str = Field(min_length=1, max_length=120)
    target_skill: str = Field(min_length=1, max_length=120)
    weight: float = Field(ge=0, le=1, allow_inf_nan=False)
    source: str = Field(min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_relation(self):
        if not all(value.strip() for value in (self.source_skill, self.target_skill, self.source)):
            raise ValueError("Values must not be blank")
        if self.source_skill.strip().casefold() == self.target_skill.strip().casefold():
            raise ValueError("Source and target skills must differ")
        return self


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole


class JobCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=20, max_length=20_000)
    location: str | None = Field(default=None, max_length=120)
    required_experience_years: int = Field(default=0, ge=0, le=60)
    salary_range_max: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    salary_range_min: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    requires_work_authorization: bool = False
    required_skills: list[str] = Field(default_factory=list, max_length=50)
    mandatory_certifications: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_salary_range(self):
        if self.salary_range_min is not None and self.salary_range_max is not None and self.salary_range_min > self.salary_range_max:
            raise ValueError("salary_range_min must not exceed salary_range_max")
        return self

    @field_validator("required_skills", "mandatory_certifications")
    @classmethod
    def tidy_certifications(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    posted_at: datetime | None = None
    title: str
    description: str
    location: str | None
    required_experience_years: int
    salary_range_max: Decimal | None
    salary_range_min: Decimal | None = None
    requires_work_authorization: bool = False
    required_skills: list[str] | None
    mandatory_certifications: list[str] | None
    status: str


class JobUpdateRequest(JobCreateRequest):
    status: JobStatus = JobStatus.open


class ApplicationStatusUpdate(BaseModel):
    status: Literal["reviewing", "shortlisted", "rejected", "hired"]


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_id: UUID
    candidate_id: UUID
    job_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime


class ApplicantResponse(ApplicationResponse):
    candidate_name: str
    candidate_location: str | None
    years_experience: int
    skills: list[str]
    certifications: list[str]


class CandidateApplicationResponse(ApplicationResponse):
    job_title: str
    company_name: str
    job_location: str | None
    job_status: str


class StoredMatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    match_id: UUID
    candidate_id: UUID
    job_id: UUID
    hard_rule_passed: bool
    matching_status: str
    similarity_score: float | None
    growth_score: float | None
    skill_overlap_score: float | None
    final_weighted_score: float | None
    skill_gap_breakdown: dict | None
    model_version: str | None
    created_at: datetime


class ProfileResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    role: UserRole


class CandidateProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    location: str | None = Field(default=None, max_length=120)
    years_experience: int = Field(default=0, ge=0, le=60)
    expected_salary: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    work_authorized: bool | None = None
    parsed_resume_text: str | None = Field(default=None, max_length=20_000)
    skills: list[str] = Field(default_factory=list, max_length=50)
    certifications: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("skills", "certifications")
    @classmethod
    def tidy_profile_values(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class CandidateProfileResponse(CandidateProfileUpdate):
    candidate_id: UUID
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @field_validator("skills", "certifications", mode="before")
    @classmethod
    def normalise_nullable_arrays(cls, value: list[str] | None) -> list[str]:
        return value or []


class OpportunityResponse(BaseModel):
    job_id: UUID
    title: str
    company_name: str
    description: str
    location: str | None
    salary_range_max: Decimal | None
    required_experience_years: int
    required_skills: list[str]
    mandatory_certifications: list[str]
    match_score: float
    status: OpportunityStatus | None


class CandidateDashboardResponse(BaseModel):
    available_opportunities: list[OpportunityResponse]
    for_you: list[OpportunityResponse]
    history: list[OpportunityResponse]


class OpportunityActionRequest(BaseModel):
    status: OpportunityStatus


class MatchCandidateResponse(BaseModel):
    match_id: UUID | None = None
    matched_skills: list[str] | None = None
    missing_skills: list[str] | None = None
    model_version: str | None = None
    candidate_id: UUID
    full_name: str
    hard_rule_passed: bool
    rule_reasons: list[str]
    skill_overlap: float
    semantic_score: float
    growth_score: float
    final_score: float


class MatchEvaluationResponse(BaseModel):
    job_id: UUID
    evaluated_at: datetime | None = None
    candidates: list[MatchCandidateResponse]


class AdminUserResponse(BaseModel):
    user_id: UUID
    email: str
    role: UserRole
    display_name: str
    company_name: str | None = None
    is_active: bool
    is_demo: bool
    created_at: datetime


class AccountStatusUpdate(BaseModel):
    is_active: bool


class JobStatusUpdate(BaseModel):
    status: JobStatus


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    event_id: UUID
    actor_user_id: UUID | None
    action: str
    resource_type: str
    resource_id: UUID | None
    details: dict | None
    created_at: datetime


class AdminOverviewResponse(BaseModel):
    users_count: int
    candidates_count: int
    employers_count: int
    jobs_count: int
    match_results_count: int
    applications_count: int
    pending_graph_events: int
    suspended_users_count: int
    recent_users: list[AdminUserResponse]
    recent_jobs: list[JobResponse]
    recent_activity: list[AuditEventResponse]

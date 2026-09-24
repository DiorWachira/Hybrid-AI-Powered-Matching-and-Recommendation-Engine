from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.db.models import OpportunityStatus, UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    role: UserRole
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    company_name: str | None = Field(default=None, min_length=2, max_length=255)
    industry: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)

    @field_validator("full_name")
    @classmethod
    def normalise_name(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


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
    required_skills: list[str] = Field(default_factory=list, max_length=50)
    mandatory_certifications: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("required_skills", "mandatory_certifications")
    @classmethod
    def tidy_certifications(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: UUID
    title: str
    description: str
    location: str | None
    required_experience_years: int
    salary_range_max: Decimal | None
    required_skills: list[str] | None
    mandatory_certifications: list[str] | None
    status: str


class ProfileResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    role: UserRole


class CandidateProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    location: str | None = Field(default=None, max_length=120)
    years_experience: int = Field(default=0, ge=0, le=60)
    expected_salary: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
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
    candidates: list[MatchCandidateResponse]


class AdminOverviewResponse(BaseModel):
    users_count: int
    candidates_count: int
    employers_count: int
    jobs_count: int
    match_results_count: int
    recent_users: list[ProfileResponse]
    recent_jobs: list[JobResponse]

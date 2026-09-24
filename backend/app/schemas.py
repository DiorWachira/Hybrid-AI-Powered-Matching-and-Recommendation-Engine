from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.db.models import UserRole


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
    mandatory_certifications: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("mandatory_certifications")
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
    mandatory_certifications: list[str] | None
    status: str


class ProfileResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    role: UserRole

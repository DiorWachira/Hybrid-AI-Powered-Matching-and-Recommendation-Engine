from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    candidate = "candidate"
    recruiter = "recruiter"
    admin = "admin"


class JobStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    candidate_profile = relationship("Candidate", back_populates="user", uselist=False)
    employer_profile = relationship("Employer", back_populates="user", uselist=False)


class Candidate(Base):
    __tablename__ = "candidates"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    location: Mapped[Optional[str]] = mapped_column(String(120))
    years_experience: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_salary: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    expected_salary: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    parsed_resume_text: Mapped[Optional[str]] = mapped_column(Text)
    embedding_vector: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    user = relationship("User", back_populates="candidate_profile")
    matches = relationship("MatchResult", back_populates="candidate")


class Employer(Base):
    __tablename__ = "employers"

    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[Optional[str]] = mapped_column(String(120))
    location: Mapped[Optional[str]] = mapped_column(String(120))

    user = relationship("User", back_populates="employer_profile")
    job_postings = relationship("JobPosting", back_populates="employer")


class JobPosting(Base):
    __tablename__ = "job_postings"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    employer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employers.employer_id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required_experience_years: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    salary_range_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    location: Mapped[Optional[str]] = mapped_column(String(120))
    mandatory_certifications: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(120)))
    embedding_vector: Mapped[Optional[dict]] = mapped_column(JSONB)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.open, nullable=False
    )

    employer = relationship("Employer", back_populates="job_postings")
    matches = relationship("MatchResult", back_populates="job")


class MatchResult(Base):
    __tablename__ = "match_results"

    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.job_id", ondelete="CASCADE"), nullable=False)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.candidate_id", ondelete="CASCADE"), nullable=False)
    hard_rule_passed: Mapped[bool] = mapped_column(nullable=False)
    similarity_score: Mapped[Optional[float]] = mapped_column(Float)
    growth_score: Mapped[Optional[float]] = mapped_column(Float)
    final_weighted_score: Mapped[Optional[float]] = mapped_column(Float)
    skill_gap_breakdown: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    job = relationship("JobPosting", back_populates="matches")
    candidate = relationship("Candidate", back_populates="matches")

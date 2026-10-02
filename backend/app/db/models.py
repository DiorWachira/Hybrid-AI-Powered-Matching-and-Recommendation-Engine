from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, Computed, DateTime, Enum, Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
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


class OpportunityStatus(str, enum.Enum):
    saved = "saved"
    applied = "applied"
    viewed = "viewed"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    candidate_profile = relationship("Candidate", back_populates="user", uselist=False)
    employer_profile = relationship("Employer", back_populates="user", uselist=False)


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        CheckConstraint("years_experience >= 0", name="ck_candidate_experience"),
        CheckConstraint("expected_salary >= 0", name="ck_candidate_salary"),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    location: Mapped[Optional[str]] = mapped_column(String(120))
    years_experience: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_salary: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    expected_salary: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    work_authorized: Mapped[Optional[bool]] = mapped_column(Boolean)
    parsed_resume_text: Mapped[Optional[str]] = mapped_column(Text)
    skills: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(120)))
    certifications: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(120)))
    embedding_vector: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    user = relationship("User", back_populates="candidate_profile")
    matches = relationship("MatchResult", back_populates="candidate")
    opportunity_activity = relationship("CandidateOpportunity", back_populates="candidate")


class Employer(Base):
    __tablename__ = "employers"

    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[Optional[str]] = mapped_column(String(255))
    industry: Mapped[Optional[str]] = mapped_column(String(120))
    location: Mapped[Optional[str]] = mapped_column(String(120))

    user = relationship("User", back_populates="employer_profile")
    job_postings = relationship("JobPosting", back_populates="employer")


class JobPosting(Base):
    __tablename__ = "job_postings"
    __table_args__ = (
        CheckConstraint("required_experience_years >= 0", name="ck_job_experience"),
        CheckConstraint("salary_range_min >= 0 AND salary_range_max >= 0", name="ck_job_salary_nonnegative"),
        CheckConstraint("salary_range_min <= salary_range_max", name="ck_job_salary_order"),
        Index("ix_job_employer", "employer_id"),
        Index("ix_job_status_posted", "status", "posted_at"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    employer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("employers.employer_id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required_experience_years: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    salary_range_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    salary_range_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    requires_work_authorization: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(120))
    required_skills: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(120)))
    mandatory_certifications: Mapped[Optional[list[str]]] = mapped_column(ARRAY(String(120)))
    embedding_vector: Mapped[Optional[dict]] = mapped_column(JSONB)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.open, nullable=False
    )
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    employer = relationship("Employer", back_populates="job_postings")
    matches = relationship("MatchResult", back_populates="job")
    opportunity_activity = relationship("CandidateOpportunity", back_populates="job")


class CandidateOpportunity(Base):
    __tablename__ = "candidate_opportunities"
    __table_args__ = (UniqueConstraint("candidate_id", "job_id", name="uq_candidate_opportunity"),)

    activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.candidate_id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.job_id", ondelete="CASCADE"), nullable=False)
    status: Mapped[OpportunityStatus] = mapped_column(Enum(OpportunityStatus, name="opportunity_status"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    candidate = relationship("Candidate", back_populates="opportunity_activity")
    job = relationship("JobPosting", back_populates="opportunity_activity")


class MatchResult(Base):
    __tablename__ = "match_results"
    __table_args__ = (
        CheckConstraint("final_weighted_score BETWEEN 0 AND 1", name="ck_match_score"),
        Index("ix_match_candidate_created", "candidate_id", "created_at"),
        Index("ix_match_job_score", "job_id", "final_weighted_score"),
        Index("ix_match_results_candidate_id", "candidate_id"),
        Index("ix_match_results_job_id", "job_id"),
    )

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
    skill_overlap_score: Mapped[Optional[float]] = mapped_column(Float)
    model_version: Mapped[Optional[str]] = mapped_column(String(120))
    matching_status: Mapped[str] = mapped_column(String(16), Computed("CASE WHEN hard_rule_passed THEN 'eligible' ELSE 'filtered' END", persisted=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

    job = relationship("JobPosting", back_populates="matches")
    candidate = relationship("Candidate", back_populates="matches")


class JobApplication(Base):
    __tablename__ = "job_applications"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_application_candidate_job"),
        CheckConstraint("status IN ('submitted', 'reviewing', 'shortlisted', 'rejected', 'hired', 'withdrawn')", name="ck_application_status"),
        Index("ix_application_job_status", "job_id", "status"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("candidates.candidate_id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.job_id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="submitted", server_default="submitted", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class GraphSyncEvent(Base):
    __tablename__ = "graph_sync_events"
    __table_args__ = (
        CheckConstraint("entity_type IN ('candidate', 'job', 'application')", name="ck_graph_sync_entity"),
        Index("ix_graph_sync_created", "created_at"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_created", "created_at"),)

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.user_id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    details: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"))

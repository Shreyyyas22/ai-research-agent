import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ResearchJob(Base):
    __tablename__ = "research_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    tasks: Mapped[list["ResearchTask"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    sources: Mapped[list["Source"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )
    report: Mapped["Report | None"] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        uselist=False,
    )
    evaluations: Mapped[list["ReportEvaluation"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )


class ResearchTask(Base):
    __tablename__ = "research_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    search_queries: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    job: Mapped["ResearchJob"] = relationship(
        back_populates="tasks",
    )


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    job: Mapped["ResearchJob"] = relationship(
        back_populates="sources",
    )
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "url",
            name="uq_sources_job_url",
        ),
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    excerpt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    source: Mapped["Source"] = relationship(
        back_populates="evidence",
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    executive_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    key_findings: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    detailed_analysis: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    conclusion: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    trade_offs: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    limitations: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    job: Mapped["ResearchJob"] = relationship(
        back_populates="report",
    )


class ReportEvaluation(Base):
    __tablename__ = "report_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    iteration: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    grounded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    citation_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    hallucination_detected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    reasoning: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    unsupported_claims: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    job: Mapped["ResearchJob"] = relationship(
        back_populates="evaluations",
    )
    report: Mapped["Report"] = relationship()
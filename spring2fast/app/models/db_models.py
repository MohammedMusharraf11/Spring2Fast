"""Database models for migration job tracking."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Enum as SqlEnum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobStatus(str, Enum):
    """Supported migration job states."""

    PENDING = "pending"
    INGESTING = "ingesting"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    MIGRATING = "migrating"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class MigrationJob(Base):
    """Tracks progress for a migration request."""

    __tablename__ = "migration_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32))
    source_url: Mapped[str] = mapped_column(Text)
    branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        SqlEnum(JobStatus),
        default=JobStatus.PENDING,
        nullable=False,
    )
    current_step: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

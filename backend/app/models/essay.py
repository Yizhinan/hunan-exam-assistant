"""Essay submission and grading result models."""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, Text, ForeignKey, func
from sqlalchemy.dialects.sqlite import JSON  # Use SQLite JSON (works with PostgreSQL too)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import gen_uuid


class EssaySubmission(Base):
    """An essay submitted for grading."""

    __tablename__ = "essay_submissions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=gen_uuid
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    material: Mapped[str | None] = mapped_column(Text, nullable=True)  # 给定资料/参考材料
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending / grading / completed / error

    # Grading result
    total_score: Mapped[float] = mapped_column(Float, nullable=True)
    grade: Mapped[str] = mapped_column(String(20), nullable=True)
    grading_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<EssaySubmission {self.id} score={self.total_score}>"

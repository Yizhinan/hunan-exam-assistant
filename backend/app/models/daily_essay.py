"""Daily recommended essay model — 每日范文推荐."""

from datetime import datetime, date

from sqlalchemy import String, Integer, DateTime, Text, Date, Boolean, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import gen_uuid

# 岗位类别
CATEGORY_XZ = "行政执法"
CATEGORY_XX = "县乡基层"
CATEGORY_SSZ = "省市直"
CATEGORY_ZH = "综合通用"

EXAM_CATEGORIES = [CATEGORY_XZ, CATEGORY_XX, CATEGORY_SSZ, CATEGORY_ZH]


class DailyEssay(Base):
    """A curated model essay recommended for daily study."""

    __tablename__ = "daily_essays"
    __table_args__ = (
        UniqueConstraint("recommend_date", "exam_category", name="uq_date_category"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=gen_uuid
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(200), nullable=True)
    source_name: Mapped[str] = mapped_column(String(200), nullable=True)
    source_url: Mapped[str] = mapped_column(String(2000), nullable=True)

    # 岗位类别: 行政执法 / 县乡基层 / 省市直 / 综合通用
    exam_category: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CATEGORY_ZH, index=True
    )

    recommend_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    highlights: Mapped[str] = mapped_column(Text, nullable=True)
    key_points: Mapped[str] = mapped_column(Text, nullable=True)

    view_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<DailyEssay {self.recommend_date} [{self.exam_category}] — {self.title}>"

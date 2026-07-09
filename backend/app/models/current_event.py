"""Current event model for general-knowledge exam prep — 时政大事件."""

from datetime import datetime, date

from sqlalchemy import String, Integer, DateTime, Text, Date, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import gen_uuid

# 领域分类
CATEGORIES = ["科技", "政治党建", "经济", "文化", "体育", "外交", "民生", "生态"]

# 考试相关度
RELEVANCE_BIBEI = "必知"
RELEVANCE_LIAOJIE = "了解"
RELEVANCE_TUOZHAN = "拓展"
RELEVANCE_LEVELS = [RELEVANCE_BIBEI, RELEVANCE_LIAOJIE, RELEVANCE_TUOZHAN]


class CurrentEvent(Base):
    """A major current event relevant to civil-service exam prep."""

    __tablename__ = "current_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=gen_uuid
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)

    category: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    relevance: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RELEVANCE_LIAOJIE, index=True
    )

    source: Mapped[str | None] = mapped_column(String(500), nullable=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<CurrentEvent [{self.category}] {self.title}>"

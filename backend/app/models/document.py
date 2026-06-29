"""Document model for tracking knowledge base uploads."""

from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.user import gen_uuid


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=gen_uuid
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    doc_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # exam / policy / news / model
    source_url: Mapped[str] = mapped_column(String(2000), nullable=True)
    source_name: Mapped[str] = mapped_column(String(200), nullable=True)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)  # pdf / md / txt
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending / ingested / error
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Document {self.title} [{self.doc_type}]>"

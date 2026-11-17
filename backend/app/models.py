import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.config import settings
from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Category(Base):
    """One row per official YouTube category. `embedding` is the vector
    anchor computed once at seed time from representative seed phrases."""

    __tablename__ = "categories"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))


class ClassificationCache(Base):
    """Caches the result for a given (title, channel) pair so the same
    video is never re-embedded or re-sent to the LLM twice. Also doubles
    as the example pool for the RAG retrieval step — past classifications
    with high confidence become few-shot examples for ambiguous new ones."""

    __tablename__ = "classification_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    video_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(256))
    text_embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))
    category_key: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float)
    focus_score: Mapped[float] = mapped_column(Float, default=0.5)
    method: Mapped[str] = mapped_column(String(32))  # "embedding" | "llm"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TrustedChannel(Base):
    """A channel the user manually marked as 'always allow', bypassing
    classification entirely regardless of confidence."""

    __tablename__ = "trusted_channels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    channel: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_categories: Mapped[list] = mapped_column(JSON, default=list)
    debug: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

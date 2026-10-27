import uuid
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.auth.models import Base


class DemoUpload(Base):
    __tablename__ = "demo_uploads"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    storage_name: Mapped[str] = mapped_column(String(64), unique=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    work_bytes: Mapped[int] = mapped_column(BigInteger, server_default="0")
    status: Mapped[str] = mapped_column(String(20), index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    demo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("demo_uploads.id", ondelete="CASCADE"), unique=True)
    map_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    score: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    parser_version: Mapped[str] = mapped_column(String(32))
    analysis_version: Mapped[str] = mapped_column(String(32))
    facts: Mapped[dict] = mapped_column(JSON)


class MatchPlayer(Base):
    __tablename__ = "match_players"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    steam_id64: Mapped[str | None] = mapped_column(String(20), nullable=True)
    name: Mapped[str] = mapped_column(String(128))
    team: Mapped[str | None] = mapped_column(String(32), nullable=True)
    kills: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deaths: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assists: Mapped[int | None] = mapped_column(Integer, nullable=True)
    headshots: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MatchRound(Base):
    __tablename__ = "match_rounds"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    match_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    winner: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tick: Mapped[int | None] = mapped_column(Integer, nullable=True)

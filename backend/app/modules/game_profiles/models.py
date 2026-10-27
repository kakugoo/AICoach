import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.auth.models import Base


class FaceitProfile(Base):
    __tablename__ = "faceit_profiles"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    faceit_player_id: Mapped[uuid.UUID] = mapped_column(unique=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(64), nullable=False)
    steam_id64: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    profile_url: Mapped[str] = mapped_column(String(512), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    elo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skill_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TrackedProfile(Base):
    __tablename__ = "tracked_profiles"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("faceit_profiles.id", ondelete="CASCADE"), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

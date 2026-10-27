import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert

from app.modules.auth.models import User
from app.modules.auth.router import Db
from app.modules.auth.service import current_user, guard_origin, limit_attempts
from app.modules.game_profiles.client import FaceitClient, Player, get_faceit_client
from app.modules.game_profiles.models import FaceitProfile, TrackedProfile

router = APIRouter(prefix="/game-profiles", tags=["game profiles"])
Client = Annotated[FaceitClient, Depends(get_faceit_client)]


class AddProfile(BaseModel):
    faceit_player_id: uuid.UUID


class SavedProfile(Player):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    updated_at: datetime
    added_at: datetime
    is_primary: bool = False


def throttled(db: Db, request: Request, user_id: uuid.UUID) -> None:
    limit_attempts(db.get_bind(), request.client.host if request.client else "unknown",
                   str(user_id), "faceit")


def persist_profile(db: Db, player: Player) -> FaceitProfile:
    values = player.model_dump() | {"updated_at": datetime.now(UTC), "id": uuid.uuid4()}
    stmt = insert(FaceitProfile).values(**values)
    stmt = stmt.on_conflict_do_update(index_elements=[FaceitProfile.faceit_player_id],
                                      set_={k: v for k, v in values.items() if k not in ("id", "faceit_player_id")})
    profile_id = db.scalar(stmt.returning(FaceitProfile.id))
    return db.get(FaceitProfile, profile_id)


def saved(profile: FaceitProfile, added_at: datetime, is_primary: bool = False) -> SavedProfile:
    return SavedProfile(**Player.model_validate(profile, from_attributes=True).model_dump(),
                        id=profile.id, updated_at=profile.updated_at, added_at=added_at, is_primary=is_primary)


@router.get("/status")
def status(request: Request, db: Db, client: Client) -> dict[str, bool]:
    current_user(db, request)
    return {"configured": bool(client.api_key)}


@router.get("/search", response_model=Player)
def search(request: Request, response: Response, db: Db, client: Client,
           nickname: Annotated[str, Query(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]) -> Player:
    user = current_user(db, request)
    response.headers["Cache-Control"] = "no-store"
    if not client.api_key:
        raise HTTPException(503, "FACEIT integration is not configured")
    throttled(db, request, user.id)
    return client.search(nickname)


@router.get("", response_model=list[SavedProfile])
def list_profiles(request: Request, response: Response, db: Db) -> list[SavedProfile]:
    user = current_user(db, request)
    response.headers["Cache-Control"] = "no-store"
    rows = db.execute(select(FaceitProfile, TrackedProfile.added_at, TrackedProfile.is_primary).join(
        TrackedProfile, TrackedProfile.profile_id == FaceitProfile.id).where(
            TrackedProfile.user_id == user.id).order_by(TrackedProfile.added_at.desc())).all()
    return [saved(profile, added_at, is_primary) for profile, added_at, is_primary in rows]


@router.post("", response_model=SavedProfile, status_code=201)
def add_profile(data: AddProfile, request: Request, db: Db, client: Client) -> SavedProfile:
    guard_origin(request)
    user = current_user(db, request)
    if not client.api_key:
        raise HTTPException(503, "FACEIT integration is not configured")
    throttled(db, request, user.id)
    player = client.get_player(data.faceit_player_id)
    profile = persist_profile(db, player)
    stmt = insert(TrackedProfile).values(user_id=user.id, profile_id=profile.id).on_conflict_do_nothing()
    added_at = db.scalar(stmt.returning(TrackedProfile.added_at))
    if added_at is None:
        db.rollback()
        raise HTTPException(409, "Profile already tracked")
    result = saved(profile, added_at)
    db.commit()
    return result


@router.post("/{profile_id}/refresh", response_model=SavedProfile)
def refresh_profile(profile_id: uuid.UUID, request: Request, db: Db, client: Client) -> SavedProfile:
    guard_origin(request)
    user = current_user(db, request)
    tracked = db.get(TrackedProfile, (user.id, profile_id))
    if not tracked:
        raise HTTPException(404, "Tracked profile not found")
    if not client.api_key:
        raise HTTPException(503, "FACEIT integration is not configured")
    throttled(db, request, user.id)
    profile = db.get(FaceitProfile, profile_id)
    updated = persist_profile(db, client.get_player(profile.faceit_player_id))
    db.refresh(updated)
    result = saved(updated, tracked.added_at, tracked.is_primary)
    db.commit()
    return result


@router.post("/{profile_id}/primary", status_code=204)
def set_primary(profile_id: uuid.UUID, request: Request, db: Db) -> None:
    guard_origin(request)
    user = current_user(db, request)
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    tracked = db.get(TrackedProfile, (user.id, profile_id))
    if not tracked:
        raise HTTPException(404, "Tracked profile not found")
    db.execute(update(TrackedProfile).where(TrackedProfile.user_id == user.id).values(is_primary=False))
    db.execute(update(TrackedProfile).where(TrackedProfile.user_id == user.id,
                                           TrackedProfile.profile_id == profile_id).values(is_primary=True))
    db.commit()


@router.delete("/{profile_id}/primary", status_code=204)
def clear_primary(profile_id: uuid.UUID, request: Request, db: Db) -> None:
    guard_origin(request)
    user = current_user(db, request)
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    tracked = db.get(TrackedProfile, (user.id, profile_id))
    if not tracked:
        raise HTTPException(404, "Tracked profile not found")
    tracked.is_primary = False
    db.commit()


@router.delete("/{profile_id}", status_code=204)
def remove_profile(profile_id: uuid.UUID, request: Request, db: Db) -> None:
    guard_origin(request)
    user = current_user(db, request)
    result = db.execute(delete(TrackedProfile).where(TrackedProfile.user_id == user.id,
                                                      TrackedProfile.profile_id == profile_id))
    if result.rowcount == 0:
        raise HTTPException(404, "Tracked profile not found")
    db.commit()

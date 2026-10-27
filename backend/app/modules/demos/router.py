import hashlib
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.modules.auth.router import Db
from app.modules.auth.service import current_user, guard_origin
from app.modules.demos.comparison import compare, rates
from app.modules.demos.models import DemoUpload, Match, MatchPlayer, MatchRound
from app.modules.demos.parser_ids import steam_id
from app.modules.demos.personalization import personal_result
from app.modules.game_profiles.models import FaceitProfile, LocalGameProfile, TrackedProfile

router = APIRouter(prefix="/demos", tags=["demos"])
MAGIC = b"PBDEMS2\x00"


def primary_steam(db: Db, user_id: uuid.UUID) -> str | None:
    local = db.get(LocalGameProfile, user_id)
    if local and local.is_primary:
        return local.steam_id64
    return db.scalar(select(FaceitProfile.steam_id64).join(
        TrackedProfile, TrackedProfile.profile_id == FaceitProfile.id).where(
            TrackedProfile.user_id == user_id, TrackedProfile.is_primary.is_(True)))


class DemoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    original_name: str
    size_bytes: int
    status: str
    error: str | None
    created_at: datetime
    completed_at: datetime | None


def storage() -> Path:
    root = Path(get_settings().demo_storage_dir).resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def owned(db: Db, request: Request, demo_id: uuid.UUID) -> DemoUpload:
    user = current_user(db, request)
    job = db.scalar(select(DemoUpload).where(DemoUpload.id == demo_id, DemoUpload.owner_id == user.id))
    if not job:
        raise HTTPException(404, "Demo not found")
    return job


@router.get("/limits")
def limits(request: Request, db: Db) -> dict:
    current_user(db, request)
    return {"max_bytes": get_settings().demo_max_bytes, "max_uncompressed_bytes": get_settings().demo_max_uncompressed_bytes}


@router.post("", response_model=DemoOut, status_code=201)
async def upload(request: Request, db: Db, filename: Annotated[str, Query(min_length=1, max_length=255)]) -> DemoUpload:
    guard_origin(request)
    user = current_user(db, request)
    safe_name = filename.replace("\\", "/").split("/")[-1]
    if any(ord(char) < 32 for char in safe_name):
        raise HTTPException(422, "Invalid filename")
    compressed = safe_name.lower().endswith(".zst")
    if not (safe_name.lower().endswith(".dem") or compressed) or len(safe_name) < 5:
        raise HTTPException(415, "Only .dem, .dem.zst and .zst files are supported")
    length = request.headers.get("content-length", "")
    if not length.isascii() or not length.isdigit():
        raise HTTPException(411, "Content length required")
    size = int(length)
    settings = get_settings()
    if size < len(MAGIC):
        raise HTTPException(422, "File is empty or invalid")
    if size > settings.demo_max_bytes:
        raise HTTPException(413, "File exceeds size limit")
    root = storage()
    # Reservation under transaction lock bounds total concurrent uploads as well as stored files.
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 0x43533255})
    used = db.scalar(select(func.coalesce(func.sum(DemoUpload.size_bytes + DemoUpload.work_bytes), 0))) or 0
    reserved = db.scalar(select(func.coalesce(func.sum(DemoUpload.size_bytes), 0)).where(
        DemoUpload.status == "uploaded")) or 0
    work_reserved = db.scalar(select(func.coalesce(func.sum(DemoUpload.work_bytes), 0))) or 0
    if used + size > settings.demo_quota_bytes or shutil.disk_usage(root).free < reserved + work_reserved + size + 104857600:
        raise HTTPException(507, "Not enough storage space")
    job = DemoUpload(id=uuid.uuid4(), owner_id=user.id, original_name=safe_name,
                     storage_name=f"{uuid.uuid4().hex}.dem" + (".zst" if compressed else ""), size_bytes=size, status="uploaded")
    db.add(job)
    db.commit()
    db.refresh(job)
    temp = root / (job.storage_name + ".part")
    target = root / job.storage_name
    digest = hashlib.sha256()
    written = 0
    prefix = b""
    try:
        with temp.open("xb") as output:
            async for chunk in request.stream():
                written += len(chunk)
                if written > size or written > settings.demo_max_bytes:
                    raise HTTPException(413, "File exceeds size limit")
                if len(prefix) < len(MAGIC):
                    prefix += chunk[:len(MAGIC) - len(prefix)]
                output.write(chunk)
                digest.update(chunk)
        expected_magic = b"\x28\xb5\x2f\xfd" if compressed else MAGIC
        if written != size or not prefix.startswith(expected_magic):
            raise HTTPException(422, "Invalid or incomplete CS2 demo")
        temp.replace(target)
        job.checksum = digest.hexdigest()
        job.status = "queued"
        db.commit()
        db.refresh(job)
        return job
    except BaseException:
        temp.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        db.rollback()
        job = db.get(DemoUpload, job.id)
        if job:
            db.delete(job)
            db.commit()
        raise


@router.get("", response_model=list[DemoOut])
def list_demos(request: Request, response: Response, db: Db) -> list[DemoUpload]:
    user = current_user(db, request)
    response.headers["Cache-Control"] = "no-store"
    return list(db.scalars(select(DemoUpload).where(DemoUpload.owner_id == user.id).order_by(DemoUpload.created_at.desc())))


@router.get("/summary")
def demo_summary(request: Request, response: Response, db: Db) -> dict:
    user = current_user(db, request)
    response.headers["Cache-Control"] = "no-store"
    rows = db.execute(select(DemoUpload, Match).outerjoin(Match, Match.demo_id == DemoUpload.id)
                      .where(DemoUpload.owner_id == user.id).order_by(DemoUpload.created_at.desc())).all()
    steam = primary_steam(db, user.id)
    match_ids = [match.id for job, match in rows[:5] if match and job.status == "completed"]
    players = db.scalars(select(MatchPlayer).where(MatchPlayer.match_id.in_(match_ids))).all() if match_ids else []
    return {"total": len(rows), "completed": sum(job.status == "completed" for job, _ in rows),
            "processing": sum(job.status in ("uploaded", "queued", "processing") for job, _ in rows),
            "failed": sum(job.status == "failed" for job, _ in rows),
            "recent": [{"id": str(job.id), "created_at": job.created_at.isoformat(), "status": job.status,
                        "map_name": match.map_name if match and job.status == "completed" else None,
                        "score": match.score if match and job.status == "completed" else None,
                        "personal": personal_result(steam, [p for p in players if p.match_id == match.id],
                                                    match.score, match.analysis_version)
                                    if match and job.status == "completed" else None,
                        "original_name": job.original_name} for job, match in rows[:5]]}


@router.get("/{demo_id}")
def detail(demo_id: uuid.UUID, request: Request, response: Response, db: Db) -> dict:
    job = owned(db, request, demo_id)
    response.headers["Cache-Control"] = "no-store"
    result = {"demo": DemoOut.model_validate(job).model_dump(mode="json"), "match": None}
    match = db.scalar(select(Match).where(Match.demo_id == job.id))
    if match and job.status == "completed":
        players = db.scalars(select(MatchPlayer).where(MatchPlayer.match_id == match.id)).all()
        rounds = db.scalars(select(MatchRound).where(MatchRound.match_id == match.id).order_by(MatchRound.number)).all()
        result["match"] = {"id": str(match.id), "map_name": match.map_name, "score": match.score,
                           "personal": personal_result(primary_steam(db, job.owner_id), players, match.score,
                                                       match.analysis_version),
                           "parser_version": match.parser_version, "analysis_version": match.analysis_version,
                           "competitive_rounds": len(match.facts.get("rounds", [])),
                           "advanced": match.facts.get("advanced"),
                           "utility_economy": {k: v for k, v in match.facts.get("utility_economy", {}).items() if k not in ("events", "source", "source_smoke")} or None,
                           "round_context": match.facts.get("rounds", []),
                           "players": [{"id": str(p.id), "name": p.name, "steam_id64": p.steam_id64, "team": p.team,
                                        "kills": p.kills, "deaths": p.deaths, "assists": p.assists, "headshots": p.headshots} for p in players],
                           "rounds": [{"number": r.number, "winner": r.winner, "tick": r.tick} for r in rounds]}
    return result


@router.get("/{demo_id}/comparison")
def comparison(demo_id: uuid.UUID, request: Request, response: Response, db: Db, player_id: uuid.UUID) -> dict:
    job = owned(db, request, demo_id)
    response.headers["Cache-Control"] = "no-store"
    match = db.scalar(select(Match).where(Match.demo_id == job.id))
    if not match or job.status != "completed":
        raise HTTPException(404, "Analysis unavailable")
    player = db.scalar(select(MatchPlayer).where(MatchPlayer.match_id == match.id, MatchPlayer.id == player_id))
    if not player:
        raise HTTPException(404, "Player not found")
    sid = steam_id(player.steam_id64)
    if not sid:
        return {"metrics": compare(None, []), "source": "personal_history"}
    count = db.scalar(select(func.count()).select_from(MatchPlayer).where(MatchPlayer.match_id == match.id, MatchPlayer.steam_id64 == sid))
    current = rates(match.facts, sid) if count == 1 and match.analysis_version == "competitive-2" else None
    history = []
    seen = {job.checksum} if job.checksum else set()
    if job.checksum:
        entries = db.execute(select(DemoUpload, Match).join(Match, Match.demo_id == DemoUpload.id).where(
            DemoUpload.owner_id == job.owner_id, DemoUpload.status == "completed", DemoUpload.created_at < job.created_at,
            Match.analysis_version == "competitive-2").order_by(DemoUpload.created_at.desc(), DemoUpload.id)).all()
        for past, previous in entries:
            if not past.checksum or past.checksum in seen:
                continue
            ids = db.scalars(select(MatchPlayer.steam_id64).where(MatchPlayer.match_id == previous.id, MatchPlayer.steam_id64 == sid)).all()
            if len(ids) != 1:
                continue
            row = rates(previous.facts, sid)
            if row is not None:
                seen.add(past.checksum)
                history.append(row)
    return {"metrics": compare(current, history), "source": "personal_history"}


@router.get("/{demo_id}/diagnostics")
def diagnostics(demo_id: uuid.UUID, request: Request, response: Response, db: Db) -> dict:
    job = owned(db, request, demo_id)
    match = db.scalar(select(Match).where(Match.demo_id == job.id))
    if not match or job.status != "completed":
        raise HTTPException(404, "Analysis unavailable")
    response.headers["Cache-Control"] = "no-store"
    return {"analysis_version": match.analysis_version, "facts": match.facts}


@router.post("/{demo_id}/retry", response_model=DemoOut)
def retry(demo_id: uuid.UUID, request: Request, db: Db) -> DemoUpload:
    guard_origin(request)
    job = owned(db, request, demo_id)
    job = db.scalar(select(DemoUpload).where(DemoUpload.id == job.id).with_for_update())
    if job.status not in ("failed", "completed"):
        raise HTTPException(409, "Demo is already queued or processing")
    if not (storage() / job.storage_name).is_file():
        raise HTTPException(409, "Demo file is unavailable")
    job.status, job.error, job.completed_at = "queued", None, None
    db.commit()
    db.refresh(job)
    return job


@router.delete("/{demo_id}", status_code=204)
def remove(demo_id: uuid.UUID, request: Request, db: Db) -> None:
    guard_origin(request)
    job = owned(db, request, demo_id)
    job = db.scalar(select(DemoUpload).where(DemoUpload.id == job.id).with_for_update())
    if job.status in ("uploaded", "processing"):
        raise HTTPException(409, "Demo is being processed")
    path = storage() / job.storage_name
    db.delete(job)
    db.commit()
    path.unlink(missing_ok=True)

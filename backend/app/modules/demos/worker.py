"""Single PostgreSQL-locked worker; child parser has a hard time limit."""
import json
import shutil
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_engine
from app.modules.demos.models import DemoUpload, Match, MatchPlayer, MatchRound

LOCK_ID = 0x43533244


def run_one(engine, runner=None) -> bool:
    with Session(engine) as db:
        job = db.scalar(select(DemoUpload).where(DemoUpload.status == "queued").order_by(
            DemoUpload.created_at).with_for_update(skip_locked=True).limit(1))
        if not job:
            return False
        job.status = "processing"
        job.error = None
        job_id, filename = job.id, job.storage_name
        db.commit()
    root = Path(get_settings().demo_storage_dir).resolve()
    source = root / filename
    output = root / f"{uuid.uuid4().hex}.result"
    unpacked = root / f"{uuid.uuid4().hex}.unpacked"
    try:
        max_unpacked = 0
        if filename.endswith(".zst"):
            with Session(engine) as db:
                db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 0x43533255})
                used = db.scalar(select(func.coalesce(func.sum(DemoUpload.size_bytes + DemoUpload.work_bytes), 0))) or 0
                max_unpacked = min(get_settings().demo_max_uncompressed_bytes, get_settings().demo_quota_bytes - used)
                if max_unpacked < 8 or shutil.disk_usage(root).free < max_unpacked + 104857600:
                    raise ValueError("Insufficient disk space for decompression")
                job = db.get(DemoUpload, job_id)
                job.work_bytes = max_unpacked
                db.commit()
        if runner is None:
            command = [sys.executable, "-m", "app.modules.demos.parse_cli", str(source), str(output)]
            if max_unpacked:
                command.extend([str(unpacked), str(max_unpacked)])
            subprocess.run(command,
                           check=True, timeout=get_settings().demo_timeout_seconds,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with output.open(encoding="utf-8") as stream:
                result = json.load(stream)
        else:
            result = runner(str(source))
        with Session(engine) as db:
            job = db.scalar(select(DemoUpload).where(DemoUpload.id == job_id).with_for_update())
            if job is None or job.status != "processing":
                return True
            db.execute(delete(Match).where(Match.demo_id == job_id))
            match = Match(demo_id=job_id, map_name=result["map_name"], score=result["score"],
                          parser_version=result["parser_version"], analysis_version=result["analysis_version"], facts=result["facts"])
            db.add(match)
            db.flush()
            db.add_all(MatchPlayer(match_id=match.id, **p) for p in result["players"])
            db.add_all(MatchRound(match_id=match.id, **r) for r in result["rounds"])
            job.status = "completed"
            job.completed_at = datetime.now(UTC)
            db.commit()
    except Exception as exc:  # noqa: BLE001 - native parser failures must never leave a job processing
        message = "Не удалось разобрать демку. Проверьте файл и попробуйте снова."
        if isinstance(exc, ValueError) and str(exc) == "Insufficient disk space for decompression":
            message = "Недостаточно места для распаковки демки."
        elif isinstance(exc, subprocess.TimeoutExpired):
            message = "Превышено время обработки демки."
        elif isinstance(exc, subprocess.CalledProcessError) and exc.returncode == 21:
            message = "Архив повреждён или не содержит демку CS2."
        elif isinstance(exc, subprocess.CalledProcessError) and exc.returncode == 22:
            message = "Размер распакованной демки превышает допустимый лимит."
        with Session(engine) as db:
            job = db.get(DemoUpload, job_id)
            if job and job.status == "processing":
                job.status = "failed"
                job.error = message
                job.completed_at = datetime.now(UTC)
                db.commit()
    finally:
        output.unlink(missing_ok=True)
        unpacked.unlink(missing_ok=True)
        with Session(engine) as db:
            job = db.get(DemoUpload, job_id)
            if job and job.work_bytes:
                job.work_bytes = 0
                db.commit()
    return True


def main() -> None:
    engine = get_engine()
    root = Path(get_settings().demo_storage_dir).resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with engine.connect() as lock:
        if not lock.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID}):
            print("Another demo worker is already running.", file=sys.stderr)
            return
        lock.commit()
        with Session(engine) as db:
            stale = db.scalars(select(DemoUpload).where(DemoUpload.status == "processing")).all()
            for job in stale:
                job.status, job.error = "queued", None
            interrupted = db.scalars(select(DemoUpload).where(DemoUpload.status == "uploaded",
                DemoUpload.created_at < datetime.now(UTC) - timedelta(hours=24))).all()
            for job in interrupted:
                (root / (job.storage_name + ".part")).unlink(missing_ok=True)
                (root / job.storage_name).unlink(missing_ok=True)
                job.status, job.error, job.size_bytes = "failed", "Загрузка была прервана.", 0
            db.commit()
        for pattern in ("*.result", "*.unpacked"):
            for partial in root.glob(pattern):
                partial.unlink(missing_ok=True)
        with Session(engine) as db:
            for job in db.scalars(select(DemoUpload).where(DemoUpload.work_bytes > 0)):
                job.work_bytes = 0
            db.commit()
        while True:
            if not run_one(engine):
                time.sleep(2)


if __name__ == "__main__":
    main()

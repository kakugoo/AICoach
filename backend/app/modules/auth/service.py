import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, Response
from pwdlib import PasswordHash
from sqlalchemy import delete, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.auth.models import LoginAttempt, User, UserSession

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash("not-a-real-password-constant")
SESSION_SECONDS = 60 * 60 * 24 * 7


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def guard_origin(request: Request) -> None:
    if (request.headers.get("origin") not in get_settings().allowed_origins
            or request.headers.get("x-csrf-protection") != "1"):
        raise HTTPException(403, "Request origin not allowed")


def limit_attempts(engine: Engine, ip: str, email: str, kind: str = "login") -> None:
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=15)
    ip_key = digest(f"{kind}:ip:{ip}")
    email_key = digest(f"{kind}:email:{email}")
    # Transaction-scoped locks keep counting and insertion atomic across API workers.
    with Session(engine) as db, db.begin():
        for key in sorted((ip_key, email_key)):
            db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key})
        db.execute(delete(LoginAttempt).where(LoginAttempt.attempted_at < cutoff))
        count_ip = db.scalar(select(func.count()).select_from(LoginAttempt).where(
            LoginAttempt.ip_key == ip_key, LoginAttempt.attempted_at >= cutoff))
        count_email = db.scalar(select(func.count()).select_from(LoginAttempt).where(
            LoginAttempt.email_key == email_key, LoginAttempt.attempted_at >= cutoff))
        if (count_ip or 0) >= 30 or (count_email or 0) >= 5:
            raise HTTPException(429, "Too many attempts. Try again later.")
        db.add(LoginAttempt(ip_key=ip_key, email_key=email_key, attempted_at=now))


def issue_session(db: Session, user: User, request: Request, response: Response) -> None:
    old = request.cookies.get(get_settings().cookie_name)
    if old:
        db.execute(delete(UserSession).where(UserSession.token_hash == digest(old)))
    token = secrets.token_urlsafe(32)
    db.add(UserSession(token_hash=digest(token), user_id=user.id,
                       expires_at=datetime.now(UTC) + timedelta(seconds=SESSION_SECONDS)))
    db.commit()
    response.set_cookie(get_settings().cookie_name, token, httponly=True,
                        secure=get_settings().cookie_secure, samesite="strict", path="/",
                        max_age=SESSION_SECONDS)
    response.headers["Cache-Control"] = "no-store"


def current_user(db: Session, request: Request) -> User:
    token = request.cookies.get(get_settings().cookie_name)
    if not token or len(token) > 128:
        raise HTTPException(401, "Not authenticated")
    user = db.scalar(select(User).join(UserSession, UserSession.user_id == User.id).where(
        UserSession.token_hash == digest(token), UserSession.expires_at > datetime.now(UTC)))
    if user is None:
        raise HTTPException(401, "Not authenticated")
    return user

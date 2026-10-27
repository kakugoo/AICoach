from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_engine
from app.modules.auth.models import User, UserSession
from app.modules.auth.schemas import Credentials, Profile, Registration
from app.modules.auth.service import (
    DUMMY_HASH,
    current_user,
    digest,
    guard_origin,
    issue_session,
    limit_attempts,
    passwords,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def get_db() -> Iterator[Session]:
    with Session(get_engine()) as db:
        yield db


Db = Annotated[Session, Depends(get_db)]


@router.post("/register", response_model=Profile, status_code=201)
def register(data: Registration, request: Request, response: Response, db: Db) -> User:
    guard_origin(request)
    limit_attempts(db.get_bind(), request.client.host if request.client else "unknown", str(data.email), "register")
    user = User(email=str(data.email), password_hash=passwords.hash(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Email already registered") from exc
    issue_session(db, user, request, response)
    return user


@router.post("/login", response_model=Profile)
def login(data: Credentials, request: Request, response: Response, db: Db) -> User:
    guard_origin(request)
    limit_attempts(db.get_bind(), request.client.host if request.client else "unknown", str(data.email))
    user = db.scalar(select(User).where(User.email == str(data.email)))
    valid = passwords.verify(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "Invalid email or password")
    issue_session(db, user, request, response)
    return user


@router.get("/me", response_model=Profile)
def me(request: Request, response: Response, db: Db) -> User:
    response.headers["Cache-Control"] = "no-store"
    return current_user(db, request)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Db) -> None:
    guard_origin(request)
    current_user(db, request)
    token = request.cookies.get(get_settings().cookie_name)
    session = db.get(UserSession, digest(token or ""))
    if session:
        db.delete(session)
        db.commit()
    response.delete_cookie(get_settings().cookie_name, path="/", secure=get_settings().cookie_secure,
                           httponly=True, samesite="strict")
    response.headers["Cache-Control"] = "no-store"

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_engine

router = APIRouter()


class Status(BaseModel):
    status: str


@router.get("/health", response_model=Status)
def health() -> Status:
    return Status(status="ok")


@router.get("/ready", response_model=Status)
def ready(engine: Annotated[Engine, Depends(get_engine)]) -> Status:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return Status(status="ok")

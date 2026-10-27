import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.main import app
from app.modules.auth.models import Base
from app.modules.auth.router import get_db

HEADERS = {"Origin": "http://localhost:3000", "X-CSRF-Protection": "1"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    schema = "test_" + uuid.uuid4().hex
    admin = create_engine(get_settings().database_url)
    with admin.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(get_settings().database_url, connect_args={"options": f"-csearch_path={schema}"})
    Base.metadata.create_all(engine)

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app, base_url="http://localhost:8000", headers=HEADERS) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_engine
from app.main import app


class BrokenEngine:
    def connect(self):
        raise OperationalError("SELECT 1", {}, Exception("offline"))


def test_health_is_independent_of_database():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_unavailable_database():
    app.dependency_overrides[get_engine] = lambda: BrokenEngine()
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}
    finally:
        app.dependency_overrides.clear()

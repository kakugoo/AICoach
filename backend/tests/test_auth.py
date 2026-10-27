from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.models import User, UserSession
from app.modules.auth.router import get_db
from app.modules.auth.service import digest

HEADERS = {"Origin": "http://localhost:3000", "X-CSRF-Protection": "1"}
PASSWORD = "a secure passphrase 123"




def register(client: TestClient, email: str = "alice@example.com"):
    return client.post("/auth/register", json={"email": email, "password": PASSWORD})


def test_registration_session_reload_and_logout(client: TestClient):
    assert client.get("/auth/me").status_code == 401
    response = register(client, "Alice@example.com")
    assert response.status_code == 201
    assert response.json()["email"] == "alice@example.com"
    cookie = client.cookies.get("cs2_session")
    assert cookie and "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    with next(get_db_override()) as db:
        user = db.query(User).filter_by(email="alice@example.com").one()
        assert PASSWORD not in user.password_hash and user.password_hash.startswith("$argon2id$")
        assert db.get(UserSession, digest(cookie)) is not None
    assert client.get("/auth/me").json()["email"] == "alice@example.com"
    assert client.get("/auth/me").status_code == 200
    assert client.post("/auth/logout").status_code == 204
    client.cookies.set("cs2_session", cookie, domain="localhost.local", path="/")
    assert client.get("/auth/me").status_code == 401


def get_db_override():
    return app.dependency_overrides[get_db]()


def test_duplicate_invalid_and_login(client: TestClient):
    assert register(client).status_code == 201
    assert client.post("/auth/logout").status_code == 204
    assert register(client, "ALICE@example.com").status_code == 409
    invalid = client.post("/auth/register", json={"email": "not-an-email", "password": "short"})
    assert invalid.status_code == 422
    assert "short" not in invalid.text
    assert client.post("/auth/login", json={"email": "alice@example.com", "password": "wrong"}).status_code == 401
    assert client.post("/auth/login", json={"email": "alice@example.com", "password": PASSWORD}).status_code == 200
    assert client.get("/auth/me").json()["email"] == "alice@example.com"


def test_user_isolation_and_csrf(client: TestClient):
    assert register(client).status_code == 201
    alice_cookie = client.cookies.get("cs2_session")
    assert register(client, "bob@example.com").status_code == 201
    assert client.get("/auth/me").json()["email"] == "bob@example.com"
    # Logging in as another user rotates and invalidates the previous session.
    client.cookies.set("cs2_session", alice_cookie, domain="localhost.local", path="/")
    assert client.get("/auth/me").status_code == 401
    assert client.post("/auth/login", headers={"Origin": "https://evil.example"}, json={"email": "bob@example.com", "password": PASSWORD}).status_code == 403


def test_login_attempt_limit(client: TestClient):
    for _ in range(5):
        assert client.post("/auth/login", json={"email": "unknown@example.com", "password": "bad"}).status_code == 401
    assert client.post("/auth/login", json={"email": "unknown@example.com", "password": "bad"}).status_code == 429


def test_two_users_cannot_read_each_others_profile(client: TestClient):
    assert register(client).status_code == 201
    alice_id = client.get("/auth/me").json()["id"]
    with TestClient(app, base_url="http://localhost:8000", headers=HEADERS) as other:
        assert register(other, "bob@example.com").status_code == 201
        bob = other.get("/auth/me").json()
        assert bob["id"] != alice_id
        assert bob["email"] == "bob@example.com"
        assert client.get("/auth/me").json()["id"] == alice_id
        assert other.get(f"/users/{alice_id}").status_code == 404


def test_missing_csrf_header_and_missing_origin_rejected(client: TestClient):
    data = {"email": "alice@example.com", "password": PASSWORD}
    assert client.post("/auth/login", headers={"X-CSRF-Protection": ""}, json=data).status_code == 403
    assert client.post("/auth/login", headers={"Origin": ""}, json=data).status_code == 403

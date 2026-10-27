import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_auth import HEADERS, register

from app.main import app
from app.modules.auth.router import get_db
from app.modules.game_profiles.client import FaceitClient, get_faceit_client
from app.modules.game_profiles.models import FaceitProfile, TrackedProfile

PLAYER_ID = "f4dd2a41-6cd3-4542-ad70-0b7603975287"
# Synthetic fixture in the documented FACEIT player-details response shape.
PLAYER = {
    "player_id": PLAYER_ID,
    "nickname": "example_player",
    "avatar": "https://cdn.example.test/avatar.jpg",
    "faceit_url": "https://www.faceit.com/en/players/example_player",
    "steam_id_64": "76561198000000000",
    "games": {"cs2": {"faceit_elo": 1250, "skill_level": 4}},
}


def mock_client(status: int = 200, payload: object = PLAYER) -> FaceitClient:
    def handle(req: httpx.Request) -> httpx.Response:
        assert req.url.host == "open.faceit.com"
        assert req.headers["authorization"] == "Bearer test-key"
        if req.url.path.endswith("/players"):
            assert req.url.params["nickname"] == "example_player"
        else:
            assert req.url.path.endswith(PLAYER_ID)
        return httpx.Response(status, json=payload)
    return FaceitClient(api_key="test-key", transport=httpx.MockTransport(handle))


@pytest.fixture(autouse=True)
def clear_override():
    yield
    app.dependency_overrides.pop(get_faceit_client, None)


def test_unconfigured_and_unauthenticated(client):
    app.dependency_overrides[get_faceit_client] = lambda: FaceitClient(api_key="")
    assert client.get("/game-profiles").status_code == 401
    assert client.get("/game-profiles/search?nickname=example_player").status_code == 401
    assert register(client).status_code == 201
    assert client.get("/game-profiles/status").json() == {"configured": False}
    assert client.get("/game-profiles/search?nickname=example_player").status_code == 503
    assert client.get("/game-profiles").json() == []


def test_search_and_profile_lifecycle(client):
    app.dependency_overrides[get_faceit_client] = mock_client
    assert register(client).status_code == 201
    result = client.get("/game-profiles/search?nickname=example_player")
    assert result.status_code == 200
    assert result.json()["faceit_player_id"] == PLAYER_ID
    assert result.json()["elo"] == 1250 and result.json()["steam_id64"] == PLAYER["steam_id_64"]
    assert client.get("/game-profiles").json() == []
    add = client.post("/game-profiles", json={"faceit_player_id": PLAYER_ID})
    assert add.status_code == 201, add.text
    saved = add.json()
    profile_id = saved["id"]
    assert saved["added_at"] and saved["updated_at"]
    assert client.post("/game-profiles", json={"faceit_player_id": PLAYER_ID}).status_code == 409
    assert client.get("/game-profiles").json()[0]["id"] == profile_id
    # Dispose the database pool and recreate the client to exercise persisted rows.
    with next(app.dependency_overrides[get_db]()) as db:
        db.get_bind().dispose()
    # A new client with the same cookie emulates a newly opened application session.
    with TestClient(app, base_url="http://localhost:8000", headers=HEADERS, cookies=client.cookies) as resumed:
        assert resumed.get("/game-profiles").json()[0]["id"] == profile_id
    changed = PLAYER | {"nickname": "renamed_player", "games": {"cs2": {"faceit_elo": 1500, "skill_level": 5}}}
    app.dependency_overrides[get_faceit_client] = lambda: mock_client(payload=changed)
    refreshed = client.post(f"/game-profiles/{profile_id}/refresh")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["nickname"] == "renamed_player" and refreshed.json()["elo"] == 1500
    assert client.delete(f"/game-profiles/{profile_id}").status_code == 204
    assert client.get("/game-profiles").json() == []
    with next(app.dependency_overrides[get_db]()) as db:
        assert db.scalar(select(FaceitProfile).where(FaceitProfile.faceit_player_id == uuid.UUID(PLAYER_ID)))


def test_shared_profile_and_other_user_cannot_remove(client):
    app.dependency_overrides[get_faceit_client] = mock_client
    assert register(client).status_code == 201
    profile_id = client.post("/game-profiles", json={"faceit_player_id": PLAYER_ID}).json()["id"]
    with TestClient(app, base_url="http://localhost:8000", headers=HEADERS) as other:
        assert register(other, "bob@example.com").status_code == 201
        assert other.delete(f"/game-profiles/{profile_id}").status_code == 404
        assert other.post(f"/game-profiles/{profile_id}/refresh").status_code == 404
        assert other.get("/game-profiles").json() == []
        assert other.post("/game-profiles", json={"faceit_player_id": PLAYER_ID}).status_code == 201
        assert client.delete(f"/game-profiles/{profile_id}").status_code == 204
        assert other.get("/game-profiles").json()[0]["id"] == profile_id
        with next(app.dependency_overrides[get_db]()) as db:
            assert len(db.scalars(select(TrackedProfile)).all()) == 1


@pytest.mark.parametrize(("upstream", "expected"), [(404, 404), (401, 503), (403, 503), (429, 429), (500, 502), (503, 502)])
def test_upstream_errors(client, upstream, expected):
    app.dependency_overrides[get_faceit_client] = lambda: mock_client(status=upstream)
    assert register(client).status_code == 201
    response = client.get("/game-profiles/search?nickname=example_player")
    assert response.status_code == expected
    assert "test-key" not in response.text


def test_input_csrf_and_rate_limit(client):
    app.dependency_overrides[get_faceit_client] = mock_client
    assert register(client).status_code == 201
    assert client.get("/game-profiles/search", params={"nickname": "../bad"}).status_code == 422
    assert client.post("/game-profiles", headers={"Origin": "https://evil.example"}, json={"faceit_player_id": PLAYER_ID}).status_code == 403
    for _ in range(5):
        assert client.get("/game-profiles/search?nickname=example_player").status_code == 200
    assert client.get("/game-profiles/search?nickname=example_player").status_code == 429


def test_timeout_and_invalid_payload(client):
    def timeout(req):
        raise httpx.ReadTimeout("timeout", request=req)
    app.dependency_overrides[get_faceit_client] = lambda: FaceitClient(api_key="test-key", transport=httpx.MockTransport(timeout))
    assert register(client).status_code == 201
    assert client.get("/game-profiles/search?nickname=example_player").status_code == 502
    app.dependency_overrides[get_faceit_client] = lambda: mock_client(payload={"nickname": "broken"})
    assert client.get("/game-profiles/search?nickname=example_player").status_code == 502


def test_primary_profile_selection_is_owner_scoped_without_key(client):
    app.dependency_overrides[get_faceit_client] = mock_client
    assert register(client).status_code == 201
    profile_id = client.post("/game-profiles", json={"faceit_player_id": PLAYER_ID}).json()["id"]
    app.dependency_overrides[get_faceit_client] = lambda: FaceitClient(api_key="")
    assert client.post(f"/game-profiles/{profile_id}/primary").status_code == 204
    assert client.get("/game-profiles").json()[0]["is_primary"] is True
    with TestClient(app, base_url="http://localhost:8000", headers=HEADERS) as other:
        assert register(other, "primary-other@example.com").status_code == 201
        assert other.post(f"/game-profiles/{profile_id}/primary").status_code == 404
        assert other.delete(f"/game-profiles/{profile_id}/primary").status_code == 404
    assert client.delete(f"/game-profiles/{profile_id}/primary").status_code == 204
    assert client.get("/game-profiles").json()[0]["is_primary"] is False
    assert client.post(f"/game-profiles/{profile_id}/primary").status_code == 204
    assert client.delete(f"/game-profiles/{profile_id}").status_code == 204
    assert client.get("/game-profiles").json() == []


def test_switch_primary_and_keep_other_tracking(client):
    from datetime import UTC, datetime

    app.dependency_overrides[get_faceit_client] = mock_client
    assert register(client).status_code == 201
    first = client.post("/game-profiles", json={"faceit_player_id": PLAYER_ID}).json()["id"]
    with next(app.dependency_overrides[get_db]()) as db:
        tracked = db.scalar(select(TrackedProfile))
        second = FaceitProfile(faceit_player_id=uuid.uuid4(), nickname="second", profile_url="https://www.faceit.com/en/players/second", updated_at=datetime.now(UTC))
        db.add(second)
        db.flush()
        second_id = str(second.id)
        db.add(TrackedProfile(user_id=tracked.user_id, profile_id=second.id))
        db.commit()
    assert client.post(f"/game-profiles/{first}/primary").status_code == 204
    assert client.post(f"/game-profiles/{second_id}/primary").status_code == 204
    profiles = client.get("/game-profiles").json()
    assert {p["id"]: p["is_primary"] for p in profiles} == {first: False, second_id: True}

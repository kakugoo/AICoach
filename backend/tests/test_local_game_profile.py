import pytest
from fastapi.testclient import TestClient
from test_auth import HEADERS, register
from test_demos import RESULT, engine, upload
from test_game_profiles import PLAYER_ID, mock_client

from app.core.config import get_settings
from app.main import app
from app.modules.demos.worker import run_one
from app.modules.game_profiles.client import FaceitClient, get_faceit_client

SID = "76561198000000000"


@pytest.fixture(autouse=True)
def isolated_demo_storage(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "demo_max_bytes", 1024)
    monkeypatch.setattr(settings, "demo_quota_bytes", 4096)


def test_local_selection_privacy_switch_and_reconnect(client):
    app.dependency_overrides[get_faceit_client] = mock_client
    try:
        assert client.get("/game-profiles/local").status_code == 401
        assert register(client).status_code == 201
        faceit = client.post("/game-profiles", json={"faceit_player_id": PLAYER_ID}).json()["id"]
        assert client.post(f"/game-profiles/{faceit}/primary").status_code == 204
        app.dependency_overrides[get_faceit_client] = lambda: FaceitClient(api_key="")
        demo_id = upload(client).json()["id"]
        synthetic = RESULT | {"analysis_version": "competitive-2", "score": {"teams": [{"name": "A", "score": 5}, {"name": "B", "score": 13}]},
                              "players": [RESULT["players"][0] | {"steam_id64": SID, "team": "B"}]}
        assert run_one(engine(), runner=lambda path: synthetic)
        player_id = client.get(f"/demos/{demo_id}").json()["match"]["players"][0]["id"]
        body = {"demo_id": demo_id, "player_id": player_id}
        with TestClient(app, base_url="http://localhost:8000", headers=HEADERS) as other:
            assert register(other, "local-other@example.com").status_code == 201
            assert other.post("/game-profiles/local", json=body).status_code == 404
            assert other.get("/game-profiles/local").json() is None
        assert client.post("/game-profiles/local", headers={"Origin": "https://evil.example"}, json=body).status_code == 403
        assert client.post("/game-profiles/local", json=body).status_code == 204
        assert client.get("/game-profiles/local").json() == {"nickname": "test_player", "steam_id64": SID, "is_primary": True}
        assert client.get("/game-profiles").json()[0]["is_primary"] is False
        assert client.get("/demos/summary").json()["recent"][0]["personal"]["score"] == [13, 5]
        assert client.get(f"/demos/{demo_id}").json()["match"]["personal"]["player_id"] == player_id
        engine().dispose()
        assert client.get("/game-profiles/local").json()["steam_id64"] == SID
        assert client.post(f"/game-profiles/{faceit}/primary").status_code == 204
        assert client.get("/game-profiles/local").json()["is_primary"] is False
        assert client.post("/game-profiles/local/primary").status_code == 204
        assert client.get("/game-profiles").json()[0]["is_primary"] is False
        assert client.delete("/game-profiles/local").status_code == 204
        assert client.get("/game-profiles/local").json() is None
        assert client.get("/game-profiles").json()[0]["id"] == faceit
    finally:
        app.dependency_overrides.pop(get_faceit_client, None)


def test_local_rejects_missing_id(client):
    assert register(client).status_code == 201
    demo = upload(client).json()["id"]
    assert run_one(engine(), runner=lambda path: RESULT)
    player = client.get(f"/demos/{demo}").json()["match"]["players"][0]["id"]
    assert client.post("/game-profiles/local", json={"demo_id": demo, "player_id": player}).status_code == 422
    assert client.get("/game-profiles/local").json() is None


def test_change_local_profile_and_apply_to_multiple_matches(client):
    assert register(client).status_code == 201
    demo_ids = []
    for team in ("A", "B"):
        demo = upload(client).json()["id"]
        result = RESULT | {"analysis_version": "competitive-2", "score": {"teams": [{"name": "A", "score": 5}, {"name": "B", "score": 13}]},
                           "players": [RESULT["players"][0] | {"steam_id64": SID, "team": team},
                                       RESULT["players"][0] | {"name": "Other", "steam_id64": "76561198000000001", "team": "B"}]}
        assert run_one(engine(), runner=lambda path, value=result: value)
        demo_ids.append(demo)
    players = client.get(f"/demos/{demo_ids[0]}").json()["match"]["players"]
    assert client.post("/game-profiles/local", json={"demo_id": demo_ids[0], "player_id": players[0]["id"]}).status_code == 204
    assert {r["personal"]["outcome"] for r in client.get("/demos/summary").json()["recent"]} == {"win", "loss"}
    assert client.post("/game-profiles/local", json={"demo_id": demo_ids[0], "player_id": players[1]["id"]}).status_code == 204
    assert client.get("/game-profiles/local").json()["steam_id64"] == "76561198000000001"
    assert client.delete(f"/demos/{demo_ids[0]}").status_code == 204
    assert client.get("/game-profiles/local").json()["steam_id64"] == "76561198000000001"


def test_duplicate_steam_id_is_rejected(client):
    assert register(client).status_code == 201
    demo = upload(client).json()["id"]
    player = RESULT["players"][0] | {"steam_id64": SID}
    assert run_one(engine(), runner=lambda path: RESULT | {"players": [player, player]})
    player_id = client.get(f"/demos/{demo}").json()["match"]["players"][0]["id"]
    assert client.post("/game-profiles/local", json={"demo_id": demo, "player_id": player_id}).status_code == 422

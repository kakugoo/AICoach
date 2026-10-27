import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_auth import HEADERS, register

from app.core.config import get_settings
from app.main import app
from app.modules.auth.router import get_db
from app.modules.demos.models import DemoUpload
from app.modules.demos.parser import parse_demo
from app.modules.demos.worker import run_one

MAGIC = b"PBDEMS2\x00" + b"test-only-not-a-real-demo"
# Synthetic parser result; used only to test queue persistence and authorization.
RESULT = {"map_name": "test_map", "score": None, "parser_version": "test", "analysis_version": "test",
          "facts": {"events": [], "event_scope": "test"},
          "players": [{"name": "test_player", "steam_id64": None, "team": None, "kills": 2, "deaths": 1, "assists": 0, "headshots": 1}],
          "rounds": [{"number": 1, "winner": "CT", "tick": 100}]}


@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "demo_max_bytes", 1024)
    monkeypatch.setattr(settings, "demo_quota_bytes", 4096)
    return tmp_path


def upload(client, data=MAGIC, name="match.dem"):
    return client.post("/demos", params={"filename": name}, content=data,
                       headers={"Content-Type": "application/octet-stream"})


def engine():
    with next(app.dependency_overrides[get_db]()) as db:
        return db.get_bind()


def test_upload_rejects_unauthenticated_and_invalid(client, storage):
    assert upload(client).status_code == 401
    assert register(client).status_code == 201
    assert upload(client, name="archive.zip").status_code == 415
    assert upload(client, b"").status_code == 422
    assert upload(client, b"not a cs2 demo").status_code == 422
    assert upload(client, MAGIC + b"x" * 1024).status_code == 413
    assert not list(storage.iterdir())
    assert client.get("/demos").json() == []
    assert upload(client, name="../match.dem").status_code == 201
    assert client.get("/demos").json()[0]["original_name"] == "match.dem"


def test_queue_save_retry_and_access_control(client):
    assert register(client).status_code == 201
    result = upload(client)
    assert result.status_code == 201, result.text
    demo_id = result.json()["id"]
    assert result.json()["status"] == "queued"
    assert client.post(f"/demos/{demo_id}/retry").status_code == 409
    with TestClient(app, base_url="http://localhost:8000", headers=HEADERS) as other:
        assert register(other, "other@example.com").status_code == 201
        assert other.get(f"/demos/{demo_id}").status_code == 404
        assert other.delete(f"/demos/{demo_id}").status_code == 404
        assert other.post(f"/demos/{demo_id}/retry").status_code == 404
    assert run_one(engine(), runner=lambda path: RESULT)
    detail = client.get(f"/demos/{demo_id}").json()
    assert detail["demo"]["status"] == "completed"
    assert detail["match"]["players"][0]["kills"] == 2
    assert detail["match"]["rounds"][0]["winner"] == "CT"
    assert client.post(f"/demos/{demo_id}/retry").json()["status"] == "queued"
    assert client.get(f"/demos/{demo_id}").json()["match"] is None
    assert run_one(engine(), runner=lambda path: RESULT)
    assert client.delete(f"/demos/{demo_id}").status_code == 204
    assert client.get(f"/demos/{demo_id}").status_code == 404


def test_processing_error_and_retry(client):
    assert register(client).status_code == 201
    demo_id = upload(client).json()["id"]
    def fail(path):
        raise ValueError("parser failed")
    assert run_one(engine(), runner=fail)
    item = client.get(f"/demos/{demo_id}").json()
    assert item["demo"]["status"] == "failed" and item["match"] is None
    assert client.post(f"/demos/{demo_id}/retry").json()["status"] == "queued"
    with Session(engine()) as db:
        assert db.get(DemoUpload, __import__("uuid").UUID(demo_id)).checksum


def test_real_parser_rejects_corrupt_demo(tmp_path):
    path = tmp_path / "invalid.dem"
    path.write_bytes(MAGIC)
    result = subprocess.run([sys.executable, "-m", "app.modules.demos.parse_cli", str(path),
                             str(tmp_path / "out.json")], capture_output=True, timeout=20, check=False)
    assert result.returncode != 0


@pytest.mark.skipif(not os.environ.get("CS2_TEST_DEMO"), reason="No real CS2 demo supplied")
def test_real_cs2_demo():
    path = Path(os.environ["CS2_TEST_DEMO"])
    result = parse_demo(str(path))
    assert result["map_name"] and result["players"]
    if os.environ.get("CS2_TEST_FACEIT_REFERENCE") == "1":
        import hashlib
        import json

        reference_path = Path(os.environ.get("CS2_TEST_REFERENCE", "../storage/fixtures/faceit-reference.json"))
        if not reference_path.is_file():
            pytest.skip("Private real-match reference fixture not available")
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        got = {p["name"]: (p["kills"], p["deaths"], p["assists"]) for p in result["players"]}
        assert all(got[name] == tuple(value) for name, value in reference["players"].items())
        assert sorted(team["score"] for team in result["score"]["teams"]) == reference["score_sorted"]
        baseline = {
            "players": sorted((p["steam_id64"], p["team"], p["kills"], p["deaths"], p["assists"])
                              for p in result["players"]),
            "score": result["score"],
            "rounds": result["facts"]["rounds"],
        }
        encoded = json.dumps(baseline, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
        assert hashlib.sha256(encoded).hexdigest() == reference["baseline_sha256"]
        target = next(player for player in result["players"] if player["name"] == reference["target"])
        if "advanced" in result["facts"]:
            advanced = result["facts"]["advanced"]["players"][target["steam_id64"]]
            for key, expected_value in reference["advanced"].items():
                assert advanced[key] == expected_value
        if "utility_economy" in result["facts"]:
            utility = result["facts"]["utility_economy"]["players"][target["steam_id64"]]
            for key, expected_value in reference["utility"].items():
                assert (utility["uses"][key] if key in utility["uses"] else utility[key]) == expected_value


def test_corrupt_file_fails_in_real_worker_and_is_retryable(client):
    assert register(client).status_code == 201
    demo_id = upload(client).json()["id"]
    assert run_one(engine())
    result = client.get(f"/demos/{demo_id}").json()
    assert result["demo"]["status"] == "failed"
    assert result["match"] is None
    assert client.post(f"/demos/{demo_id}/retry").json()["status"] == "queued"


def test_storage_quota_and_csrf(client, monkeypatch):
    assert register(client).status_code == 201
    monkeypatch.setattr(get_settings(), "demo_quota_bytes", len(MAGIC))
    assert upload(client).status_code == 201
    assert upload(client).status_code == 507
    bad = client.post("/demos?filename=bad.dem", content=MAGIC,
                      headers={"Origin": "https://evil.example", "Content-Type": "application/octet-stream"})
    assert bad.status_code == 403


def test_event_statistics_are_labeled_recording_facts(monkeypatch):
    import pandas as pd

    from app.modules.demos import parser as module

    sid_a, sid_b = 76561198000000001, 76561198000000002
    class FakeParser:
        def __init__(self, path):
            pass
        def parse_header(self):
            return {"demo_file_stamp": "PBDEMS2\x00", "map_name": "test_map"}
        def parse_player_info(self):
            return pd.DataFrame([{"name": "A", "steamid": sid_a}, {"name": "B", "steamid": sid_b}])
        def parse_event(self, name):
            if name == "player_death":
                return pd.DataFrame([{"attacker_steamid": sid_a, "user_steamid": sid_b,
                                      "assister_steamid": 0, "headshot": True, "tick": 42}])
            return pd.DataFrame([{"winner": 3, "tick": 60}])
    monkeypatch.setattr(module, "DemoParser", FakeParser)
    result = module.parse_demo("test-only.dem")
    assert result["score"] is None
    assert result["players"][0]["kills"] is None
    assert result["rounds"] == []
    assert result["facts"]["phases"][0]["phase"] == "unknown"


def test_timeout_leaves_no_partial_match(client, monkeypatch):
    assert register(client).status_code == 201
    demo_id = upload(client).json()["id"]
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="parser", timeout=1)
    monkeypatch.setattr(subprocess, "run", timeout)
    assert run_one(engine())
    result = client.get(f"/demos/{demo_id}").json()
    assert result["demo"]["status"] == "failed" and result["match"] is None


@pytest.mark.skipif(not os.environ.get("CS2_TEST_DEMO"), reason="No real CS2 demo supplied")
def test_real_zstd_upload_worker_and_retry(client, tmp_path, monkeypatch):
    import zstandard

    settings = get_settings()
    monkeypatch.setattr(settings, "demo_max_bytes", 1073741824)
    monkeypatch.setattr(settings, "demo_max_uncompressed_bytes", 1073741824)
    monkeypatch.setattr(settings, "demo_quota_bytes", 2147483648)
    source = Path(os.environ["CS2_TEST_DEMO"])
    archive = tmp_path / "fixture" / "real-fixture.dem.zst"
    archive.parent.mkdir()
    with source.open("rb") as raw, archive.open("wb") as compressed:
        zstandard.ZstdCompressor(level=3).copy_stream(raw, compressed)
    assert register(client).status_code == 201
    uploaded = client.post("/demos?filename=fixture.dem.zst", content=archive.read_bytes(),
                           headers={"Content-Type": "application/octet-stream"})
    assert uploaded.status_code == 201, uploaded.text
    demo_id = uploaded.json()["id"]
    assert run_one(engine())
    result = client.get(f"/demos/{demo_id}").json()
    assert result["demo"]["status"] == "completed", result
    assert result["match"]["analysis_version"] == "competitive-2"
    assert result["match"]["map_name"]
    assert not list(Path(settings.demo_storage_dir).glob("*.unpacked"))
    assert len(list(Path(settings.demo_storage_dir).glob("*.dem.zst"))) == 1
    assert client.post(f"/demos/{demo_id}/retry").status_code == 200
    assert run_one(engine())
    result2 = client.get(f"/demos/{demo_id}").json()
    assert result2["demo"]["status"] == "completed"
    assert len(result2["match"]["players"]) == len(result["match"]["players"])


def test_failed_reanalysis_preserves_prior_rows_and_original(client):
    from sqlalchemy import select

    from app.modules.demos.models import Match, MatchPlayer

    assert register(client).status_code == 201
    demo_id = upload(client).json()["id"]
    assert run_one(engine(), runner=lambda path: RESULT)
    diagnostic = client.get(f"/demos/{demo_id}/diagnostics")
    assert diagnostic.status_code == 200
    assert client.post(f"/demos/{demo_id}/retry").status_code == 200
    def failure(path):
        raise ValueError("failed reanalysis")
    assert run_one(engine(), runner=failure)
    assert client.get(f"/demos/{demo_id}").json()["demo"]["status"] == "failed"
    with Session(engine()) as db:
        match = db.scalar(select(Match).where(Match.demo_id == __import__("uuid").UUID(demo_id)))
        assert match and len(db.scalars(select(MatchPlayer).where(MatchPlayer.match_id == match.id)).all()) == 1
        job = db.get(DemoUpload, __import__("uuid").UUID(demo_id))
        assert (Path(get_settings().demo_storage_dir) / job.storage_name).is_file()
    assert client.post(f"/demos/{demo_id}/retry").status_code == 200
    assert run_one(engine(), runner=lambda path: RESULT)
    with Session(engine()) as db:
        matches = db.scalars(select(Match).where(Match.demo_id == __import__("uuid").UUID(demo_id))).all()
        assert len(matches) == 1
        assert len(db.scalars(select(MatchPlayer).where(MatchPlayer.match_id == matches[0].id)).all()) == 1

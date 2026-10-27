from app.modules.demos.comparison import compare, percentile, rates

SID = "76561198000000001"


def facts(rounds=10, smoke=5):
    return {"advanced": {"version": "advanced-1", "players": {SID: {"rounds": rounds}}},
            "utility_economy": {"version": "utility-economy-1", "players": {SID: {"uses": {"smoke": smoke}, "rounds": [{} for _ in range(rounds)]}}}}


def test_normalization_and_unknown():
    assert rates(facts(10, 5), SID)["smoke"] == .5
    assert rates(facts(0), SID) is None
    assert rates(facts(), SID)["he"] is None
    bad = facts(); bad["advanced"]["version"] = "other"
    assert rates(bad, SID) is None


def test_percentiles_and_boundaries():
    assert percentile([0, 1, 2, 3], .25) == .75
    history = [{"smoke": float(n)} for n in range(10)]
    assert compare({"smoke": 2}, history)["smoke"]["category"] == "below"
    assert compare({"smoke": 5}, history)["smoke"]["category"] == "usual"
    assert compare({"smoke": 8}, history)["smoke"]["category"] == "above"
    assert compare({"smoke": 8}, history[:9])["smoke"]["category"] == "insufficient"
    assert compare({"smoke": None}, history)["smoke"]["category"] == "insufficient"
    zeros = [{"smoke": 0.0}] * 10
    assert compare({"smoke": 0}, zeros)["smoke"]["category"] == "usual"


def test_history_is_private_prior_and_deduplicated(client):
    import uuid
    from datetime import UTC, datetime, timedelta

    from fastapi.testclient import TestClient
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from test_auth import HEADERS, register
    from test_demos import engine

    from app.main import app
    from app.modules.auth.models import User
    from app.modules.demos.models import DemoUpload, Match, MatchPlayer

    assert register(client).status_code == 201
    with Session(engine()) as db:
        user = db.scalar(select(User))
        now = datetime.now(UTC)
        ids = []
        for i in range(13):
            job = DemoUpload(owner_id=user.id, original_name="test.dem", storage_name=uuid.uuid4().hex,
                             checksum=str(i if i != 11 else 0).zfill(64), size_bytes=9,
                             status="completed", created_at=now + timedelta(minutes=i))
            db.add(job); db.flush()
            match = Match(demo_id=job.id, map_name="test", score=None, parser_version="test",
                          analysis_version="competitive-2", facts=facts(10, 5))
            db.add(match); db.flush()
            player = MatchPlayer(match_id=match.id, steam_id64=SID, name="test", team="A")
            db.add(player); db.flush()
            ids.append((str(job.id), str(player.id)))
        db.commit()
    demo, player = ids[-1]
    result = client.get(f"/demos/{demo}/comparison", params={"player_id": player})
    assert result.status_code == 200
    assert result.json()["metrics"]["smoke"]["count"] == 11
    assert result.json()["metrics"]["smoke"]["category"] == "usual"
    with TestClient(app, base_url="http://localhost:8000", headers=HEADERS) as other:
        assert register(other, "other-comparison@example.com").status_code == 201
        assert other.get(f"/demos/{demo}/comparison", params={"player_id": player}).status_code == 404
    assert client.get(f"/demos/{demo}/comparison", params={"player_id": ids[0][1]}).status_code == 404

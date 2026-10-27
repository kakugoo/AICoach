from types import SimpleNamespace

from app.modules.demos.personalization import personal_result

SID = "76561198000000000"


def player(sid=SID, team="B", ident="p"):
    return SimpleNamespace(steam_id64=sid, team=team, id=ident)


def test_personal_score_orientation_and_unknown():
    score = {"teams": [{"name": "A", "score": 5}, {"name": "B", "score": 13}]}
    assert personal_result(SID, [player()], score, "competitive-2") == {"player_id": "p", "score": [13, 5], "outcome": "win"}
    assert personal_result(SID, [player(team="A")], score, "competitive-2")["outcome"] == "loss"
    assert personal_result(SID, [player(), player(ident="other")], score, "competitive-2")["player_id"] is None
    assert personal_result(None, [player()], score, "competitive-2")["outcome"] is None
    assert personal_result(SID, [player()], score, "events-1")["score"] is None
    assert personal_result(SID, [player(team="missing")], score, "competitive-2")["outcome"] is None
    assert personal_result(SID, [player()], None, "competitive-2")["score"] is None
    assert personal_result(SID, [player()], {"teams": [{"name": "A", "score": 12}, {"name": "B", "score": 12}]}, "competitive-2")["outcome"] == "draw"

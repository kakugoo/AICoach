"""Match a chosen tracked profile to verified match facts without nickname inference."""
from app.modules.demos.parser_ids import steam_id


def personal_result(steam, players, score, analysis_version):
    sid = steam_id(steam)
    if sid is None or analysis_version != "competitive-2":
        return {"player_id": None, "outcome": None, "score": None}
    matches = [p for p in players if steam_id(p.steam_id64) == sid]
    if len(matches) != 1:
        return {"player_id": None, "outcome": None, "score": None}
    player = matches[0]
    result = {"player_id": str(player.id), "outcome": None, "score": None}
    teams = score.get("teams") if isinstance(score, dict) else None
    if not isinstance(teams, list) or len(teams) != 2 or not player.team:
        return result
    if any(not isinstance(t, dict) or not isinstance(t.get("name"), str) or type(t.get("score")) is not int
           or t["score"] < 0 for t in teams):
        return result
    own = [t for t in teams if t["name"] == player.team]
    if len(own) != 1 or teams[0]["name"] == teams[1]["name"]:
        return result
    other = next(t for t in teams if t is not own[0])
    a, b = own[0]["score"], other["score"]
    result.update({"score": [a, b], "outcome": "win" if a > b else "loss" if a < b else "draw"})
    return result

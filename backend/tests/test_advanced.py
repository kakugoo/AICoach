from app.modules.demos.advanced import calculate

A, B, C = "76561198000000001", "76561198000000002", "76561198000000003"


def fixture():
    players = [{"steam_id64": A, "team": "one"}, {"steam_id64": B, "team": "two"}, {"steam_id64": C, "team": "one"}]
    rnd = {"number": 1, "start_tick": 100, "end_tick": 1000, "winner": "T", "teams": [{"name": "one", "side": "T"}, {"name": "two", "side": "CT"}]}
    facts = {"rounds": [rnd], "events": [], "statistics_available": True}
    snaps = [{"tick": t, "steamid": s, "team_num": side, "is_alive": True, "health": 100} for t in (100, 900) for s, side in ((A, 2), (B, 3), (C, 2))]
    return players, facts, snaps, [{"tick": 900, "winner": "T"}]


def death(tick, attacker, victim, at, vt):
    return {"tick": tick, "round": 1, "excluded": None, "attacker": attacker, "victim": victim,
            "attacker_team": at, "victim_team": vt, "assister": None, "assister_team": at,
            "teamkill": at == vt, "suicide": attacker == victim, "headshot": True}


def test_round_without_kills_requires_alive_snapshot_and_round_end():
    players, facts, snaps, ends = fixture()
    res = calculate(players, facts, snaps, ends, [], [])
    assert res["players"][A]["kast_percent"] == 100
    assert res["players"][A]["opening_kills"] == 0
    snaps[:] = [s for s in snaps if not (s["tick"] == 900 and s["steamid"] == A)]
    assert calculate(players, facts, snaps, ends, [], [])["players"][A]["kast_percent"] is None
    assert calculate(players, facts, snaps, [], [], [])["players"][A]["adr"] is None


def test_opening_trade_side_and_kast():
    players, facts, snaps, ends = fixture()
    facts["events"] = [death(200, B, A, 3, 2), death(300, C, B, 2, 3)]
    result = calculate(players, facts, snaps, ends, [], [])["players"]
    assert result[B]["opening_kills"] == 1 and result[A]["opening_deaths"] == 1
    assert result[A]["traded_deaths"] == 1 and result[C]["trades"] == 1
    assert result[A]["kast_percent"] == 100 and result[C]["headshot_percent"] == 100
    assert result[C]["sides"]["T"]["kills"] == 1
    result = calculate(players, facts, snaps, ends, [], [], trade_window_ticks=50)["players"]
    assert result[A]["traded_deaths"] == 0 and result[C]["trades"] == 0


def test_damage_overkill_friendly_and_disconnect():
    players, facts, snaps, ends = fixture()
    hurts = [{"tick": 200, "user_steamid": int(B), "attacker_steamid": int(A), "dmg_health": 140, "health": 0, "attacker_team_num": 2, "user_team_num": 3},
             {"tick": 201, "user_steamid": int(C), "attacker_steamid": int(A), "dmg_health": 10, "health": 90, "attacker_team_num": 2, "user_team_num": 2},
             {"tick": 950, "user_steamid": int(A), "attacker_steamid": int(B), "dmg_health": 100, "health": 0, "attacker_team_num": 3, "user_team_num": 2}]
    result = calculate(players, facts, snaps, ends, hurts, [])["players"]
    assert result[A]["adr"] == 100 and result[B]["adr"] == 0
    result = calculate(players, facts, snaps, ends, hurts, [{"tick": 500, "user_steamid": int(A)}])["players"]
    assert result[A]["adr"] is None and result[A]["kast_percent"] is None


def test_unknown_participation_does_not_invent_zeroes():
    players, facts, snaps, ends = fixture()
    snaps[:] = [s for s in snaps if not (s["tick"] == 100 and s["steamid"] == A)]
    assert A not in calculate(players, facts, snaps, ends, [], [])["players"]


def test_same_tick_opening_and_trade_are_unknown():
    players, facts, snaps, ends = fixture()
    facts["events"] = [death(200, B, A, 3, 2), death(200, C, B, 2, 3)]
    result = calculate(players, facts, snaps, ends, [], [])["players"]
    assert result[A]["opening_deaths"] is None
    assert result[A]["traded_deaths"] is None
    assert result[A]["kast_percent"] is None

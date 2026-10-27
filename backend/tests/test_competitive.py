from copy import deepcopy

from app.modules.demos.competitive import normalize

A, B = "76561198000000001", "76561198000000002"


def player(sid):
    return {"steam_id64": sid, "name": sid, "team": None, "kills": None,
            "deaths": None, "assists": None, "headshots": None}


def event(tick, attacker, victim, round_number, attacker_team=2, victim_team=3, weapon="ak47"):
    return {"tick": tick, "attacker_steamid": attacker, "user_steamid": victim, "assister_steamid": None,
            "attacker_team_num": attacker_team, "user_team_num": victim_team, "assister_team_num": None,
            "is_warmup_period": False, "is_match_started": True, "game_phase": 2,
            "total_rounds_played": round_number, "headshot": True, "weapon": weapon}


def fixture():
    starts = [{"tick": 20, "game_phase": 2, "total_rounds_played": 0, "is_match_started": True, "is_warmup_period": False},
              {"tick": 40, "game_phase": 3, "total_rounds_played": 1, "is_match_started": True, "is_warmup_period": False}]
    ann = [{"tick": 20, "game_phase": 2, "total_rounds_played": 0, "is_warmup_period": False}]
    restarts = [{"tick": 15}]
    panels = [{"tick": 60}]
    rows = []
    for tick, sa, sb, score_a, score_b in [(20, 2, 3, 0, 0), (40, 3, 2, 1, 0), (60, 3, 2, 1, 1)]:
        rows += [{"tick": tick, "steamid": A, "team_num": sa, "team_rounds_total": score_a, "team_clan_name": "A"},
                 {"tick": tick, "steamid": B, "team_num": sb, "team_rounds_total": score_b, "team_clan_name": "B"}]
    return [player(A), player(B)], starts, ann, restarts, panels, rows


def test_knife_excluded_knife_kill_in_live_and_side_switch():
    players, starts, ann, restarts, panels, rows = fixture()
    starts.insert(0, {"tick": 1, "game_phase": 1})
    ann.insert(0, {"tick": 1, "game_phase": 1})
    knife = event(5, A, B, 0, weapon="knife") | {"game_phase": 1}
    live = event(25, A, B, 0, weapon="knife")
    p, rounds, score, facts = normalize(players, [knife, live], starts, ann, restarts, panels, rows, [{"tick": 10}], [])
    assert facts["events"][0]["excluded"] == "knife_round"
    assert facts["events"][1]["excluded"] is None and p[0]["kills"] == 1
    assert score["teams"][0]["score"] == 1 and score["teams"][1]["score"] == 1
    assert rounds[0]["winner"] == "T" and rounds[1]["winner"] == "T"
    assert any(phase["phase"] == "side_switch" for phase in facts["phases"])


def test_no_knife_warmup_teamkill_suicide_and_after_match():
    players, starts, ann, restarts, panels, rows = fixture()
    events = [event(18, A, B, 0) | {"is_warmup_period": True}, event(25, A, B, 0, 2, 2),
              event(30, A, A, 0, 2, 2), event(61, A, B, 2)]
    p, _, _, facts = normalize(players, events, starts, ann, restarts, panels, rows)
    assert not any(phase["phase"] == "knife_round" for phase in facts["phases"])
    assert p[0]["kills"] == 0 and p[0]["deaths"] == 1 and p[1]["deaths"] == 1
    assert facts["events"][0]["excluded"] == "pre_match"
    assert facts["events"][-1]["excluded"] == "after_match"


def test_missing_completion_restarts_and_ambiguous_scores_are_unknown():
    players, starts, ann, restarts, panels, rows = fixture()
    p, rounds, score, _ = normalize(deepcopy(players), [event(25, A, B, 0)], starts, ann, restarts, [], rows)
    assert not rounds and score is None and p[0]["kills"] is None
    broken = deepcopy(starts); broken[1]["total_rounds_played"] = 0
    p, rounds, score, _ = normalize(deepcopy(players), [event(25, A, B, 0)], broken, ann, restarts, panels, rows)
    assert not rounds and score is None and p[0]["kills"] is None
    rows[-1]["team_rounds_total"] = 10
    _, _, score, _ = normalize(deepcopy(players), [event(25, A, B, 0)], starts, ann, restarts, panels, rows)
    assert score is None


def test_unknown_phase_not_inferred_and_mismatched_overtime_excluded():
    players, starts, ann, restarts, panels, rows = fixture()
    ev = event(25, A, B, 0) | {"game_phase": 7}
    _, _, _, facts = normalize(players, [ev], starts, ann, restarts, panels, rows)
    assert facts["events"][0]["excluded"] == "non_live_or_unknown_phase"


def test_extra_rounds_and_multiple_side_switches():
    players, _, ann, restarts, _, _ = fixture()
    starts, rows, score_a, score_b = [], [], 0, 0
    for i in range(30):
        tick = 20 + i * 100
        switched = (12 <= i < 24) or (27 <= i < 30)
        side_a, side_b = (3, 2) if switched else (2, 3)
        starts.append({"tick": tick, "game_phase": 3 if switched else 2, "total_rounds_played": i,
                       "is_match_started": True, "is_warmup_period": False})
        rows.extend([{"tick": tick, "steamid": A, "team_num": side_a, "team_rounds_total": score_a, "team_clan_name": "A"},
                     {"tick": tick, "steamid": B, "team_num": side_b, "team_rounds_total": score_b, "team_clan_name": "B"}])
        if i % 2 == 0 or i == 29:
            score_a += 1
        else:
            score_b += 1
    finish = 3020
    rows.extend([{"tick": finish, "steamid": A, "team_num": 3, "team_rounds_total": score_a, "team_clan_name": "A"},
                 {"tick": finish, "steamid": B, "team_num": 2, "team_rounds_total": score_b, "team_clan_name": "B"}])
    _, rounds, score, facts = normalize(players, [event(25, A, B, 0)], starts, ann, restarts, [{"tick": finish}], rows)
    assert len(rounds) == 30
    assert sorted(team["score"] for team in score["teams"]) == [14, 16]
    assert len([phase for phase in facts["phases"] if phase["phase"] == "side_switch"]) == 3


def test_missing_assister_and_unknown_identity_does_not_invent_totals():
    players, starts, ann, restarts, panels, rows = fixture()
    ev = event(25, float(A), B, 0)
    result, _, _, facts = normalize(players, [ev], starts, ann, restarts, panels, rows)
    assert result[0]["kills"] is None and facts["statistics_available"] is False

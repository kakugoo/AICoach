from app.modules.demos.utility_economy import calculate

A, B = "76561198000000001", "76561198000000002"


def fixture():
    players = [{"steam_id64": A, "team": "A"}, {"steam_id64": B, "team": "B"}]
    rnd = {"number": 1, "start_tick": 100, "end_tick": 200, "winner": "T", "teams": [{"name": "A", "side": "T"}, {"name": "B", "side": "CT"}]}
    states = {A: {"participated": True, "side": "T", "won": True}, B: {"participated": True, "side": "CT", "won": False}}
    facts = {"rounds": [rnd], "advanced": {"rounds": [{"number": 1, "end_tick": 180, "players": states}]}}
    snapshots = [{"tick": 100, "steamid": int(s), "team_num": side, "is_alive": True, "balance": 500,
                  "current_equip_value": 2000, "cash_spent_this_round": 1500, "armor_value": 100,
                  "has_helmet": True, "has_defuser": False, "inventory": ["AK-47"]} for s, side in ((A, 2), (B, 3))]
    return players, facts, snapshots


def test_excludes_pre_match_and_after_round_counts_grenades_and_blinds():
    players, facts, snapshots = fixture()
    def shot(tick, weapon):
        return {"tick": tick, "weapon": weapon, "user_steamid": int(A), "user_team_num": 2}
    shots = [shot(50, "weapon_flashbang"), shot(101, "weapon_flashbang"), shot(110, "weapon_smokegrenade"),
             shot(120, "weapon_molotov"), shot(121, "weapon_incgrenade"), shot(190, "weapon_hegrenade")]
    blinds = [{"tick": 105, "attacker_steamid": int(A), "user_steamid": int(B), "attacker_team_num": 2, "user_team_num": 3, "blind_duration": 1.5},
              {"tick": 106, "attacker_steamid": int(A), "user_steamid": int(A), "attacker_team_num": 2, "user_team_num": 2, "blind_duration": 0.5}]
    res = calculate(players, facts, shots, blinds, [], snapshots)
    p = res["players"][A]
    assert p["uses"] == {"flash": 1, "smoke": 1, "he": 0, "molotov": 1, "incendiary": 1, "decoy": 0}
    assert p["blind_enemies"] == 1 and p["blind_self"] == 1
    assert p["rounds"][0]["economy"]["equipment_value"] == 2000
    assert res["rounds"][0]["teams"][0]["equipment_value"] == 2000


def test_he_fire_damage_and_overkill_and_unknown_disconnect():
    players, facts, snapshots = fixture()
    hurts = [{"tick": 110, "user_steamid": int(B), "attacker_steamid": int(A), "dmg_health": 60, "health": 40, "attacker_team_num": 2, "user_team_num": 3, "weapon": "hegrenade"},
             {"tick": 120, "user_steamid": int(B), "attacker_steamid": int(A), "dmg_health": 100, "health": 0, "attacker_team_num": 2, "user_team_num": 3, "weapon": "inferno"}]
    p = calculate(players, facts, [], [], hurts, snapshots)["players"][A]
    assert p["damage_he_enemy"] == 60 and p["damage_fire_enemy"] == 40
    p = calculate(players, facts, [], [], hurts, snapshots, [{"tick": 140, "user_steamid": int(A)}])["players"][A]
    assert p["damage_he_enemy"] is None and p["uses"]["flash"] is None


def test_missing_snapshots_and_ambiguous_events_not_assumed_zero():
    players, facts, snapshots = fixture()
    snapshots.pop()
    shots = [{"tick": 110, "weapon": "weapon_hegrenade", "user_steamid": None, "user_team_num": 2}]
    r = calculate(players, facts, shots, [], [], snapshots)
    assert r["players"][A]["uses"]["he"] is None
    assert r["rounds"][0]["teams"][1]["equipment_value"] is None


def test_same_tick_health_order_unknown_and_missing_round_end():
    players, facts, snapshots = fixture()
    hurt = {"tick": 110, "user_steamid": int(B), "attacker_steamid": int(A), "dmg_health": 10, "health": 90, "attacker_team_num": 2, "user_team_num": 3, "weapon": "hegrenade"}
    result = calculate(players, facts, [], [], [hurt, hurt | {"health": 80}], snapshots)
    assert result["players"][A]["damage_he_enemy"] is None
    facts["advanced"]["rounds"][0]["end_tick"] = None
    assert calculate(players, facts, [], [], [], snapshots)["players"] == {}


def test_flash_ally_and_side_switch():
    players, facts, snapshots = fixture()
    c = "76561198000000003"
    players.append({"steam_id64": c, "team": "A"})
    facts["rounds"][0]["teams"] = [{"name": "A", "side": "CT"}, {"name": "B", "side": "T"}]
    facts["advanced"]["rounds"][0]["players"][A]["side"] = "CT"
    facts["advanced"]["rounds"][0]["players"][c] = {"participated": True, "side": "CT", "won": True}
    snapshots[0]["team_num"] = 3
    blinds = [{"tick": 105, "attacker_steamid": int(A), "user_steamid": int(c), "attacker_team_num": 3, "user_team_num": 3, "blind_duration": 0.5}]
    p = calculate(players, facts, [], blinds, [], snapshots)["players"][A]
    assert p["blind_allies"] == 1 and p["rounds"][0]["side"] == "CT"

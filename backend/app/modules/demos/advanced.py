"""Versioned analytics over explicitly verified competitive round evidence."""
from app.modules.demos.parser_ids import steam_id

VERSION = "advanced-1"


def calculate(players, facts, snapshots, round_ends, hurts, disconnects, trade_window_ticks=320):
    """Calculate conservative per-round facts; None means evidence is insufficient."""
    ids = {p["steam_id64"]: p for p in players if p.get("steam_id64")}
    rounds = facts.get("rounds", [])
    if not rounds or not facts.get("statistics_available"):
        return {"version": VERSION, "players": {}, "rounds": []}
    snap = {(r.get("tick"), str(r.get("steamid"))): r for r in snapshots}
    all_results = {sid: [] for sid in ids}
    result_rounds = []
    for rnd in rounds:
        start, boundary = rnd["start_tick"], rnd["end_tick"]
        ends = [e for e in round_ends if isinstance(e.get("tick"), int) and start <= e["tick"] < boundary
                and e.get("winner") == rnd.get("winner")]
        end = ends[0]["tick"] if len(ends) == 1 else None
        states = {}
        for sid, player in ids.items():
            initial = snap.get((start, sid))
            side_num = initial.get("team_num") if initial else None
            side = {2: "T", 3: "CT"}.get(side_num)
            expected = next((t.get("side") for t in rnd.get("teams", []) if t.get("name") == player.get("team")), None)
            participated = bool(initial and initial.get("is_alive") is True and initial.get("health") == 100
                                and side and side == expected)
            # A missing or invalid start snapshot is not proof of nonparticipation.
            states[sid] = {"participated": True if participated else None, "side": side if participated else None,
                           "round_end_verified": end is not None,
                           "kills": 0, "deaths": 0, "assists": 0, "headshots": 0,
                           "opening_kill": False, "opening_death": False, "trades": 0, "traded_deaths": 0,
                           "damage": 0, "kast": None, "won": (expected == rnd.get("winner")) if participated else None}
        deaths = [e for e in facts.get("events", []) if e.get("excluded") is None and e.get("round") == rnd["number"]
                  and end is not None and e.get("tick") is not None and e["tick"] <= end]
        deaths.sort(key=lambda e: e["tick"])
        enemy = [e for e in deaths if e.get("attacker") in ids and e.get("victim") in ids
                 and not e.get("teamkill") and not e.get("suicide") and e.get("attacker_team") in (2, 3)
                 and e.get("victim_team") in (2, 3) and e["attacker_team"] != e["victim_team"]]
        headshots_known = all(isinstance(e.get("headshot"), bool) for e in enemy)
        assists_known = all(not e.get("assister") or e.get("assister_team") in (2, 3) for e in enemy)
        trade_ambiguous = len({e["tick"] for e in enemy}) != len(enemy)
        first_tick = enemy[0]["tick"] if enemy else end
        unresolved_first = any(e.get("attacker") is None and e["tick"] <= first_tick for e in deaths)
        opening_known = end is not None and not unresolved_first and (len(enemy) < 2 or enemy[0]["tick"] != enemy[1]["tick"])
        if opening_known and enemy:
            states[enemy[0]["attacker"]]["opening_kill"] = True
            states[enemy[0]["victim"]]["opening_death"] = True
        for e in deaths:
            victim, attacker, assister = e.get("victim"), e.get("attacker"), e.get("assister")
            if victim in states:
                states[victim]["deaths"] += 1
            if e in enemy:
                states[attacker]["kills"] += 1
                states[attacker]["headshots"] += int(e.get("headshot") is True)
                if assister in states and assister not in (attacker, victim) and e.get("assister_team") == e.get("attacker_team"):
                    states[assister]["assists"] += 1
        for i, death in enumerate(enemy):
            # A trade kills the original attacker, by a teammate of the victim, in the same round.
            candidates = [e for e in enemy[i + 1:] if 0 < e["tick"] - death["tick"] <= trade_window_ticks
                          and e["victim"] == death["attacker"] and e["attacker_team"] == death["victim_team"]]
            if candidates and (len(candidates) == 1 or candidates[0]["tick"] != candidates[1]["tick"]):
                states[candidates[0]["attacker"]]["trades"] += 1
                states[death["victim"]]["traded_deaths"] += 1
        hp = {sid: 100 for sid, state in states.items() if state["participated"]}
        damage_known = end is not None
        for h in sorted((e for e in hurts if end is not None and start <= e.get("tick", -1) <= end), key=lambda e: e["tick"]):
            victim, attacker = steam_id(h.get("user_steamid")), steam_id(h.get("attacker_steamid"))
            damage, remaining = h.get("dmg_health"), h.get("health")
            if victim not in hp or not isinstance(damage, int) or not isinstance(remaining, int) or damage < 0 or remaining < 0:
                damage_known = False
                continue
            health_loss = hp[victim] - remaining
            # CS2 exposes rounded integer damage and health separately; one point can differ.
            if health_loss < 0 or abs(health_loss - min(damage, hp[victim])) > 1:
                damage_known = False
            effective = max(0, health_loss)
            hp[victim] = remaining
            if (h.get("attacker_team_num") in (2, 3) and h.get("user_team_num") in (2, 3)
                    and h["attacker_team_num"] != h["user_team_num"] and attacker not in states):
                damage_known = False
            if attacker in states and attacker != victim and h.get("attacker_team_num") in (2, 3) and h.get("user_team_num") in (2, 3) and h["attacker_team_num"] != h["user_team_num"]:
                states[attacker]["damage"] += effective
        for sid, state in states.items():
            if not state["participated"]:
                continue
            if not headshots_known:
                state["headshots"] = None
            disconnected = any(start <= d.get("tick", -1) <= (end if end is not None else boundary)
                               and str(d.get("user_steamid")) == sid for d in disconnects)
            end_state = snap.get((end, sid)) if end is not None else None
            survived = (end_state.get("is_alive") if end_state else None)
            if state["deaths"]:
                survived = False
            if disconnected and not state["deaths"]:
                survived = None
            if end is not None and (state["kills"] or state["assists"] or
                                    (state["traded_deaths"] and not trade_ambiguous) or survived is True):
                state["kast"] = True
            elif end is not None and survived is False and assists_known and not trade_ambiguous:
                state["kast"] = False
            if not assists_known:
                state["assists"] = None
            if trade_ambiguous:
                state["trades"] = state["traded_deaths"] = None
            if not damage_known or disconnected:
                state["damage"] = None
            if not opening_known:
                state["opening_kill"] = state["opening_death"] = None
            all_results[sid].append({"round": rnd["number"], **state})
        result_rounds.append({"number": rnd["number"], "end_tick": end, "players": states})
    aggregates = {}
    for sid, rows in all_results.items():
        n = len(rows)
        if not n:
            continue
        complete = len(rows) == len(rounds) and all(r["round_end_verified"] for r in rows)
        def ratio(a, b):
            return round(a / b, 4) if b else None
        kills, deaths = sum(r["kills"] for r in rows), sum(r["deaths"] for r in rows)
        damage_valid = all(r["damage"] is not None for r in rows)
        kast_valid = all(r["kast"] is not None for r in rows)
        headshots_valid = all(r["headshots"] is not None for r in rows)
        openings_valid = all(r["opening_kill"] is not None for r in rows)
        trades_valid = all(r["trades"] is not None for r in rows)
        ok, od = sum(r["opening_kill"] is True for r in rows), sum(r["opening_death"] is True for r in rows)
        sides = {}
        for side in ("CT", "T"):
            subset = [r for r in rows if r["side"] == side]
            sides[side] = {"rounds": len(subset), "kills": sum(r["kills"] for r in subset),
                           "deaths": sum(r["deaths"] for r in subset), "assists": sum(r["assists"] for r in subset) if all(r["assists"] is not None for r in subset) else None} if complete else None
        aggregates[sid] = {"rounds": n if complete else None, "kills": kills if complete else None,
            "deaths": deaths if complete else None, "kd": ratio(kills, deaths) if complete else None,
            "kd_difference": kills - deaths if complete else None,
            "headshot_percent": ratio(sum(r["headshots"] for r in rows) * 100, kills) if complete and headshots_valid else None,
            "kills_per_round": ratio(kills, n) if complete else None,
            "adr": ratio(sum(r["damage"] for r in rows), n) if complete and damage_valid else None,
            "kast_percent": ratio(sum(r["kast"] for r in rows) * 100, n) if complete and kast_valid else None,
            "opening_kills": ok if complete and openings_valid else None, "opening_deaths": od if complete and openings_valid else None,
            "opening_win_percent": ratio(ok * 100, ok + od) if complete and openings_valid else None,
            "opening_participation_percent": ratio((ok + od) * 100, n) if complete and openings_valid else None,
            "trades": sum(r["trades"] for r in rows) if complete and trades_valid else None,
            "traded_deaths": sum(r["traded_deaths"] for r in rows) if complete and trades_valid else None,
            "sides": sides, "round_details": rows}
    return {"version": VERSION, "trade_window_ticks": trade_window_ticks, "players": aggregates, "rounds": result_rounds}

"""Conservative round normalization; ambiguous data stays explicitly unknown."""
import math
from collections import Counter
from numbers import Integral, Real

from app.modules.demos.parser_ids import steam_id

ANALYSIS_VERSION = "competitive-2"


def integer(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real) and math.isfinite(value) and value.is_integer() and abs(value) < 1000000000:
        return int(value)
    return None


def normalize(players, deaths, starts, announcements, restarts, panels, tick_rows, warmups=None, prestarts=None):
    warmups, prestarts = warmups or [], prestarts or []
    # Require an explicit reset/new-match marker followed by a live-phase announcement.
    anchors = sorted(integer(e.get("tick")) for e in restarts if integer(e.get("tick")) is not None)
    candidates = sorted(integer(e.get("tick")) for e in announcements
        if integer(e.get("tick")) is not None and e.get("game_phase") == 2
        and e.get("is_warmup_period") is False and e.get("total_rounds_played") == 0)
    start_tick = next((tick for tick in reversed(candidates) if any(a <= tick for a in anchors)), None)
    finish_ticks = sorted(integer(e.get("tick")) for e in panels if integer(e.get("tick")) is not None
                          and start_tick is not None and integer(e.get("tick")) > start_tick)
    finish_tick = finish_ticks[-1] if finish_ticks else None
    knife_start = next((integer(e.get("tick")) for e in starts
        if start_tick is not None and integer(e.get("tick")) is not None
        and e["tick"] < start_tick and e.get("game_phase") == 1
        and any(a.get("tick") == e["tick"] and a.get("game_phase") == 1 for a in announcements)), None)
    knife_end = next((integer(e.get("tick")) for e in warmups
        if knife_start is not None and integer(e.get("tick")) is not None
        and knife_start < e["tick"] < start_tick), None)
    knife_events = [e for e in deaths if knife_start is not None and knife_end is not None
                    and integer(e.get("tick")) is not None and knife_start <= e["tick"] < knife_end]
    # The knives corroborate a separately signalled pre-match round; they are not sufficient alone.
    if not knife_events or not all(str(e.get("weapon", "")).startswith(("knife", "bayonet"))
                                   for e in knife_events):
        knife_start, knife_end = None, None
    round_starts = sorted((e for e in starts if start_tick is not None and integer(e.get("tick")) is not None
        and e["tick"] >= start_tick and (finish_tick is None or e["tick"] < finish_tick)
        and e.get("is_warmup_period") is False and e.get("is_match_started") is True
        and integer(e.get("total_rounds_played")) is not None), key=lambda e: e["tick"])
    rounds = []
    # Never treat a duplicate/restarted round as an official round.
    for index, event in enumerate(round_starts):
        number = integer(event.get("total_rounds_played"))
        next_tick = integer(round_starts[index + 1].get("tick")) if index + 1 < len(round_starts) else finish_tick
        if number != index or next_tick is None:
            rounds = []
            break
        rounds.append({"number": index + 1, "start_tick": integer(event["tick"]),
                       "end_tick": next_tick, "winner": None, "tick": next_tick})
    if not rounds or finish_tick is None:
        rounds = []
    raw = []
    counted = []
    identity_ambiguous = False
    for e in deaths:
        tick = integer(e.get("tick"))
        # IDs represented as floating point can lose precision; never silently count them as absent.
        for key in ("attacker_steamid", "user_steamid", "assister_steamid"):
            value = e.get(key)
            if isinstance(value, Real) and not isinstance(value, Integral) and math.isfinite(value) and abs(value) > 1000:
                identity_ambiguous = True
        attacker = steam_id(e.get("attacker_steamid"))
        victim = steam_id(e.get("user_steamid"))
        assister = steam_id(e.get("assister_steamid"))
        n = integer(e.get("total_rounds_played"))
        phase = integer(e.get("game_phase"))
        reason = None
        if tick is None or start_tick is None or not rounds:
            reason = "insufficient_round_evidence"
        elif tick < start_tick:
            reason = "knife_round" if knife_start is not None and knife_start <= tick < knife_end else "pre_match"
        elif finish_tick is not None and (tick >= finish_tick or e.get("is_match_started") is False):
            reason = "after_match"
        elif e.get("is_warmup_period") is not False:
            reason = "warmup_or_unknown"
        elif e.get("is_match_started") is not True or phase not in (2, 3):
            reason = "non_live_or_unknown_phase"
        elif n is None or n >= len(rounds) or n < 0 or not (rounds[n]["start_tick"] <= tick < rounds[n]["end_tick"]):
            reason = "outside_completed_round"
        at, vt = integer(e.get("attacker_team_num")), integer(e.get("user_team_num"))
        flags = {"teamkill": attacker is not None and victim is not None and attacker != victim and at in (2, 3) and at == vt,
                 "suicide": attacker is not None and attacker == victim}
        headshot = e.get("headshot")
        item = {"type": "player_death", "tick": tick, "round": n + 1 if n is not None else None,
                "attacker": attacker, "victim": victim, "assister": assister,
                "headshot": headshot if isinstance(headshot, bool) else None,
                "weapon": str(e.get("weapon"))[:80] if e.get("weapon") is not None else None,
                "attacker_team": at, "victim_team": vt, "assister_team": integer(e.get("assister_team_num")), "excluded": reason, **flags}
        raw.append(item)
        if reason is None:
            counted.append(item)
    # Two fixed player rosters identified from the first live freeze end.
    first_tick = rounds[0]["start_tick"] if rounds else None
    first = [r for r in tick_rows if integer(r.get("tick")) == first_tick and steam_id(r.get("steamid"))]
    groups = {}
    for r in first:
        side = integer(r.get("team_num"))
        sid = steam_id(r.get("steamid"))
        if side in (2, 3):
            groups.setdefault(side, set()).add(sid)
    score = None
    group_meta = []
    if set(groups) == {2, 3} and groups[2] and groups[3] and not (groups[2] & groups[3]):
        group_meta = [{"name": next((str(r.get("team_clan_name")) for r in first
                       if integer(r.get("team_num")) == side and r.get("team_clan_name")), f"Команда {i}"),
                       "members": groups[side]} for i, side in enumerate((2, 3), 1)]
        snapshots = []
        for tick in [r["start_tick"] for r in rounds] + [finish_tick]:
            rows = [r for r in tick_rows if integer(r.get("tick")) == tick]
            states = []
            for group in group_meta:
                subset = [r for r in rows if steam_id(r.get("steamid")) in group["members"]]
                sides = {integer(r.get("team_num")) for r in subset}
                scores = {integer(r.get("team_rounds_total")) for r in subset}
                if not subset or len(sides) != 1 or len(scores) != 1 or None in sides or None in scores:
                    states = []
                    break
                states.append((sides.pop(), scores.pop()))
            snapshots.append(states)
        valid = all(len(states) == 2 and {states[0][0], states[1][0]} == {2, 3} for states in snapshots)
        if valid:
            for i, rnd in enumerate(rounds):
                delta = [snapshots[i+1][j][1] - snapshots[i][j][1] for j in (0, 1)]
                if delta not in ([1, 0], [0, 1]):
                    valid = False
                    break
                winner_idx = delta.index(1)
                rnd["winner"] = "T" if snapshots[i][winner_idx][0] == 2 else "CT"
                rnd["winning_team"] = group_meta[winner_idx]["name"]
                rnd["teams"] = [{"name": group_meta[j]["name"], "side": "T" if snapshots[i][j][0] == 2 else "CT"} for j in (0, 1)]
        if valid and snapshots[0][0][1] == snapshots[0][1][1] == 0:
            score = {"teams": [{"name": group_meta[j]["name"], "score": snapshots[-1][j][1]} for j in (0, 1)]}
        else:
            for rnd in rounds:
                rnd["winner"] = None
                rnd.pop("winning_team", None)
                rnd.pop("teams", None)
    if score is None:
        # A freeze boundary alone does not prove a round was scored or completed.
        for item in raw:
            if item["excluded"] is None:
                item["excluded"] = "unverified_round_outcome"
        counted = []
        rounds = []
    # Missing/ambiguous IDs or sides make the relevant totals unknown, not zero.
    known_players = {p["steam_id64"]: p for p in players}
    phase_ambiguous = any(e["excluded"] in ("insufficient_round_evidence", "warmup_or_unknown", "non_live_or_unknown_phase") for e in raw)
    data_valid = bool(rounds) and bool(counted) and not identity_ambiguous and not phase_ambiguous and all(e["victim"] in known_players and
        (e["attacker"] is None or e["attacker"] in known_players) and
        (e["assister"] is None or e["assister"] in known_players) and
        (e["attacker"] is None or e["suicide"] or (e["attacker_team"] in (2, 3) and e["victim_team"] in (2, 3)))
        for e in counted)
    assists_valid = data_valid and all(not e["assister"] or e["assister_team"] in (2, 3) for e in counted)
    headshots_valid = data_valid and all(e["headshot"] is not None for e in counted if e["attacker"] and not e["suicide"] and not e["teamkill"])
    totals = {sid: Counter() for sid in known_players}
    if data_valid:
        for e in counted:
            totals[e["victim"]]["deaths"] += 1
            if e["attacker"] and not e["suicide"] and not e["teamkill"]:
                totals[e["attacker"]]["kills"] += 1
                if e["headshot"]:
                    totals[e["attacker"]]["headshots"] += 1
                if e["assister"] and e["assister_team"] == e["attacker_team"] and e["assister"] not in (e["attacker"], e["victim"]):
                    totals[e["assister"]]["assists"] += 1
        for p in players:
            p.update({key: totals[p["steam_id64"]][key] for key in ("kills", "deaths", "assists", "headshots")})
            if not assists_valid:
                p["assists"] = None
            if not headshots_valid:
                p["headshots"] = None
            for group in group_meta:
                if p["steam_id64"] in group["members"]:
                    p["team"] = group["name"][:32]
    phases = []
    if start_tick is not None:
        if knife_start is not None:
            phases.append({"phase": "knife_round", "start_tick": knife_start, "end_tick": knife_end})
            phases.append({"phase": "side_selection_or_pre_match", "start_tick": knife_end, "end_tick": start_tick})
        else:
            phases.append({"phase": "pre_match_unknown", "end_tick": start_tick, "start_tick": None})
        for e in prestarts:
            if e.get("is_warmup_period") is True and integer(e.get("tick")) is not None and e["tick"] < start_tick:
                warmup_end = next((integer(candidate.get("tick")) for candidate in sorted(prestarts, key=lambda item: item.get("tick", -1))
                    if integer(candidate.get("tick")) is not None and candidate["tick"] > e["tick"]
                    and candidate["tick"] <= start_tick and candidate.get("is_warmup_period") is False), start_tick)
                phases.append({"phase": "warmup", "start_tick": integer(e["tick"]), "end_tick": warmup_end})
        phases.append({"phase": "live_match", "start_tick": start_tick, "end_tick": finish_tick})
        for i in range(1, len(rounds)):
            if rounds[i].get("teams") and rounds[i-1].get("teams") and rounds[i]["teams"][0]["side"] != rounds[i-1]["teams"][0]["side"]:
                phases.append({"phase": "side_switch", "start_tick": rounds[i]["start_tick"], "end_tick": rounds[i]["start_tick"]})
        if finish_tick is not None:
            phases.append({"phase": "completed", "start_tick": finish_tick, "end_tick": None})
    else:
        phases.append({"phase": "unknown", "start_tick": None, "end_tick": None})
    facts = {"events": raw, "phases": phases, "rounds": rounds, "match_start_tick": start_tick,
             "match_end_tick": finish_tick, "statistics_available": data_valid,
             "algorithm": ANALYSIS_VERSION, "excluded_reasons": dict(Counter(e["excluded"] for e in raw if e["excluded"]))}
    return players, rounds, score, facts

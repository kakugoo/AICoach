"""Extract observed demo events without interpreting player decisions."""
import math
from importlib.metadata import version
from numbers import Integral, Real

from demoparser2 import DemoParser

ANALYSIS_VERSION = "events-1"


def steam_id(value: object) -> str | None:
    if isinstance(value, Integral):
        value = str(int(value))
    if isinstance(value, str) and value.isdigit() and len(value) == 17:
        return value
    return None


def parse_demo(path: str) -> dict:
    parser = DemoParser(path)
    header = parser.parse_header()
    if header.get("demo_file_stamp") != "PBDEMS2\x00":
        raise ValueError("Not a CS2 demo")
    map_name = header.get("map_name") or None
    if map_name is not None and (not isinstance(map_name, str) or len(map_name) > 128):
        raise ValueError("Invalid map name")
    player_info = parser.parse_player_info()
    if not {"name", "steamid"}.issubset(player_info.columns):
        raise ValueError("Player information unavailable")
    players = {}
    for row in player_info.to_dict("records"):
        sid = steam_id(row.get("steamid"))
        name = row.get("name")
        if sid and isinstance(name, str) and name:
            players[sid] = {"steam_id64": sid, "name": name[:128], "team": None,
                            "kills": None, "deaths": None, "assists": None, "headshots": None}
    if not players:
        raise ValueError("No identifiable players")
    deaths = parser.parse_event("player_death")
    columns = set(deaths.columns)
    required = {"attacker_steamid", "user_steamid", "assister_steamid", "headshot", "tick"}
    events = []
    records = deaths.to_dict("records") if required.issubset(columns) else []
    # Floating-point Steam IDs may already have lost precision; never turn those
    # events into apparently authoritative zero totals.
    imprecise = any(isinstance(row.get(key), Real) and not isinstance(row.get(key), Integral)
                    and math.isfinite(row[key]) and row[key] != 0
                    for row in records for key in ("attacker_steamid", "user_steamid", "assister_steamid"))
    if required.issubset(columns) and not imprecise:
        for player in players.values():
            player.update(kills=0, deaths=0, assists=0, headshots=0)
        for row in records:
            attacker, victim, assister = (steam_id(row.get(k)) for k in ("attacker_steamid", "user_steamid", "assister_steamid"))
            headshot = row.get("headshot")
            if victim in players:
                players[victim]["deaths"] += 1
            if attacker in players and attacker != victim:
                players[attacker]["kills"] += 1
                if headshot is True or headshot == 1:
                    players[attacker]["headshots"] += 1
            if assister in players and assister not in (attacker, victim):
                players[assister]["assists"] += 1
            tick = row.get("tick")
            if len(events) < 20000 and isinstance(tick, Integral):
                events.append({"type": "player_death", "tick": int(tick), "attacker": attacker,
                               "victim": victim, "assister": assister, "headshot": bool(headshot) if headshot is not None and not (isinstance(headshot, float) and math.isnan(headshot)) else None})
    round_data = parser.parse_event("round_end")
    rounds = []
    if {"winner", "tick"}.issubset(round_data.columns):
        for row in round_data.to_dict("records"):
            tick = row.get("tick")
            winner = row.get("winner")
            side = {2: "T", 3: "CT", "TERRORIST": "T", "CT": "CT"}.get(winner)
            rounds.append({"number": len(rounds) + 1, "winner": side, "tick": int(tick) if isinstance(tick, Integral) else None})
    return {"map_name": map_name, "score": None, "parser_version": version("demoparser2"),
            "analysis_version": ANALYSIS_VERSION, "players": list(players.values()), "rounds": rounds,
            "facts": {"events": events, "event_scope": "all_recorded_events_may_include_warmup", "events_truncated": len(deaths) > len(events)}}

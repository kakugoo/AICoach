"""Extract raw events and conservative competitive facts from a CS2 demo."""
from importlib.metadata import version
from numbers import Integral

from demoparser2 import DemoParser

from app.core.config import get_settings
from app.modules.demos.advanced import calculate
from app.modules.demos.competitive import ANALYSIS_VERSION, integer, normalize
from app.modules.demos.parser_ids import steam_id


def parse_demo(path: str) -> dict:
    parser = DemoParser(path)
    header = parser.parse_header()
    if header.get("demo_file_stamp") != "PBDEMS2\x00":
        raise ValueError("Not a CS2 demo")
    map_name = header.get("map_name") or None
    if map_name is not None and (not isinstance(map_name, str) or len(map_name) > 128):
        raise ValueError("Invalid map name")
    info = parser.parse_player_info()
    if not {"name", "steamid"}.issubset(info.columns):
        raise ValueError("Player information unavailable")
    players = {}
    for row in info.to_dict("records"):
        sid, name = steam_id(row.get("steamid")), row.get("name")
        if sid and isinstance(name, str) and name:
            players[sid] = {"steam_id64": sid, "name": name[:128], "team": None,
                            "kills": None, "deaths": None, "assists": None, "headshots": None}
    if not players:
        raise ValueError("No identifiable players")
    props = ["is_warmup_period", "is_match_started", "total_rounds_played", "game_phase"]
    # A missing or incompatible phase property must not turn all deaths into live statistics.
    try:
        deaths = parser.parse_event("player_death", player=["team_num"], other=props).to_dict("records")
        starts = parser.parse_event("round_freeze_end", other=props).to_dict("records")
        announcements = parser.parse_event("round_announce_match_start", other=props).to_dict("records")
        restarts = parser.parse_event("begin_new_match", other=props).to_dict("records")
        panels = parser.parse_event("cs_win_panel_match", other=props).to_dict("records")
        warmups = parser.parse_event("round_announce_warmup", other=props).to_dict("records")
        prestarts = parser.parse_event("round_prestart", other=props).to_dict("records")
        ticks = sorted({int(r["tick"]) for r in starts + panels if isinstance(r.get("tick"), Integral)})
        ticks_data = parser.parse_ticks(["team_num", "team_rounds_total", "team_clan_name"], ticks=ticks).to_dict("records") if ticks else []
    except Exception:  # noqa: BLE001 - retain raw events when phase properties are unavailable
        deaths_frame = parser.parse_event("player_death")
        deaths = deaths_frame.to_dict("records")
        starts, announcements, restarts, panels, ticks_data, warmups, prestarts = [], [], [], [], [], [], []
    player_list, rounds, score, facts = normalize(list(players.values()), deaths, starts, announcements, restarts, panels, ticks_data, warmups, prestarts)
    if rounds:
        try:
            ends = parser.parse_event("round_end").to_dict("records")
            hurts = parser.parse_event("player_hurt", player=["team_num"]).to_dict("records")
            disconnects = parser.parse_event("player_disconnect").to_dict("records")
            snapshot_ticks = sorted({r["start_tick"] for r in rounds} | {
                int(e["tick"]) for e in ends if isinstance(e.get("tick"), Integral)})
            snapshots = parser.parse_ticks(["team_num", "is_alive", "health"], ticks=snapshot_ticks).to_dict("records")
            facts["advanced"] = calculate(player_list, facts, snapshots, ends, hurts, disconnects,
                                          trade_window_ticks=get_settings().demo_trade_window_ticks)
            facts["advanced_source"] = {
                "hurt": [{"tick": integer(h.get("tick")), "attacker": steam_id(h.get("attacker_steamid")),
                          "victim": steam_id(h.get("user_steamid")), "damage_health": integer(h.get("dmg_health")),
                          "health": integer(h.get("health")), "attacker_team": integer(h.get("attacker_team_num")),
                          "victim_team": integer(h.get("user_team_num"))} for h in hurts],
                "disconnects": [{"tick": integer(e.get("tick")), "player": steam_id(e.get("user_steamid"))}
                                for e in disconnects],
            }
        except (KeyError, TypeError, ValueError, AttributeError):
            # Advanced analysis is optional; never compromise the established result.
            facts["advanced"] = {"version": "advanced-1", "players": {}, "rounds": []}
    stored_rounds = [{"number": r["number"], "winner": r["winner"], "tick": r["tick"]} for r in rounds]
    return {"map_name": map_name, "score": score, "parser_version": version("demoparser2"),
            "analysis_version": ANALYSIS_VERSION, "players": player_list, "rounds": stored_rounds, "facts": facts}

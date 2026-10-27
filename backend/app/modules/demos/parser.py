"""Extract raw events and conservative competitive facts from a CS2 demo."""
import math
from importlib.metadata import version
from numbers import Integral, Real

from demoparser2 import DemoParser

from app.core.config import get_settings
from app.modules.demos.advanced import calculate
from app.modules.demos.competitive import ANALYSIS_VERSION, integer, normalize
from app.modules.demos.parser_ids import steam_id
from app.modules.demos.utility_economy import calculate as calculate_utility_economy


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
        try:
            shots = parser.parse_event("weapon_fire", player=["team_num"]).to_dict("records")
            blinds = parser.parse_event("player_blind", player=["team_num"]).to_dict("records")
            equipment = parser.parse_ticks(["team_num", "is_alive", "balance", "current_equip_value",
                "cash_spent_this_round", "armor_value", "has_helmet", "has_defuser", "inventory"],
                ticks=[r["start_tick"] for r in rounds]).to_dict("records")
            if len(shots) + len(blinds) + len(hurts) > 200000:
                raise ValueError("Too many events for utility analysis")
            facts["utility_economy"] = calculate_utility_economy(player_list, facts, shots, blinds, hurts, equipment, disconnects)
            facts["utility_economy"]["source"] = {
                "weapon_fire": [{"tick": integer(e.get("tick")), "player": steam_id(e.get("user_steamid")),
                                 "team": integer(e.get("user_team_num")), "weapon": e.get("weapon")}
                                for e in shots if e.get("weapon") in (
                                    "weapon_flashbang", "weapon_smokegrenade", "weapon_hegrenade",
                                    "weapon_molotov", "weapon_incgrenade", "weapon_decoy")],
                "grenade_hurt": [{"tick": integer(e.get("tick")), "attacker": steam_id(e.get("attacker_steamid")),
                                  "victim": steam_id(e.get("user_steamid")), "weapon": e.get("weapon"),
                                  "damage_health": integer(e.get("dmg_health")), "health": integer(e.get("health"))}
                                 for e in hurts if e.get("weapon") in ("hegrenade", "inferno")],
                "player_blind": [{"tick": integer(e.get("tick")), "attacker": steam_id(e.get("attacker_steamid")),
                                  "victim": steam_id(e.get("user_steamid")), "entity": integer(e.get("entityid")),
                                  "duration": float(e["blind_duration"]) if isinstance(e.get("blind_duration"), Real)
                                  and math.isfinite(e["blind_duration"]) else None} for e in blinds],
            }
            smoke = []
            for event_type in ("smokegrenade_detonate", "smokegrenade_expired"):
                frame = parser.parse_event(event_type, player=["team_num"])
                if hasattr(frame, "to_dict"):
                    smoke.extend({"type": event_type, "tick": integer(e.get("tick")),
                                  "player": steam_id(e.get("user_steamid")), "entity": integer(e.get("entityid"))}
                                 for e in frame.to_dict("records"))
            facts["utility_economy"]["source_smoke"] = smoke
        except Exception:  # noqa: BLE001 - optional parser features must not break existing analytics
            facts["utility_economy"] = {"version": "utility-economy-1", "players": {}, "rounds": []}
    stored_rounds = [{"number": r["number"], "winner": r["winner"], "tick": r["tick"]} for r in rounds]
    return {"map_name": map_name, "score": score, "parser_version": version("demoparser2"),
            "analysis_version": ANALYSIS_VERSION, "players": player_list, "rounds": stored_rounds, "facts": facts}

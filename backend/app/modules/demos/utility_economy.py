"""Conservative utility and freeze-end economy from confirmed rounds."""
import math
from numbers import Real

from app.modules.demos.parser_ids import steam_id

VERSION = "utility-economy-1"
WEAPONS = {"weapon_flashbang": "flash", "weapon_smokegrenade": "smoke", "weapon_hegrenade": "he", "weapon_molotov": "molotov", "weapon_incgrenade": "incendiary", "weapon_decoy": "decoy"}


def calculate(players, facts, shots, blinds, hurts, snapshots, disconnects=None):
    rounds = facts.get("rounds", [])
    advanced = {r["number"]: r for r in facts.get("advanced", {}).get("rounds", [])}
    if not rounds or not advanced:
        return {"version": VERSION, "players": {}, "rounds": []}
    known = {p["steam_id64"]: p for p in players if p.get("steam_id64")}
    by_tick = {(s.get("tick"), steam_id(s.get("steamid"))): s for s in snapshots}
    result = {sid: [] for sid in known}
    output_rounds, events = [], []
    for rnd in rounds:
        n, start = rnd["number"], rnd["start_tick"]
        context = advanced.get(n, {})
        end = context.get("end_tick")
        states = context.get("players", {})
        if not isinstance(end, int):
            continue
        rr = {sid: {"round": n, "side": states.get(sid, {}).get("side"), "won": states.get(sid, {}).get("won"),
                    "uses": dict.fromkeys(WEAPONS.values(), 0), "blind_enemies": 0, "blind_allies": 0,
                    "blind_self": 0, "damage_he_enemy": 0, "damage_fire_enemy": 0,
                    "damage_he_allies": 0, "damage_fire_allies": 0,
                    "damage_he_self": 0, "damage_fire_self": 0, "economy": None}
              for sid in known if states.get(sid, {}).get("participated") is True}
        valid = True
        for shot in shots:
            tick = shot.get("tick")
            kind = WEAPONS.get(shot.get("weapon"))
            if not kind or not isinstance(tick, int) or not start <= tick <= end:
                continue
            sid = steam_id(shot.get("user_steamid")); side = shot.get("user_team_num")
            if sid not in rr or side not in (2, 3) or rr[sid]["side"] != {2: "T", 3: "CT"}[side]:
                valid = False
                continue
            rr[sid]["uses"][kind] += 1
            events.append({"type": "use", "tick": tick, "round": n, "player": sid, "side": rr[sid]["side"], "weapon": kind})
        for blind in blinds:
            tick = blind.get("tick")
            if not isinstance(tick, int) or not start <= tick <= end:
                continue
            attacker = steam_id(blind.get("attacker_steamid")); victim = steam_id(blind.get("user_steamid"))
            at, vt = blind.get("attacker_team_num"), blind.get("user_team_num")
            duration = blind.get("blind_duration")
            if (attacker not in rr or victim not in rr or at not in (2, 3) or vt not in (2, 3)
                    or rr[attacker]["side"] != {2: "T", 3: "CT"}[at]
                    or rr[victim]["side"] != {2: "T", 3: "CT"}[vt]):
                valid = False
                continue
            relation = "self" if attacker == victim else "allies" if at == vt else "enemies"
            rr[attacker][f"blind_{relation}"] += 1
            events.append({"type": "blind", "tick": tick, "round": n, "player": attacker, "victim": victim,
                           "relation": relation, "duration": float(duration) if isinstance(duration, Real) and math.isfinite(duration) and duration >= 0 else None})
        hp = dict.fromkeys(rr, 100)
        damage_valid = True
        seen_hurts = set()
        for hurt in sorted((h for h in hurts if isinstance(h.get("tick"), int) and start <= h["tick"] <= end), key=lambda h: h["tick"]):
            victim = steam_id(hurt.get("user_steamid")); attacker = steam_id(hurt.get("attacker_steamid"))
            key = (hurt.get("tick"), victim)
            if key in seen_hurts:
                damage_valid = False
            seen_hurts.add(key)
            amount, remaining = hurt.get("dmg_health"), hurt.get("health")
            if victim not in hp or not isinstance(amount, int) or not isinstance(remaining, int) or amount < 0 or remaining < 0:
                damage_valid = False; continue
            loss = hp[victim] - remaining
            if loss < 0 or abs(loss - min(amount, hp[victim])) > 1:
                damage_valid = False
            hp[victim] = remaining
            weapon = hurt.get("weapon")
            if weapon not in ("hegrenade", "inferno"):
                continue
            at, vt = hurt.get("attacker_team_num"), hurt.get("user_team_num")
            if (attacker not in rr or at not in (2, 3) or vt not in (2, 3)
                    or rr[attacker]["side"] != {2: "T", 3: "CT"}[at]
                    or rr[victim]["side"] != {2: "T", 3: "CT"}[vt]):
                damage_valid = False; continue
            relation = "self" if attacker == victim else "allies" if at == vt else "enemy"
            kind = "he" if weapon == "hegrenade" else "fire"
            rr[attacker][f"damage_{kind}_{relation}"] += max(0, loss)
            events.append({"type": "hurt", "tick": hurt["tick"], "round": n, "player": attacker,
                           "victim": victim, "weapon": kind, "relation": relation, "health_lost": max(0, loss)})
        for sid, row in rr.items():
            disconnected = any(start <= d.get("tick", -1) <= end and steam_id(d.get("user_steamid")) == sid
                               for d in (disconnects or []))
            snap = by_tick.get((start, sid))
            if snap and snap.get("team_num") == {"T": 2, "CT": 3}.get(row["side"]) and snap.get("is_alive") is True:
                def nonnegative(name, current=snap):
                    val = current.get(name)
                    return int(val) if isinstance(val, int) and not isinstance(val, bool) and val >= 0 else None
                row["economy"] = {"balance": nonnegative("balance"), "equipment_value": nonnegative("current_equip_value"),
                                  "spent": nonnegative("cash_spent_this_round"), "armor": nonnegative("armor_value"),
                                  "helmet": snap.get("has_helmet") if isinstance(snap.get("has_helmet"), bool) else None,
                                  "defuser": snap.get("has_defuser") if isinstance(snap.get("has_defuser"), bool) else None,
                                  "inventory": snap.get("inventory") if isinstance(snap.get("inventory"), list) and all(isinstance(x, str) for x in snap["inventory"]) else None}
            if not valid or disconnected:
                row["uses"] = None
                for key in ("blind_enemies", "blind_allies", "blind_self"): row[key] = None
            if not damage_valid or disconnected:
                for key in ("damage_he_enemy", "damage_fire_enemy", "damage_he_allies", "damage_fire_allies", "damage_he_self", "damage_fire_self"): row[key] = None
            result[sid].append(row)
        teams = []
        for team in rnd.get("teams", []):
            members = [sid for sid, p in known.items() if p.get("team") == team.get("name")]
            values = [rr[sid]["economy"]["equipment_value"] for sid in members if sid in rr and rr[sid]["economy"]]
            teams.append({"name": team.get("name"), "side": team.get("side"),
                          "equipment_value": sum(values) if members and len(values) == len(members) and all(v is not None for v in values) else None})
        output_rounds.append({"number": n, "teams": teams, "winner": rnd.get("winner")})
    aggregates = {}
    for sid, rows in result.items():
        if len(rows) != len(rounds):
            continue
        uses = {kind: sum(r["uses"][kind] for r in rows) if all(r["uses"] is not None for r in rows) else None for kind in WEAPONS.values()}
        keys = ("blind_enemies", "blind_allies", "blind_self", "damage_he_enemy", "damage_fire_enemy", "damage_he_allies", "damage_fire_allies", "damage_he_self", "damage_fire_self")
        aggregates[sid] = {"uses": uses, **{key: sum(r[key] for r in rows) if all(r[key] is not None for r in rows) else None for key in keys}, "rounds": rows}
    return {"version": VERSION, "players": aggregates, "rounds": output_rounds, "events": events}

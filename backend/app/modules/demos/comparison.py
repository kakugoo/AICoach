"""Personal historical percentiles, independent of demo parsing."""
from math import floor, isfinite
from statistics import mean, median

METRICS = ("flash", "smoke", "he", "molotov", "incendiary", "decoy", "blind_enemies", "blind_allies", "damage_he_enemy", "damage_fire_enemy")


def percentile(values, fraction):
    ordered = sorted(values)
    pos = (len(ordered) - 1) * fraction
    index = floor(pos)
    remainder = pos - index
    return ordered[index] if index + 1 == len(ordered) else ordered[index] * (1 - remainder) + ordered[index + 1] * remainder


def rates(facts, sid):
    advanced = facts.get("advanced") or {}
    utility = facts.get("utility_economy") or {}
    player = utility.get("players", {}).get(sid)
    adv_player = advanced.get("players", {}).get(sid)
    if utility.get("version") != "utility-economy-1" or advanced.get("version") != "advanced-1" or not player or not adv_player:
        return None
    n = adv_player.get("rounds")
    rows = player.get("rounds")
    if type(n) is not int or n <= 0 or not isinstance(rows, list) or len(rows) != n:
        return None
    values = player.get("uses") or {}
    return {k: v / n if type(v) in (int, float) and isfinite(v) and v >= 0 else None
            for k in METRICS for v in [values.get(k) if k in ("flash", "smoke", "he", "molotov", "incendiary", "decoy") else player.get(k)]}


def compare(current, history):
    output = {}
    for metric in METRICS:
        score = current.get(metric) if current else None
        values = [row[metric] for row in history if row and row.get(metric) is not None]
        item = {"value": score, "count": len(values), "mean": None, "median": None, "p25": None, "p75": None, "category": "insufficient"}
        if score is not None and len(values) >= 10:
            lo, hi = percentile(values, .25), percentile(values, .75)
            item.update(mean=mean(values), median=median(values), p25=lo, p75=hi,
                        category="below" if score < lo else "above" if score > hi else "usual")
        output[metric] = item
    return output

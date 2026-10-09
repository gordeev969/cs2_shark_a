"""Pure replay normalization. Only complete, non-warmup rounds are measured."""

import math


def sid(value):
    # Never round floats into a SteamID: float64 loses identity precision.
    if isinstance(value, float) or value is None or isinstance(value, bool):
        return None
    value = str(value)
    return value if value.isascii() and value.isdigit() and len(value) == 17 else None


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value) if math.isfinite(float(value)) else None
    except (TypeError, ValueError, OverflowError):
        return None


def integer(value):
    value = number(value)
    return int(value) if value is not None and value >= 0 and value.is_integer() else None


def team(value):
    value = number(value)
    return int(value) if value in (2, 3) else None


def enemy(event, role="attacker"):
    a, b = team(event.get(f"{role}_team_num")), team(event.get("user_team_num"))
    return None if a is None or b is None else a != b


def live_rounds(starts, ends, official_ends=(), round_starts=(), match_end_tick=None):
    """Measure cooldown combat through official end, before the next round's buytime.

    `round_end` determines the winner, but surviving players can still deal damage
    afterwards. The official-end tick can also be the next round-start tick and
    belongs to the next round, so the previous interval ends one tick earlier.
    Missing round counters are allowed only with confirmed temporal boundaries.
    """
    starts = [
        {**s, "tick": integer(s.get("tick"))} for s in starts if integer(s.get("tick")) is not None
    ]
    ends = [
        {**e, "tick": integer(e.get("tick"))} for e in ends if integer(e.get("tick")) is not None
    ]
    official_ticks = sorted(
        integer(e.get("tick"))
        for e in official_ends
        if integer(e.get("tick")) is not None and e.get("is_warmup_period") is False
    )
    next_start_ticks = sorted(
        integer(e.get("tick"))
        for e in round_starts
        if integer(e.get("tick")) is not None and e.get("is_warmup_period") is False
    )
    match_end_tick = integer(match_end_tick)
    rounds = []
    previous_end = -1
    for end in sorted(ends, key=lambda e: e["tick"]):
        if end.get("is_warmup_period") is not False or team(end.get("winner")) is None:
            continue
        if match_end_tick is not None and end["tick"] > match_end_tick:
            continue
        end_number = integer(end.get("total_rounds_played"))
        candidates = [
            s
            for s in starts
            if s.get("is_warmup_period") is False
            and previous_end < s["tick"] <= end["tick"]
            and (
                integer(s.get("total_rounds_played")) is None
                or end_number is None
                or integer(s.get("total_rounds_played")) == end_number
            )
        ]
        if not candidates:
            continue
        start = max(candidates, key=lambda e: e["tick"])
        boundaries = [tick for tick in next_start_ticks if tick > end["tick"]]
        next_start = min(boundaries) if boundaries else None
        boundaries = [
            tick
            for tick in official_ticks
            if tick > end["tick"] and (next_start is None or tick <= next_start)
        ]
        official_end = min(boundaries) if boundaries else None
        boundary = official_end if official_end is not None else next_start
        measured_end = boundary - 1 if boundary is not None else end["tick"]
        boundary_source = (
            "round_officially_ended"
            if official_end is not None
            else "round_start"
            if next_start is not None
            else "round_end"
        )
        if (
            boundary is None
            and match_end_tick is not None
            and not any(
                end["tick"] < s["tick"] <= match_end_tick and s.get("is_warmup_period") is False
                for s in starts
            )
        ):
            measured_end = match_end_tick
            boundary_source = "cs_win_panel_match"
        if match_end_tick is not None:
            if match_end_tick < measured_end:
                boundary_source = "cs_win_panel_match"
            measured_end = min(measured_end, match_end_tick)
        rounds.append(
            {
                "number": len(rounds) + 1,
                "start_tick": start["tick"],
                "end_tick": measured_end,
                "result_tick": end["tick"],
                "boundary_source": boundary_source,
                "winning_side": team(end["winner"]),
                "source_round": integer(start.get("total_rounds_played")),
                "round_counter_verified": (
                    integer(start.get("total_rounds_played")) is not None and end_number is not None
                ),
            }
        )
        previous_end = end["tick"]
    return rounds


def calculate(raw):
    rounds = live_rounds(
        raw["starts"],
        raw["ends"],
        raw.get("official_ends", ()),
        raw.get("round_starts", ()),
        raw.get("match_end_tick"),
    )
    if not rounds:
        raise ValueError("Не найдены завершённые игровые раунды с подтверждёнными границами.")
    participants = {}
    for p in raw["players"]:
        steam = sid(p.get("steamid"))
        if steam:
            participants[steam] = str(p.get("name") or steam)
    for e in raw["deaths"] + raw["hurts"] + raw.get("spawns", []):
        for role in ("user", "attacker", "assister"):
            steam = sid(e.get(f"{role}_steamid"))
            if steam:
                participants[steam] = str(e.get(f"{role}_name") or participants.get(steam, steam))
    for p in raw["snapshots"]:
        steam = sid(p.get("steamid"))
        if steam:
            participants[steam] = str(p.get("name") or participants.get(steam, steam))
    stats = {
        s: {
            "steam_id64": s,
            "nickname": name,
            "team": None,
            "kills": 0,
            "deaths": 0,
            "assists": 0,
            "hs_kills": 0,
            "rounds_played": 0,
            "effective_damage": 0,
            "missing_reasons": [],
        }
        for s, name in participants.items()
    }
    diagnostics = list(raw.get("diagnostics", []))
    if any(not r["round_counter_verified"] for r in rounds):
        diagnostics.append(
            "Номера части раундов недоступны; использованы подтверждённые временные границы."
        )
    if any(r["boundary_source"] == "round_end" for r in rounds):
        diagnostics.append(
            "Нет официальной границы части раундов: учитываются события только до round_end."
        )
    for r in rounds:
        roster = {
            sid(p.get("steamid")): p
            for p in raw["snapshots"]
            if p.get("tick") == r["start_tick"]
            and sid(p.get("steamid")) in stats
            and team(p.get("team_num")) is not None
            and number(p.get("health")) is not None
            and number(p.get("health")) > 0
            and p.get("is_connected") == 0
        }
        deaths = [
            e
            for e in raw["deaths"]
            if r["start_tick"] <= e["tick"] <= r["end_tick"] and e.get("is_warmup_period") is False
        ]
        hurts = [
            e
            for e in raw["hurts"]
            if r["start_tick"] <= e["tick"] <= r["end_tick"] and e.get("is_warmup_period") is False
        ]
        # Late joins evidenced by spawn/event are participants even without freeze snapshot.
        for e in raw.get("spawns", []) + deaths + hurts:
            if not (
                r["start_tick"] <= e["tick"] <= r["end_tick"] and e.get("is_warmup_period") is False
            ):
                continue
            for role in ("user", "attacker", "assister"):
                s = sid(e.get(f"{role}_steamid"))
                if s in stats and team(e.get(f"{role}_team_num")):
                    roster.setdefault(s, {"team_num": e[f"{role}_team_num"], "health": None})
        health = {s: number(p.get("health")) for s, p in roster.items()}
        per_round = {
            s: {
                "side": team(p.get("team_num")),
                "kills": 0,
                "deaths": 0,
                "assists": 0,
                "hs_kills": 0,
                "effective_damage": 0,
            }
            for s, p in roster.items()
        }
        side_groups = {
            side: {
                stats[s]["team"]
                for s, p in roster.items()
                if team(p.get("team_num")) == side and stats[s]["team"]
            }
            for side in (2, 3)
        }
        for s, p in roster.items():
            stats[s]["rounds_played"] += 1
            if stats[s]["team"] is None:
                groups = side_groups[team(p["team_num"])]
                if r["number"] == 1:
                    stats[s]["team"] = "A" if team(p["team_num"]) == 2 else "B"
                elif len(groups) == 1:
                    stats[s]["team"] = next(iter(groups))

        def unavailable(s, keys, reason):
            for key in keys:
                stats[s][key] = None
                per_round[s][key] = None
            stats[s]["missing_reasons"].append(reason)

        def increment(s, key, amount=1):
            if stats[s][key] is not None:
                stats[s][key] += amount
            if per_round[s][key] is not None:
                per_round[s][key] += amount

        assists_incomplete = not raw.get("assist_fields_complete", False) or any(
            "assister_steamid" not in e or "assister_team_num" not in e for e in deaths
        )
        if assists_incomplete:
            for s in roster:
                unavailable(s, ("assists",), "Недоступны поля ассистов")
        for e in deaths:
            victim, attacker, assister = (
                sid(e.get(f"{role}_steamid")) for role in ("user", "attacker", "assister")
            )
            if victim in per_round:
                increment(victim, "deaths")
            if attacker in per_round and attacker != victim:
                if enemy(e) is None:
                    unavailable(
                        attacker, ("kills", "hs_kills"), "Не определена команда в событии смерти"
                    )
                elif enemy(e):
                    increment(attacker, "kills")
                    if not isinstance(e.get("headshot"), bool):
                        unavailable(attacker, ("hs_kills",), "Недоступно поле headshot")
                    elif e["headshot"]:
                        increment(attacker, "hs_kills")
            if assister in per_round and assister not in (victim, attacker):
                relation = enemy(e, "assister")
                kill_relation = enemy(e)
                if relation is None or kill_relation is None:
                    unavailable(assister, ("assists",), "Не определена команда в событии ассиста")
                elif relation and kill_relation:
                    increment(assister, "assists")
        damage_incomplete = not raw.get("hurt_fields_complete", False)
        for e in sorted(hurts, key=lambda e: e["tick"]):
            victim, attacker = sid(e.get("user_steamid")), sid(e.get("attacker_steamid"))
            before = health.get(victim)
            after, amount = number(e.get("health")), number(e.get("dmg_health"))
            relation = enemy(e)
            valid = (
                before is not None
                and after is not None
                and amount is not None
                and 0 <= after <= before
                and amount >= 0
            )
            # post-health + previous observed health verifies health loss and caps overkill.
            if valid and after > 0 and abs(before - after - amount) > 1:
                valid = False
            if valid and amount + 1 < before - after:
                valid = False
            if attacker in per_round and attacker != victim:
                if relation is None or (relation and not valid):
                    damage_incomplete = True
                elif relation:
                    effective = before - after
                    stats[attacker]["effective_damage"] = (
                        stats[attacker]["effective_damage"] or 0
                    ) + effective
                    per_round[attacker]["effective_damage"] += effective
            if victim:
                health[victim] = after
        if damage_incomplete:
            for s in roster:
                stats[s]["missing_reasons"].append("ADR: неполные поля урона, здоровья или команд")
        r["players"] = per_round
        if damage_incomplete:
            for p in per_round.values():
                p["effective_damage"] = None
    for p in stats.values():
        p["missing_reasons"] = sorted(set(p["missing_reasons"]))
        if any(reason.startswith("ADR:") for reason in p["missing_reasons"]):
            p["effective_damage"] = None
        if not p["rounds_played"]:
            for key in ("kills", "deaths", "assists", "hs_kills", "effective_damage"):
                p[key] = None
            p["missing_reasons"].append("Участие в завершённых раундах не подтверждено")
        k, d, n = p["kills"], p["deaths"], p["rounds_played"]
        p["kd"] = round(k / max(d, 1), 3) if k is not None else None
        p["hs_percent"] = (
            (round(p["hs_kills"] / k * 100, 2) if k else 0)
            if p["hs_kills"] is not None and k is not None
            else None
        )
        p["kr"] = round(k / n, 3) if n and k is not None else None
        p["adr"] = (
            round(p["effective_damage"] / n, 2) if n and p["effective_damage"] is not None else None
        )
    scores = None
    if raw.get("final_snapshots"):
        final = [p for p in raw["final_snapshots"] if team(p.get("team_num"))]
        groups = {
            g: {
                integer(p.get("team_rounds_total"))
                for p in final
                if sid(p.get("steamid")) in stats and stats[sid(p["steamid"])]["team"] == g
            }
            for g in ("A", "B")
        }
        sides = {
            g: {
                team(p.get("team_num"))
                for p in final
                if sid(p.get("steamid")) in stats and stats[sid(p["steamid"])]["team"] == g
            }
            for g in ("A", "B")
        }
        if (
            all(len(v) == 1 and None not in v for v in groups.values())
            and all(len(v) == 1 for v in sides.values())
            and sides["A"] != sides["B"]
        ):
            scores = {g: int(next(iter(v))) for g, v in groups.items()}
    if scores is None:
        diagnostics.append(
            "Итоговый счёт не подтверждён; показаны только завершённые раунды записи."
        )
    elif sum(scores.values()) != len(rounds):
        diagnostics.append(
            f"Итоговый счёт включает {sum(scores.values())} раундов; для метрик подтверждено "
            f"{len(rounds)} полных раундов. Неполные раунды не входят в знаменатель ADR и K/R."
        )
    return {
        "map_name": raw.get("map_name"),
        "played_at": None,
        "team_scores": scores,
        "parser_version": raw.get("parser_version"),
        "rounds": rounds,
        "players": list(stats.values()),
        "diagnostics": diagnostics,
    }

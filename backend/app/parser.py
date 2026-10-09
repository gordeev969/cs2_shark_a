"""The demoparser2 boundary. Invoked only in a disposable subprocess."""

import importlib.metadata
import json
import sys

from .metrics import calculate


def records(frame):
    # Pandas JSON retains uint64 integers, removes NaN, and converts numpy bools.
    return json.loads(frame.to_json(orient="records"))


def parse_demo(path):
    # Never load the native parser into the API process, including helper imports.
    from demoparser2 import DemoParser

    parser = DemoParser(str(path))
    events = set(parser.list_game_events())
    required = {"player_death", "round_end"}
    if not required <= events:
        raise ValueError("Демка не содержит необходимых событий смертей и завершения раундов.")
    diagnostics = []
    other = ["is_warmup_period", "total_rounds_played"]

    def event(name, player=False):
        if name not in events:
            return [], set()
        frame = parser.parse_event(name, player=["team_num"] if player else None, other=other)
        return records(frame), set(frame.columns)

    round_starts, _ = event("round_start")
    starts, _ = event("round_freeze_end")
    if not starts:
        starts = round_starts
        diagnostics.append("Нет round_freeze_end: используются подтверждённые round_start.")
    ends, _ = event("round_end")
    official_ends, _ = event("round_officially_ended")
    deaths, death_fields = event("player_death", True)
    hurts, hurt_fields = event("player_hurt", True)
    spawns, _ = event("player_spawn", True)
    ticks = sorted({s["tick"] for s in starts if s.get("is_warmup_period") is False})
    if not ticks:
        raise ValueError("Не найдены игровые раунды вне разминки.")
    props = ["team_num", "health", "is_connected", "team_rounds_total"]
    snapshots = records(parser.parse_ticks(props, ticks=ticks))
    finals = (
        records(parser.parse_event("cs_win_panel_match")) if "cs_win_panel_match" in events else []
    )
    final_tick = min(e["tick"] for e in finals) if finals else None
    final_snapshots = (
        records(parser.parse_ticks(props, ticks=[final_tick])) if final_tick is not None else []
    )
    diagnostics.append(
        "SteamID берётся из replay; команды A/B обозначают стороны первого участия. Дата игры не восстанавливается."
    )
    diagnostics.append(
        "ADR: изменение целочисленного HP. dmg_health может отличаться на 1 из-за округления; больший разрыв обнуляет достоверность ADR."
    )
    diagnostics.append("Поля player_death: " + ", ".join(sorted(death_fields)))
    diagnostics.append("Поля player_hurt: " + ", ".join(sorted(hurt_fields)))
    return calculate(
        {
            "players": records(parser.parse_player_info()),
            "starts": starts,
            "ends": ends,
            "round_starts": round_starts,
            "official_ends": official_ends,
            "match_end_tick": final_tick,
            "deaths": deaths,
            "hurts": hurts,
            "spawns": spawns,
            "snapshots": snapshots,
            "final_snapshots": final_snapshots,
            "map_name": parser.parse_header().get("map_name"),
            "parser_version": importlib.metadata.version("demoparser2"),
            "assist_fields_complete": {"assister_steamid", "assister_team_num"} <= death_fields,
            "hurt_fields_complete": {"health", "dmg_health", "attacker_team_num", "user_team_num"}
            <= hurt_fields,
            "diagnostics": diagnostics,
        }
    )


if __name__ == "__main__":
    try:
        result = parse_demo(sys.argv[1])
        with open(sys.argv[2], "w", encoding="utf-8") as output:
            json.dump(result, output, ensure_ascii=False, allow_nan=False)
    except Exception as exc:
        print(f"Ошибка разбора CS2: {str(exc)[:500]}", file=sys.stderr)
        sys.exit(1)

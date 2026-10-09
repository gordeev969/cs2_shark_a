from copy import deepcopy

import pytest

from backend.app.metrics import calculate

P, Q, R = "76561198000000001", "76561198000000002", "76561198000000003"


def event(tick, attacker, victim, at=2, vt=3, **extra):
    return {
        "tick": tick,
        "attacker_steamid": attacker,
        "user_steamid": victim,
        "attacker_team_num": at,
        "user_team_num": vt,
        "assister_steamid": None,
        "assister_team_num": None,
        "headshot": False,
        "is_warmup_period": False,
        **extra,
    }


@pytest.fixture
def raw():
    return {
        "map_name": "de_test",
        "parser_version": "fixture",
        "players": [
            {"steamid": P, "name": "Альфа"},
            {"steamid": Q, "name": "Бета"},
            {"steamid": R, "name": "Третий"},
        ],
        "starts": [
            {"tick": 0, "is_warmup_period": True, "total_rounds_played": 0},
            {"tick": 10, "is_warmup_period": False, "total_rounds_played": 0},
            {"tick": 110, "is_warmup_period": False, "total_rounds_played": 1},
        ],
        "ends": [
            {"tick": 100, "is_warmup_period": False, "total_rounds_played": 0, "winner": 2},
            {"tick": 200, "is_warmup_period": False, "total_rounds_played": 1, "winner": 2},
        ],
        "snapshots": [
            {"tick": tick, "steamid": s, "team_num": side, "health": 100, "is_connected": 0}
            for tick, sides in ((10, (2, 3, 2)), (110, (3, 2, 3)))
            for s, side in zip((P, Q, R), sides)
        ],
        "deaths": [
            event(5, P, Q, headshot=True, is_warmup_period=True),
            event(31, P, Q, headshot=True, assister_steamid=R, assister_team_num=2),
            event(151, Q, P, at=2, vt=3),
            event(170, Q, Q, at=2, vt=2),
            event(180, None, R, at=None, vt=3),
            event(201, P, Q, at=3, vt=2),
        ],
        "hurts": [
            event(20, P, R, vt=2, health=80, dmg_health=20),
            event(30, P, Q, health=0, dmg_health=150),
            event(120, Q, P, health=65, dmg_health=34),
            event(150, Q, P, health=0, dmg_health=100),
        ],
        "spawns": [],
        "final_snapshots": [],
        "assist_fields_complete": True,
        "hurt_fields_complete": True,
        "diagnostics": [],
    }


@pytest.fixture
def parsed(raw):
    return calculate(deepcopy(raw))

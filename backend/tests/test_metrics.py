from copy import deepcopy

import pytest

from backend.app.metrics import calculate, live_rounds, number, sid, team
from backend.app.parser import records
from backend.tests.conftest import P, Q, R, event


def by_id(result):
    return {p["steam_id64"]: p for p in result["players"]}


def test_enemy_only_kills_all_deaths_assists_and_side_swaps(parsed):
    p, q, r = (by_id(parsed)[s] for s in (P, Q, R))
    assert (p["kills"], p["deaths"], p["assists"], p["hs_percent"], p["kd"]) == (1, 1, 0, 100, 1)
    assert (q["kills"], q["deaths"], q["kd"], q["team"]) == (1, 2, 0.5, "B")
    assert (r["kills"], r["deaths"], r["assists"], r["hs_percent"]) == (0, 1, 1, 0)
    assert all(p["rounds_played"] == 2 for p in parsed["players"])
    assert parsed["rounds"][1]["players"][P]["side"] == 3


def test_adr_caps_overkill_excludes_friendly_and_handles_rounding(parsed):
    players = by_id(parsed)
    assert players[P]["effective_damage"] == 100
    assert players[Q]["effective_damage"] == 100  # 35 + 65, not 34 + 100
    assert players[P]["adr"] == players[Q]["adr"] == 50
    assert players[R]["adr"] == 0
    assert parsed["rounds"][1]["players"][Q]["effective_damage"] == 100


def test_teamkill_and_suicide_are_not_enemy_kills(raw):
    raw["deaths"].append(event(50, P, R, vt=2, headshot=True))
    players = by_id(calculate(raw))
    assert players[P]["kills"] == 1
    assert players[P]["hs_kills"] == 1
    assert players[R]["deaths"] == 2
    assert players[Q]["kills"] == 1


@pytest.mark.parametrize("field", ["health", "dmg_health", "attacker_team_num", "user_team_num"])
def test_missing_damage_field_produces_null(raw, field):
    raw["hurts"][1].pop(field)
    p = by_id(calculate(raw))[P]
    assert p["adr"] is None and p["effective_damage"] is None
    assert p["missing_reasons"]


def test_missing_event_type_is_not_zero_damage(raw):
    raw["hurts"] = []
    raw["hurt_fields_complete"] = False
    assert all(p["adr"] is None for p in calculate(raw)["players"])


def test_health_gap_produces_null(raw):
    raw["hurts"][2]["dmg_health"] = 10
    assert by_id(calculate(raw))[Q]["adr"] is None


def test_fatal_damage_must_cover_observed_health_loss(raw):
    raw["hurts"][1]["dmg_health"] = 1
    assert by_id(calculate(raw))[P]["adr"] is None


def test_unavailable_assist_columns(raw):
    raw["assist_fields_complete"] = False
    assert all(p["assists"] is None for p in calculate(raw)["players"])


def test_missing_assists_remain_null_across_rounds(raw):
    raw["assist_fields_complete"] = False
    raw["deaths"].append(event(160, P, Q, at=3, vt=2, assister_steamid=R, assister_team_num=3))
    result = calculate(raw)
    assert by_id(result)[R]["assists"] is None
    assert all(p["assists"] is None for r in result["rounds"] for p in r["players"].values())


def test_unknown_assist_team_is_unavailable(raw):
    raw["deaths"][1]["assister_team_num"] = None
    result = calculate(raw)
    assert by_id(result)[R]["assists"] is None
    assert result["rounds"][0]["players"][R]["assists"] is None


@pytest.mark.parametrize("headshot", [None, 1, "true"])
def test_unknown_headshot_is_null_instead_of_zero(raw, headshot):
    raw["deaths"][1]["headshot"] = headshot
    result = calculate(raw)
    assert by_id(result)[P]["kills"] == 1
    assert by_id(result)[P]["hs_kills"] is None
    assert by_id(result)[P]["hs_percent"] is None
    assert result["rounds"][0]["players"][P]["hs_kills"] is None
    assert by_id(result)[P]["missing_reasons"]


def test_unknown_kill_teams_do_not_fabricate_kills(raw):
    raw["deaths"][1]["attacker_team_num"] = None
    result = calculate(raw)
    assert by_id(result)[P]["kills"] is None
    assert result["rounds"][0]["players"][P]["kills"] is None


def test_unknown_round_kills_do_not_become_known_after_later_kill(raw):
    raw["deaths"][1]["attacker_team_num"] = None
    raw["deaths"].append(event(40, P, Q))
    result = calculate(raw)
    assert by_id(result)[P]["kills"] is None
    assert result["rounds"][0]["players"][P]["kills"] is None


def test_post_round_damage_and_kills_exclude_next_buytime_and_postmatch(raw):
    raw["round_starts"] = [
        {"tick": 109, "is_warmup_period": False},
        {"tick": 210, "is_warmup_period": False},
    ]
    raw["official_ends"] = deepcopy(raw["round_starts"])
    raw["match_end_tick"] = 205
    raw["deaths"] = [e for e in raw["deaths"] if e["tick"] != 201]
    raw["hurts"].append(event(105, Q, R, at=3, vt=2, health=0, dmg_health=100))
    raw["deaths"] += [
        event(106, Q, R, at=3, vt=2),
        event(109, Q, P, at=3, vt=2),
        event(206, P, Q, at=3, vt=2),
        event(210, P, Q, at=3, vt=2),
    ]
    result = calculate(raw)
    assert result["rounds"][0]["result_tick"] == 100
    assert result["rounds"][0]["end_tick"] == 108
    assert result["rounds"][1]["end_tick"] == 205
    assert by_id(result)[Q]["kills"] == 2
    assert by_id(result)[Q]["effective_damage"] == 180
    assert by_id(result)[Q]["adr"] == 90
    assert by_id(result)[P]["kills"] == 1
    assert by_id(result)[P]["deaths"] == 1


def test_next_round_start_confirms_cooldown_without_official_event(raw):
    raw["round_starts"] = [{"tick": 109, "is_warmup_period": False}]
    raw["deaths"].append(event(105, Q, R, at=3, vt=2))
    result = calculate(raw)
    assert result["rounds"][0]["boundary_source"] == "round_start"
    assert by_id(result)[Q]["kills"] == 2


def test_postmatch_rounds_are_excluded(raw):
    raw["match_end_tick"] = 100
    result = calculate(raw)
    assert len(result["rounds"]) == 1
    assert by_id(result)[P]["rounds_played"] == 1


def test_final_panel_includes_last_cooldown_and_excludes_postmatch(raw):
    raw["match_end_tick"] = 205
    raw["deaths"].append(event(206, P, Q, at=3, vt=2))
    result = calculate(raw)
    assert result["rounds"][1]["end_tick"] == 205
    assert result["rounds"][1]["boundary_source"] == "cs_win_panel_match"
    assert by_id(result)[P]["kills"] == 2  # Includes tick 201, excludes tick 206.
    assert result["rounds"][0]["end_tick"] == 100


def test_unfinished_round_and_restarts(raw):
    raw["starts"].append({"tick": 220, "is_warmup_period": False, "total_rounds_played": 2})
    assert len(calculate(raw)["rounds"]) == 2
    restarted = deepcopy(raw)
    restarted["starts"].append({"tick": 15, "is_warmup_period": False, "total_rounds_played": 0})
    assert live_rounds(restarted["starts"], restarted["ends"])[0]["start_tick"] == 15


def test_missing_round_counters_use_confirmed_temporal_boundaries(raw):
    raw["starts"][1].pop("total_rounds_played")
    raw["ends"][1]["total_rounds_played"] = None
    result = calculate(raw)
    assert len(result["rounds"]) == 2
    assert result["rounds"][0]["source_round"] is None
    assert any("Номера части раундов" in d for d in result["diagnostics"])


def test_invalid_round_ticks_are_ignored_and_mismatched_counters_do_not_pair(raw):
    raw["starts"] += [{"tick": None}, {"tick": float("inf")}]
    raw["ends"] += [{"tick": None}, {"tick": -2}]
    assert len(calculate(raw)["rounds"]) == 2
    raw["ends"][0]["total_rounds_played"] = 20
    assert len(calculate(raw)["rounds"]) == 1


def test_overtime_no_assumed_round_count(raw):
    starts, ends, snapshots = [], [], []
    for n in range(30):
        tick = n * 1000 + 10
        starts.append({"tick": tick, "is_warmup_period": False, "total_rounds_played": n})
        ends.append(
            {"tick": tick + 500, "is_warmup_period": False, "total_rounds_played": n, "winner": 2}
        )
        snapshots += [
            {"tick": tick, "steamid": s, "team_num": side, "health": 100, "is_connected": 0}
            for s, side in ((P, 2), (Q, 3))
        ]
    raw.update(starts=starts, ends=ends, snapshots=snapshots, deaths=[], hurts=[])
    assert len(calculate(raw)["rounds"]) == 30
    assert by_id(calculate(raw))[P]["rounds_played"] == 30


def test_disconnected_and_late_join_participation(raw):
    raw["snapshots"] = [s for s in raw["snapshots"] if not (s["steamid"] == R and s["tick"] == 110)]
    raw["deaths"] = [e for e in raw["deaths"] if e["user_steamid"] != R]
    p = by_id(calculate(raw))[R]
    assert p["rounds_played"] == 1
    raw["spawns"] = [event(140, None, R, at=None, vt=3)]
    assert by_id(calculate(raw))[R]["rounds_played"] == 2


def test_scores_require_consistent_final_team_data(raw):
    assert calculate(raw)["team_scores"] is None
    raw["final_snapshots"] = [
        {"steamid": P, "team_num": 3, "team_rounds_total": 6},
        {"steamid": Q, "team_num": 2, "team_rounds_total": 8},
        {"steamid": R, "team_num": None, "team_rounds_total": None},
    ]
    assert calculate(raw)["team_scores"] == {"A": 6, "B": 8}
    assert any("для метрик подтверждено 2" in d for d in calculate(raw)["diagnostics"])
    raw["final_snapshots"].append({"steamid": R, "team_num": 2, "team_rounds_total": 8})
    assert calculate(raw)["team_scores"] is None


@pytest.mark.parametrize("score", [None, -1, 6.5, float("inf")])
def test_missing_or_invalid_score_does_not_get_truncated(raw, score):
    raw["final_snapshots"] = [
        {"steamid": P, "team_num": 3, "team_rounds_total": 6},
        {"steamid": R, "team_num": 3, "team_rounds_total": score},
        {"steamid": Q, "team_num": 2, "team_rounds_total": 8},
    ]
    assert calculate(raw)["team_scores"] is None


def test_numeric_normalization_rejects_overflow_and_nonfinite_values():
    assert number(10**400) is None
    assert number(float("inf")) is None
    assert number(float("nan")) is None
    assert team("2.0") == 2
    assert team("invalid") is None
    assert sid("７６５６１１９８００００００００１") is None


def test_no_live_rounds_fails(raw):
    raw["starts"] = []
    with pytest.raises(ValueError, match="раунды"):
        calculate(raw)


def test_steamid_integrity_and_pandas_nan():
    import pandas as pd

    assert sid(int(P)) == P
    assert sid(float(P)) is None
    frame = pd.DataFrame(
        {"steamid": [int(P)], "assister_steamid": [float("nan")], "headshot": [True]}
    )
    converted = records(frame)[0]
    assert converted["steamid"] == int(P)
    assert converted["assister_steamid"] is None
    assert converted["headshot"] is True

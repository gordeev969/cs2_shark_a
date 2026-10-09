from copy import deepcopy

import pytest

from backend.app.db import Database
from backend.app.insights import aggregate, format_number_ru, history_insights, match_notes
from backend.tests.conftest import P


def test_weighted_totals_and_partial_adr_sample():
    rows = [
        dict(kills=20, deaths=10, assists=3, rounds_played=20, hs_kills=10, effective_damage=2000),
        dict(kills=5, deaths=0, assists=1, rounds_played=5, hs_kills=0, effective_damage=250),
        dict(kills=2, deaths=3, assists=0, rounds_played=10, hs_kills=1, effective_damage=None),
    ]
    result = aggregate(rows)
    assert result["kd"] == round(27 / 13, 3)
    assert result["adr"] == 90 and result["adr_matches"] == 2 and result["adr_rounds"] == 25
    assert result["matches"] == 3
    assert result["hs_percent"] == round(11 / 27 * 100, 2)


@pytest.mark.parametrize("n", [0, 1, 9])
def test_anomaly_threshold(n, parsed):
    result = history_insights([parsed["players"][0]] * n)
    assert result["status"] == "insufficient"
    assert result["observations"] == []
    assert result["sample_size"] == n


def test_descriptive_5_vs_10_window(parsed):
    row = parsed["players"][0]
    current = {**row, "effective_damage": 400, "kills": 3}
    result = history_insights([current] * 5 + [row] * 12)
    adr = next(o for o in result["observations"] if o["metric"] == "adr")
    assert (
        adr["current_matches"],
        adr["baseline_matches"],
        adr["current"],
        adr["baseline"],
        adr["delta"],
    ) == (5, 10, 200, 50, 150)
    assert result["sample_size"] == 17


def test_exactly_ten_and_missing_baselines(parsed):
    rows = [parsed["players"][0]] * 10
    result = history_insights(rows)
    assert result["status"] == "descriptive"
    assert result["observations"][0]["baseline_matches"] == 5
    rows[0] = {**rows[0], "effective_damage": None}
    assert not any(o["metric"] == "adr" for o in history_insights(rows)["observations"])


def test_single_profile_across_renames_and_map_splits(tmp_path, parsed):
    db = Database(tmp_path / "db.sqlite3")
    db.initialize()
    for index in range(3):
        match_id, _ = db.reserve(str(index) * 64)
        updated = deepcopy(parsed)
        updated["players"][0]["nickname"] = f"Альфа-{index}"
        db.persist(match_id, updated)
    p = db.player(P)
    assert p["latest_nickname"] == "Альфа-2"
    assert p["summary"]["matches"] == 3
    assert p["summary"]["kills"] == 3
    assert len(p["map_splits"]) == 1
    assert p["map_splits"][0]["matches"] == 3
    assert len(db.search("АЛЬФА")) == 1
    assert db.search(P)[0]["matches"] == 3
    assert p["history"][0]["nickname"] == "Альфа-2"
    assert p["history"][-1]["nickname"] == "Альфа-0"


def test_no_accusation_language(parsed):
    text = " ".join(match_notes(parsed["players"][0])) + str(
        history_insights([parsed["players"][0]] * 15)
    )
    for word in ("читер", "cheat", "вероятность чит", "подозрительный игрок"):
        assert word not in text.lower()


def test_insight_copy_uses_russian_decimal_separator(parsed):
    p = {**parsed["players"][0], "adr": 135.44, "kd": 2.2, "kr": 0.933}
    text = " ".join(match_notes(p))
    assert "ADR 135,44" in text and "K/D 2,2" in text and "0,933" in text
    assert format_number_ru(-0.0, signed=True) == "+0"
    current = {**p, "effective_damage": 101.5}
    prior = {**p, "effective_damage": 100}
    result = history_insights([current] * 5 + [prior] * 10)
    adr = next(o for o in result["observations"] if o["metric"] == "adr")
    assert adr["current"] == 50.75
    assert "50,75" in adr["text"] and "+0,75" in adr["text"]

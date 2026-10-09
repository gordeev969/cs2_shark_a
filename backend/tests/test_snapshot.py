import json
from copy import deepcopy

import pytest

from backend.app.db import Database
from backend.app.export_snapshot import export_snapshot
from backend.tests.conftest import P


def test_export_isolates_selected_match_and_excludes_account_data(tmp_path, parsed):
    db = Database(tmp_path / "db.sqlite3")
    db.initialize()
    first, _ = db.reserve("a" * 64)
    db.persist(first, parsed)
    second, _ = db.reserve("b" * 64)
    private = deepcopy(parsed)
    private["players"][0]["nickname"] = "private nickname"
    private["players"][0]["kills"] = 999
    db.persist(second, private)
    with db.connect() as c:
        c.execute("INSERT INTO settings VALUES ('private_key', 'private secret')")
        c.execute("INSERT INTO auth_states VALUES ('session secret','nonce secret',99999999)")
    result = export_snapshot(db.path, [first], "https://example.com/public.dem")
    text = json.dumps(result)
    assert set(result["matches"]) == {str(first)}
    assert "private nickname" not in text
    assert "private secret" not in text
    assert "session secret" not in text
    assert result["profiles"][P]["summary"]["matches"] == 1
    assert result["profiles"][P]["summary"]["kills"] == parsed["players"][0]["kills"]
    assert result["dashboards"][P]["recent_matches"][0]["personal_stats"] == parsed["players"][0]
    assert result["source"]["matches"][0]["sha256"] == "a" * 64


def test_export_rejects_unready_or_implicit_selection(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    db.initialize()
    match, _ = db.reserve("a" * 64)
    with pytest.raises(ValueError):
        export_snapshot(db.path, [match], "https://example.com/public.dem")
    with pytest.raises(ValueError):
        export_snapshot(db.path, [], "https://example.com/public.dem")

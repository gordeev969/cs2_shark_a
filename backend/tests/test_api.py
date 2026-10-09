import hashlib
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Config
from backend.app.db import Database
from backend.app.main import create_app
from backend.tests.conftest import P

DEMO = b"PBDEMS2\x00" + b"synthetic-payload" * 10


def await_job(client, match_id):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = client.get(f"/api/matches/{match_id}").json()
        if result["status"] in ("ready", "failed"):
            return result
        time.sleep(0.01)
    pytest.fail("Job did not finish")


def test_upload_dedup_persistence_settings_and_routes(tmp_path, parsed):
    config = Config(require_steam_login=False, data_dir=tmp_path)
    calls = []

    def parse(path, timeout):
        calls.append(path)
        assert path.parent == config.uploads and path.read_bytes() == DEMO
        return parsed

    app = create_app(config, parse)
    with TestClient(app) as client:
        assert client.get("/api/health").json()["ai_enabled"] is False
        response = client.post("/api/matches/import", files={"file": ("../../outside.dem", DEMO)})
        assert response.status_code == 202
        match_id = response.json()["id"]
        match = await_job(client, match_id)
        assert match["status"] == "ready"
        assert len(match["players"]) == 3 and len(match["rounds"]) == 2
        assert match["file_sha256"] == hashlib.sha256(DEMO).hexdigest()
        duplicate = client.post("/api/matches/import", files={"file": ("again.dem", DEMO)}).json()
        assert duplicate["duplicate"] and duplicate["id"] == match_id
        assert len(calls) == 1
        assert len(client.get("/api/matches").json()) == 1
        assert client.get(f"/api/players/{P}").json()["summary"]["matches"] == 1
        assert client.get("/api/players?query=альфа").json()[0]["steam_id64"] == P
        assert (
            client.get(f"/api/matches/{match_id}/insights?steam_id64={P}").json()[0]["history"][
                "status"
            ]
            == "insufficient"
        )
        saved = client.put("/api/settings", json={"steam_id64": P, "compact": True})
        assert saved.status_code == 200
        assert client.get("/api/dashboard").json()["personal"]["steam_id64"] == P
        assert client.put("/api/settings", json={"steam_id64": "123"}).status_code == 422
        assert not list(config.uploads.iterdir())
    with TestClient(create_app(config, parse)) as client:
        assert client.get("/api/settings").json()["steam_id64"] == P
        assert client.get(f"/api/matches/{match_id}").json()["status"] == "ready"


@pytest.mark.parametrize(
    "name,payload,code",
    [
        ("x.zip", DEMO, 415),
        ("x.dem", b"", 422),
        ("x.dem", b"HL2DEMO" + b"x" * 30, 422),
        ("x.dem", b"x" * 40, 422),
    ],
)
def test_invalid_formats(tmp_path, name, payload, code):
    with TestClient(create_app(Config(require_steam_login=False, data_dir=tmp_path))) as client:
        assert (
            client.post("/api/matches/import", files={"file": (name, payload)}).status_code == code
        )
        assert client.get("/api/matches").json() == []
        assert list((tmp_path / "uploads").iterdir()) == []


def test_size_limit_and_browser_origin(tmp_path):
    with TestClient(
        create_app(Config(require_steam_login=False, data_dir=tmp_path, max_upload_bytes=32))
    ) as client:
        assert (
            client.post("/api/matches/import", files={"file": ("x.dem", DEMO)}).status_code == 413
        )
        assert (
            client.post(
                "/api/matches/import",
                files={"file": ("x.dem", DEMO)},
                headers={"Content-Length": "2000000"},
            ).status_code
            == 413
        )
        assert (
            client.put(
                "/api/settings",
                json={"steam_id64": P},
                headers={"Origin": "https://external.example"},
            ).status_code
            == 403
        )
        assert client.get("/api/health", headers={"Host": "external.example"}).status_code == 400


def test_parser_failure_retry_no_duplicate_and_retention(tmp_path, parsed):
    config = Config(require_steam_login=False, data_dir=tmp_path, retain_demos=True)
    calls = 0

    def parse(path, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("Повреждённые события")
        return parsed

    with TestClient(create_app(config, parse)) as client:
        one = client.post("/api/matches/import", files={"file": ("x.dem", DEMO)}).json()
        assert await_job(client, one["id"])["error"] == "Повреждённые события"
        assert client.get("/api/players").json() == []
        two = client.post("/api/matches/import", files={"file": ("x.dem", DEMO)}).json()
        assert two["id"] == one["id"] and not two["duplicate"]
        assert await_job(client, two["id"])["status"] == "ready"
        assert len(list(config.uploads.glob("*.dem"))) == 1
        assert client.get(f"/api/players/{P}").json()["summary"]["matches"] == 1


def test_concurrent_hash_reservations_are_unique(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    db.initialize()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: db.reserve("a" * 64), range(12)))
    assert len({r[0] for r in results}) == 1
    assert sum(r[1] for r in results) == 1


def test_restart_recovers_durable_queue(tmp_path, parsed):
    config = Config(require_steam_login=False, data_dir=tmp_path)
    config.uploads.mkdir()
    db = Database(config.database)
    db.initialize()
    match_id, _ = db.reserve(hashlib.sha256(DEMO).hexdigest())
    path = config.uploads / f"{hashlib.sha256(DEMO).hexdigest()}.dem"
    path.write_bytes(DEMO)
    db.status(match_id, "processing")
    with TestClient(create_app(config, lambda path, timeout: parsed)) as client:
        assert await_job(client, match_id)["status"] == "ready"


def test_missing_routes_and_pending_insights(tmp_path):
    with TestClient(create_app(Config(require_steam_login=False, data_dir=tmp_path))) as client:
        assert client.get("/api/matches/999").status_code == 404
        assert client.get("/api/players/999").status_code == 404
        match_id, _ = client.app.state.db.reserve("0" * 64)
        assert client.get(f"/api/matches/{match_id}/insights").status_code == 409

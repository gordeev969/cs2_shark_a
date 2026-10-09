import bz2
import hashlib
import os
import socket
import time
from copy import deepcopy

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.auth import SecretCipher
from backend.app.config import Config
from backend.app.cs2sync import (
    GCClient,
    SteamMatchClient,
    SyncError,
    Synchronizer,
    SyncStore,
    ValveDemoDownloader,
)
from backend.app.db import Database
from backend.app.jobs import parse_isolated
from backend.app.main import create_app
from backend.tests.conftest import P, Q
from backend.tests.test_auth import login_as

CODE_A = "CSGO-AAAAA-AAAAA-AAAAA-AAAAA-AAAAA"
CODE_B = "CSGO-BBBBB-BBBBB-BBBBB-BBBBB-BBBBB"
AUTH = "ABCD-EFGHJ-KLMN"
DEMO = b"PBDEMS2\x00" + b"demo payload" * 200
URL = "http://replay123.valve.net/730/123_456.dem.bz2"


def public_dns(*args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 80))]


def download_client(data):
    return httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, stream=httpx.ByteStream(data))
        )
    )


def test_bzip_download_and_hash(tmp_path):
    target = tmp_path / "demo.dem"
    with download_client(bz2.compress(DEMO)) as client:
        downloader = ValveDemoDownloader(100000, 100000, client, public_dns)
        assert downloader.download(URL, target) == hashlib.sha256(DEMO).hexdigest()
        assert target.read_bytes() == DEMO


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/730/x.dem",
        "http://replay1.valve.net.attacker.example/730/x.dem",
        "http://replay1.valve.net:9000/730/x.dem",
        "https://replay1.valve.net/730/x.dem?secret=x",
        "http://user:pass@replay1.valve.net/730/x.dem",
        "http://replay1.valve.net/730/../x.dem",
        "file:///730/x.dem",
    ],
)
def test_download_denies_non_valve_urls(tmp_path, url):
    with pytest.raises(SyncError):
        ValveDemoDownloader(10000, 10000, dns_resolver=public_dns).download(url, tmp_path / "x.dem")


def test_download_denies_private_dns(tmp_path):
    def private(*args, **kw):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]

    with pytest.raises(SyncError):
        ValveDemoDownloader(10000, 10000, dns_resolver=private).download(URL, tmp_path / "x.dem")


@pytest.mark.parametrize(
    "data,limit",
    [
        (bz2.compress(DEMO), 32),
        (bz2.compress(DEMO)[:-3], 10000),
        (bz2.compress(DEMO) + bz2.compress(DEMO), 10000),
        (bz2.compress(b"not a demo"), 10000),
    ],
)
def test_download_limits_truncated_extra_member_and_signature(tmp_path, data, limit):
    path = tmp_path / "x.dem"
    with download_client(data) as client, pytest.raises(SyncError):
        ValveDemoDownloader(10000, limit, client, public_dns).download(URL, path)
    assert not path.exists()


@pytest.mark.parametrize(
    "status,state", [(403, "auth_error"), (429, "rate_limited"), (500, "error")]
)
def test_steam_errors_do_not_expose_keys(status, state):
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(status))
    ) as client:
        with pytest.raises(SyncError) as error:
            SteamMatchClient("SUPER-SECRET", client).next_code(P, AUTH, CODE_A)
        assert (
            error.value.status == state
            and "SUPER-SECRET" not in str(error.value)
            and AUTH not in str(error.value)
        )


def test_steam_next_code_official_parameters_and_none():
    seen = []

    def handler(request):
        seen.append(request)
        assert request.url.params["steamidkey"] == AUTH
        assert request.url.params["steamid"] == P
        assert request.url.params["knowncode"] == CODE_A
        return httpx.Response(200, json={"result": {"nextcode": CODE_B}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert SteamMatchClient("key", client).next_code(P, AUTH, CODE_A) == CODE_B
    assert len(seen) == 1
    for response in [
        httpx.Response(202),
        httpx.Response(200, json={"result": {"nextcode": "n/a"}}),
    ]:
        with httpx.Client(transport=httpx.MockTransport(lambda request: response)) as client:
            assert SteamMatchClient("key", client).next_code(P, AUTH, CODE_A) is None


def mocked_sync(db, config, store, parsed):
    def steam(request):
        nextcode = CODE_B if request.url.params["knowncode"] == CODE_A else "n/a"
        return httpx.Response(200, json={"result": {"nextcode": nextcode}})

    def gc(request):
        assert request.headers["Authorization"] == "Bearer bridge-secret"
        assert AUTH not in request.content.decode()
        return httpx.Response(
            200, json={"demo_url": URL, "match_id": "9007199254740993", "played_at": 1700000000}
        )

    return Synchronizer(
        db,
        config,
        store,
        SteamMatchClient("key", httpx.Client(transport=httpx.MockTransport(steam))),
        GCClient(
            "http://gc:8001", "bridge-secret", httpx.Client(transport=httpx.MockTransport(gc))
        ),
        ValveDemoDownloader(100000, 100000, download_client(bz2.compress(DEMO)), public_dns),
        parse=lambda path, timeout: parsed,
    )


def test_full_account_api_discovery_parse_dedup_secret_and_disconnect(tmp_path, parsed):
    app = create_app(
        Config(data_dir=tmp_path),
        sync_factory=lambda db, config, store: mocked_sync(db, config, store, parsed),
    )
    with TestClient(app) as client:
        csrf = login_as(app, client)
        assert (
            client.post(
                "/api/cs2/connection", json={"auth_code": AUTH, "sharing_code": CODE_A}
            ).status_code
            == 403
        )
        connected = client.post(
            "/api/cs2/connection", json={"auth_code": AUTH, "sharing_code": CODE_A}, headers=csrf
        )
        assert connected.status_code == 200 and connected.json()["connected"]
        assert AUTH not in connected.text
        with app.state.db.connect() as c:
            encrypted = c.execute("SELECT auth_code FROM cs2_connections").fetchone()[0]
        assert encrypted != AUTH and app.state.cipher.decrypt(encrypted) == AUTH
        assert client.post("/api/cs2/sync", headers=csrf).status_code == 202
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            status = client.get("/api/cs2/connection").json()
            if status["status"] not in ("queued", "syncing"):
                break
            time.sleep(0.01)
        assert status["status"] == "idle" and status["imported_count"] == 2
        assert len(client.get("/api/matches").json()) == 1
        dashboard = client.get("/api/dashboard").json()
        assert dashboard["personal"]["steam_id64"] == P
        assert dashboard["recent_matches"][0]["personal_stats"]["steam_id64"] == P
        assert dashboard["recent_matches"][0]["played_at"].startswith("2023-11-14")
        match_id = dashboard["recent_matches"][0]["id"]
        assert client.get(f"/api/matches/{match_id}").json()["status"] == "ready"
        assert client.delete("/api/cs2/connection", headers=csrf).status_code == 200
        assert len(client.get("/api/matches").json()) == 1
        with app.state.db.connect() as c:
            assert c.execute("SELECT COUNT(*) FROM cs2_connections").fetchone()[0] == 0


def test_sync_requires_owner_in_replay(tmp_path, parsed):
    config = Config(data_dir=tmp_path)
    db = Database(config.database)
    db.initialize()
    store = SyncStore(db, SecretCipher(config))
    store.initialize()
    store.configure(Q, AUTH, CODE_A)
    alien = deepcopy(parsed)
    alien["players"] = [p for p in alien["players"] if p["steam_id64"] != Q]
    sync = mocked_sync(db, config, store, alien)
    assert sync.refresh(Q)["imported_count"] == 0
    with db.connect() as c:
        assert c.execute("SELECT COUNT(*) FROM account_matches").fetchone()[0] == 0


def test_account_scope_blocks_foreign_match_profile_and_history(tmp_path, parsed):
    app = create_app(Config(data_dir=tmp_path))
    with TestClient(app) as client:
        foreign = deepcopy(parsed)
        foreign["players"] = [p for p in foreign["players"] if p["steam_id64"] != P]
        match_id, _ = app.state.db.reserve("foreign")
        app.state.db.persist(match_id, foreign)
        login_as(app, client)
        assert client.get(f"/api/matches/{match_id}").status_code == 404
        assert client.get(f"/api/matches/{match_id}/insights").status_code == 404
        assert client.get(f"/api/players/{Q}").status_code == 404
        assert client.get("/api/players").json() == []
        assert client.get("/api/dashboard").json()["match_count"] == 0
        assert client.get(f"/api/players/{P}").json()["history"] == []


def test_missing_server_config_is_reported_without_fabrication(tmp_path):
    app = create_app(Config(data_dir=tmp_path))
    with TestClient(app) as client:
        csrf = login_as(app, client)
        client.post(
            "/api/cs2/connection", headers=csrf, json={"auth_code": AUTH, "sharing_code": CODE_A}
        )
        app.state.synchronizer.refresh(P)
        status = client.get("/api/cs2/connection").json()
        assert status["status"] == "configuration_required"
        assert not status["steam_api_configured"] and not status["gc_configured"]
        assert status["imported_count"] == 0 and client.get("/api/matches").json() == []


def test_optional_true_demo_through_sync_pipeline(tmp_path):
    path = os.getenv("CS2_TEST_DEMO")
    if not path:
        pytest.skip("Set CS2_TEST_DEMO to validate the native parser through sync downloads")
    from pathlib import Path

    actual = Path(path).read_bytes()
    parsed = parse_isolated(Path(path), 180)
    owner = parsed["players"][0]["steam_id64"]
    config = Config(data_dir=tmp_path)
    db = Database(config.database)
    db.initialize()
    store = SyncStore(db, SecretCipher(config))
    store.initialize()
    store.configure(owner, AUTH, CODE_A)
    steam = SteamMatchClient(
        "key", httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(202)))
    )
    gc = GCClient(
        "http://gc:8001",
        "secret",
        httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"demo_url": URL})
            )
        ),
    )
    sync = Synchronizer(
        db,
        config,
        store,
        steam,
        gc,
        ValveDemoDownloader(
            len(actual) * 2, len(actual) * 2, download_client(bz2.compress(actual)), public_dns
        ),
        parse=parse_isolated,
    )
    status = sync.refresh(owner)
    assert status["imported_count"] == 1
    match = db.match(db.matches()[0]["id"])
    assert {p["steam_id64"]: p for p in match["players"]} == {
        p["steam_id64"]: p for p in parsed["players"]
    }
    assert match["rounds"] == parsed["rounds"]

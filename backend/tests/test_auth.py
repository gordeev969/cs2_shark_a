import time
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.auth import (
    OPENID_NAMESPACE,
    SESSION_COOKIE,
    STATE_COOKIE,
    STEAM_OPENID_ENDPOINT,
    csrf_token,
    token_hash,
)
from backend.app.config import Config
from backend.app.db import now
from backend.app.main import create_app
from backend.tests.conftest import P, Q


def signed_callback(client, **changes):
    login = client.get("/api/auth/steam/login", follow_redirects=False)
    assert login.status_code == 303
    location = urlsplit(login.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == STEAM_OPENID_ENDPOINT
    params = parse_qs(location.query)
    return_to = params["openid.return_to"][0]
    state = parse_qs(urlsplit(return_to).query)["state"][0]
    assert client.cookies.get(STATE_COOKIE) == state
    values = {
        "state": state,
        "openid.ns": OPENID_NAMESPACE,
        "openid.mode": "id_res",
        "openid.op_endpoint": STEAM_OPENID_ENDPOINT,
        "openid.claimed_id": f"https://steamcommunity.com/openid/id/{P}",
        "openid.identity": f"https://steamcommunity.com/openid/id/{P}",
        "openid.return_to": return_to,
        "openid.response_nonce": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + state,
        "openid.assoc_handle": "provider-association",
        "openid.signed": "op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle",
        "openid.sig": "provider-signature",
    }
    values.update(changes)
    return values


def login_as(app, client, steam=P, token="test-session-secret"):
    with app.state.db.connect() as c:
        c.execute(
            "INSERT OR IGNORE INTO auth_users VALUES(?,?,?,?,?)",
            (steam, "Test Steam user", None, f"https://steamcommunity.com/profiles/{steam}", now()),
        )
        c.execute(
            "INSERT OR REPLACE INTO auth_sessions VALUES(?,?,?,?)",
            (token_hash(token), steam, int(time.time()), int(time.time()) + 3600),
        )
    client.cookies.set(SESSION_COOKIE, token)
    return {"X-CSRF-Token": csrf_token(token)}


def provider(request):
    assert request.url == STEAM_OPENID_ENDPOINT
    assert request.method == "POST"
    assert parse_qs(request.content.decode())["openid.mode"] == ["check_authentication"]
    return httpx.Response(200, text=f"ns:{OPENID_NAMESPACE}\nis_valid:true\n")


def test_real_openid_handshake_session_csrf_logout(tmp_path):
    app = create_app(Config(data_dir=tmp_path), auth_transport=httpx.MockTransport(provider))
    with TestClient(app) as client:
        assert client.get("/api/auth/session").json() == {
            "authenticated": False,
            "required": True,
            "user": None,
            "csrf_token": None,
        }
        assert client.get("/api/dashboard").status_code == 401
        assert client.get("/api/health").status_code == 200
        values = signed_callback(client)
        callback = client.get(
            "/api/auth/steam/callback?" + urlencode(values), follow_redirects=False
        )
        assert callback.status_code == 303 and callback.headers["location"] == "/connect"
        assert "HttpOnly" in callback.headers.get("set-cookie")
        session = client.get("/api/auth/session").json()
        assert session["authenticated"] and session["user"]["steam_id64"] == P
        assert session["csrf_token"] and session["user"]["display_name"] == P
        with app.state.db.connect() as c:
            stored = c.execute("SELECT token_hash FROM auth_sessions").fetchone()[0]
        assert stored != client.cookies.get(SESSION_COOKIE)
        assert client.get("/api/dashboard?steam_id64=" + Q).json()["personal"]["steam_id64"] == P
        assert client.get("/api/settings").json()["steam_id64"] == P
        assert client.put("/api/settings", json={"steam_id64": P}).status_code == 403
        csrf = {"X-CSRF-Token": session["csrf_token"]}
        assert client.put("/api/settings", json={"steam_id64": Q}, headers=csrf).status_code == 403
        assert client.put("/api/settings", json={"steam_id64": P}, headers=csrf).status_code == 200
        assert client.post("/api/auth/logout").status_code == 403
        assert client.post("/api/auth/logout", headers=csrf).status_code == 200
        assert client.get("/api/dashboard").status_code == 401
        assert not client.get("/api/auth/session").json()["authenticated"]


@pytest.mark.parametrize(
    "changes",
    [
        {"state": "wrong"},
        {"openid.op_endpoint": "https://attacker.example"},
        {"openid.claimed_id": f"https://steamcommunity.com/openid/id/{Q}"},
        {"openid.identity": f"http://steamcommunity.com/openid/id/{P}"},
        {"openid.return_to": "https://attacker.example/"},
        {"openid.mode": "cancel"},
        {"openid.signed": "identity,claimed_id"},
        {"openid.ns": "wrong"},
        {"openid.response_nonce": "invalid"},
        {
            "openid.response_nonce": (datetime.now(timezone.utc) - timedelta(hours=1)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            + "old"
        },
    ],
)
def test_openid_rejects_forged_fields_without_contacting_provider(tmp_path, changes):
    def forbidden(request):
        pytest.fail("Invalid local assertion should not contact Steam")

    app = create_app(Config(data_dir=tmp_path), auth_transport=httpx.MockTransport(forbidden))
    with TestClient(app) as client:
        values = signed_callback(client, **changes)
        response = client.get(
            "/api/auth/steam/callback?" + urlencode(values), follow_redirects=False
        )
        assert response.headers["location"].startswith("/login?error=")
        assert not client.get("/api/auth/session").json()["authenticated"]


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text=f"ns:{OPENID_NAMESPACE}\nis_valid:false\n"),
        httpx.Response(302, headers={"Location": "https://attacker.example"}),
        httpx.Response(503),
    ],
)
def test_provider_failure_does_not_create_session(tmp_path, response):
    app = create_app(
        Config(data_dir=tmp_path), auth_transport=httpx.MockTransport(lambda request: response)
    )
    with TestClient(app) as client:
        values = signed_callback(client)
        client.get("/api/auth/steam/callback?" + urlencode(values), follow_redirects=False)
        assert not client.get("/api/auth/session").json()["authenticated"]


def test_nonce_replay_and_duplicate_query_rejected(tmp_path):
    app = create_app(Config(data_dir=tmp_path), auth_transport=httpx.MockTransport(provider))
    with TestClient(app) as client:
        one = signed_callback(client)
        assert (
            client.get(
                "/api/auth/steam/callback?" + urlencode(one), follow_redirects=False
            ).headers["location"]
            == "/connect"
        )
        two = signed_callback(client, **{"openid.response_nonce": one["openid.response_nonce"]})
        client.cookies.delete(SESSION_COOKIE)
        rejected = client.get("/api/auth/steam/callback?" + urlencode(two), follow_redirects=False)
        assert rejected.headers["location"].startswith("/login?error=")
        three = signed_callback(client)
        duplicate = client.get(
            "/api/auth/steam/callback?" + urlencode(three) + "&openid.identity=x",
            follow_redirects=False,
        )
        assert duplicate.headers["location"].startswith("/login?error=")
        assert not client.get("/api/auth/session").json()["authenticated"]


def test_expired_session_and_cookie_https(tmp_path):
    app = create_app(Config(data_dir=tmp_path, steam_public_url="https://local.example"))
    with TestClient(app) as client:
        login = client.get("/api/auth/steam/login", follow_redirects=False)
        assert "Secure" in login.headers["set-cookie"]
        login_as(app, client)
        with app.state.db.connect() as c:
            c.execute("UPDATE auth_sessions SET expires_at=0")
        assert client.get("/api/dashboard").status_code == 401

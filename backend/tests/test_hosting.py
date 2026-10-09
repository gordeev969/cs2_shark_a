from fastapi.testclient import TestClient

from backend.app.config import Config
from backend.app.main import create_app


def test_same_origin_frontend_routes_assets_and_steam_login(tmp_path):
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("<html><body>CS2 app</body></html>")
    (frontend / "assets").mkdir()
    (frontend / "assets" / "app.css").write_text("body{color:lime}")
    app = create_app(
        Config(
            data_dir=tmp_path / "data",
            frontend_dir=frontend,
            steam_public_url="https://cs2-test.onrender.com",
        )
    )
    with TestClient(app) as client:
        for route in ("/", "/login", "/connect", "/players/76561198000000001", "/matches/1"):
            response = client.get(route)
            assert response.status_code == 200
            assert "CS2 app" in response.text
        assert client.get("/assets/app.css").status_code == 200
        assert client.get("/assets/missing.js").status_code == 404
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/dashboard").status_code == 401
        login = client.get("/api/auth/steam/login", follow_redirects=False)
        assert login.status_code == 303
        assert "cs2-test.onrender.com" in login.headers["location"]
        assert "Secure" in login.headers["set-cookie"]


def test_offline_unknown_api_is_not_a_successful_html_page(tmp_path):
    (tmp_path / "index.html").write_text("<html>app</html>")
    with TestClient(
        create_app(
            Config(data_dir=tmp_path / "data", frontend_dir=tmp_path, require_steam_login=False)
        )
    ) as client:
        assert client.get("/api/unknown-endpoint").status_code == 404


def test_hosting_requires_actual_build(tmp_path):
    import pytest

    with pytest.raises(RuntimeError, match="CS2_FRONTEND_DIR"):
        create_app(Config(data_dir=tmp_path / "data", frontend_dir=tmp_path))

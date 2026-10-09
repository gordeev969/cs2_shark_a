"""Steam OpenID 2.0 verification and opaque, locally stored sessions."""

import hashlib
import hmac
import re
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse, RedirectResponse

from .db import now
from .steam_api import steam_profile

STEAM_OPENID_ENDPOINT = "https://steamcommunity.com/openid/login"
OPENID_NAMESPACE = "http://specs.openid.net/auth/2.0"
IDENTIFIER_SELECT = "http://specs.openid.net/auth/2.0/identifier_select"
SESSION_COOKIE = "cs2_session"
STATE_COOKIE = "cs2_openid_state"
STATE_TTL = 10 * 60
SESSION_TTL = 7 * 24 * 60 * 60
IDENTITY_PATTERN = re.compile(r"^https://steamcommunity\.com/openid/id/([0-9]{17})$")
NONCE_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)(.+)$")


def token_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def csrf_token(session_token):
    # The derived value allows a page to authorize mutations without exposing its session token.
    return hashlib.sha256(b"cs2-csrf\0" + session_token.encode("utf-8")).hexdigest()


def constant_time_equal(first, second):
    return hmac.compare_digest(first.encode("utf-8"), second.encode("utf-8"))


def authenticated_user(request):
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(401, "Войдите через Steam.")
    return user


class SecretCipher:
    """String adapter shared by the encrypted CS2 account connection store."""

    def __init__(self, config):
        self.fernet = Fernet(config.encryption_key())

    def encrypt(self, value):
        return self.fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value):
        try:
            return self.fernet.decrypt(value.encode("ascii")).decode("utf-8")
        except (InvalidToken, ValueError, UnicodeError) as exc:
            raise ValueError("Не удалось расшифровать сохранённый код CS2.") from exc


class AuthService:
    def __init__(self, db, config, transport=None):
        self.db, self.config, self.transport = db, config, transport

    def client(self):
        return httpx.Client(timeout=10, follow_redirects=False, transport=self.transport)

    def cleanup(self):
        timestamp = int(time.time())
        with self.db.connect() as connection:
            for table in ("auth_states", "auth_nonces", "auth_sessions"):
                connection.execute(f"DELETE FROM {table} WHERE expires_at<=?", (timestamp,))

    def begin_login(self):
        self.cleanup()
        state = secrets.token_urlsafe(32)
        return_to = (
            f"{self.config.public_origin}/api/auth/steam/callback?{urlencode({'state': state})}"
        )
        with self.db.connect() as connection:
            connection.execute(
                "INSERT INTO auth_states VALUES(?,?,?)",
                (token_hash(state), token_hash(return_to), int(time.time()) + STATE_TTL),
            )
        parameters = {
            "openid.ns": OPENID_NAMESPACE,
            "openid.mode": "checkid_setup",
            "openid.return_to": return_to,
            "openid.realm": self.config.public_origin + "/",
            "openid.identity": IDENTIFIER_SELECT,
            "openid.claimed_id": IDENTIFIER_SELECT,
        }
        response = RedirectResponse(STEAM_OPENID_ENDPOINT + "?" + urlencode(parameters), 303)
        response.headers["Cache-Control"] = "no-store"
        response.set_cookie(
            STATE_COOKIE,
            state,
            max_age=STATE_TTL,
            httponly=True,
            secure=self.config.secure_cookies,
            samesite="lax",
            path="/",
        )
        return response

    def session(self, raw_token):
        if not raw_token or len(raw_token) > 128:
            return None
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT u.steam_id64,u.display_name,u.avatar_url,u.profile_url "
                "FROM auth_sessions s JOIN auth_users u USING(steam_id64) "
                "WHERE s.token_hash=? AND s.expires_at>?",
                (token_hash(raw_token), int(time.time())),
            ).fetchone()
        return dict(row) if row else None

    def verify_callback(self, request):
        query = request.query_params
        if any(len(query.getlist(key)) != 1 for key in query):
            raise HTTPException(400, "Повторяющиеся параметры Steam OpenID.")
        state = query.get("state", "")
        cookie_state = request.cookies.get(STATE_COOKIE, "")
        if not state or len(state) > 128 or not constant_time_equal(state, cookie_state):
            raise HTTPException(400, "Состояние входа Steam не совпадает. Повторите вход.")
        with self.db.connect() as connection:
            stored = connection.execute(
                "DELETE FROM auth_states WHERE state_hash=? AND expires_at>? RETURNING return_to_hash",
                (token_hash(state), int(time.time())),
            ).fetchone()
        if stored is None:
            raise HTTPException(400, "Ссылка входа Steam истекла или уже использована.")
        if query.get("openid.mode") == "cancel":
            raise HTTPException(400, "Вход Steam отменён.")
        identity = query.get("openid.identity", "")
        matched = IDENTITY_PATTERN.fullmatch(identity)
        required_signed = {
            "op_endpoint",
            "claimed_id",
            "identity",
            "return_to",
            "response_nonce",
            "assoc_handle",
        }
        signed = query.get("openid.signed", "").split(",")
        if (
            query.get("openid.ns") != OPENID_NAMESPACE
            or query.get("openid.mode") != "id_res"
            or query.get("openid.op_endpoint") != STEAM_OPENID_ENDPOINT
            or matched is None
            or query.get("openid.claimed_id") != identity
            or token_hash(query.get("openid.return_to", "")) != stored["return_to_hash"]
            or not required_signed.issubset(signed)
            or len(signed) != len(set(signed))
            or not query.get("openid.sig")
            or not query.get("openid.assoc_handle")
        ):
            raise HTTPException(400, "Некорректное подтверждение Steam OpenID.")
        nonce = query.get("openid.response_nonce", "")
        nonce_match = NONCE_PATTERN.fullmatch(nonce)
        try:
            nonce_time = (
                datetime.strptime(nonce_match[1], "%Y-%m-%dT%H:%M:%SZ")
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
        except (TypeError, ValueError):
            raise HTTPException(400, "Некорректная дата подтверждения Steam.") from None
        timestamp = time.time()
        if nonce_time < timestamp - STATE_TTL or nonce_time > timestamp + 60 or len(nonce) > 512:
            raise HTTPException(400, "Подтверждение Steam просрочено.")
        with self.db.connect() as connection:
            if connection.execute(
                "SELECT 1 FROM auth_nonces WHERE nonce_hash=?", (token_hash(nonce),)
            ).fetchone():
                raise HTTPException(400, "Подтверждение Steam уже использовано.")
        parameters = {key: value for key, value in query.items() if key.startswith("openid.")}
        parameters["openid.mode"] = "check_authentication"
        try:
            with self.client() as client:
                verified = client.post(STEAM_OPENID_ENDPOINT, data=parameters)
                verified.raise_for_status()
                lines = [line.split(":", 1) for line in verified.text.splitlines() if ":" in line]
                values = dict(lines)
                if (
                    len(lines) != len(values)
                    or values.get("ns") != OPENID_NAMESPACE
                    or values.get("is_valid") != "true"
                ):
                    raise HTTPException(401, "Steam не подтвердил вход.")
                profile = steam_profile(matched[1], self.config.steam_web_api_key, client)
        except httpx.HTTPError:
            raise HTTPException(502, "Steam временно недоступен. Повторите вход.") from None
        session_token = secrets.token_urlsafe(32)
        with self.db.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO auth_nonces VALUES(?,?)",
                (token_hash(nonce), int(timestamp) + STATE_TTL + 60),
            )
            if connection.execute("SELECT changes()").fetchone()[0] != 1:
                raise HTTPException(400, "Подтверждение Steam уже использовано.")
            connection.execute(
                "INSERT INTO auth_users VALUES(?,?,?,?,?) ON CONFLICT(steam_id64) DO UPDATE SET "
                "display_name=excluded.display_name,avatar_url=excluded.avatar_url,"
                "profile_url=excluded.profile_url,updated_at=excluded.updated_at",
                (
                    profile["steam_id64"],
                    profile["display_name"],
                    profile["avatar_url"],
                    profile["profile_url"],
                    now(),
                ),
            )
            connection.execute(
                "INSERT INTO auth_sessions VALUES(?,?,?,?)",
                (
                    token_hash(session_token),
                    profile["steam_id64"],
                    int(timestamp),
                    int(timestamp) + SESSION_TTL,
                ),
            )
        self.db.save_settings(profile["steam_id64"], self.db.settings()["compact"])
        with self.db.connect() as connection:
            connected = connection.execute(
                "SELECT 1 FROM cs2_connections WHERE steam_id64=?", (profile["steam_id64"],)
            ).fetchone()
        response = RedirectResponse("/" if connected else "/connect", 303)
        response.headers["Cache-Control"] = "no-store"
        response.set_cookie(
            SESSION_COOKIE,
            session_token,
            max_age=SESSION_TTL,
            httponly=True,
            secure=self.config.secure_cookies,
            samesite="lax",
            path="/",
        )
        response.delete_cookie(
            STATE_COOKIE, secure=self.config.secure_cookies, httponly=True, samesite="lax"
        )
        return response

    def logout(self, request):
        raw_token = request.cookies.get(SESSION_COOKIE, "")
        with self.db.connect() as connection:
            connection.execute(
                "DELETE FROM auth_sessions WHERE token_hash=?", (token_hash(raw_token),)
            )
        response = JSONResponse({"authenticated": False}, headers={"Cache-Control": "no-store"})
        response.delete_cookie(
            SESSION_COOKIE, secure=self.config.secure_cookies, httponly=True, samesite="lax"
        )
        return response


class SessionMiddleware:
    PUBLIC_API_PATHS = {
        "/api/health",
        "/api/auth/session",
        "/api/auth/steam/login",
        "/api/auth/steam/callback",
    }

    def __init__(self, app, auth):
        self.app, self.auth = app, auth

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        request = Request(scope)
        raw_token = request.cookies.get(SESSION_COOKIE, "")
        user = self.auth.session(raw_token)
        scope.setdefault("state", {})["user"] = user
        scope["state"]["csrf_token"] = csrf_token(raw_token) if user else None
        path, method = scope["path"], scope["method"]
        if path.startswith("/api/") and path not in self.PUBLIC_API_PATHS and method != "OPTIONS":
            if user is None and (
                self.auth.config.require_steam_login or path == "/api/auth/logout"
            ):
                return await JSONResponse({"detail": "Войдите через Steam."}, 401)(
                    scope, receive, send
                )
            if user and method not in ("GET", "HEAD"):
                submitted = request.headers.get("x-csrf-token", "")
                if not constant_time_equal(submitted, scope["state"]["csrf_token"]):
                    return await JSONResponse({"detail": "Недействительный CSRF-токен."}, 403)(
                        scope, receive, send
                    )
        return await self.app(scope, receive, send)


def auth_router(auth):
    router = APIRouter(prefix="/api/auth", tags=["Steam"])

    @router.get("/session")
    def session(request: Request):
        return JSONResponse(
            {
                "authenticated": request.state.user is not None,
                "required": auth.config.require_steam_login,
                "user": request.state.user,
                "csrf_token": request.state.csrf_token,
            },
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/steam/login")
    def login():
        return auth.begin_login()

    @router.get("/steam/callback")
    def callback(request: Request):
        try:
            return auth.verify_callback(request)
        except HTTPException:
            response = RedirectResponse("/login?error=steam", 303)
            response.headers["Cache-Control"] = "no-store"
            response.delete_cookie(
                STATE_COOKIE, secure=auth.config.secure_cookies, httponly=True, samesite="lax"
            )
            return response

    @router.post("/logout")
    def logout(request: Request):
        return auth.logout(request)

    return router

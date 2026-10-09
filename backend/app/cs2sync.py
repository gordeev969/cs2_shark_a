"""Real Valve match-code discovery, replay download, and durable account imports.

Steam OpenID identifies an account. Game Authentication Code and the Web API key
discover *subsequent* sharing codes; a CS2 Game Coordinator connection resolves
those codes to a replay URL. Neither credential substitutes for the GC connection.
"""

import bz2
import hashlib
import ipaddress
import re
import socket
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .db import now
from .jobs import parse_isolated, run_job

SHARE_CODE = re.compile(
    r"^CSGO(?:-[ABCDEFGHJKLMNOPQRSTUVWXYZabcdefhijkmnopqrstuvwxyz23456789]{5}){5}$"
)
AUTH_CODE = re.compile(r"^[A-Za-z0-9]{4,8}(?:-[A-Za-z0-9]{4,8}){2}$")
STEAM_ID = re.compile(r"^[0-9]{17}$")
REPLAY_HOST = re.compile(r"^replay[0-9]{1,5}\.valve\.net$", re.ASCII)
STEAM_NEXT_URL = "https://api.steampowered.com/ICSGOPlayers_730/GetNextMatchSharingCode/v1/"
MAX_CODES_PER_SYNC = 20
CHUNK = 64 * 1024


class SyncError(Exception):
    """A fixed, credential-free message which is safe to return to the browser."""

    def __init__(self, message, status="error"):
        super().__init__(message)
        self.status = status


class SyncStore:
    def __init__(self, db, cipher):
        self.db, self.cipher = db, cipher

    def initialize(self):
        with self.db.connect() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS cs2_connections (
                    steam_id64 TEXT PRIMARY KEY, auth_code TEXT NOT NULL,
                    initial_sharecode TEXT NOT NULL, latest_sharecode TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'idle', error TEXT, last_sync TEXT);
                CREATE TABLE IF NOT EXISTS cs2_sharecodes (
                    steam_id64 TEXT NOT NULL REFERENCES cs2_connections(steam_id64) ON DELETE CASCADE,
                    sharecode TEXT NOT NULL, discovered_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending', error TEXT,
                    match_id INTEGER REFERENCES matches(id), valve_match_id TEXT,
                    PRIMARY KEY(steam_id64,sharecode));
            """)

    def configure(self, steam_id, authcode, sharecode):
        if not STEAM_ID.fullmatch(steam_id):
            raise SyncError("Некорректный SteamID64.")
        authcode, sharecode = authcode.strip(), sharecode.strip()
        if not AUTH_CODE.fullmatch(authcode):
            raise SyncError("Скопируйте Game Authentication Code из личных данных CS2 в Steam.")
        if not SHARE_CODE.fullmatch(sharecode):
            raise SyncError("Укажите код матча в формате CSGO-xxxxx-xxxxx-xxxxx-xxxxx-xxxxx.")
        encrypted = self.cipher.encrypt(authcode)
        with self.db.connect() as c:
            c.execute(
                """INSERT INTO cs2_connections
                   (steam_id64,auth_code,initial_sharecode,latest_sharecode)
                   VALUES(?,?,?,?) ON CONFLICT(steam_id64) DO UPDATE SET
                   auth_code=excluded.auth_code,
                   latest_sharecode=CASE WHEN cs2_connections.initial_sharecode=excluded.initial_sharecode
                     THEN cs2_connections.latest_sharecode ELSE excluded.latest_sharecode END,
                   initial_sharecode=excluded.initial_sharecode,status='idle',error=NULL""",
                (steam_id, encrypted, sharecode, sharecode),
            )
            c.execute(
                "INSERT OR IGNORE INTO cs2_sharecodes(steam_id64,sharecode,discovered_at) VALUES(?,?,?)",
                (steam_id, sharecode, now()),
            )

    def connection(self, steam_id):
        with self.db.connect() as c:
            row = c.execute(
                "SELECT * FROM cs2_connections WHERE steam_id64=?", (steam_id,)
            ).fetchone()
        if row is None:
            raise SyncError("Сначала подключите код авторизации CS2 и код последнего матча.")
        result = dict(row)
        try:
            result["auth_code"] = self.cipher.decrypt(result["auth_code"])
        except Exception:
            raise SyncError("Не удалось расшифровать код CS2. Подключите его повторно.") from None
        return result

    def status(self, steam_id, gc_configured=False, api_configured=False):
        with self.db.connect() as c:
            row = c.execute(
                "SELECT initial_sharecode,latest_sharecode,status,error,last_sync "
                "FROM cs2_connections WHERE steam_id64=?",
                (steam_id,),
            ).fetchone()
            codes = c.execute(
                "SELECT status,COUNT(*) AS n FROM cs2_sharecodes WHERE steam_id64=? GROUP BY status",
                (steam_id,),
            ).fetchall()
        counts = {r["status"]: r["n"] for r in codes}
        return {
            "connected": row is not None,
            "status": row["status"] if row else "disconnected",
            "error": row["error"] if row else None,
            "last_sync": row["last_sync"] if row else None,
            "initial_sharecode": row["initial_sharecode"] if row else None,
            "latest_sharecode": row["latest_sharecode"] if row else None,
            "discovered_count": sum(counts.values()),
            "imported_count": counts.get("ready", 0),
            "pending_count": sum(v for k, v in counts.items() if k not in ("ready", "unavailable")),
            "failed_count": counts.get("failed", 0) + counts.get("unavailable", 0),
            "gc_configured": gc_configured,
            "api_configured": api_configured,
            "steam_api_configured": api_configured,
        }

    def enqueue(self, steam_id):
        with self.db.connect() as c:
            c.execute(
                "UPDATE cs2_connections SET status='queued',error=NULL "
                "WHERE steam_id64=? AND status NOT IN ('queued','syncing')",
                (steam_id,),
            )
            return c.execute("SELECT changes()").fetchone()[0] == 1

    def set_state(self, steam_id, state, error=None, completed=False):
        with self.db.connect() as c:
            c.execute(
                "UPDATE cs2_connections SET status=?,error=?,last_sync=CASE WHEN ? "
                "THEN ? ELSE last_sync END WHERE steam_id64=?",
                (state, error, completed, now(), steam_id),
            )

    def discover(self, steam_id, code):
        with self.db.connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO cs2_sharecodes(steam_id64,sharecode,discovered_at) VALUES(?,?,?)",
                (steam_id, code, now()),
            )
            fresh = c.execute("SELECT changes()").fetchone()[0] == 1
            c.execute(
                "UPDATE cs2_connections SET latest_sharecode=? WHERE steam_id64=?", (code, steam_id)
            )
        return fresh

    def pending(self, steam_id, limit=MAX_CODES_PER_SYNC):
        with self.db.connect() as c:
            return [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM cs2_sharecodes WHERE steam_id64=? AND status NOT IN ('ready','unavailable') "
                    "ORDER BY discovered_at,sharecode LIMIT ?",
                    (steam_id, limit),
                )
            ]

    def mark_code(self, steam_id, code, state, error=None, match_id=None, valve_match_id=None):
        with self.db.connect() as c:
            c.execute(
                "UPDATE cs2_sharecodes SET status=?,error=?,match_id=?,valve_match_id=? "
                "WHERE steam_id64=? AND sharecode=?",
                (state, error, match_id, valve_match_id, steam_id, code),
            )

    def remove(self, steam_id):
        with self.db.connect() as c:
            c.execute("DELETE FROM cs2_connections WHERE steam_id64=?", (steam_id,))


class SteamMatchClient:
    """Official GetNextMatchSharingCode. Never surface query-string exceptions."""

    def __init__(self, api_key, client=None):
        self.api_key = api_key
        self.client = client

    def next_code(self, steam_id, authcode, knowncode):
        if not self.api_key:
            raise SyncError(
                "Для автоматической истории администратор должен настроить STEAM_WEB_API_KEY.",
                "configuration_required",
            )
        try:
            if self.client:
                response = self._request(self.client, steam_id, authcode, knowncode)
            else:
                with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
                    response = self._request(client, steam_id, authcode, knowncode)
        except httpx.HTTPError:
            raise SyncError("Steam Web API недоступен. Повторите синхронизацию позже.") from None
        if response.status_code == 202:
            return None
        if response.status_code in (401, 403):
            raise SyncError("Steam отклонил ключ API или код авторизации CS2.", "auth_error")
        if response.status_code == 429:
            raise SyncError("Steam ограничил частоту запросов. Повторите позже.", "rate_limited")
        if response.status_code != 200:
            raise SyncError("Steam не вернул историю матчей. Повторите позже.")
        try:
            code = response.json()["result"]["nextcode"]
        except (ValueError, KeyError, TypeError):
            raise SyncError("Steam вернул неподдерживаемый ответ истории матчей.") from None
        if code == "n/a":
            return None
        if not isinstance(code, str) or not SHARE_CODE.fullmatch(code):
            raise SyncError("Steam вернул некорректный код матча.")
        return code

    def _request(self, client, steam_id, authcode, knowncode):
        return client.get(
            STEAM_NEXT_URL,
            params={
                "key": self.api_key,
                "steamid": steam_id,
                "steamidkey": authcode,
                "knowncode": knowncode,
            },
        )


def reliable_played_at(value):
    """GC Unix timestamp is reliable; reject missing, implausible or naive dates."""
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            date = datetime.fromtimestamp(value, timezone.utc)
        elif isinstance(value, str):
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if date.tzinfo is None:
                return None
        else:
            return None
        if (
            datetime(2012, 1, 1, tzinfo=timezone.utc)
            <= date
            <= datetime.now(timezone.utc) + timedelta(days=1)
        ):
            return date.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        pass
    return None


class GCClient:
    """Internal trusted CS2 GC bridge; users cannot choose this destination."""

    def __init__(self, url, secret, client=None):
        parts = urlsplit(url)
        if (
            parts.scheme not in ("http", "https")
            or not parts.hostname
            or parts.username
            or parts.password
        ):
            raise ValueError("CS2_GC_URL должен быть адресом внутреннего сервиса.")
        if parts.query or parts.fragment or not secret:
            raise ValueError("Для GC bridge необходим CS2_GC_SECRET и URL без query/fragment.")
        self.url, self.secret, self.client = url.rstrip("/") + "/resolve", secret, client

    def resolve(self, sharecode):
        try:
            if self.client:
                response = self._request(self.client, sharecode)
            else:
                with httpx.Client(timeout=45, follow_redirects=False, trust_env=False) as client:
                    response = self._request(client, sharecode)
        except httpx.HTTPError:
            raise SyncError("Сервис CS2 Game Coordinator недоступен. Повторите позже.") from None
        if response.status_code in (404, 410):
            raise SyncError("Valve больше не хранит демку этого матча.", "unavailable")
        if response.status_code == 503:
            raise SyncError(
                "CS2 Game Coordinator ещё не подключён. Повторите позже.", "waiting_replay"
            )
        if response.status_code != 200:
            raise SyncError("Не удалось получить демку из CS2 Game Coordinator.")
        try:
            data = response.json()
            url = data["demo_url"]
            if not isinstance(url, str):
                raise ValueError
            valve_id = data.get("match_id")
            if valve_id is not None and not re.fullmatch(r"[0-9]{1,30}", str(valve_id)):
                raise ValueError
            return {
                "demo_url": url,
                "match_id": str(valve_id) if valve_id else None,
                "played_at": reliable_played_at(data.get("played_at")),
            }
        except (ValueError, KeyError, TypeError):
            raise SyncError("GC bridge вернул некорректные данные демки.") from None

    def _request(self, client, code):
        return client.post(
            self.url, headers={"Authorization": f"Bearer {self.secret}"}, json={"sharecode": code}
        )


class ValveDemoDownloader:
    def __init__(self, download_limit, decompressed_limit, client=None, dns_resolver=None):
        self.download_limit, self.decompressed_limit = download_limit, decompressed_limit
        self.client = client
        self.dns_resolver = dns_resolver or socket.getaddrinfo

    def validate_url(self, url):
        try:
            parts = urlsplit(url)
            if (
                parts.scheme not in ("http", "https")
                or not parts.hostname
                or not REPLAY_HOST.fullmatch(parts.hostname)
                or parts.username
                or parts.password
                or parts.query
                or parts.fragment
                or parts.port not in (None, 80 if parts.scheme == "http" else 443)
                or not re.fullmatch(r"/730/[A-Za-z0-9_-]+\.dem(?:\.bz2)?", parts.path)
            ):
                raise ValueError
            addresses = self.dns_resolver(
                parts.hostname,
                parts.port or (443 if parts.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
            if not addresses or any(not ipaddress.ip_address(r[4][0]).is_global for r in addresses):
                raise ValueError
        except (ValueError, OSError):
            raise SyncError(
                "Разрешены только публичные серверы демо Valve replay*.valve.net."
            ) from None
        return parts

    def download(self, url, target):
        """Stream .dem or one .bz2 member. Both compressed and output bytes are bounded."""
        parts = self.validate_url(url)
        target = Path(target)
        try:
            if self.client:
                return self._download(self.client, url, target, parts.path.endswith(".bz2"))
            with httpx.Client(
                timeout=httpx.Timeout(30, read=60), follow_redirects=False, trust_env=False
            ) as client:
                return self._download(client, url, target, parts.path.endswith(".bz2"))
        except SyncError:
            target.unlink(missing_ok=True)
            raise
        except (httpx.HTTPError, OSError, EOFError, ValueError):
            target.unlink(missing_ok=True)
            raise SyncError(
                "Не удалось скачать или распаковать CS2-демку. Повторите позже."
            ) from None

    def _download(self, client, url, target, compressed):
        digest, signature = hashlib.sha256(), b""
        total_in = total_out = 0
        decoder = bz2.BZ2Decompressor() if compressed else None
        with client.stream(
            "GET", url, follow_redirects=False, headers={"Accept-Encoding": "identity"}
        ) as response:
            if response.status_code in (404, 410):
                raise SyncError("Valve больше не хранит демку этого матча.", "unavailable")
            if response.status_code != 200:
                raise SyncError("Сервер Valve не вернул демку. Повторите позже.")
            if response.headers.get("content-encoding", "identity").lower() not in ("", "identity"):
                raise SyncError("Сервер вернул неподдерживаемое сжатие ответа.")
            length = response.headers.get("content-length")
            if length is not None and (not length.isdigit() or int(length) > self.download_limit):
                raise SyncError("Размер загрузки демки превышает установленный лимит.")
            with target.open("wb") as output:
                for chunk in response.iter_raw(CHUNK):
                    total_in += len(chunk)
                    if total_in > self.download_limit:
                        raise SyncError("Размер загрузки демки превышает установленный лимит.")
                    if decoder and decoder.eof:
                        raise SyncError("Архив содержит данные после CS2-демки.")
                    pending = chunk
                    while True:
                        piece = (
                            decoder.decompress(pending, max_length=CHUNK) if decoder else pending
                        )
                        total_out += len(piece)
                        if total_out > self.decompressed_limit:
                            raise SyncError("Распакованная демка превышает установленный лимит.")
                        signature = (signature + piece)[:8]
                        digest.update(piece)
                        output.write(piece)
                        if not decoder or decoder.needs_input or decoder.eof:
                            break
                        pending = b""
                    if decoder and decoder.unused_data:
                        raise SyncError("Архив содержит данные после CS2-демки.")
        if decoder and not decoder.eof:
            raise SyncError("Архив CS2-демки повреждён или обрезан.")
        if total_out < 16 or signature != b"PBDEMS2\x00":
            raise SyncError("Загруженный файл не является бинарной CS2-демкой PBDEMS2.")
        return digest.hexdigest()


class Synchronizer:
    """Run refresh in a worker thread, not on FastAPI's async event loop."""

    def __init__(
        self, db, config, store, steam_client, gc_client=None, downloader=None, parse=parse_isolated
    ):
        self.db, self.config, self.store = db, config, store
        self.steam_client, self.gc_client, self.parse = steam_client, gc_client, parse
        self.downloader = downloader or ValveDemoDownloader(
            config.max_upload_bytes, config.max_upload_bytes
        )
        self._lock = threading.Lock()

    def status(self, steam_id):
        return self.store.status(
            steam_id, self.gc_client is not None, bool(self.steam_client.api_key)
        )

    def refresh(self, steam_id):
        if not self._lock.acquire(blocking=False):
            raise SyncError("Синхронизация уже выполняется.", "syncing")
        try:
            connection = self.store.connection(steam_id)
            self.store.set_state(steam_id, "syncing")
            discovery_error = None
            known = connection["latest_sharecode"]
            seen = {known}
            try:
                for _ in range(MAX_CODES_PER_SYNC):
                    code = self.steam_client.next_code(steam_id, connection["auth_code"], known)
                    if code is None:
                        break
                    if code in seen:
                        raise SyncError(
                            "Steam вернул повторяющийся код матча; синхронизация остановлена."
                        )
                    seen.add(code)
                    self.store.discover(steam_id, code)
                    known = code
            except SyncError as exc:
                discovery_error = exc
            pending = self.store.pending(steam_id)
            failures = []
            if self.gc_client:
                for row in pending:
                    try:
                        self._import_code(steam_id, row["sharecode"])
                    except SyncError as exc:
                        self.store.mark_code(
                            steam_id,
                            row["sharecode"],
                            "unavailable" if exc.status == "unavailable" else "failed",
                            str(exc),
                        )
                        failures.append(str(exc))
            if discovery_error:
                self.store.set_state(
                    steam_id, discovery_error.status, str(discovery_error), completed=True
                )
            elif failures:
                self.store.set_state(steam_id, "partial", failures[0], completed=True)
            elif pending and not self.gc_client:
                self.store.set_state(
                    steam_id,
                    "waiting_replay",
                    "Коды матчей сохранены. Для загрузки демо нужен подключённый CS2 Game Coordinator. "
                    "Пока можно импортировать .dem вручную.",
                    completed=True,
                )
            elif self.store.pending(steam_id, 1):
                self.store.set_state(steam_id, "pending", completed=True)
            else:
                self.store.set_state(steam_id, "idle", completed=True)
            return self.status(steam_id)
        except SyncError:
            raise
        except Exception:
            self.store.set_state(
                steam_id, "error", "Синхронизация прервана. Повторите позже.", completed=True
            )
            return self.status(steam_id)
        finally:
            self._lock.release()

    def _import_code(self, steam_id, code):
        self.store.mark_code(steam_id, code, "downloading")
        replay = self.gc_client.resolve(code)
        self.config.uploads.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(
            dir=self.config.uploads, prefix="incoming-", suffix=".tmp", delete=False
        ) as output:
            path = Path(output.name)
        try:
            digest = self.downloader.download(replay["demo_url"], path)
            match_id, fresh = self.db.reserve(digest)
            target = self.config.uploads / f"{digest}.dem"
            if fresh:
                path.replace(target)
                run_job(self.db, self.config, match_id, target, self.parse)
            match = self.db.match(match_id)
            if match["status"] != "ready":
                raise SyncError(
                    "Не удалось разобрать демку CS2. Проверьте импорт или повторите позже."
                )
            if not any(p["steam_id64"] == steam_id for p in match["players"]):
                raise SyncError("В загруженной демке нет авторизованного Steam-профиля.")
            played_at = reliable_played_at(replay.get("played_at"))
            if played_at and not match["played_at"]:
                with self.db.connect() as c:
                    c.execute(
                        "UPDATE matches SET played_at=? WHERE id=? AND played_at IS NULL",
                        (played_at, match_id),
                    )
            from .account_data import AccountData

            AccountData(self.db).attach(steam_id, match_id, "cs2_sync")
            self.store.mark_code(
                steam_id, code, "ready", match_id=match_id, valve_match_id=replay.get("match_id")
            )
        finally:
            path.unlink(missing_ok=True)

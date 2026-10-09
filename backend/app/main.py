import hashlib
import importlib.metadata
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from .account_data import AccountData
from .auth import AuthService, SecretCipher, SessionMiddleware, auth_router, authenticated_user
from .config import Config
from .cs2sync import GCClient, SteamMatchClient, SyncError, Synchronizer, SyncStore
from .db import Database
from .insights import match_notes
from .jobs import parse_isolated, run_job
from .web import SPAStaticFiles

LOCAL_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
}


class RequestGuard:
    """Bound multipart size before Starlette spools, and local browser origins."""

    def __init__(self, app, limit, public_origin):
        self.app, self.limit = app, limit + 1024 * 1024
        self.origins = LOCAL_ORIGINS | {public_origin}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        origin = headers.get(b"origin", b"").decode()
        steam_callback = (
            scope["method"] == "GET"
            and scope["path"] == "/api/auth/steam/callback"
            and origin == "https://steamcommunity.com"
        )
        if origin and origin not in self.origins and not steam_callback:
            return await JSONResponse(
                {"detail": "Разрешены только локальные запросы."}, status_code=403
            )(scope, receive, send)
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Некорректный Content-Length."}, status_code=400)(
                scope, receive, send
            )
        if length > self.limit:
            return await JSONResponse({"detail": "Превышен лимит загрузки."}, status_code=413)(
                scope, receive, send
            )
        total = 0

        async def bounded():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > self.limit:
                raise HTTPException(413, "Превышен лимит загрузки.")
            return message

        return await self.app(scope, bounded, send)


class SettingsInput(BaseModel):
    steam_id64: str = Field(default="", pattern=r"^(?:[0-9]{17})?$")
    compact: bool = False


class CS2ConnectionInput(BaseModel):
    auth_code: str = Field(min_length=1, max_length=128)
    sharing_code: str = Field(min_length=1, max_length=64)


def create_app(config=None, parse=parse_isolated, auth_transport=None, sync_factory=None):
    config = config or Config()
    db = Database(config.database)
    auth = AuthService(db, config, transport=auth_transport)
    accounts = AccountData(db)

    @asynccontextmanager
    async def lifespan(application):
        config.uploads.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(config.data_dir, 0o700)
        os.chmod(config.uploads, 0o700)
        db.initialize()
        application.state.cipher = SecretCipher(config)
        store = SyncStore(db, application.state.cipher)
        store.initialize()
        gc = GCClient(config.cs2_gc_url, config.cs2_gc_secret) if config.cs2_gc_url else None
        synchronizer = Synchronizer(
            db, config, store, SteamMatchClient(config.steam_api_key), gc, parse=parse
        )
        application.state.sync_store = store
        application.state.synchronizer = (
            sync_factory(db, config, store) if sync_factory else synchronizer
        )
        with db.connect() as c:
            c.execute(
                "UPDATE cs2_connections SET status='idle',error='Синхронизация прервана перезапуском. Повторите её.' WHERE status IN ('queued','syncing')"
            )
        auth.cleanup()
        os.chmod(config.database, 0o600)
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cs2-parser")
        application.state.pool = pool
        # A process crash can interrupt parsing. Complete queued imports after restart.
        for row in db.matches():
            if row["status"] in ("queued", "processing"):
                path = config.uploads / f"{row['file_sha256']}.dem"
                if path.exists():
                    db.status(row["id"], "queued")
                    pool.submit(run_job, db, config, row["id"], path, parse)
                else:
                    db.status(
                        row["id"],
                        "failed",
                        "Импорт прерван: файл отсутствует. Загрузите демку повторно.",
                    )
        # Unreserved partial uploads have no durable job and are safe to discard.
        for path in config.uploads.glob("incoming-*.tmp"):
            path.unlink(missing_ok=True)
        yield
        pool.shutdown(wait=True, cancel_futures=False)

    application = FastAPI(title="CS2 Premier Analyzer", version="0.1.0", lifespan=lifespan)
    application.state.db = db
    application.state.auth = auth
    application.add_middleware(SessionMiddleware, auth=auth)
    application.add_middleware(
        RequestGuard, limit=config.max_upload_bytes, public_origin=config.public_origin
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(LOCAL_ORIGINS | {config.public_origin}),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            "localhost",
            "127.0.0.1",
            "[::1]",
            "testserver",
            urlsplit(config.public_origin).hostname,
        ],
    )
    application.include_router(auth_router(auth))

    @application.get("/api/health")
    def health():
        return {
            "status": "ok",
            "parser_version": importlib.metadata.version("demoparser2"),
            "max_upload_bytes": config.max_upload_bytes,
            "retain_demos": config.retain_demos,
            "ai_enabled": False,
        }

    @application.post("/api/matches/import", status_code=202)
    async def import_match(request: Request, file: UploadFile = File(...)):
        path = None
        try:
            if not file.filename or not file.filename.lower().endswith(".dem"):
                raise HTTPException(
                    415,
                    "Поддерживаются только несжатые .dem. Распакуйте .bz2 или .zip самостоятельно.",
                )
            digest, size, signature = hashlib.sha256(), 0, b""
            with tempfile.NamedTemporaryFile(
                dir=config.uploads, prefix="incoming-", suffix=".tmp", delete=False
            ) as output:
                path = Path(output.name)
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > config.max_upload_bytes:
                        raise HTTPException(
                            413,
                            f"Файл превышает лимит {config.max_upload_bytes // 1024 // 1024} МБ.",
                        )
                    if len(signature) < 8:
                        signature = (signature + chunk)[:8]
                    digest.update(chunk)
                    output.write(chunk)
            if size < 16 or signature != b"PBDEMS2\x00":
                raise HTTPException(
                    422,
                    "Файл не является бинарной CS2-демкой (ожидается PBDEMS2). CS:GO и пустые файлы не поддерживаются.",
                )
            match_id, fresh = db.reserve(digest.hexdigest())
            accounts.attach(owner(request), match_id)
            if fresh:
                target = config.uploads / f"{digest.hexdigest()}.dem"
                try:
                    path.replace(target)
                    application.state.pool.submit(run_job, db, config, match_id, target, parse)
                except Exception:
                    db.status(
                        match_id,
                        "failed",
                        "Не удалось сохранить или запустить импорт. Повторите загрузку.",
                    )
                    target.unlink(missing_ok=True)
                    raise HTTPException(500, "Не удалось запустить импорт.") from None
            return {"id": match_id, "status": db.match(match_id)["status"], "duplicate": not fresh}
        finally:
            await file.close()
            if path:
                path.unlink(missing_ok=True)

    def owner(request):
        return request.state.user["steam_id64"] if request.state.user else None

    def own_settings(request):
        return {**db.settings(), **({"steam_id64": owner(request)} if owner(request) else {})}

    @application.get("/api/matches")
    def matches(request: Request):
        return accounts.matches(owner(request), own_settings(request)["steam_id64"])

    @application.get("/api/matches/{match_id}")
    def match(match_id: int, request: Request):
        result = accounts.match(match_id, owner(request))
        if result is None:
            raise HTTPException(404, "Матч не найден.")
        return result

    @application.get("/api/players")
    def players(request: Request, query: str = Query(default="", max_length=120)):
        return accounts.search(query, owner(request))

    @application.get("/api/players/{steam_id64}")
    def player(steam_id64: str, request: Request):
        result = accounts.player(steam_id64, owner(request), request.state.user)
        if result is None:
            raise HTTPException(404, "Игрок не найден в локальных импортах.")
        return result

    @application.get("/api/dashboard")
    def dashboard(request: Request, steam_id64: str | None = None):
        steam = owner(request) or steam_id64 or db.settings()["steam_id64"]
        matches = accounts.matches(owner(request), steam)
        profile = accounts.player(steam, owner(request), request.state.user) if steam else None
        return {
            "match_count": sum(r["status"] == "ready" for r in matches),
            "queued_count": sum(r["status"] in ("queued", "processing") for r in matches),
            "player_count": accounts.player_count(owner(request)),
            "recent_matches": matches[:8],
            "personal": profile,
            "profile": request.state.user,
            "cs2": application.state.synchronizer.status(steam) if owner(request) else None,
            "settings": own_settings(request),
        }

    @application.get("/api/matches/{match_id}/insights")
    def insights(match_id: int, request: Request, steam_id64: str | None = None):
        result = match(match_id, request)
        if result["status"] != "ready":
            raise HTTPException(409, "Сначала дождитесь успешного разбора демки.")
        selected = [p for p in result["players"] if not steam_id64 or p["steam_id64"] == steam_id64]
        if not selected:
            raise HTTPException(404, "Игрок отсутствует в этом матче.")
        return [
            {
                "steam_id64": p["steam_id64"],
                "notes": match_notes(p),
                "history": accounts.player(p["steam_id64"], owner(request))["insights"],
            }
            for p in selected
        ]

    @application.get("/api/settings")
    def settings(request: Request):
        return own_settings(request)

    @application.put("/api/settings")
    def update_settings(values: SettingsInput, request: Request):
        steam = values.steam_id64
        if request.state.user:
            steam = request.state.user["steam_id64"]
            if values.steam_id64 and values.steam_id64 != steam:
                raise HTTPException(403, "SteamID определяется аккаунтом, вошедшим через Steam.")
        return db.save_settings(steam, values.compact)

    def connection_owner(request):
        return authenticated_user(request)["steam_id64"]

    def idle_connection(steam):
        if application.state.synchronizer.status(steam)["status"] in ("queued", "syncing"):
            raise HTTPException(409, "Дождитесь завершения текущей синхронизации.")

    @application.get("/api/cs2/connection")
    def connection(request: Request):
        return application.state.synchronizer.status(connection_owner(request))

    @application.post("/api/cs2/connection")
    def connect_cs2(values: CS2ConnectionInput, request: Request):
        steam = connection_owner(request)
        idle_connection(steam)
        try:
            application.state.sync_store.configure(steam, values.auth_code, values.sharing_code)
        except SyncError as exc:
            raise HTTPException(422, str(exc)) from None
        return application.state.synchronizer.status(steam)

    @application.delete("/api/cs2/connection")
    def disconnect_cs2(request: Request):
        steam = connection_owner(request)
        idle_connection(steam)
        application.state.sync_store.remove(steam)
        return application.state.synchronizer.status(steam)

    @application.post("/api/cs2/sync", status_code=202)
    def sync_cs2(request: Request):
        steam = connection_owner(request)
        idle_connection(steam)
        try:
            application.state.sync_store.connection(steam)
        except SyncError as exc:
            raise HTTPException(409, str(exc)) from None
        if not application.state.sync_store.enqueue(steam):
            raise HTTPException(409, "Синхронизация уже в очереди.")

        def refresh():
            try:
                application.state.synchronizer.refresh(steam)
            except SyncError as exc:
                application.state.sync_store.set_state(steam, exc.status, str(exc), completed=True)
            except Exception:
                application.state.sync_store.set_state(
                    steam, "error", "Синхронизация прервана. Повторите позже.", completed=True
                )

        application.state.pool.submit(refresh)
        return application.state.synchronizer.status(steam)

    if config.frontend_dir:
        if not (config.frontend_dir / "index.html").is_file():
            raise RuntimeError("CS2_FRONTEND_DIR должен содержать собранный frontend/index.html.")
        application.mount("/", SPAStaticFiles(directory=config.frontend_dir, html=True))

    return application


app = create_app()

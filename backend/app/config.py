import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet


@dataclass(frozen=True)
class Config:
    data_dir: Path = Path(os.getenv("CS2_DATA_DIR", "./data")).resolve()
    max_upload_bytes: int = int(os.getenv("CS2_MAX_UPLOAD_MB", "512")) * 1024 * 1024
    parser_timeout: int = int(os.getenv("CS2_PARSER_TIMEOUT", "180"))
    retain_demos: bool = os.getenv("CS2_RETAIN_DEMOS", "false").lower() == "true"
    max_pending_imports: int = int(os.getenv("CS2_MAX_PENDING_IMPORTS", "8"))
    steam_public_url: str = (
        os.getenv("STEAM_PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://127.0.0.1:8000"
    ).rstrip("/")
    frontend_dir: Path | None = (
        Path(os.environ["CS2_FRONTEND_DIR"]).resolve() if os.getenv("CS2_FRONTEND_DIR") else None
    )
    steam_web_api_key: str = os.getenv("STEAM_WEB_API_KEY", "")
    require_steam_login: bool = os.getenv("CS2_REQUIRE_STEAM_LOGIN", "true").lower() == "true"
    cs2_secret_key: str = os.getenv("CS2_SECRET_KEY", "")
    cs2_gc_url: str = os.getenv("CS2_GC_URL", "")
    cs2_gc_secret: str = os.getenv("CS2_GC_SECRET", "")

    @property
    def steam_api_key(self):
        return self.steam_web_api_key

    def __post_init__(self):
        if self.max_pending_imports < 1:
            raise ValueError("CS2_MAX_PENDING_IMPORTS должен быть положительным числом.")
        public = urlsplit(self.steam_public_url)
        if (
            public.scheme not in ("http", "https")
            or not public.hostname
            or public.username
            or public.password
            or public.query
            or public.fragment
            or public.path not in ("", "/")
        ):
            raise ValueError(
                "STEAM_PUBLIC_URL должен быть адресом приложения без пути и параметров."
            )

    @property
    def public_origin(self):
        public = urlsplit(self.steam_public_url)
        return f"{public.scheme}://{public.netloc}"

    @property
    def secure_cookies(self):
        return urlsplit(self.steam_public_url).scheme == "https"

    def encryption_key(self):
        """Persist the Fernet key locally; never expose it through the API."""
        if self.cs2_secret_key:
            key = self.cs2_secret_key.encode("ascii")
        else:
            self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            path = self.data_dir / ".cs2-secret-key"
            try:
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                with path.open("rb") as existing:
                    key = existing.read(256).strip()
                os.chmod(path, 0o600)
            else:
                key = Fernet.generate_key()
                with os.fdopen(descriptor, "wb") as output:
                    output.write(key + b"\n")
        try:
            Fernet(key)
        except (ValueError, TypeError) as exc:
            raise ValueError("CS2_SECRET_KEY должен быть корректным ключом Fernet.") from exc
        return key

    @property
    def database(self):
        return self.data_dir / "analyzer.sqlite3"

    @property
    def uploads(self):
        return self.data_dir / "uploads"

"""Prepare a fresh persistent disk, then run the server as the analyzer user."""

import os
import sys
from pathlib import Path

storage = Path("/var/data")
storage.mkdir(parents=True, exist_ok=True, mode=0o700)
if os.getuid() == 0:
    os.chown(storage, 10001, 10001)
    os.setgroups([])
    os.setgid(10001)
    os.setuid(10001)

os.execv(
    sys.executable,
    [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        os.getenv("PORT", "8000"),
    ],
)

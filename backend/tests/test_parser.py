import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.jobs import parse_isolated


def test_native_corrupt_demo_returns_actionable_error(tmp_path):
    path = tmp_path / "corrupt.dem"
    path.write_bytes(b"PBDEMS2\x00" + b"not-valid-protobuf" * 5)
    with pytest.raises(ValueError, match="Парсер завершился"):
        parse_isolated(path, 30)
    assert not list(tmp_path.glob("cs2-parser-*"))


def test_timeout_is_reported(tmp_path, monkeypatch):
    def expire(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 1)

    monkeypatch.setattr(subprocess, "run", expire)
    with pytest.raises(ValueError, match="Превышено время"):
        parse_isolated(tmp_path / "x.dem", 1)


@pytest.mark.parametrize("payload", ["invalid JSON", "[]"])
def test_invalid_subprocess_output_is_reported(tmp_path, monkeypatch, payload):
    def finish(command, **kwargs):
        assert kwargs["shell"] is False
        assert Path(command[-2]).is_absolute()
        Path(command[-1]).write_text(payload)
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(subprocess, "run", finish)
    with pytest.raises(ValueError, match="Парсер вернул"):
        parse_isolated(tmp_path / "x.dem", 1)
    assert not list(tmp_path.glob("cs2-parser-*"))


def test_importing_parser_helpers_does_not_load_native_library():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import backend.app.parser, sys; assert 'demoparser2' not in sys.modules",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(
    not os.getenv("CS2_TEST_DEMO"), reason="Set CS2_TEST_DEMO to a real legally obtained CS2 demo"
)
def test_real_demo():
    from pathlib import Path

    result = parse_isolated(Path(os.environ["CS2_TEST_DEMO"]).resolve(), 180)
    assert result["parser_version"] == "0.42.0"
    assert len(result["players"]) >= 2
    assert len(result["rounds"]) >= 1
    assert all(p["rounds_played"] > 0 for p in result["players"])
    assert all(p["steam_id64"].isdigit() and len(p["steam_id64"]) == 17 for p in result["players"])
    assert all(
        p["effective_damage"] is None or p["effective_damage"] >= 0 for p in result["players"]
    )

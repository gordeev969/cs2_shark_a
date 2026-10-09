import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def parse_isolated(path, timeout):
    path = Path(path).resolve()
    with tempfile.TemporaryDirectory(prefix="cs2-parser-", dir=path.parent) as directory:
        output = Path(directory) / "result.json"
        env = {**os.environ, "POLARS_MAX_THREADS": "2", "RAYON_NUM_THREADS": "2"}
        try:
            result = subprocess.run(
                [sys.executable, "-m", "backend.app.parser", str(path), str(output)],
                cwd=Path(__file__).resolve().parents[2],
                env=env,
                capture_output=True,
                shell=False,
                timeout=timeout,
                text=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError(
                f"Превышено время разбора ({timeout} с). Увеличьте CS2_PARSER_TIMEOUT для большой демки."
            ) from exc
        if result.returncode != 0:
            detail = result.stderr[-700:].strip()
            raise ValueError(
                f"Парсер завершился с ошибкой ({result.returncode}). Демка повреждена или её версия не поддерживается. {detail}"
            )
        if not output.exists() or output.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("Парсер не вернул допустимый результат.")
        try:
            parsed = json.loads(output.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise ValueError("Парсер вернул повреждённый результат JSON.") from exc
        if not isinstance(parsed, dict):
            raise ValueError("Парсер вернул недопустимый формат результата.")
        return parsed


def run_job(db, config, match_id, path, parse=parse_isolated):
    db.status(match_id, "processing")
    try:
        parsed = parse(path, config.parser_timeout)
        if not parsed.get("players"):
            raise ValueError("В демке не найдены участники с достоверными SteamID64.")
        db.persist(match_id, parsed)
    except Exception as exc:
        db.status(match_id, "failed", str(exc)[:1200])
    finally:
        if not config.retain_demos:
            path.unlink(missing_ok=True)

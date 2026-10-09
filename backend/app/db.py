import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .insights import aggregate, history_insights


def now():
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            version = c.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1, 2):
                raise RuntimeError(
                    "Неподдерживаемая версия SQLite. Сохраните базу и используйте совместимую версию приложения."
                )
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript("""
                CREATE TABLE IF NOT EXISTS matches (
                    id INTEGER PRIMARY KEY, file_sha256 TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL, map_name TEXT, played_at TEXT, imported_at TEXT NOT NULL,
                    team_scores TEXT, parser_version TEXT, error TEXT, diagnostics TEXT NOT NULL DEFAULT '[]');
                CREATE TABLE IF NOT EXISTS players (
                    steam_id64 TEXT PRIMARY KEY, latest_nickname TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS match_players (
                    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
                    steam_id64 TEXT NOT NULL REFERENCES players(steam_id64),
                    nickname TEXT NOT NULL, team TEXT, kills INTEGER, deaths INTEGER, assists INTEGER,
                    rounds_played INTEGER, effective_damage REAL, hs_kills INTEGER, metrics_json TEXT NOT NULL,
                    PRIMARY KEY(match_id, steam_id64));
                CREATE INDEX IF NOT EXISTS player_history ON match_players(steam_id64, match_id);
                CREATE TABLE IF NOT EXISTS match_rounds (
                    match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
                    number INTEGER NOT NULL, winning_side INTEGER, summary_json TEXT NOT NULL,
                    PRIMARY KEY(match_id, number));
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS auth_users (
                    steam_id64 TEXT PRIMARY KEY, display_name TEXT NOT NULL,
                    avatar_url TEXT, profile_url TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    token_hash TEXT PRIMARY KEY, steam_id64 TEXT NOT NULL REFERENCES auth_users(steam_id64),
                    created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS auth_session_expiration ON auth_sessions(expires_at);
                CREATE TABLE IF NOT EXISTS auth_states (
                    state_hash TEXT PRIMARY KEY, return_to_hash TEXT NOT NULL, expires_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS auth_nonces (
                    nonce_hash TEXT PRIMARY KEY, expires_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS account_matches (
                    steam_id64 TEXT NOT NULL, match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
                    source TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(steam_id64,match_id));
                PRAGMA user_version=2;
            """)

    def reserve(self, digest):
        with self.connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO matches(file_sha256,status,imported_at) VALUES(?, 'queued', ?)",
                (digest, now()),
            )
            fresh = c.execute("SELECT changes()").fetchone()[0] == 1
            row = dict(c.execute("SELECT * FROM matches WHERE file_sha256=?", (digest,)).fetchone())
            if row["status"] == "failed":
                c.execute(
                    "UPDATE matches SET status='queued',error=NULL WHERE id=? AND status='failed'",
                    (row["id"],),
                )
                fresh = c.execute("SELECT changes()").fetchone()[0] == 1
            return row["id"], fresh

    def status(self, match_id, status, error=None):
        with self.connect() as c:
            c.execute("UPDATE matches SET status=?, error=? WHERE id=?", (status, error, match_id))

    def persist(self, match_id, parsed):
        with self.connect() as c:
            c.execute("DELETE FROM match_players WHERE match_id=?", (match_id,))
            c.execute("DELETE FROM match_rounds WHERE match_id=?", (match_id,))
            for p in parsed["players"]:
                c.execute(
                    "INSERT INTO players VALUES(?,?,?) ON CONFLICT(steam_id64) DO UPDATE SET latest_nickname=excluded.latest_nickname,updated_at=excluded.updated_at",
                    (p["steam_id64"], p["nickname"], now()),
                )
                c.execute(
                    "INSERT INTO match_players VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        match_id,
                        p["steam_id64"],
                        p["nickname"],
                        p["team"],
                        p["kills"],
                        p["deaths"],
                        p["assists"],
                        p["rounds_played"],
                        p["effective_damage"],
                        p["hs_kills"],
                        json.dumps(p),
                    ),
                )
            for r in parsed["rounds"]:
                c.execute(
                    "INSERT INTO match_rounds VALUES(?,?,?,?)",
                    (match_id, r["number"], r["winning_side"], json.dumps(r)),
                )
            c.execute(
                "UPDATE matches SET status='ready',map_name=?,played_at=?,team_scores=?,parser_version=?,diagnostics=?,error=NULL WHERE id=?",
                (
                    parsed["map_name"],
                    parsed["played_at"],
                    json.dumps(parsed["team_scores"]),
                    parsed["parser_version"],
                    json.dumps(parsed["diagnostics"]),
                    match_id,
                ),
            )

    @staticmethod
    def decode(row):
        if row is None:
            return None
        row = dict(row)
        row["team_scores"] = json.loads(row["team_scores"]) if row["team_scores"] else None
        row["diagnostics"] = json.loads(row["diagnostics"])
        return row

    def matches(self):
        with self.connect() as c:
            return [
                self.decode(r)
                for r in c.execute(
                    "SELECT m.*, (SELECT COUNT(*) FROM match_players WHERE match_id=m.id) AS player_count, (SELECT COUNT(*) FROM match_rounds WHERE match_id=m.id) AS round_count FROM matches m ORDER BY m.id DESC"
                )
            ]

    def match(self, match_id):
        with self.connect() as c:
            row = self.decode(c.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone())
            if row is None:
                return None
            row["players"] = [
                json.loads(r[0])
                for r in c.execute(
                    "SELECT metrics_json FROM match_players WHERE match_id=? ORDER BY team,kills DESC",
                    (match_id,),
                )
            ]
            row["rounds"] = [
                json.loads(r[0])
                for r in c.execute(
                    "SELECT summary_json FROM match_rounds WHERE match_id=? ORDER BY number",
                    (match_id,),
                )
            ]
            row["player_count"] = len(row["players"])
            row["round_count"] = len(row["rounds"])
            return row

    def search(self, query):
        # Casefold in Python supports Cyrillic nicknames, unlike default SQLite LIKE.
        with self.connect() as c:
            rows = c.execute(
                "SELECT p.*,COUNT(mp.match_id) AS matches FROM players p JOIN match_players mp USING(steam_id64) JOIN matches m ON m.id=mp.match_id AND m.status='ready' GROUP BY p.steam_id64 ORDER BY p.updated_at DESC"
            ).fetchall()
            return [
                dict(r)
                for r in rows
                if query.casefold() in r["latest_nickname"].casefold() or query in r["steam_id64"]
            ][:200]

    def player(self, steam):
        with self.connect() as c:
            player = c.execute("SELECT * FROM players WHERE steam_id64=?", (steam,)).fetchone()
            if player is None:
                return None
            rows = [
                dict(r)
                for r in c.execute(
                    "SELECT mp.metrics_json,m.id AS match_id,m.map_name,m.imported_at,m.played_at FROM match_players mp JOIN matches m ON m.id=mp.match_id WHERE mp.steam_id64=? AND m.status='ready' ORDER BY m.id DESC",
                    (steam,),
                )
            ]
        history = [{**json.loads(r.pop("metrics_json")), **r} for r in rows]
        maps = sorted({r["map_name"] for r in history if r["map_name"]})
        return {
            **dict(player),
            "summary": aggregate(history),
            "rolling": aggregate(history[:20]),
            "history": history,
            "insights": history_insights(history),
            "map_splits": [
                {"map_name": name, **aggregate([r for r in history if r["map_name"] == name])}
                for name in maps
                if sum(r["map_name"] == name for r in history) >= 3
            ],
        }

    def settings(self):
        with self.connect() as c:
            values = {r[0]: json.loads(r[1]) for r in c.execute("SELECT key,value FROM settings")}
        return {
            "steam_id64": values.get("steam_id64", ""),
            "compact": values.get("compact", False),
            "ai_enabled": False,
        }

    def save_settings(self, steam, compact):
        with self.connect() as c:
            for k, v in (("steam_id64", steam), ("compact", compact)):
                c.execute(
                    "INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (k, json.dumps(v)),
                )
        return self.settings()

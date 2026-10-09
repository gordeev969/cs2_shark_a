"""Export explicitly selected, publishable matches; never export account tables."""

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path

from .account_data import AccountData
from .db import Database
from .insights import match_notes


def export_snapshot(source_path, match_ids, source_url):
    if not match_ids or not source_url.startswith("https://"):
        raise ValueError("Choose public matches explicitly and provide their HTTPS source.")
    with tempfile.TemporaryDirectory() as directory:
        isolated = Database(Path(directory) / "selected.sqlite3")
        isolated.initialize()
        source = sqlite3.connect(f"file:{Path(source_path).resolve()}?mode=ro", uri=True)
        source.row_factory = sqlite3.Row
        try:
            with isolated.connect() as target:
                for match_id in dict.fromkeys(match_ids):
                    match = source.execute(
                        "SELECT * FROM matches WHERE id=? AND status='ready'", (match_id,)
                    ).fetchone()
                    if not match:
                        raise ValueError(f"Match {match_id} has not been parsed successfully.")
                    for table, rows in (
                        ("matches", [match]),
                        (
                            "players",
                            source.execute(
                                "SELECT p.* FROM players p JOIN match_players mp USING(steam_id64) "
                                "WHERE mp.match_id=?",
                                (match_id,),
                            ).fetchall(),
                        ),
                        (
                            "match_players",
                            source.execute(
                                "SELECT * FROM match_players WHERE match_id=?", (match_id,)
                            ).fetchall(),
                        ),
                        (
                            "match_rounds",
                            source.execute(
                                "SELECT * FROM match_rounds WHERE match_id=?", (match_id,)
                            ).fetchall(),
                        ),
                    ):
                        for row in rows:
                            columns = ",".join(row.keys())
                            placeholders = ",".join("?" for _ in row)
                            target.execute(
                                f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})",
                                tuple(row),
                            )
        finally:
            source.close()
        accounts = AccountData(isolated)
        players = accounts.search()
        if not players:
            raise ValueError("No participants in selected matches.")
        default = players[0]["steam_id64"]
        profiles = {p["steam_id64"]: accounts.player(p["steam_id64"]) for p in players}
        matches = {str(i): isolated.match(i) for i in dict.fromkeys(match_ids)}
        settings = {"steam_id64": default, "compact": False, "ai_enabled": False}
        dashboards = {}
        for steam in ["", *profiles]:
            briefs = accounts.matches(personal=steam)
            dashboards[steam] = {
                "match_count": len(briefs),
                "player_count": len(players),
                "queued_count": 0,
                "recent_matches": briefs[:8],
                "personal": profiles.get(steam),
                "profile": None,
                "cs2": None,
                "settings": {**settings, "steam_id64": steam},
            }
        insights = {
            key: [
                {
                    "steam_id64": p["steam_id64"],
                    "notes": match_notes(p),
                    "history": profiles[p["steam_id64"]]["insights"],
                }
                for p in match["players"]
            ]
            for key, match in matches.items()
        }
        return {
            "schema_version": 1,
            "source": {
                "url": source_url,
                "matches": [
                    {
                        "id": m["id"],
                        "sha256": m["file_sha256"],
                        "parser_version": m["parser_version"],
                    }
                    for m in matches.values()
                ],
            },
            "settings": settings,
            "players": players,
            "profiles": profiles,
            "matches": matches,
            "dashboards": dashboards,
            "insights": insights,
            "health": {
                "status": "snapshot",
                "parser_version": next(iter(matches.values()))["parser_version"],
                "max_upload_bytes": 0,
                "retain_demos": False,
                "ai_enabled": False,
            },
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--match", type=int, action="append", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = export_snapshot(args.database, args.match, args.source_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

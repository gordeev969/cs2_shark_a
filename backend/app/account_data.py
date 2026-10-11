"""Read local statistics within the signed-in account's imported matches."""

import json

from .db import now
from .insights import aggregate, history_insights


class AccountData:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def scope(owner, alias="m"):
        if not owner:
            return "1=1", ()
        return (
            f"(EXISTS (SELECT 1 FROM account_matches am WHERE am.match_id={alias}.id "
            "AND am.steam_id64=?) OR EXISTS (SELECT 1 FROM match_players own "
            f"WHERE own.match_id={alias}.id AND own.steam_id64=?))",
            (owner, owner),
        )

    def attach(self, owner, match_id, source="manual"):
        if owner:
            with self.db.connect() as c:
                c.execute(
                    "INSERT OR IGNORE INTO account_matches VALUES(?,?,?,?)",
                    (owner, match_id, source, now()),
                )

    def matches(self, owner=None, personal=None):
        scope, params = self.scope(owner)
        with self.db.connect() as c:
            rows = c.execute(
                "SELECT m.*, (SELECT COUNT(*) FROM match_players WHERE match_id=m.id) "
                "AS player_count, (SELECT COUNT(*) FROM match_rounds WHERE match_id=m.id) "
                "AS round_count, (SELECT metrics_json FROM match_players "
                "WHERE match_id=m.id AND steam_id64=?) AS personal_json FROM matches m "
                f"WHERE {scope} ORDER BY COALESCE(m.played_at,m.imported_at) DESC,m.id DESC",
                (personal or owner or "", *params),
            ).fetchall()
        result = []
        positions = self.db.queue_positions()
        for raw in rows:
            row = self.db.decode(raw)
            stats = row.pop("personal_json")
            row["personal_stats"] = json.loads(stats) if stats else None
            row["result"] = self.result(row)
            row["queue_position"] = positions.get(row["id"]) if row["status"] == "queued" else None
            result.append(row)
        return result

    @staticmethod
    def result(row):
        player, scores = row.get("personal_stats"), row.get("team_scores")
        team = player.get("team") if player else None
        if (
            team not in ("A", "B")
            or not scores
            or any(not isinstance(scores.get(t), (int, float)) for t in ("A", "B"))
        ):
            return None
        own, enemy = scores[team], scores["B" if team == "A" else "A"]
        return "win" if own > enemy else "loss" if own < enemy else "draw"

    def match(self, match_id, owner=None):
        scope, params = self.scope(owner)
        with self.db.connect() as c:
            visible = c.execute(
                f"SELECT 1 FROM matches m WHERE m.id=? AND {scope}", (match_id, *params)
            ).fetchone()
        return self.db.match(match_id) if visible else None

    def player_count(self, owner=None):
        scope, params = self.scope(owner)
        with self.db.connect() as c:
            return c.execute(
                "SELECT COUNT(DISTINCT mp.steam_id64) FROM match_players mp "
                f"JOIN matches m ON m.id=mp.match_id WHERE m.status='ready' AND {scope}",
                params,
            ).fetchone()[0]

    def search(self, query="", owner=None):
        scope, params = self.scope(owner)
        with self.db.connect() as c:
            rows = c.execute(
                "SELECT mp.steam_id64,mp.nickname AS latest_nickname,m.imported_at AS updated_at, "
                "COUNT(*) OVER (PARTITION BY mp.steam_id64) AS matches, "
                "ROW_NUMBER() OVER (PARTITION BY mp.steam_id64 ORDER BY m.id DESC) AS rank "
                "FROM match_players mp JOIN matches m ON m.id=mp.match_id "
                f"WHERE m.status='ready' AND {scope} ORDER BY m.id DESC",
                params,
            ).fetchall()
        return [
            {k: r[k] for k in ("steam_id64", "latest_nickname", "updated_at", "matches")}
            for r in rows
            if r["rank"] == 1
            and (query.casefold() in r["latest_nickname"].casefold() or query in r["steam_id64"])
        ][:200]

    def player(self, steam, owner=None, user=None):
        scope, params = self.scope(owner)
        with self.db.connect() as c:
            rows = c.execute(
                "SELECT mp.metrics_json,m.id AS match_id,m.map_name,m.imported_at,m.played_at "
                "FROM match_players mp JOIN matches m ON m.id=mp.match_id "
                f"WHERE mp.steam_id64=? AND m.status='ready' AND {scope} "
                "ORDER BY COALESCE(m.played_at,m.imported_at) DESC,m.id DESC",
                (steam, *params),
            ).fetchall()
        history = []
        for raw in rows:
            row = dict(raw)
            history.append({**json.loads(row.pop("metrics_json")), **row})
        if not history and not (user and user["steam_id64"] == steam):
            return None
        maps = sorted({r["map_name"] for r in history if r["map_name"]})
        insights = history_insights(history)
        insights["source"] = (
            "Локальная выборка; сортировка по дате игры, при её отсутствии — по времени импорта"
        )
        return {
            "steam_id64": steam,
            "latest_nickname": history[0]["nickname"] if history else user["display_name"],
            "summary": aggregate(history),
            "rolling": aggregate(history[:20]),
            "history": history,
            "insights": insights,
            "map_splits": [
                {"map_name": name, **aggregate([r for r in history if r["map_name"] == name])}
                for name in maps
                if sum(r["map_name"] == name for r in history) >= 3
            ],
        }

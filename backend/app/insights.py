"""Deterministic summaries. Source is always the local imported sample."""


def format_number_ru(value, signed=False):
    if value is None:
        return "нет данных"
    # JSON metrics remain numbers; only user-facing Russian copy uses a comma.
    value = 0 if value == 0 else value
    return format(value, "+.3f" if signed else ".3f").rstrip("0").rstrip(".").replace(".", ",")


def aggregate(rows):
    n = len(rows)

    def total(key):
        return (
            sum(r[key] for r in rows)
            if rows and all(r.get(key) is not None for r in rows)
            else None
        )

    kills, deaths, assists, rounds, hs = (
        total(key) for key in ("kills", "deaths", "assists", "rounds_played", "hs_kills")
    )
    complete = [r for r in rows if r.get("effective_damage") is not None and r.get("rounds_played")]
    damage_rounds = sum(r["rounds_played"] for r in complete)
    return {
        "matches": n,
        "kills": kills,
        "deaths": deaths,
        "assists": assists,
        "rounds_played": rounds,
        "kd": round(kills / max(deaths, 1), 3)
        if kills is not None and deaths is not None
        else None,
        "adr": round(sum(r["effective_damage"] for r in complete) / damage_rounds, 2)
        if damage_rounds
        else None,
        "adr_matches": len(complete),
        "adr_rounds": damage_rounds,
        "kr": round(kills / rounds, 3) if rounds and kills is not None else None,
        "hs_percent": (round(hs / kills * 100, 2) if kills else 0)
        if kills is not None and hs is not None
        else None,
    }


def history_insights(rows):
    n = len(rows)
    base = {
        "source": "Локальные импорты; порядок импорта, дата игры неизвестна",
        "sample_size": n,
        "minimum_matches": 10,
        "observations": [],
    }
    if n < 10:
        return {
            **base,
            "status": "insufficient",
            "message": f"Недостаточно данных для оценки аномальности: {n} из 10 матчей. Недостаточно истории для оценки стабильности.",
        }
    recent, prior = rows[:5], rows[5:15]
    a, b = aggregate(recent), aggregate(prior)
    observations = []
    for metric, label in (("adr", "ADR"), ("kd", "K/D")):
        if a[metric] is None or b[metric] is None:
            continue
        if metric == "adr" and (a["adr_matches"] != len(recent) or b["adr_matches"] != len(prior)):
            continue
        delta = round(a[metric] - b[metric], 2)
        observations.append(
            {
                "metric": metric,
                "current": a[metric],
                "baseline": b[metric],
                "delta": delta,
                "current_matches": len(recent),
                "baseline_matches": len(prior),
                "text": f"{label}: последние {len(recent)} импортов — {format_number_ru(a[metric])}, предыдущие {len(prior)} — {format_number_ru(b[metric])}; изменение {format_number_ru(delta, signed=True)}. Это описание вашей локальной выборки.",
            }
        )
    return {
        **base,
        "status": "descriptive",
        "message": "Сравнение с собственной историей. Статистическое отличие не объясняет причину изменения.",
        "observations": observations,
    }


def match_notes(player):
    notes = []
    if player.get("kills") is not None:
        notes.append(
            f"{player['kills']} убийств противников и {player['deaths']} смертей; K/D {format_number_ru(player['kd'])}. Тимкиллы и самоубийства не входят в K."
        )
    if player.get("adr") is not None:
        notes.append(
            f"ADR {format_number_ru(player['adr'])} за {player['rounds_played']} раундов: {format_number_ru(player['effective_damage'])} эффективного урона противникам, включая гранаты и огонь."
        )
    if player.get("kr") is not None:
        if player["kr"] >= 0.8:
            notes.append(
                f"Сильная сторона в этой записи: {format_number_ru(player['kr'])} убийства на раунд. Порог заметки — 0,8; это правило приложения, а не сравнение с мировой выборкой."
            )
        elif player["kr"] < 0.5:
            notes.append(
                f"Повод разобрать свои раунды: {format_number_ru(player['kr'])} убийства на раунд (порог заметки 0,5). По одной статистике нельзя определить причину."
            )
    notes.append(
        "Один матч не определяет стабильность. Рейтинг Premier, KAST, трейды и клатчи в MVP не рассчитываются."
    )
    return notes

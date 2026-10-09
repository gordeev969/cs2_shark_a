# Адаптер demoparser2

Граница native-парсера: `backend/app/parser.py`. Чистые расчёты и нормализация: `backend/app/metrics.py`. `backend/app/jobs.py` запускает новый Python процесс на каждую загрузку, ограничивает время выполнения и проверяет JSON результата. API процесс не загружает native библиотеку.

API установленной версии `0.42.0` проверен через Python introspection, документацию библиотеки и реальный replay. Используются существующие методы:

```python
DemoParser(path)
parser.list_game_events()
parser.parse_header()
parser.parse_player_info()
parser.parse_event(name, player=["team_num"], other=["is_warmup_period", "total_rounds_played"])
parser.parse_ticks(["team_num", "health", "is_connected", "team_rounds_total"], ticks=[...])
```

Доступность событий определяется из самой записи; их перечень и фактические колонки выводятся в диагностике. Обязательные события смертей/окончания раундов должны присутствовать. Отсутствие необходимых данных не заменяется предполагаемыми игровыми событиями.

| Источник | Используемые поля |
| --- | --- |
| `parse_player_info` | `steamid`, `name` |
| `round_freeze_end` / `round_start` | `tick`, `is_warmup_period`, `total_rounds_played` |
| `round_end` | те же поля, `winner` |
| `round_officially_ended` | подтверждённая временная граница до следующего раунда |
| `cs_win_panel_match` | граница завершения матча и snapshot итогового счёта |
| `player_death` | user/attacker/assister SteamID, team_num, nickname; `headshot`, tick, warmup |
| `player_hurt` | user/attacker SteamID и team_num, `dmg_health`, остаточное `health`, tick, warmup |
| `player_spawn` | подтверждение участия вошедшего игрока |
| `parse_ticks` | точный SteamID, имя, сторона 2/3, HP и connection state на начале раунда, счёт стороны в конце |

Стороны CS: T=2, CT=3. В контрольной записи `is_connected=0` означает подключённого игрока. Snapshot участия требует положительный HP, игровую сторону и этот connection state; события боя/появления могут подтвердить позднее участие. Без наблюдаемого первоначального HP позднего участника его ADR остаётся неизвестным, если точный урон восстановить нельзя.

Конец боевого интервала — tick перед `round_officially_ended` или следующим подтверждённым `round_start`. Для последнего полного раунда доступная финальная панель ограничивает интервал включительно, чтобы не потерять смерти того же tick. При отсутствии этих границ используется `round_end` с явным сообщением об ограничении. Для незавершённых/присуждённых раундов без полного старта метрики не создаются.

SteamID хранится как строка или точный integer. Float64 нельзя безопасно превратить в 64-битный SteamID: такие значения отклоняются, а не округляются. Pandas DataFrame преобразуется через JSON для удаления NaN и преобразования numpy bool без потери uint64.

Формулы, политика пропущенных значений и округления ADR описаны в README; их крайние случаи проверяются `backend/tests/test_metrics.py`. Проверка одного replay не означает поддержку всех режимов/версий; статус проверок — в `VALIDATION.md`.

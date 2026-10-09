# Private Steam Game Coordinator bridge

Получает replay URL настоящего матча через `steam-user` + `globaloffensive`. Steam OpenID и Game Authentication Code не дают SteamClient-сессию: она отдельно нужна этому сервису. Используйте аккаунт с доступом к CS2. Не запускайте одновременно игру и сервис с одной сессией: Steam может отключить один из клиентов.

Из корня репозитория:

```bash
npm --prefix gc-worker ci
npm --prefix gc-worker run login
```

CLI показывает QR-код. Отсканируйте его мобильным Steam и подтвердите вход для локального сервиса. Refresh token записывается в `.secrets/steam-refresh-token` с правами `0600`; в консоли токен не выводится. `.secrets` исключена из Git, Docker context и поставки. Если сессия истекла, повторите вход. `CS2_GC_TOKEN_FILE` переопределяет путь. Для Compose файл должен быть доступен UID 1000 сервиса; не делайте его общедоступным.

Для native-запуска экспортируйте один и тот же случайный `CS2_GC_SECRET` (минимум 24 символа) в backend и worker, задайте backend `CS2_GC_URL=http://127.0.0.1:8001`, затем:

```bash
npm --prefix gc-worker start
```

Backend также требует `STEAM_WEB_API_KEY` для обнаружения следующих матчей. При отсутствии сервиса доступен ручной импорт `.dem`.

В Docker задайте `CS2_GC_URL=http://gc-worker:8001` и запустите `docker compose --profile gc up --build -d`. У worker нет опубликованного host-port. Он имеет исходящий доступ к Steam через WebSocket. Сессия в `.secrets` доступна только локальному worker, не frontend. Возобновление сессии сохраняет обновлённый токен атомарно.

API: `POST /resolve`, `Authorization: Bearer <CS2_GC_SECRET>`, JSON `{ "sharecode": "CSGO-..." }` → `{ "demo_url": "http://replay....valve.net/730/...dem.bz2", "match_id": "uint64", "played_at": unix_seconds? }`. `GET /health` сообщает готовность GC. Сервис сверяет ответ с uint64 match ID из sharing code, последовательно выполняет запросы, ограничивает очередь/таймаут/JSON и отдаёт только Valve replay URL. Backend дополнительно проверяет адрес, ограничивает загрузку и распаковку.

`npm --prefix gc-worker test` проверяет протокол на контролируемых GC-ответах. Live Steam/GC-вход без настоящей сессии не проверяется. Реализация использует клиентские библиотеки; изменения протокола Valve могут потребовать обновления адаптера.

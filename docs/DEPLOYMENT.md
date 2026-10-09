# Развёртывание полной версии на VPS

Нужны Linux VPS, Docker Engine и Compose 2.24.4+, домен и доступ по SSH. Рекомендуется начать с 2 vCPU, 4 ГБ RAM и 30 ГБ диска: native-парсер обрабатывает большую демку в отдельном процессе. Хостинг статических страниц и Cloudflare Workers не запускают этот Python/Rust-парсер и постоянный SteamClient-сервис.

## Установка

1. Направьте DNS A-запись выбранного домена на сервер. AAAA задавайте только при рабочем IPv6. Откройте входящие TCP 80/443; другие порты приложения публиковать не нужно.
2. Загрузите архив исходников на VPS и распакуйте в отдельную папку. Установите Docker Engine и Compose по инструкции вашей Linux-системы.
3. В корне проекта выполните:

```bash
cp deploy/production.env.example .env
# Отредактируйте .env: ANALYZER_DOMAIN=ваш.домен
bash deploy/start.sh
```

Gateway Caddy обслуживает HTTPS и автоматически получает/обновляет сертификат. `compose.production.yaml` убирает локальный frontend-port и публикует только gateway на 80/443. `STEAM_PUBLIC_URL` автоматически становится `https://<ANALYZER_DOMAIN>`; вход Steam обязателен. Default `compose.yaml` по-прежнему рассчитан на localhost.

Откройте `https://<ANALYZER_DOMAIN>`. Проверки: `/api/health` отвечает 200, `/api/dashboard` без сессии — 401, сайт показывает вход Steam. Callback возвращается на этот же HTTPS-домен; пароль вводится у Steam.

## Автоматическая история CS2

Вход Steam и ручной импорт работают без server API key. Для обнаружения следующих матчей нужен `STEAM_WEB_API_KEY`. Для получения replay URL нужна SteamClient-сессия GC worker, отдельно от browser OpenID. См. [STEAM.md](STEAM.md) и [gc-worker/README.md](../gc-worker/README.md).

Получите сессию QR-авторизацией локально либо на сервере с Node.js 22+, сохраните её в `.secrets/steam-refresh-token` с правами `0600`, доступную UID 1000 worker. Настройте в `.env` одинаковый случайный `CS2_GC_SECRET` длиной от 24 символов и `CS2_GC_URL=http://gc-worker:8001`. Затем запустите:

```bash
bash deploy/start.sh --gc
```

Не размещайте Web API key, Game Authentication Code, refresh token или `.env` в исходниках. Для подключения секретов используйте среду сервера, а не сообщения в чате. Backend и GC worker не публикуют свои порты. Worker требует исходящих соединений к Steam, backend — HTTPS Steam API и загрузку Valve replay.

## Обновление и сохранность

После загрузки новых исходников повторите `bash deploy/start.sh` (или с `--gc`). Именованный volume `analyzer-data` сохраняет SQLite и ключ шифрования; Caddy volumes — сертификаты. Не выполняйте `docker compose down -v`, если нужно сохранить данные.

Для резервной копии остановите backend, скопируйте **всю** папку `/data` из его контейнера, затем запустите backend снова. Копия должна включать SQLite и `.cs2-secret-key`; храните её приватно. SteamClient-сессия находится отдельно в `.secrets` и тоже требует приватного хранения.

```bash
docker compose -f compose.yaml -f compose.production.yaml ps
docker compose -f compose.yaml -f compose.production.yaml logs --tail=50 gateway backend
```

В текущей рабочей среде проверена конфигурация Compose и работа приложения в Docker. Публичный VPS и домен пока не подключены; публичная ссылка и выпуск настоящего TLS-сертификата не заявляются. Live Steam/GC проверяется после подключения настоящего аккаунта.

# Простой запуск на Render

Для запуска этой версии без администрирования VPS подготовлены `render.yaml` и `deploy/Dockerfile.render`. Один Docker Web Service обслуживает React и FastAPI на одном HTTPS-домене. Native-парсер работает в том же сервисе, SQLite и ключ шифрования сохраняются на Persistent Disk.

## Что нужно сделать в аккаунте

1. Зарегистрируйтесь в [Render](https://dashboard.render.com/) и разместите распакованные исходники в **приватном GitHub-репозитории**. В корне репозитория должны находиться `render.yaml`, `backend/`, `frontend/`, `deploy/`. Не загружайте `.env`, `.secrets`, данные, демки или `node_modules`.
2. В Render выберите **New → Blueprint**, подключите этот репозиторий и выберите `render.yaml`. Конфигурация предлагает Web Service `standard` и диск 10 ГБ. Проверьте текущую цену в Render перед созданием: сервис и диск платные. Free-тариф не сохраняет эту SQLite и имеет недостаточно памяти для больших демок.
3. После успешного deploy откройте предоставленный адрес `https://…onrender.com`. HTTPS и адрес Steam callback определяются автоматически через `RENDER_EXTERNAL_URL`. Вручную `STEAM_PUBLIC_URL` задавать не нужно. При собственном домене задайте его полный HTTPS-адрес в `STEAM_PUBLIC_URL`.

Установка зависит от подключения GitHub и аккаунта Render: из текущей среды доступа к ним для deploy нет. Оплата и регистрация выполняются владельцем аккаунта. Подготовка файлов и локальная проверка image не означают, что Render-сервис уже создан.

## Что работает сразу

Вход Steam, ручной импорт настоящей `.dem`, статистика матчей и игроков, личный дашборд, история в SQLite. Без server Steam Web API key вместо публичного Steam-ника отображается SteamID. Runtime использует непривилегированного пользователя: launcher только подготавливает mount диска и затем сбрасывает root.

После деплоя проверьте `/api/health`, вход Steam, импорт своей демки и сохранение истории после restart сервиса. Большая демка расходует оперативную память и временный диск; при timeout измените `CS2_PARSER_TIMEOUT`, при превышении памяти — размер instance. Render Persistent Disk допускает только один instance, что соответствует очереди и SQLite этого MVP.

## Автоматическая загрузка матчей

Это отдельное подключение. Добавьте `STEAM_WEB_API_KEY` в Environment сервиса, получите SteamClient-сессию для GC worker через QR, разверните worker отдельным Private Service и настройте `CS2_GC_URL`/общий `CS2_GC_SECRET`. Worker запускается из `gc-worker/Dockerfile`, хранит обновляемую сессию приватно и имеет исходящий доступ к Steam. Дополнительный worker также требует тариф и настройку хранения сессии.

Game Authentication Code и sharing code пользователь вводит в интерфейсе после Steam-входа. Они не заменяют server API key или GC-сессию. Пока worker не настроен, UI сообщает об этом, и работает ручной импорт. Полная схема: [STEAM.md](STEAM.md) и [gc-worker/README.md](../gc-worker/README.md).

Документация хостинга: [Blueprint](https://render.com/docs/blueprint-spec), [Persistent Disk](https://render.com/docs/disks), [RENDER_EXTERNAL_URL](https://render.com/docs/environment-variables).

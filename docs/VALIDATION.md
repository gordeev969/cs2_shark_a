# Проверка реализации — 9 октября 2026

Это отчёт о выполненных проверках, а не подтверждение всех версий CS2 и режимов Premier.

## Автоматические проверки

| Проверка | Результат |
| --- | --- |
| `CS2_TEST_DEMO=… make check` | Успешно: Ruff, тесты, TypeScript, Vite production build |
| Backend pytest с настоящей демкой | **98 passed**, включая native-parser через синхронизацию |
| Frontend Vitest | **8 passed**: FSD границы импортов и nullable/русское форматирование |
| ESLint, включая FSD | Успешно |
| Prettier и Ruff format | Успешно |
| Playwright Chromium | **5 passed**: навигация/мобильный экран; реальный импорт, все участники, свой профиль, поиск, настройки и дедупликация; повреждённый файл; Steam guard и CS2 connect/sync/logout с mock responses |
| Docker build всех трёх сервисов | Успешно, backend, frontend (production build внутри образа), GC worker |
| Docker Compose runtime | Backend healthy; frontend опубликован только на localhost (8000 по умолчанию, 18000 в изолированной проверке); у backend/GC нет host-port |
| Production UI через Nginx | Новая сборка: login guard, 401 private API, настоящий Steam redirect, мобильный экран; JavaScript ошибок нет. Отчёт/профиль также проверены браузерным E2E на настоящей демке |
| Обновление контейнера и SQLite v1→v2 | Матч и статистика сохранились в volume, schema v2, backend healthy |
| Node GC worker tests | **7 passed**: sharing code/uint64, matchList correlation, сериализация, таймауты, whitelist URL, HTTP auth и private token file |

Backend проверен на Python 3.12; frontend — Node.js 24, контейнерная сборка — Node.js 22. Docker Engine 28.4.0. Парсер закреплён на `demoparser2 0.42.0`.

Один warning тестовой зависимости: Starlette сообщает о будущем переходе TestClient с httpx на httpx2. Это предупреждение, тесты проходят. В обычном запуске приложения TestClient не используется.

## Настоящий контрольный replay

Источник: публичный [test_demo.dem проекта demoparser2](https://github.com/LaihoE/demoparser/blob/main/src/parser/test_demo.dem). Демо не включено в исходники или архив приложения; production UI не использует синтетические данные.

SHA-256 файла:

```text
84a1a4191302bdd2a3bbb5a727842093744b1fb1a228aeec630369e44b622cb2
```

Фактический результат импорта:

- карта `de_mirage`, **10 участников** с точными SteamID64;
- **9 полных игровых раундов**, разминка исключена;
- подтверждённый итоговый счёт **A 8 : B 2**; surrender добавляет присуждённый раунд без полного боевого интервала;
- **64 убийства противников и 64 смерти**, ADR доступен всем 10 участникам;
- K, D и headshot kills каждого участника независимо сверены с исходными `player_death` событиями демопарсера;
- убийства в промежутке после `round_end` и до `round_officially_ended` учтены; следующий buytime и события после финальной панели исключены;
- повторная загрузка возвращает тот же match ID с `duplicate=true`, в базе один матч, в профиле один наблюдаемый матч;
- история правильно сообщает о недостаточной выборке; никаких античит-вердиктов;
- удаление временной демки после разбора, поиск, личный SteamID и настройки проверены;
- браузерный сценарий не делает внешних запросов; неизвестные Host/Origin отклоняются.

Результаты не сверялись с отдельным игровым табло: доступен бинарный replay и native-события, а не независимая эталонная статистика стороннего сервиса. ADR проверен по реконструкции целочисленного HP и синтетическим регрессиям, с явно описанной политикой округления.

## Какие настоящие демки нужны ещё

Для окончательной приёмки на вашей игре нужен актуальный **CS2 Premier `.dem`** и его итоговое табло. Сравните K/D/A/HS, количество раундов и счёт; выберите себя в профиле и повторите импорт.

Смена сторон и 30 раундов проверены синтетически. Настоящие записи с овертаймом, переподключениями, сменой состава и другими версиями CS2 нужны для проверки специфики этих режимов. Полнота любой нестандартной или обрезанной записи не предполагается: недоступные метрики имеют `null` и причины в диагностике.

Optional AI не реализован: приложение и аналитика работают без ключей и внешней модели.

## Повторить проверки

Основные команды находятся в [README](../README.md). Для проверки настоящего replay передайте свой путь через `CS2_TEST_DEMO`. Без этого переменная интеграционного теста отсутствует, и он явно пропускается.

Для точной контрольной записи выше можно дополнительно указать `CS2_UPSTREAM_FIXTURE=1` при запуске Playwright: тогда проверяются 10 участников, 9 полных раундов, счёт 8:2 и суммы 64 K / 64 D. Этот флаг применяется только к тестам, не к приложению.

Скриншоты production интерфейса на контрольном replay: [desktop](screenshots/match-desktop.png), [mobile](screenshots/match-mobile.png). Показанные значения вычислены из настоящей загруженной записи.

## Steam-этап и его пределы

`make check` выполнен с настоящей контрольной демкой: **98 backend + 8 frontend + 7 GC tests**, все проверки форматирования/FSD/TypeScript и production build прошли. Native replay также прошёл путь через bounded BZip2 downloader → isolated parser → SQLite → account statistics; ответы Steam/GC/download в этом тесте контролируемые, содержимое `.dem` настоящее.

Все **5 Playwright-сценариев прошли**, включая реальный импорт и mock Steam UI. Реальный OpenID endpoint и формирование redirect проверены в собранном Docker приложении; successful live login не выполнялся. Нужны ваш Steam-аккаунт, Game Authentication Code, sharing code, server Web API key и SteamClient-сессия GC worker. Отсутствующие секреты не обходились тестовым пользователем в production.

Скриншоты: [дашборд](screenshots/dashboard-desktop.png), [мобильный дашборд](screenshots/dashboard-mobile.png), [Steam-вход](screenshots/steam-login.png). Дашборд снят с действующего native frontend/backend в автономном режиме на настоящей локальной записи; вход — с новой Docker production-сборки. Статистика не синтетическая; live Steam-авторизация этими изображениями не подтверждается.

## Подготовка хостинга Render

Добавлены `render.yaml`, single-service Docker image и раздача собранного React frontend самим API. `RENDER_EXTERNAL_URL` определяет HTTPS callback без ручного адреса. SQLite и ключ шифрования размещаются на Persistent Disk; сервер после подготовки mount работает с UID 10001.

Проверены: Docker build (с настоящим frontend production build), старт image с пустым volume, выдача assets/SPA routes, 401 закрытого API, автоматический адрес Steam redirect и Secure cookie. Backend после добавления hosting tests: **99 passed, 2 skipped** (опциональные тесты настоящей демки без переменной `CS2_TEST_DEMO`); TypeScript прошёл. Предыдущая проверка native parser и BZip2 pipeline с настоящей демкой остаётся актуальной — числовая логика не менялась.

Также прошли syntax check `deploy/start.sh` и Compose configuration checks публичного VPS-варианта с/без GC profile. Render account/GitHub repository не подключены: удалённый deploy, публичный URL и выпуск настоящего TLS не выполнялись.

## GitHub Pages export

Readonly snapshot: 101 backend tests passed (2 optional real-demo tests skipped in this run), 11 frontend tests and 7 GC tests passed. Lint, formatting, typecheck and Pages build passed. Snapshot tests verify selection isolation, exclusion of sessions/settings, real 64K/64D totals, unknown game date and insufficient sample. Browser smoke checks use the actual static build without API.

# Бесплатный просмотр на GitHub Pages

GitHub Pages размещает статические файлы. Здесь работает отдельная сборка с режимом просмотра: дашборд, отчёт матча, профили, поиск игроков и выбор участника для обзора. Steam/OpenID, Game Authentication Code, загрузка демок, Python-парсер и SQLite работают в полной серверной версии — см. [RENDER.md](RENDER.md).

В `frontend/public/snapshot.json` лежит результат реального разбора публичной [демки demoparser2](https://github.com/LaihoE/demoparser/blob/main/src/parser/test_demo.dem): SHA256 `84a1a4191302bdd2a3bbb5a727842093744b1fb1a228aeec630369e44b622cb2`, Mirage, 10 игроков, 9 завершённых раундов, суммарно 64 убийства и 64 смерти. Подтверждённый итоговый счёт 8:2 включает присуждённый раунд при сдаче; сам присуждённый раунд в знаменатель ADR не включён. Дата игры неизвестна. Одного матча недостаточно для анализа изменений и разбивки по картам, поэтому интерфейс показывает это ограничение.

Численные показатели и наблюдения экспортированы сервером. Браузер не пересчитывает игровые метрики. Выбранный игрок и компактный вид сохраняются в localStorage, без подтверждения принадлежности Steam-аккаунта. База, демка, ключи и сессии не публикуются.

## Включение

В публичном репозитории откройте **Settings → Pages → Build and deployment → Source → GitHub Actions**. Workflow `.github/workflows/pages.yml` публикует сайт после push в main. При первом включении после загрузки кода можно выбрать **Actions → Publish dashboard to GitHub Pages → Run workflow** или перезапустить последний запуск.

Адрес для этого репозитория: `https://gordeev969.github.io/cs2_shark_a/`. Маршруты используют hash (`/#/matches/1`), поэтому прямые ссылки и обновление страницы не требуют сервера.

## Локальная сборка

```bash
npm --prefix frontend ci
VITE_APP_MODE=snapshot VITE_ROUTER_MODE=hash VITE_BASE_PATH=/cs2_shark_a/ npm --prefix frontend run build
```

Без `VITE_APP_MODE=snapshot` приложение использует настоящий API. Экспорт не подставляется в обычные серверные маршруты.

## Повторный экспорт

Публикуйте только данные, на публикацию которых у вас есть право. Выбор матчей обязателен; остальные матчи, аккаунты и ключи исключаются из временной базы перед расчётом профилей.

```bash
PYTHONPATH=backend .venv/bin/python -m app.export_snapshot \
  --database /path/to/analyzer.sqlite3 --match 1 \
  --source-url https://example.com/public-demo-source \
  --output frontend/public/snapshot.json
npm --prefix frontend run format
```

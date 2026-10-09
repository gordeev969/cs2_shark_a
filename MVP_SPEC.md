# CS2 Premier Analyzer — MVP specification

Version: 0.1 (personal/local prototype)
Language: Russian UI. Audience: one person. Platform: desktop web browser on the same machine.

## 1. Goal

Build a local web application that imports Counter-Strike 2 Premier `.dem` replays, computes reliable per-match statistics for all available participants, creates locally searchable player profiles from **already imported replays**, shows the owner's progress, and highlights statistical outliers without alleging cheating.

**Success criterion:** With one valid CS2 Premier demo and no API keys, the user can start the app, upload the demo, see the scoreboard of the match and all participants, select their own SteamID, open any participant's locally accumulated profile, and receive a deterministic explanation of strong/weak points. Re-importing the same demo must not duplicate the match.

## 2. Explicit non-goals for MVP

- No public website, registration, authentication through Steam, subscription, payments, ads, sharing or search indexing.
- No gathering arbitrary strangers' full Steam histories by their SteamID: profiles only contain matches imported into this local database.
- No automated Premier/Steam sync in the first iteration, no scraping and no reliance on undocumented Valve APIs.
- No cheat verdict, cheat probability, player ban list, public “suspicious person” labels, or reporting players to platforms.
- No 2D replay/tick-by-tick aim tracking, video clips, match prediction or MCP server.
- No fabricated Premier CS Rating if the replay does not reliably contain it.

## 3. User stories / screens

### Dashboard `/`
- Recently imported matches, number of imported matches and players, quick personal rolling average (K/D and ADR when available).
- Prominent `Загрузить демку` action and empty state.
- Personal SteamID64 setting for highlighting own stats; optional until entered.

### Import `/import`
- Upload one `.dem` file, size check and helpful error on unsupported/corrupt data.
- Show `queued`, `processing`, `ready`, `failed` with useful error messages.
- Avoid duplicate import by SHA-256 of uploaded bytes. Store only a copy of the demo when needed; retention configurable. Protect against path traversal and oversized files.
- MVP may accept only uncompressed `.dem` to simplify verification; explain clearly how to provide one. Support for `.bz2`/`.zip` is a stretch goal with safe extraction.

### Match details `/matches/:id`
- Map, match result/team scores **only when reliable**; otherwise render `нет данных`.
- Scoreboard for all participants parsed from that demo. Columns: player, team, K, D, A, K/D, ADR, HS%, K/R. Show additional metrics only after their formulas are verified.
- Click any player to open `/players/:steamId`.
- Player-facing notes: strong metrics, opportunities for improvement, contextual caveats.
- Clear marker that all statistics were computed from the imported replay.

### Players `/players` and `/players/:steamId`
- Search **within the imported database** by nickname / SteamID64.
- Player profile with totals and trends over matches in this database, recent games, map splits when sample permits, and sample size.
- If only one match is available, show `Недостаточно истории для оценки стабильности`, not global conclusions.
- Do not attempt to resolve public Steam profile and fetch remote match history without a user-initiated integration in a later milestone.

### Settings `/settings`
- Personal SteamID64 and display preferences.
- Optional AI integration: disabled by default; provider base URL, model and API key via environment variables rather than storing secret in browser.
- Toggle for sending anonymized aggregate metrics to an external AI provider; default OFF.

## 4. Definitions, precision and missing data

All displayed metric formulas must be documented in code and README, tested on synthetic fixtures, and derived from available replay events. No guessed events.

- K = enemy kills, excluding teamkills and suicides; D = all player deaths; A = valid in-game assists.
- K/D = K / max(D, 1), but also show K and D to avoid misinterpretation.
- HS% = headshot enemy kills / enemy kills * 100. When K=0, show 0% or `—` consistently and document the policy.
- K/R = enemy kills / rounds participated.
- ADR = **effective health damage against enemies** divided by rounds participated, excluding friendly damage and overkill where the available event fields make it possible; if event fields are incomplete, return `null`/`—`, never silently substitute weapon damage or invent an amount. Document how grenades and utility are counted.
- Avoid warmup rounds. Handle side swaps and overtime if available; use parsed round/team data rather than assuming all matches have 24 rounds.
- Future: KAST / entry duels / trades / clutch require separately verified definitions and fixtures; do **not** output them as if reliable in v0.1.
- Round and team detection may vary by replay version. Surface missing-value reasons and parser diagnostics in a developer panel/log.
- SteamID64 from parsed participant data is the stable local key. Nicknames can change, must not be used as identities.

## 5. Anomaly / strengths engine

### Deterministic first; no anti-cheat judgement

- Compute observations, not verdicts: high damage, unusual K/D, changes in last matches, map-specific trends, high impact for own play.
- Prefer comparisons to **the same player's own imported history**; for any metric show baseline window, sample size and source.
- A player with fewer than 10 locally observed matches is labeled `Недостаточно данных для оценки аномальности` (threshold adjustable after validation).
- Do not compare against an invented global CS Rating/ELO population. A future validated reference cohort could be added as a separate dataset.
- For eligible players, first provide descriptive deviations rather than a single numerical “cheat score”; e.g. current 5-game ADR versus prior 10-game ADR, delta, sample count.
- No numerical probability of cheating, no label `читер`/`вероятный читер`.
- Separate **strengths/weaknesses** in a match from **long-term statistical anomaly**; they are different use cases.

### Optional LLM layer

- Default to deterministic template-based notes so the app works with no API key/network.
- Optional OpenAI-compatible inference endpoint to support user-selected DeepSeek or Qwen model; keep provider/model configurable, do not hardcode current model names.
- Send only calculated numeric summaries and generic pseudonymous IDs, not raw demos, SteamID, nickname, or secrets. Explicit opt-in before any network request.
- Enforce strict structured output schema, timeout, token/output limits, and fallback to deterministic summary when provider unavailable.
- LLM must not invent statistics or imply conclusive cheat detection. Show numbers alongside every substantive explanation.

## 6. Technical architecture

Suggested starter stack:
- Frontend: React + TypeScript + Vite + Tailwind CSS; charts via Recharts.
- API: FastAPI + Python 3.11+.
- Parser: `demoparser2` (validate available fields/version before implementation).
- Persistence: SQLite (SQLAlchemy/SQLModel acceptable), migrations via Alembic optional for v0.1 but schema changes must be intentional.
- Local orchestration: Docker Compose, or fully documented commands for direct local startup if docker issues arise.
- No external cloud dependencies for baseline functionality.
- Default bind `127.0.0.1` on host, never 0.0.0.0 accessible publicly unless explicitly configured.

Pipeline:
`file upload -> SHA-256 dedup -> parse job -> normalized events -> validated metrics -> SQLite -> UI -> rules-based notes -> optional AI explanations`.

Suggested schema:
- `matches(id, file_sha256 UNIQUE, map_name, played_at nullable, status, team_scores nullable, parser_version, error)`
- `players(steam_id64 PRIMARY KEY, latest_nickname, updated_at)`
- `match_players(match_id, steam_id64, team context, K, D, A, rounds_played, effective_damage nullable, ADR nullable, HS_kills, ...; UNIQUE(match_id, steam_id64))`
- `match_rounds(match_id, number, winning_team nullable, summary_json)`
- `settings(key, value)` (exclude API keys)
- `parse_jobs(id, match_id, status, error, timestamps)` if not covered directly by `matches`.

Suggested API:
- `GET /api/health`
- `POST /api/matches/import` (multipart upload)
- `GET /api/matches` / `GET /api/matches/{id}`
- `GET /api/players?query=...` / `GET /api/players/{steam_id64}`
- `GET /api/dashboard?steam_id64=...`
- `GET /api/matches/{id}/insights?steam_id64=...`
- `POST /api/matches/{id}/ai-insights` (opt-in only; optional milestone)

## 7. Implementation stages

1. Project skeleton, Docker Compose, SQLite, API health and responsive Russian-language dark UI shell.
2. DEM importer with SHA-256 dedup, robust parser adapter, unit tests and structured error handling.
3. Match scoreboard, match list, player pages, player search and personal dashboard.
4. Deterministic strengths/weaknesses and history-based anomaly descriptions with sample checks.
5. Optional AI explanation integration with strict opt-in and local fallback.
6. Tests, fixtures, README, security and usability review.

Implement each as a working vertical slice; do not build large features before parser accuracy is validated.

## 8. Acceptance criteria

- Single command/documented steps start app locally without paid credentials.
- Upload a valid supported CS2 demo -> parse -> show match report, all parsed participants and K/D, K, D, A, HS%, rounds and ADR where valid.
- No silent wrong totals; missing/unavailable data is indicated clearly.
- Re-upload identical demo -> no duplicate match/players stats.
- One player appearing in multiple imported matches has one profile with correct aggregation and trends.
- Less than 10 observed matches -> no anomaly verdict/index, explicitly insufficient history.
- With AI disabled or failing, user still gets deterministic insights and fully working app.
- Invalid DEM, big upload and parse errors handled gracefully; nothing outside designated upload directory accessed.
- Tests exist for metric calculations, deduplication, player aggregation and insufficient-data logic; README states how to run them and lists any tests blocked by the absence of a real legal sample demo.
- Russian labels and dates/number formats; no fabricated figures in production UI.

## 9. Future (not in this task)

- Automatic Premier match sync from explicitly supplied Steam Match Sharing Code + authentication code if eligible, compliant and documented.
- Validated historical cohort statistics to compare players by CS Rating.
- Map heatmaps and grenade impact.
- MCP conversational queries.
- Public service / compliance / monetization (separate future project).

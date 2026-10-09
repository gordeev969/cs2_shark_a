# Task for Codex: Build a local CS2 Premier Analyzer MVP

You are implementing a complete, runnable, **private/local-only** prototype, not a hosted product. Read `MVP_SPEC.md` and `AGENTS.md` first. Do not replace the requested work with a mockup-only page.

## Objective

Build the smallest end-to-end app that accepts a real CS2 `.dem` file, parses it with `demoparser2`, stores normalized match/player stats in SQLite, and displays a polished Russian-language dark dashboard with a match list, match scoreboard, player profiles, own-player progress, and deterministic analytical notes. All 10 participants should be displayed if actually present in the demo data.

## Constraints

- Start from the existing repository content; if the repository is empty, initialize it. Preserve unrelated existing files.
- Work incrementally. Prioritize real parsing and correct data models over visual polish or artificial numbers.
- No login, Steam auth, public pages, payments, web scraping, Steam auto-sync, anti-cheat verdicts, MCP or paid API required for initial success.
- Use React + TypeScript + Vite + Tailwind for UI; FastAPI + Python + demoparser2 + SQLite for backend; local run via Docker Compose and/or a documented development setup. Explain any justified deviations before implementing them.
- Keep the UI in Russian; make it responsive and clean.
- Absolutely no placeholder player statistics pretending to be from an uploaded match. A separate explicitly labeled demo fixture mode is acceptable for UI development, but production routes must use persisted parsed data.
- Never guess KAST, ADR or a Premier rank if the required fields are unavailable. Return null and show “нет данных”.
- Default to local-only network binding and no external analytics/telemetry. API keys must only come from environment variables; no secrets in Git.
- Anomaly insights MUST describe unusual *statistics*, NOT imply cheating. Under 10 observed matches per player, report insufficient data. Do not invent a global comparison dataset.

## Plan of work

1. Inspect the repository, report state and a short implementation plan. Add `.env.example`, `README.md`, lint/test commands, and compose file.
2. Build parser adapter isolated from endpoints. Discover actual supported demoparser2 event names/fields via the installed version, normalize events, document assumptions. Create synthetic fixtures for metric calculations.
3. Implement upload endpoint, hashing, deduplication, safe temp storage, job status/errors, SQLite persistence, and tests.
4. Implement match list/detail UI; scoreboard with K/D, ADR when accurate, HS%, kills, deaths, assists, rounds played; player navigation.
5. Implement player search within local database, local profiles and rolling personal summary/trends. Allow configuring my SteamID64 locally.
6. Implement deterministic analytical insights and sample-aware stat-anomaly observations; make uncertainty explicit.
7. Optional stretch goal only after stages 1–6 work: opt-in configurable DeepSeek/Qwen through OpenAI-compatible API, strict structured summary output and deterministic fallback.
8. Run formatters, typechecking, unit tests and any available build/checks. Report exactly what passed and what remains unverified; in particular distinguish synthetic fixtures from real CS2 demo validation.

## Deliverables

- Working source code in repository with `frontend/`, `backend/` (or an equivalently understandable layout).
- `README.md` with local instructions, obtaining a `.dem` file legally, supported formats, limitations and debugging.
- Automated tests for parsing-normalization/metric helpers, deduplication, multi-match player stats and insights sample thresholds.
- Screens: Dashboard, Import, Matches, Match Details, Player Profile, Settings.
- Stable error/empty states, no misleading figures.

## Definition of done

A developer can clone and follow `README.md`, run the app without an AI key, import a valid demo, see all parsed participants' statistics, click one player to see profile history, and reimport without duplicate entries. On no historical sample, anomaly sections accurately say there is insufficient data. The code is tested, parsers are isolated and failures are clearly explained.

Please implement now, not just write a plan; if lacking a real replay test file, implement/tests with synthetic fixtures and clearly request one **only for end-to-end verification**. Do not block progress asking about optional preferences.

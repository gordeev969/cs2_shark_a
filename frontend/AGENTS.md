# Frontend conventions

Follow Feature-Sliced Design and `../docs/FRONTEND_ARCHITECTURE.md`.

- Dependencies point down: app → pages → widgets → features → entities → shared.
- Different slices in the same layer do not import each other. Compose them above.
- Consumers import a slice through its `index.ts` public API. Internal imports stay relative.
- Use `ui`, `model`, `api`, and `lib` segments only where there is actual code.
- Shared API contracts describe server JSON; numerical game calculations stay in backend.
- Preserve nullable metrics and their reasons. Never substitute fixture data into production routes.
- Keep user-facing copy Russian, dates and numbers localized, and interactive controls accessible.
- Run `npm run format:check`, `npm run lint`, `npm test`, and `npm run build` after changes.
- Browser tests: `npm run test:e2e`; the real import scenario requires `CS2_TEST_DEMO`.

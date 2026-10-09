# Repository agent instructions

Project: CS2 Premier Analyzer, single-user local MVP.

1. Follow `MVP_SPEC.md` and `CODEX_TASK.md` as primary requirements.
2. Prioritize correct CS2 demo parsing, per-round player statistics, deterministic insight quality, and safe local data storage. No fabricated game facts.
3. The app must work with no AI model or API keys. AI is an optional enhancement and must never be the source of truth for numerical metrics.
4. Never call any player a cheater or generate a probability of cheating. Restrict anomaly language to mathematical observations with evidence and sample size.
5. Protect uploaded files: validate extension/size, constrain paths, avoid unsafe archive extraction, hash for idempotency, and handle parser crashes with user-visible errors.
6. Default local binding only. Never commit credentials or send player identifiers to external models by default.
7. Use Russian UI copy. Keep README and test instructions clear.
8. Before marking done, run automated unit tests, frontend typecheck/build, API smoke checks if possible and report results honestly.
9. Preserve unrelated repository code. Do not perform destructive operations without clear necessity.

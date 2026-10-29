# DineMate

Campus canteen seat-availability platform. Full plan: docs/DineMate_Development_Plan.md.
Solo developer. Work one phase at a time from docs/ROADMAP.md and tick items off there as they land.

## Apps

- apps/student — installable PWA for students. Keep it simple.
- apps/console — staff console (admin, canteen manager, shop manager, safety officer).
- packages/ui — shared tokens and components (StatusPill, Ring, CanteenArt, HazardFrame, icons).
- packages/api-client — hand-written API types, TanStack Query hooks, and a client that calls the real API when `configureApi({ baseUrl })` is set, else a labelled sample "server". `src/contract.ts` makes typecheck fail if the types drift from the generated OpenAPI types in `src/generated/`.
- services/api — FastAPI + PostgreSQL, managed with uv (Python 3.12). Layout: `app/models` (SQLAlchemy), `app/services` (pure rules: occupancy, shop_status, meal_status; `views.py` loads DB → schemas), `app/routers`, `app/schemas.py`, `app/seed.py`, `app/sim.py`. Alembic migrations in `alembic/versions`.
- infra/docker-compose.yml — Postgres 16 + API (migrates and seeds an empty DB on start) + occupancy simulator. Copy infra/.env.example to infra/.env to override defaults.
- Crowding rules: `app/services/crowding.py` (pure state machine) + `app/services/rules.py` (DB, runs every 15 s via `app/jobs.py`; set DINEMATE_RULES_INTERVAL_S=0 to stop). Staff endpoints (`/alerts`, `/console/overview`) need `Authorization: Bearer $DINEMATE_STAFF_TOKEN` until Phase 4.
- Still on sample data: safety events (Phase 5) and forecasts (Phase 6).
- services/vision — separate uv project (YOLO11n + ByteTrack, CPU PyTorch). `vision/counting.py` holds the pure zone-counting rules (unit-tested without YOLO); `worker.py` posts counts only, never stores frames; `zone_tool.py` draws layouts; `studio.py` draws zones then plays a video with live counts (offline, scaled to the screen); `validate.py` compares estimates with hand counts. See services/vision/README.md. Videos live in git-ignored `data/videos/`.
- Devices authenticate with `Authorization: Device <token>`; register cameras with `uv run python -m app.devices_cli register` (services/api).

## Rules

- Seat numbers are estimates: always "about N" / "~N", never cache occupancy in the service worker.
- Stale data (> 2 min) is grey; unavailable (> 10 min) shows no number.
- Safety module stays separate (own router, tables, WebSocket channel). Simulated events are always labelled.
- Do not invent real NSBM shop names, prices, hours, exits or fire-system APIs. Use labelled sample data.
- Time zone: Asia/Colombo for display; store UTC timestamptz. UI reads "now" from the server clock (`useServerNow`), never the device clock.

## Conventions

- TypeScript strict; Python 3.12 with type hints; ruff (lint + black-compatible format); eslint + prettier.
- Clean code without inline comments.
- Conventional commits. Never add a "Co-Authored-By" line to commit messages.
- One branch per roadmap phase (`phase-<n>-<slug>`, from up-to-date main). Merge to main only when the owner says so.
- Every PR: tests pass, lint clean, no secrets committed.

## Commands

- pnpm install
- pnpm dev:student / pnpm dev:console (sample data) — add `:api` (dev:student:api, dev:console:api) to use the real API on :8000
- pnpm typecheck / pnpm build / pnpm lint / pnpm format
- pnpm stack:up / pnpm stack:down — Postgres + API + simulator in Docker (API on :8000)
- pnpm dev:api — API with reload against a local or Docker Postgres
- pnpm test:api — pytest; integration tests use `dinemate_test` on localhost:5432 and skip if Postgres is down (set DINEMATE_REQUIRE_DB_TESTS=1 to fail instead)
- pnpm api:types — after changing API schemas: re-export openapi.json and regenerate TS types (CI checks both)
- In services/api: `uv run alembic revision --autogenerate -m "..."`, `uv run alembic upgrade head`, `uv run python -m app.seed --reset`

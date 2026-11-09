# DineMate

Campus canteen seat-availability platform. Full plan: docs/DineMate_Development_Plan.md.
Solo developer. Work one phase at a time from docs/ROADMAP.md and tick items off there as they land.

## Apps

- apps/student — installable PWA for students. Keep it simple.
- apps/console — staff console (admin, canteen manager, shop manager, safety officer).
- packages/ui — shared tokens and components (StatusPill, SeatStrip, BrandMark, TableScene, CanteenArt, FoodArt, HazardFrame, icons). Look (v4, see Figma "Redesign v4"): forest #1F3D2B, sand #E8DCC4, purple #8B5CF6 for live and recommended only; Bricolage Grotesque for headings and big numbers, DM Sans for text, JetBrains Mono for clocks and prices. Sample pictures are WebP files in `src/art`, mapped in `src/photos.ts` (food by item name with a dish-category fallback, shops by ID then kind, canteens by ID). PNG masters, prompts and the manifest live in `docs/newImages` (not loaded by the apps).
- packages/api-client — hand-written API types, TanStack Query hooks, and a client that calls the real API when `configureApi({ baseUrl })` is set, else a labelled sample "server". `src/contract.ts` makes typecheck fail if the types drift from the generated OpenAPI types in `src/generated/`.
- services/api — FastAPI + PostgreSQL, managed with uv (Python 3.12). Layout: `app/models` (SQLAlchemy), `app/services` (pure rules: occupancy, shop_status, meal_status; `views.py` loads DB → schemas), `app/routers`, `app/schemas.py`, `app/seed.py`, `app/sim.py`. Alembic migrations in `alembic/versions`.
- infra/docker-compose.yml — Postgres 16 + API (migrates and seeds an empty DB on start) + occupancy simulator. Copy infra/.env.example to infra/.env to override defaults.
- Crowding rules: `app/services/crowding.py` (pure state machine) + `app/services/rules.py` (DB, runs every 15 s via `app/jobs.py`; set DINEMATE_RULES_INTERVAL_S=0 to stop). Staff endpoints need a signed-in user.
- Forecast: `app/services/forecast.py` (pure baseline + backtest) and `app/services/history.py` (DB series, 10 min cache). Always labelled experimental. Simulated history: `python -m app.seed_history`.
- services/vision — separate uv project (YOLO11s + ByteTrack, CPU PyTorch; `--model models/yolo11n.pt` for slow PCs). `vision/counting.py` holds the pure zone-counting rules (unit-tested without YOLO); `worker.py` posts counts only, never stores frames; `zone_tool.py` draws layouts; `studio.py` draws zones then plays a video with live counts (offline, scaled to the screen); `validate.py` compares estimates with hand counts (`--seats` for seat states). Seats (Phase 7): `posture.py` (sitting vs standing from pose keypoints) and `seats.py` (pure per-seat state machine: free, occupied, held, unknown), run together with zone counting by `pipeline.py`. See services/vision/README.md. Videos live in git-ignored `data/videos/`.
- Devices authenticate with `Authorization: Device <token>`; register cameras with `uv run python -m app.devices_cli register` (services/api).
- Staff auth: `app/core/security.py` (Argon2, JWT, refresh tokens, rate limit) + `app/core/auth.py` (roles, `can_manage_canteen`/`can_manage_shop`, 403 `forbidden_scope`). The console holds the access token in memory and refreshes from the httpOnly cookie on `/api/v1/auth`. Create users with `uv run python -m app.users_cli create`. Every write calls `app.services.audit.record`.
- Seats: positions live inside each seating polygon of the layout (`seats`); devices post snapshots to `POST /devices/{id}/seats` (`app/routers/seats.py`, `schemas_seats.py`) into `seat_states`, `seat_sessions` (no identities) and `zone_seat_status`; held and hidden seats are never free. Stay times: `app/services/stays.py`.
- Staff editing routers: `manage_shops.py` (hours, closure, menu drafts, publish, instant sold out), `manage_config.py` (meal schedules, thresholds), `manage_zones.py` (layout versions, rollback, zones).
- DineMate Business (Phases 8–10 built; cloud and billing not built): `apps/business` (port 5177) for cafés and restaurants, rented monthly. API in `app/business/` (own models, schemas, router under `/business`, like `app/safety/`): pure rules `tables.py` (table state), `visits.py` (anonymous visits, 60 s grace), `estimate.py` (leave-time range, experimental); `service.py` (DB, called from seat-snapshot ingest); `seed.py` (labelled Sample Café, 12 tables, 28 days of visits); `sim.py` (`cafe-simulator` compose service). Tenancy: `organizations`; a venue is a `canteens` row with `kind='venue'` and id `v-…`; roles `owner`, `venue_manager`; campus endpoints filter to `kind='canteen'`. Design and palette (graphite and cobalt) in docs/BUSINESS_DESIGN.md; ground rules in docs/ROADMAP.md. Staff and till (Phase 9): `staff_service.py`, `staff_router.py`, `staff_schemas.py`, pure rules `coverage.py` (counter coverage, queue alerts) and `till.py` (CSV import, sales); `templates.py` encrypts face templates (needs `DINEMATE_TEMPLATE_KEY`, refused when `DINEMATE_DEPLOYMENT=cloud`); `staff_sim.py` simulates presence and orders. Staff report and worker sheets are owner only and audited. Vision: `staff.py` (work areas, identity hysteresis, presence, queue), `faces.py`, `badges.py`, `identity.py`, `enrol.py`, `fetch_models.py` (models in git-ignored `models/`), `stream.py` (signed MJPEG live view). Privacy kit in docs/business/privacy. Local server (Phase 10): `app/business/camera_router.py` (cameras added from the dashboard, camera layouts and areas, hub endpoints that rotate per-camera tokens), `app/business/setup.py` (first-run CLI), `vision/hub.py` (one worker per camera), `infra/docker-compose.business.yml` + `infra/business-web/` (nginx) + `infra/install-business.ps1` / `infra/business.ps1`; owner guide docs/business/INSTALL.md; `LayoutCanvas` in packages/ui is shared by the console zone editor and the business camera setup page. Never store video or images; live view with tracking is streamed on the shop's network only; customers are never recognised.

## Rules

- Seat numbers are estimates: always "about N" / "~N", never cache occupancy in the service worker.
- Stale data (> 2 min) is grey; unavailable (> 10 min) shows no number.
- Safety module stays separate (`app/safety/`: own models, router, schemas, signing, CLI; students poll `/safety/active` every 10 s). Simulated events are always labelled; simulator sources can never create real events.
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
- pnpm dev:student / pnpm dev:console / pnpm dev:business (sample data) — add `:api` (dev:student:api, dev:console:api, dev:business:api) to use the real API on :8000; business sample sign-in: owner@ or manager@dinemate.test
- pnpm typecheck / pnpm build / pnpm lint / pnpm format
- pnpm stack:up / pnpm stack:down — Postgres + API + simulator in Docker (API on :8000)
- pnpm stack:cameras — the same stack plus the camera hub (live views on 8100–8107) for test videos: YouTube links or uploaded clips added on the console's Devices page (seen live in Zones) or as a Test video camera in Business. Temporary; see docs/TEST_VIDEOS.md (includes how to remove it)
- Business local server (Windows): `powershell -ExecutionPolicy Bypass -File infra\install-business.ps1` (add `-SampleCafe` for the labelled sample), then `infra\business.ps1 start|stop|status|logs|backup|update`; dashboard on :8080
- pnpm dev:api — API with reload against a local or Docker Postgres
- pnpm test:api — pytest; integration tests use `dinemate_test` on localhost:5432 and skip if Postgres is down (set DINEMATE_REQUIRE_DB_TESTS=1 to fail instead)
- pnpm api:types — after changing API schemas: re-export openapi.json and regenerate TS types (CI checks both)
- pnpm e2e — Playwright demo flows + axe + PWA check; starts its own API on :8001 (`app.e2e_server`, database `dinemate_e2e`) and web apps on 5183/5184/4183. Needs Postgres on :5432 and Chrome locally
- Reports (services/api): `uv run python -m app.forecast_report`, `uv run python -m app.utilisation_report`; results in docs/RESULTS.md
- In services/api: `uv run alembic revision --autogenerate -m "..."`, `uv run alembic upgrade head`, `uv run python -m app.seed --reset`

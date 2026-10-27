# DineMate — Solo Roadmap

One developer, seven phases, Week 0 → 10 Jan 2027. This replaces the four-person allocation in Section 21 of the [development plan](DineMate_Development_Plan.md); everything else in the plan still applies.

**How to work through it**

- Finish one phase before starting the next. Each phase ends with a demo you can run, not just code.
- Tick boxes here as work lands (one commit per item where possible).
- Vision input for now: the laptop webcam plus recorded canteen videos in `data/videos/` (git-ignored, never committed).
- If the competition deadline turns out earlier, use the **Cut first** list at the bottom.

| Phase                      | Weeks | Dates           | Goal                                                    |
| -------------------------- | ----- | --------------- | ------------------------------------------------------- |
| 0. Foundations             | 0     | 27 Oct – 1 Nov  | Repo, tooling, empty API and database running           |
| 1. Real data API           | 1–2   | 2 – 15 Nov      | Student app runs on the real API instead of sample data |
| 2. Live occupancy loop     | 3–4   | 16 – 29 Nov     | Webcam or video → worker → API → Home screen            |
| 3. Crowding & accuracy     | 5     | 30 Nov – 6 Dec  | Crowding alerts work; accuracy measured on videos       |
| 4. Staff tools             | 6–7   | 7 – 20 Dec      | Login, shop manager, schedules, zone editor             |
| 5. Safety module           | 8     | 21 – 27 Dec     | Labelled safety simulation end to end                   |
| 6. Forecast, polish & demo | 9–10  | 28 Dec – 10 Jan | Forecast baseline, hardening, demo rehearsed            |

---

## Already done (27 Oct)

- [x] pnpm monorepo: `apps/student`, `apps/console`, `packages/ui`, `packages/api-client`
- [x] Student PWA screens from the design (Welcome, Home, Canteen, Food, Meals, Alerts), mobile and desktop
- [x] Console Overview page from the admin design
- [x] Installable PWA: manifest, icons, service worker that never caches seat numbers
- [x] Sample "server" in `packages/api-client` with a server-driven clock

## Phase 0 — Foundations (Week 0)

- [x] Git repo and first commit
- [x] ESLint + Prettier for the TypeScript packages; ruff (lint + black-compatible format) for Python
- [x] `services/api`: FastAPI app with `/api/v1/health`, settings from `.env`, `infra/.env.example`
- [x] `infra/docker-compose.yml`: Postgres 16 + API (front ends keep running with `pnpm dev`)
- [x] GitHub Actions CI: lint, format, typecheck, build, ruff, `pytest`, Compose smoke test (green once pushed)
- [ ] Non-code: permission request, GreenExE registration, organiser questions (plan 18.4)

**Done when:** `docker compose up` serves `/api/v1/health`, and CI is green on `main`.

## Phase 1 — Real data API (Weeks 1–2)

- [x] SQLAlchemy models + Alembic migrations for the core tables (plan Section 14): canteens, seating_zones, devices, zone_layouts, occupancy_readings, shops, shop_hours, exceptions, menus, meal_schedules, overrides (+ canteen_hours, walking_times, app_state)
- [x] Seed script with the same sample canteens, zones, shops and menus the UI uses today, all flagged `is_sample` (`python -m app.seed`; Compose seeds an empty database on start)
- [x] Read endpoints: `/canteens`, `/canteens/{id}`, `/canteens/{id}/occupancy`, `/canteens/{id}/shops`, `/shops/{id}/menu`, `/meal-status`, `/student/summary`, with the plan's error format
- [x] Shop status resolution (temporary closure → exception → weekly → unknown) and meal status in Asia/Colombo, with tests for midnight, weekends and holidays
- [x] Generate `packages/api-client` types from the OpenAPI spec (`pnpm api:types`, checked in CI); real fetches behind `VITE_API_URL` (`pnpm dev:student:api`), sample mode kept for offline demos
- [x] Pulled forward from Phase 2: a database-direct occupancy simulator (`python -m app.sim`, runs in Compose) so the API has live numbers

**Done when:** the student app shows identical screens with the sample module switched off, and the schedule tests pass. ✅ 27 Oct — Alerts tab and console still use sample data until Phases 3 and 5.

Notes from Phase 1:

- Canteen and shop IDs are short text slugs (`a`, `s-rice`) instead of UUIDs, so URLs stay readable. Zones, readings and menu items use UUIDs.
- Crowding levels use the default thresholds (60/80/95). Per-zone thresholds and hysteresis arrive in Phase 3.
- `DINEMATE_DEMO_CLOCK_START` freezes the demo at a chosen moment (time keeps running from it); its anchor is stored in `app_state` so the API and simulator agree.

## Phase 2 — Live occupancy loop (Weeks 3–4)

- [x] Device tokens (hashed); `POST /devices/{id}/occupancy`, `POST /devices/{id}/heartbeat`, `GET /devices/{id}/config` (with ETag); `app.devices_cli` registers a camera from a layout file
- [x] Freshness: live → stale at 2 min → unavailable at 10 min, computed on every read from the latest reading (no background job needed until Phase 3 alerts)
- [x] Occupancy simulator for the canteens with no camera posts through the same authenticated ingest (stored as `is_simulated`)
- [x] `services/vision` worker: `--source 0` (webcam) or a video file; YOLO11n + ByteTrack, zone assignment, walkway masking, seated filter (off until calibrated), dwell, 60 s median, uncertainty band; posts counts only, frames never stored
- [x] Zone tool: grab one frame per source, click out seating outlines, save a layout JSON
- [x] Student app polls every 15 s (WebSocket `/ws/live` deferred; see Cut first)

**Done when:** you sit in a marked zone in front of the webcam and the Home screen's free seats change within about 60 s. Stopping the worker shows "No info right now" after 10 min.
Checked 28 Oct on a looping test clip (2 people): video → worker → API → "Pilot (webcam)" on Home, ~2 of 4 seats free. **Still to do by you:** the same with your webcam (steps in `services/vision/README.md`).

## Phase 3 — Crowding & accuracy (Week 5)

- [ ] Crowding state machine as a pure Python module (hysteresis + 2 min dwell, plan 8.3), with unit tests including the flapping test
- [ ] Crowding alerts: one open alert per zone, suspend on stale data, cooldown; `GET /alerts`, `POST /alerts/{id}/acknowledge`
- [ ] Console Overview reads the real API (zones table, alert queue, device health)
- [ ] Student Alerts tab shows real notices
- [ ] Validation script: manual counts (CSV) vs worker output on the canteen videos → MAE, bias, % within ±2, interval coverage

**Done when:** a 1-hour flapping simulation opens no duplicate alerts, and you have an accuracy table for at least 3 videos.

## Phase 4 — Staff tools (Weeks 6–7)

- [ ] Auth: admin-created users, Argon2, JWT + refresh cookie, roles and canteen/shop scopes (plan Section 16), login rate limit
- [ ] Audit log on every write
- [ ] Console: Shop manager page (weekly hours, exceptions, temporary closure, menu with one-tap sold out, draft → publish)
- [ ] Console: Meal schedules (campus default + canteen overrides)
- [ ] Console: Thresholds page
- [ ] Console: Zone editor (drag points, rename, capacity, save as a new version, rollback); worker picks up changes within 30 s

**Done when:** a shop manager marks an item sold out and the student Food tab shows it on the next refresh, and a shop manager editing another shop gets a 403.

## Phase 5 — Safety module (Week 8)

- [ ] `app/safety/` with its own router, tables, permissions and `/ws/safety` (or a 10 s poll of `/safety/active`)
- [ ] HMAC-signed ingest with a ±60 s window, idempotency, merging of duplicate bursts
- [ ] Safety simulator CLI; `is_simulation` forced on for simulator sources
- [ ] Acknowledge / resolve (note required) with audit trail; console Safety page
- [ ] Student banner wired to real events; "Safety alert status unknown" when the connection drops

**Done when:** the safety tests in plan Section 20 pass, and "SIMULATION" shows on every surface.

## Phase 6 — Forecast, polish & demo (Weeks 9–10)

- [ ] History endpoint + baseline forecast (persistence vs historical average), labelled experimental
- [ ] Recommendation endpoint drives "Best spot now"
- [ ] Accessibility pass (keyboard, screen reader labels, 200% text), Lighthouse PWA installable, offline shows no seat numbers
- [ ] Playwright E2E for the 5 demo flows (plan 25.1)
- [ ] Sustainability measurements and accuracy report written up
- [ ] Demo script, two rehearsals, recorded backup demo (blur faces in any canteen footage)
- [ ] Feature freeze Monday of Week 10

**Done when:** the full demo runs twice in a row on a clean laptop.

---

## Cut first (if time runs short)

1. Forecast → show today's measured history only.
2. Zone editor UI → edit the layout JSON and re-seed.
3. WebSockets → 15 s polling everywhere (already the fallback).
4. Console Thresholds page → defaults from the seed file.
5. Separate `/ws/safety` channel → 10 s poll of `/safety/active` (still its own router and tables).

**Never cut:** stale/unavailable handling, simulation labels, audit on safety actions, frames never stored.

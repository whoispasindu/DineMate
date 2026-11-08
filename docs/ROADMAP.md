# DineMate — Solo Roadmap

One developer, seven phases, Week 0 → 10 Jan 2027, then Phases 7–10 from the judges' feedback. This replaces the four-person allocation in Section 21 of the [development plan](DineMate_Development_Plan.md); everything else in the plan still applies.

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
| 7. Seat-level occupancy    | TBD   | after judging   | Every seat is free, occupied, held or unknown           |
| 8. Business core           | TBD   | after Phase 7   | DineMate Business: venues, tables, customer stays       |
| 9. Staff and till          | TBD   | after Phase 8   | Staff recognition, work areas, till data per worker     |
| 10. Deploy and sell        | TBD   | after Phase 9   | Local server, cloud plan, billing, first pilot shops    |

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
✅ 28 Oct: checked on a looping test clip, then with the laptop webcam: sitting in the desk zone took "Pilot (webcam)" on Home from 2 free to ~1 free (0–2) within one post after the 10 s dwell. Windows needs both camera privacy switches on for desktop apps.

## Phase 3 — Crowding & accuracy (Week 5)

- [x] Crowding state machine as a pure Python module (`app/services/crowding.py`: hysteresis + 2 min dwell + 10 min cooldown, plan 8.3), with unit tests including the flapping test
- [x] Crowding alerts: one active alert per zone, escalate/de-escalate, re-open on escalation after acknowledge, suspend on stale data; rules engine runs every 15 s in the API; also `data_stale` and `sensor_offline` staff alerts; `GET /alerts`, `POST /alerts/{id}/acknowledge`
- [x] Console Overview reads the real API (`GET /console/overview`: zones table, alert queue with Acknowledge, device health, today's occupancy chart) — `pnpm dev:console:api`
- [x] Student Alerts tab shows real notices (`GET /notices`: crowding with a suggested alternative, no-live-data zones, sold out, closing soon, meal started)
- [x] Validation script: `python -m vision.validate counts.csv` → MAE, bias, % within ±2, interval coverage, level accuracy per video and overall
- [ ] **You:** count seated people by hand in at least 3 canteen videos and run the validation script (steps in `services/vision/README.md`)

**Done when:** a 1-hour flapping simulation opens no duplicate alerts ✅ (unit and database tests), and you have an accuracy table for at least 3 videos (waiting on your counts).

Notes from Phase 3:

- Staff endpoints used a temporary bearer token until Phase 4 replaced it with sign-in and roles.
- Per-zone thresholds live in `crowding_thresholds` (defaults 60/80/95, 5-point hysteresis, 2 min dwell); Phase 4 added the Thresholds page.
- Forecast bars on the console chart are still empty; the baseline forecast is Phase 6.

## Phase 4 — Staff tools (Weeks 6–7)

- [x] Auth: admin-created users (`app.users_cli`), Argon2, 15 min JWT + rotating httpOnly refresh cookie (reuse after a 30 s grace revokes every session), roles and canteen/shop scopes (plan Section 16), login rate limit (5/min/IP)
- [x] Audit log on every write (`audit_log`: sign-in, alerts, shops, menus, schedules, thresholds, zones, layouts, users)
- [x] Console: Shop manager page (weekly hours, exceptions, temporary closure, menu with one-tap sold out, draft → publish)
- [x] Console: Meal schedules (campus default + canteen overrides)
- [x] Console: Thresholds page
- [x] Console: Zone editor (drag points, rename, capacity, save as a new version, rollback); worker picks up changes within 30 s

**Done when:** a shop manager marks an item sold out and the student Food tab shows it on the next refresh, and a shop manager editing another shop gets a 403.
✅ 29 Oct: signed in as the sample Rice & Curry Stall manager on the Docker stack, marked an item sold out, and `GET /shops/s-rice/menu` showed it right away. Integration tests cover the 403 on another shop's items, hours and publish. A saved layout changes the device config ETag and `layout_version` at once. The worker re-reads its config every 30 s; that wasn't re-checked here with a running worker.

Notes from Phase 4:

- Seeding creates sample staff accounts (admin@, canteen.a@, rice.stall@, safety@dinemate.test) with `DINEMATE_DEMO_PASSWORD` (Compose default in `infra/.env.example`). An already-seeded database gets them on the next `--if-empty` start.
- Create real accounts with `uv run python -m app.users_cli create --email … --name … --role … [--canteen a] [--shop s-rice]` (password prompted). Set a long random `DINEMATE_JWT_SECRET` outside development; the API refuses to start with the default.
- Menu edits are drafts (`menu_items.draft`, or unpublished new items) until Publish. Sold out is instant and never a draft.
- Staff editing pages need the real API (`pnpm dev:console:api`). In sample mode the console signs in with any password for the four sample accounts, and the editing pages say so.
- The zone editor draws on a blank 16:9 canvas. You can load a local snapshot as a backdrop. It stays in the browser and is never uploaded.

## Phase 5 — Safety module (Week 8)

- [x] `app/safety/` with its own router, tables (`safety_sources`, `safety_events`, `safety_event_acks`, `safety_instructions`), permissions (safety officer + admin) and a 10 s poll of `/safety/active` (WebSocket deferred)
- [x] HMAC-signed ingest with a ±60 s window, idempotency, merging of duplicate bursts (same id, or same type + place within 5 min → `repeat_count`), 10 messages/s per source
- [x] Safety simulator CLI (`python -m app.safety.cli trigger|heartbeat|register-source|add-instruction`); `is_simulation` forced on for simulator sources
- [x] Acknowledge / resolve (note required) with audit trail; console Safety page (simulator panel in simulation mode only, open events, source health, resolved in the last 7 days)
- [x] Student banner wired to real events; "Safety alert status unknown" when the connection drops

**Done when:** the safety tests in plan Section 20 pass, and "SIMULATION" shows on every surface.
✅ 29 Oct, plan Section 20 safety rows:

| Test                                          | Result                                                                                                                                                              |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Simulated event on the safety dashboard ≤ 5 s | Dashboard polls every 5 s; a CLI event showed up on the next poll                                                                                                   |
| Simulation label on every surface             | Student banner (Home, Alerts), console Safety page and Overview, API response and audit rows. There are no push notifications yet, so no notification text to label |
| Simulator payload with `is_simulation=false`  | Stored as simulation (test + live CLI `--claim-real`)                                                                                                               |
| Invalid signature / replayed timestamp        | 401 `invalid_signature`, logged and audited (test)                                                                                                                  |
| Duplicate burst of 50                         | 1 event, `repeat_count=50` (test); 20-event live burst merged to 1                                                                                                  |
| Ack/resolve recorded with user + time         | Test + live: audit rows carry user, time, note and the simulation label                                                                                             |
| Source heartbeat lost                         | Warning after 60 s plus at most one 15 s rules run (≤ 75 s), staff only; seen live                                                                                  |
| Client disconnect                             | "Safety alert status unknown" about 14 s after stopping the API container                                                                                           |

Notes from Phase 5:

- Sources send `Authorization: Device <token>`, `X-Timestamp` (ISO 8601) and `X-Signature: sha256=<HMAC-SHA256(token, timestamp + "." + body)>`. Only the token hash is stored; the server checks the signature with the token from the request.
- The Compose stack registers the `safety-sim` source with `DINEMATE_SAFETY_SIMULATOR_TOKEN`. A real gateway gets its own token from `register-source`, but only after written approval from the university (plan 9.6).
- With no approved instructions, students see "Follow instructions from campus staff and official alarms." No exits or routes are ever shown. `add-instruction` stores approved text with the approver's name.
- Heartbeat checks start only after a source has sent its first heartbeat. Run `python -m app.safety.cli heartbeat` to keep the simulator source online during a demo.

## Phase 6 — Forecast, polish & demo (Weeks 9–10)

- [x] History endpoint (`GET /zones/{id}/occupancy/history`) + baseline forecast (persistence, historical average, blend with α fitted on the validation week), labelled experimental; `app.forecast_report` backtests it
- [x] Recommendation endpoint (`GET /recommendations`, plan 8.5) drives "Best spot now" and the "Less crowded nearby" card
- [ ] Accessibility pass. Automated part done: axe (WCAG 2.1 A/AA) finds no serious or critical issues on the six student pages, and a contrast fix landed. **You:** keyboard-only run, screen reader spot check, 200% text. The installable PWA check now runs in E2E, because recent Lighthouse versions dropped the PWA audit. Offline shows no seat numbers (E2E)
- [x] Playwright E2E for the demo flows (plan 25.1): `pnpm e2e` uses its own `dinemate_e2e` database and API on :8001
- [ ] Sustainability measurements and accuracy report written up. Scaffold in `docs/RESULTS.md`; `app.utilisation_report` gives seat-hours, empty-zone hours and peak balance. **You:** hand counts, survey, smart-plug reading
- [ ] Demo script, two rehearsals, recorded backup demo (blur faces in any canteen footage). Script in `docs/DEMO.md`; **you:** rehearse twice, record the backup
- [ ] Feature freeze Monday of Week 10

**Done when:** the full demo runs twice in a row on a clean laptop.

Notes from Phase 6:

- `python -m app.seed_history --days 21` (services/api) adds **simulated** past weekdays for the simulator zones so the forecast has history. Re-running replaces them. The live simulator follows the same daily shape, normalised so the lunch peak equals each zone's seeded base.
- On simulated history the blend matches the historical average (α ≈ 0) with about 75% coverage of the 80% band. That only shows the pipeline works.
- The console Occupancy page charts zone history (4 h, 24 h, 7 days).
- A database seeded with the demo clock and later run on real time keeps future-dated readings, which hide live ones. Reset with `pnpm stack:down`, `docker volume rm dinemate_db-data` and `pnpm stack:up`, or keep using the demo clock.

## Phase 7 — Seat-level occupancy (after judging)

Judges asked (5 Nov 2026) how we tell sitting from standing, what happens when bags hold chairs, how short visits are handled, what happens when students leave bags while buying food, and how a big crowd around tables is counted. The answer to all five is to track each seat, not just people per zone. Plan 7.4 already says held seats are reported separately and never counted as occupied.

Every seat has one state:

| State    | Meaning                                                            | Shown to students as |
| -------- | ------------------------------------------------------------------ | -------------------- |
| free     | Empty chair seen clearly for 30 s, nothing on it or in front of it | free                 |
| occupied | A seated person stayed for the dwell time                          | taken                |
| held     | Belongings on or in front of the seat, nobody sitting              | held by bags         |
| unknown  | The seat is hidden (crowd, standing people, poor view)             | not counted as free  |

- [x] Seat map: the zone tool and studio (**T**) and the console Zones page (**Place seats**) put one point per chair inside a seating zone; seats are saved inside each seating polygon of the layout version (no migration needed), validated (inside the polygon, unique ids) and sent in the device config; a zone's capacity becomes its seat count when seats exist
- [ ] Detector: people with pose keypoints (YOLO11n-pose, `--pose-model`) every frame; belongings and table items (backpack, handbag, suitcase, laptop, book, cup, bowl, bottle, cutlery, food) every 5 s; zones without seats keep zone-only counting. **You:** measure fps on the laptop CPU with a real clip
- [x] Seated check (pure module, unit tests): knee angle when legs are visible, the existing height calibration when they are not, close to a seat point, and still for the dwell time → seated, standing or unsure
- [x] Seat state machine (pure module like `crowding.py`, unit tests): free, occupied, held and unknown with a held timer; a hidden seat keeps its last state for a while, so a passing crowd never creates a free seat; plates left with nobody there mark the seat "free soon"
- [x] Crowd mode: many standing people or 40% of seats hidden → the zone says "Crowded, few or no seats"; hidden seats count as taken, so the range never promises seats we can't see
- [x] API: `POST /devices/{id}/seats` (seat snapshot), `seat_states` (current state) and `seat_sessions` (start and end of each seat state, no identities) tables; zone summaries gain `held` and `unknown`; new schemas live in their own module, so `schemas.py` stays untouched
- [x] Student app: "about N free · M held by bags"; crowded zones say so; held and unknown seats are never counted as free
- [ ] Console: **Seats** page with free/taken/held/hidden per zone, a seat map (one dot per seat, coloured by state), seats held over 15 minutes and typical stay time by hour. Still to do: held limit and crowd settings on the Thresholds page (fixed defaults for now)
- [x] Stay times: median seat-session length by hour, and "about N seats likely to free up in 10 min" (labelled experimental, like the forecast)
- [x] Simulator: seat summaries per zone (held seats that rise at peak, hidden seats and standing people when a zone is crowded), so canteens without cameras and the demo keep working
- [ ] Validation: `vision.validate --seats` compares hand-labelled seat states (CSV: video, t_seconds, seat, state) and reports agreement, the false-free rate and accuracy per state. **You:** record three staged clips with friends who agree to it: a standing chat at a table, bags left while queuing, a crowd around several tables
- [x] Demo: one scenario per judge question in `docs/DEMO.md`

**Done when:** on the staged clips a standing person is never counted as seated, a bag-only seat shows as held, a seat stays held while its owner queues and turns occupied when they return, a crowd never produces a free seat that isn't free, and seat-state accuracy is measured.

Not in this phase: identifying people, following anyone between cameras, face recognition, recognising which dish someone eats.

Notes from Phase 7:

- Local Python (uv's Python 3.12) is blocked by Windows Application Control on this laptop since 5 Nov, so API and vision tests ran in Docker (`python:3.12-slim`) against the Compose Postgres. The YOLO models themselves were not run here; the pose and object paths are covered by tests with fake detectors.
- The worker still posts zone readings to `/occupancy` (held and hidden seats count as taken) and adds a seat snapshot to `/seats`. An older API without the seat endpoint just gets zone counts.
- Seat sessions store a seat id, a state and start/end times only. Nothing identifies a person.

## DineMate Business (Phases 8–10)

A second product for cafés, restaurants and food courts, rented monthly. It lives in this repo next to the campus apps and shares the camera worker, the API core, the seat and table logic and the design system. The judges (5 Nov) want the business version to track customers and staff; the campus apps stay counts-only and are not affected.

Ground rules for the whole product:

- No video or images are ever stored, on the shop's server or ours. Only events and numbers are kept.
- Customers are anonymous: tracked within one visit (temporary ids), never recognised again, never enrolled.
- Staff recognition is opt-in per worker, with written consent. Face templates (not photos) are stored encrypted on the shop's local server only, never in our cloud, and deleted when the worker leaves. Workers who decline use a badge instead. Workers can see their own data.
- Per-worker reports are visible to the owner only. Data is deleted automatically after a retention period the shop sets.
- Not built: "suspicious activity" detection.

Layout: `apps/business` (owner and manager dashboard), later `apps/venue` (public "check before you come" page); `services/api/app/business/` (own routers, schemas and tables, like `app/safety/`); `services/vision/vision/staff.py` and `tables.py`; `infra/docker-compose.business.yml` for a shop's local server.

## Phase 8 — Business core

- [ ] Tenancy: organizations and venues above canteens and zones; every query is scoped to the signed-in user's organization; the campus becomes one organization
- [ ] Tables: group seats into tables in the zone tool and the dashboard; a table is free, occupied, held or needs clearing; party size from its seats
- [ ] Customer visits: start and end per table (no identities), time at table, turns per table per day, busiest hours, stay after paying (matched to till orders by time, Phase 9)
- [ ] Leave-time estimate per table ("likely free in about X–Y min") from time seated, party size, time of day and what is on the table, fitted on the venue's own history
- [ ] `apps/business`: Live floor (table map with states and timers), Customers (visits, stays, turns), Reports (day, week, hours), Cameras, Settings; simple left navigation, everything reachable in two clicks
- [ ] Business design: same design language as the campus apps with its own professional palette; designed in Figma first, reviewed, then built
- [ ] Sample café with simulated tables and visits, always labelled

**Done when:** a sample café runs end to end: tables change state live, visits and turn times show in the dashboard, and the leave-time estimate is labelled experimental.

## Phase 9 — Staff and till

- [ ] Staff enrolment: opt-in face enrolment on the local server (consent record, face template only, encrypted), badge fallback (printed code on apron or lanyard), remove a worker and their data in one step
- [ ] Recognition in the worker: match staff faces or badges to tracks; customers are never matched; no images leave memory
- [ ] Work areas: mark counter, kitchen and floor areas; time per worker per area, counter coverage ("unstaffed for 6 min at 12:40"), queue length alerts
- [ ] Till data: CSV import first, then one real till system; items sold per cashier ("coffees served per worker"), orders per hour, average order
- [ ] Staff page: per-worker hours in each area, items served, busiest shifts; workers can see their own page
- [ ] Privacy kit: staff notice and consent templates, data protection impact assessment template, retention settings, audit of who viewed staff reports

**Done when:** on staged clips, enrolled staff are recognised in their work areas, customers stay anonymous, and per-worker items served match the till file.

## Phase 10 — Deploy and sell

- [ ] Local server: one-command install of the business stack on a small PC (`docker-compose.business.yml`), cameras added from the dashboard
- [ ] Cloud plan: multi-tenant hosting for shops that pay extra; cameras still run locally and send only counts and events
- [ ] Plans and billing switches (per venue per month, per camera, cloud add-on); pricing left as `[__]` until pilot shops are interviewed
- [ ] Pilot with one or two shops, with written agreements and staff consent

---

## Cut first (if time runs short)

1. Forecast → show today's measured history only.
2. Zone editor UI → edit the layout JSON and re-seed.
3. WebSockets → 15 s polling everywhere (already the fallback).
4. Console Thresholds page → defaults from the seed file.
5. Separate `/ws/safety` channel → 10 s poll of `/safety/active` (still its own router and tables).

**Never cut:** stale/unavailable handling, simulation labels, audit on safety actions, frames never stored.

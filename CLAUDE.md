# DineMate

Campus canteen seat-availability platform. Full plan: docs/DineMate_Development_Plan.md.
Solo developer. Work one phase at a time from docs/ROADMAP.md and tick items off there as they land.

## Apps

- apps/student — installable PWA for students. Keep it simple.
- apps/console — staff console (admin, canteen manager, shop manager, safety officer).
- packages/ui — shared tokens and components (StatusPill, Ring, CanteenArt, HazardFrame, icons).
- packages/api-client — API types, a sample "server" (labelled sample data) and TanStack Query hooks. Swap the sample functions for real fetches when services/api exists.
- services/api — FastAPI + PostgreSQL, managed with uv (Python 3.12). Only `/api/v1/health` so far.
- infra/docker-compose.yml — Postgres 16 + API. Copy infra/.env.example to infra/.env to override defaults.
- services/vision — YOLO worker; posts zone counts only, never stores video (not started).

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
- Every PR: tests pass, lint clean, no secrets committed.

## Commands

- pnpm install
- pnpm dev:student / pnpm dev:console
- pnpm typecheck / pnpm build / pnpm lint / pnpm format
- pnpm stack:up / pnpm stack:down — Postgres + API in Docker (API on :8000)
- pnpm dev:api — API with reload against a local or Docker Postgres
- pnpm test:api — pytest; `uv run ruff check .` and `uv run ruff format .` in services/api

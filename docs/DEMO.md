# DineMate demo script

About 4 minutes of live demo inside the 10-minute talk (plan Section 25.1). Everything shown is **labelled sample or simulated data** unless you're running a real camera.

## Before you start (10 minutes earlier)

1. In `infra/.env`, set `DINEMATE_DEMO_CLOCK_START=2026-11-20T12:30:00+05:30`. The demo then opens just before the lunch peak, and the clock keeps running from there.
2. Reset and start the stack:
   ```bash
   pnpm stack:down
   docker volume rm dinemate_db-data
   pnpm stack:up
   ```
3. Add three weeks of simulated history so the forecast has something to learn from:
   ```bash
   docker compose -f infra/docker-compose.yml exec api python -m app.seed_history --days 21
   ```
4. Keep the safety simulator source online during the talk:
   ```bash
   docker compose -f infra/docker-compose.yml exec api python -m app.safety.cli heartbeat --every 20
   ```
5. Start the web apps against the API: `pnpm dev:student:api` (port 5173) and `pnpm dev:console:api` (port 5174).
6. Open three browser windows:
   - **Student:** phone-sized window on http://localhost:5173.
   - **Console:** signed in as `admin@dinemate.test`.
   - **Console:** private window signed in as `safety@dinemate.test`.

   All sample staff accounts use `DINEMATE_DEMO_PASSWORD`.

7. Optional live camera: register the webcam (`uv run python -m app.devices_cli register`, services/api), then run `uv run python -m vision.worker --preview` from `services/vision` with `DINEMATE_DEVICE_ID` and `DINEMATE_DEVICE_TOKEN` set (see services/vision/README.md). `vision.studio` is offline only and never posts readings.
8. Run the automated flows once to make sure everything works: `pnpm e2e`. It uses its own database, so your demo data stays untouched.

## The run (≈ 4 min)

| #   | What you show                                                                                                                                                                                                         | Where                      | What to say                                                                                                                      |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Home: **Best spot now** and the canteen list with "about N free" and ranges                                                                                                                                           | Student                    | "Seat numbers are estimates with a range, updated every 15 seconds."                                                             |
| 2   | Open the crowded canteen (Canteen C). Point at the **Less crowded nearby** card with the walk time, then tap it                                                                                                       | Student                    | "When a canteen is crowded we suggest one with live data and fewer people, not a guess."                                         |
| 3   | **Next hour** strip on a canteen page, labelled **Experimental forecast**                                                                                                                                             | Student                    | "Persistence blended with the usual pattern for this weekday. We show the evaluation, not a claim."                              |
| 4   | Sit in the webcam zone, or post a high reading. Overview zone turns **Crowded**, the alert appears, then **Acknowledge**                                                                                              | Console (admin)            | "Hysteresis plus a 2-minute dwell, so it doesn't flap." For a quick demo, set that zone's dwell to 0 on Thresholds first.        |
| 5   | Sign in as `rice.stall@`, tap **Available → Sold out**, refresh the student Food tab                                                                                                                                  | Console then Student       | "Sold out is one tap and live straight away. Other edits wait in a draft until Publish."                                         |
| 6   | Meal times: countdown to the end of lunch                                                                                                                                                                             | Student                    | "It reads the server clock, so a wrong phone clock doesn't matter."                                                              |
| 7   | Safety page → **Trigger simulation** (Canteen A, note "Judging demo"). The student banner shows **SIMULATION — NOT A REAL EMERGENCY**. Acknowledge, then Resolve with a note, and show **Resolved** with who and when | Console (safety) + Student | "The safety module is separate and only takes signed messages from approved sources. The simulator can never send a real alarm." |
| 8   | Stop the camera worker or simulator. The zone goes grey "may be out of date", then **No live data**                                                                                                                   | Student                    | "Old numbers are never shown as current."                                                                                        |

## Results slide (1 min)

- Accuracy: `python -m vision.validate validation/counts.csv` from `services/vision` (MAE, bias, % within ±2, interval coverage, level accuracy) for 3+ canteen videos.
- Forecast: `python -m app.forecast_report --out ../../docs/forecast-report.md` from `services/api`. Say plainly when the numbers come from simulated data.

## Backup

- Record the full run once with OBS, blurring faces in any canteen footage, and keep the file offline.
- If the network fails, the student app shows "You're offline" with no seat numbers. That's a feature: show it.

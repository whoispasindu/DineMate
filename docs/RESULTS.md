# DineMate results

This is the write-up for the Results and Sustainability slides (plan Sections 18, 20 and 25.1). Every number here has to come from a run you can repeat. Wherever a section still says **TODO**, the data isn't in yet; don't present a placeholder as a result.

## 1. Seat-count accuracy (vision)

Source: hand counts on at least 3 canteen videos (steps in `services/vision/README.md`).

```bash
cd services/vision
uv run python -m vision.validate validation/counts.csv --out validation/compared.csv
```

| Video       | Samples | MAE (seats) | Bias | Within ±2 | Interval coverage | Level accuracy |
| ----------- | ------- | ----------- | ---- | --------- | ----------------- | -------------- |
| TODO        |         |             |      |           |                   |                |
| TODO        |         |             |      |           |                   |                |
| TODO        |         |             |      |           |                   |                |
| **Overall** |         |             |      |           |                   |                |

Conditions to report for each video (plan 20): quiet vs peak, lighting, queue present, camera angle.

## 2. Forecast (experimental)

```bash
cd services/api
uv run python -m app.forecast_report --out ../../docs/forecast-report.md
```

- With only `app.seed_history` data, the report says **simulated**. That proves the pipeline works, not that the forecast is accurate.
- On real pilot data (3–4 weeks, weekday lunches), copy the 30-minute row here.
- Say whether the blend beats persistence and the historical average, and by how much.

| Horizon | MAE persistence | MAE historical avg | MAE blend | 80% coverage |
| ------- | --------------- | ------------------ | --------- | ------------ |
| 30 min  | TODO            |                    |           |              |

## 3. Seat utilisation and energy opportunity

```bash
cd services/api
uv run python -m app.utilisation_report --days 14 --out ../../docs/utilisation-report.md
```

The report gives three things for each canteen:

- seat-hours used vs available;
- empty-zone hours during opening times;
- utilisation balance at the daily peak (coefficient of variation across canteens).

For the energy opportunity:

1. With facilities' permission, measure one zone's fan and light circuit with a smart plug for a week (kW).
2. Multiply by that zone's empty-zone hours to get the kWh at stake.
3. Present it as an opportunity. DineMate never switches anything.

| Canteen | Utilisation | Empty-zone hours / week | Measured circuit (kW) | kWh at stake / week |
| ------- | ----------- | ----------------------- | --------------------- | ------------------- |
| TODO    |             |                         |                       |                     |

## 4. Seat-search time (survey + observation)

| Measure                              | Baseline (Weeks 1–2) | With app (Weeks 8–9) | n   |
| ------------------------------------ | -------------------- | -------------------- | --- |
| Median seat-search time (observed)   | TODO                 | TODO                 |     |
| "I often search for a seat" (survey) | TODO                 | TODO                 |     |
| Walking between canteens at peak     | TODO                 | TODO                 |     |

Behaviour change over a 2–3 week pilot will be small and confounded with other factors. Call it a pilot result with limitations.

## 4b. Table leave-time estimate (DineMate Business, experimental)

The Live floor shows "likely free in about X–Y min" for seated tables: the middle half (25th–75th percentile) of remaining time among the venue's finished visits of the same party size near the same hour, from the last 28 days (`app/business/estimate.py`).

| Measure                                           | Result | Data                                                           |
| ------------------------------------------------- | ------ | -------------------------------------------------------------- |
| Leave times inside the quoted range (target ~50%) | 63%    | 1,923 predictions, 28 days of **simulated** Sample Café visits |
| Mean error of the range midpoint                  | 10 min | same                                                           |

Simulated only. It shows the method runs end to end; it says nothing about real cafés until a pilot venue has a few weeks of history.

## 5. Automated checks

| Check                                                                                                                                                         | How                                                                | Status                        |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ----------------------------- |
| API unit and integration tests                                                                                                                                | `pnpm test:api`                                                    | Passing in CI                 |
| Demo flows end to end (recommendation, crowding acknowledge, sold out, countdown with a wrong device clock, simulated safety alert, offline, PWA installable) | `pnpm e2e`                                                         | Passing locally; CI job added |
| Accessibility (axe, WCAG 2.1 A/AA, serious and critical) on the six student pages                                                                             | part of `pnpm e2e`                                                 | No violations                 |
| DineMate Business flows (live table change, mark cleared) and axe on the five business pages                                                                  | `e2e/tests/07-business.spec.ts`                                    | Passing locally               |
| Safety rows from plan Section 20                                                                                                                              | `tests/integration/test_safety.py` + docs/ROADMAP.md Phase 5 table | Passing                       |

## What we don't claim

- No direct emissions cut from less walking.
- No building-occupancy or fire-safety figures. These are seating estimates only.
- No accuracy claim from simulated data.
- No food-waste effect unless a shop logs unsold portions (plan 18.1, Could).

import argparse
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import models
from app.core import clock
from app.core.db import get_engine
from app.services.forecast import Evaluation, evaluate, slot_start
from app.services.history import canteen_series

LOOKBACK = timedelta(days=60)


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}"


def canteen_section(name: str, evaluation: Evaluation, simulated_share: float, points: int) -> list[str]:
    lines = [f"### {name}", ""]
    source = (
        "simulated"
        if simulated_share >= 0.99
        else "real"
        if simulated_share <= 0.01
        else f"{simulated_share:.0%} simulated"
    )
    lines.append(f"{points} ten-minute points; data source: **{source}**.")
    if evaluation.train_until is None or not evaluation.scores:
        return [*lines, "", "Not enough data to evaluate.", ""]
    lines += [
        f"Trained on data before {evaluation.train_until:%Y-%m-%d %H:%M} UTC, tested on the final week "
        "(time-based split, no shuffling).",
        "",
        "| Horizon | Test points | MAE persistence | MAE history avg | MAE blend | alpha | 80% band | Coverage |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in evaluation.scores:
        coverage = "—" if s.coverage is None else f"{s.coverage:.0%}"
        lines.append(
            f"| {s.horizon} min | {s.samples} | {_fmt(s.mae_persistence)} | {_fmt(s.mae_historical)} | "
            f"{_fmt(s.mae_blend)} | {s.alpha:.2f} | {s.band:.1f} | {coverage} |"
        )
    fitted = "fitted on training data" if evaluation.params.fitted else "defaults (too little training data to fit)"
    return [*lines, "", f"Blend weights: {fitted}. MAE is in percentage points of seats in use.", ""]


def build_report(session: Session, now: datetime) -> str:
    end = slot_start(now)
    lines = [
        "# Forecast evaluation (experimental)",
        "",
        f"Generated {now:%Y-%m-%d %H:%M} UTC by `python -m app.forecast_report`.",
        "",
        "Models: persistence (now), historical average for the same weekday and 10-minute slot, and a blend",
        "forecast = alpha * current + (1 - alpha) * historical, with alpha fitted per horizon.",
        "Each forecast uses only data from before its own time.",
        "",
    ]
    canteens = session.scalars(
        select(models.Canteen).options(selectinload(models.Canteen.zones)).order_by(models.Canteen.sort_order)
    )
    for canteen in canteens:
        zone_ids: list[uuid.UUID] = [z.id for z in canteen.zones if z.is_active and z.is_monitored]
        series = canteen_series(session, zone_ids, now - LOOKBACK, end)
        r = models.OccupancyReading
        total = (
            session.scalar(select(func.count()).where(r.zone_id.in_(zone_ids), r.captured_at >= now - LOOKBACK)) or 0
        )
        simulated = (
            session.scalar(
                select(func.count()).where(r.zone_id.in_(zone_ids), r.captured_at >= now - LOOKBACK, r.is_simulated)
            )
            or 0
        )
        lines += canteen_section(
            canteen.name, evaluate(series), simulated / total if total else 0.0, len(series.points)
        )
    lines += [
        "## How to read this",
        "",
        "- Results on simulated data only check that the pipeline works. They say nothing about real accuracy.",
        '- Students see the blend as "Experimental forecast" until it has been evaluated on real pilot data.',
        "- The ML model (plan 12.2 step 4) is only worth adding if it beats the blend by 10% MAE on real data.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backtest the experimental forecast for every canteen.")
    parser.add_argument("--out", type=Path, help="write the Markdown report to this file")
    args = parser.parse_args(argv)
    with Session(get_engine()) as session:
        report = build_report(session, clock.now())
    if args.out:
        args.out.write_text(report, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

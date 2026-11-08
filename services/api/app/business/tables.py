from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

TableStateName = Literal["free", "occupied", "held", "needs_clearing", "unknown"]

UNAVAILABLE_AFTER = timedelta(minutes=10)


@dataclass(frozen=True)
class SeatView:
    state: str
    since: datetime
    free_soon: bool
    updated_at: datetime


@dataclass(frozen=True)
class TableView:
    state: TableStateName
    party_size: int
    since: datetime | None
    plates_left: bool


def table_state(seats: list[SeatView], now: datetime, cleared_at: datetime | None = None) -> TableView:
    fresh = [s for s in seats if now - s.updated_at <= UNAVAILABLE_AFTER]
    known = [s for s in fresh if s.state != "unknown"]
    if not known:
        return TableView("unknown", 0, None, False)
    occupied = [s for s in known if s.state == "occupied"]
    plates = any(s.free_soon for s in known)
    if occupied:
        return TableView("occupied", len(occupied), min(s.since for s in occupied), plates)
    held = [s for s in known if s.state == "held"]
    if held:
        return TableView("held", 0, min(s.since for s in held), plates)
    emptied = max(s.since for s in known)
    if plates and (cleared_at is None or cleared_at < emptied):
        return TableView("needs_clearing", 0, emptied, True)
    return TableView("free", 0, max(emptied, cleared_at) if cleared_at else emptied, False)

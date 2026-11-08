from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from app.business.tables import TableView

GRACE = timedelta(seconds=60)

StepKind = Literal["start", "extend", "end", "none"]


@dataclass(frozen=True)
class OpenVisit:
    started_at: datetime
    last_seen_at: datetime
    party_size: int


@dataclass(frozen=True)
class VisitStep:
    kind: StepKind
    started_at: datetime | None = None
    last_seen_at: datetime | None = None
    ended_at: datetime | None = None
    party_size: int = 0


def step(open_visit: OpenVisit | None, view: TableView, now: datetime) -> VisitStep:
    if view.state == "occupied":
        if open_visit is None:
            return VisitStep("start", started_at=view.since or now, last_seen_at=now, party_size=view.party_size)
        return VisitStep("extend", last_seen_at=now, party_size=max(open_visit.party_size, view.party_size))
    if open_visit is None:
        return VisitStep("none")
    if view.state == "held":
        return VisitStep("extend", last_seen_at=now, party_size=open_visit.party_size)
    if view.state == "unknown" or now - open_visit.last_seen_at < GRACE:
        return VisitStep("none")
    return VisitStep("end", ended_at=open_visit.last_seen_at)

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from statistics import mean, pstdev

from app.services.forecast import SLOT
from app.services.timeutil import CAMPUS_TZ

SLOT_HOURS = SLOT.total_seconds() / 3600
EMPTY_SHARE = 0.05


@dataclass(frozen=True)
class ZoneSlot:
    canteen_id: str
    zone_id: str
    at: datetime
    occupied: float
    capacity: int


@dataclass(frozen=True)
class CanteenUse:
    canteen_id: str
    seat_hours_used: float
    seat_hours_available: float
    empty_zone_hours: float

    @property
    def utilisation(self) -> float | None:
        return self.seat_hours_used / self.seat_hours_available if self.seat_hours_available else None


@dataclass(frozen=True)
class Utilisation:
    canteens: list[CanteenUse]
    peak_cv: float | None
    peak_days: int


def is_empty(slot: ZoneSlot) -> bool:
    return slot.occupied <= max(1.0, slot.capacity * EMPTY_SHARE)


def summarise(slots: list[ZoneSlot], is_open: Callable[[str, datetime], bool]) -> Utilisation:
    used: dict[str, float] = defaultdict(float)
    available: dict[str, float] = defaultdict(float)
    empty: dict[str, float] = defaultdict(float)
    per_slot: dict[datetime, dict[str, list[ZoneSlot]]] = defaultdict(lambda: defaultdict(list))
    for s in slots:
        if not is_open(s.canteen_id, s.at):
            continue
        used[s.canteen_id] += s.occupied * SLOT_HOURS
        available[s.canteen_id] += s.capacity * SLOT_HOURS
        if is_empty(s):
            empty[s.canteen_id] += SLOT_HOURS
        per_slot[s.at][s.canteen_id].append(s)
    peaks: dict[date, tuple[float, datetime]] = {}
    for at, by_canteen in per_slot.items():
        total = sum(z.occupied for zones in by_canteen.values() for z in zones)
        day = at.astimezone(CAMPUS_TZ).date()
        if day not in peaks or total > peaks[day][0]:
            peaks[day] = (total, at)
    cvs = []
    for _, at in peaks.values():
        shares = [
            sum(z.occupied for z in zones) / sum(z.capacity for z in zones)
            for zones in per_slot[at].values()
            if sum(z.capacity for z in zones)
        ]
        if len(shares) >= 2 and mean(shares) > 0:
            cvs.append(pstdev(shares) / mean(shares))
    canteens = [
        CanteenUse(cid, round(used[cid], 1), round(available[cid], 1), round(empty[cid], 1))
        for cid in sorted(available)
    ]
    return Utilisation(canteens=canteens, peak_cv=round(mean(cvs), 3) if cvs else None, peak_days=len(cvs))

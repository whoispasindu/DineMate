from collections.abc import Iterable
from dataclasses import dataclass, field
from math import hypot


@dataclass(frozen=True)
class StaySettings:
    rejoin_s: float = 90.0
    rejoin_distance: float = 0.06


@dataclass
class Stay:
    started: float
    last_seen: float
    x: float
    y: float


@dataclass
class StayClock:
    settings: StaySettings = field(default_factory=StaySettings)
    active: dict[int, Stay] = field(default_factory=dict)
    lost: dict[int, Stay] = field(default_factory=dict)

    def _rejoin(self, track: int, x: float, y: float) -> Stay | None:
        if track in self.lost:
            return self.lost.pop(track)
        near = [
            (hypot(stay.x - x, stay.y - y), key)
            for key, stay in self.lost.items()
            if hypot(stay.x - x, stay.y - y) <= self.settings.rejoin_distance
        ]
        if not near:
            return None
        return self.lost.pop(min(near)[1])

    def update(self, seated: Iterable[tuple[int, float, float]], now: float) -> dict[int, float]:
        self.lost = {t: s for t, s in self.lost.items() if now - s.last_seen <= self.settings.rejoin_s}
        seen = set()
        for track, x, y in seated:
            seen.add(track)
            stay = self.active.get(track) or self._rejoin(track, x, y) or Stay(now, now, x, y)
            stay.last_seen, stay.x, stay.y = now, x, y
            self.active[track] = stay
        for track in [t for t in self.active if t not in seen]:
            self.lost[track] = self.active.pop(track)
        return {track: now - stay.started for track, stay in self.active.items()}


def stay_text(seconds: float) -> str:
    minutes = int(seconds // 60)
    if minutes < 1:
        return "<1 min"
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    unit = "hour" if hours == 1 else "hours"
    return f"{hours} {unit}" if rest == 0 else f"{hours} {unit} {rest} min"

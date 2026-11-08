import logging
import math
import random
import sys
import time as systime
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import Settings, get_settings
from app.sim import ApiClient

OPEN_HOUR, CLOSE_HOUR = 7, 21
HOURLY = {
    7: 0.3,
    8: 0.7,
    9: 0.6,
    10: 0.45,
    11: 0.6,
    12: 1.0,
    13: 1.0,
    14: 0.7,
    15: 0.5,
    16: 0.6,
    17: 0.75,
    18: 0.85,
    19: 0.7,
    20: 0.35,
}
BASE_STAY = (28.0, 42.0, 60.0)
ARRIVAL_PER_MIN = 0.045
BAG_CHANCE = 0.12
PLATES_CHANCE = 0.85
STEP = timedelta(minutes=1)

log = logging.getLogger("dinemate.cafe_sim")


@dataclass(frozen=True)
class SimTable:
    table_id: str
    zone_id: str
    seat_ids: tuple[str, ...]


@dataclass
class TableRun:
    party: int = 0
    seated_at: datetime | None = None
    leaves_at: datetime | None = None
    bag_until: datetime | None = None
    plates_until: datetime | None = None
    since: dict[str, datetime] = field(default_factory=dict)
    states: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SimVisit:
    table_id: str
    started_at: datetime
    ended_at: datetime
    party_size: int


def stay_minutes(party: int, rng: random.Random) -> float:
    base = BASE_STAY[0 if party <= 2 else 1 if party <= 4 else 2]
    return max(6.0, base * math.exp(rng.gauss(0, 0.35)))


def party_for(seats: int, rng: random.Random) -> int:
    return max(1, min(seats, round(rng.triangular(1, seats, max(1, seats - 1)))))


def rate_at(local: datetime) -> float:
    return ARRIVAL_PER_MIN * HOURLY.get(local.hour, 0.0)


class CafeSim:
    def __init__(self, tables: list[SimTable], tz: ZoneInfo, rng: random.Random) -> None:
        self.tables = tables
        self.tz = tz
        self.rng = rng
        self.runs = {t.table_id: TableRun() for t in tables}
        self.visits: list[SimVisit] = []

    def _set(self, run: TableRun, seat: str, state: str, at: datetime) -> None:
        if run.states.get(seat) != state:
            run.states[seat] = state
            run.since[seat] = at

    def step(self, now: datetime) -> None:
        local = now.astimezone(self.tz)
        for table in self.tables:
            run = self.runs[table.table_id]
            if run.leaves_at is not None and now >= run.leaves_at and run.seated_at is not None:
                self.visits.append(SimVisit(table.table_id, run.seated_at, run.leaves_at, run.party))
                run.party, run.seated_at, run.leaves_at = 0, None, None
                if self.rng.random() < PLATES_CHANCE:
                    run.plates_until = now + timedelta(minutes=self.rng.uniform(2, 9))
            if run.bag_until is not None and now >= run.bag_until:
                run.bag_until = None
                party = party_for(len(table.seat_ids), self.rng)
                run.party, run.seated_at = party, now
                run.leaves_at = now + timedelta(minutes=stay_minutes(party, self.rng))
            if run.plates_until is not None and now >= run.plates_until:
                run.plates_until = None
            idle = run.party == 0 and run.bag_until is None and run.plates_until is None
            if idle and OPEN_HOUR <= local.hour < CLOSE_HOUR and self.rng.random() < rate_at(local):
                if self.rng.random() < BAG_CHANCE:
                    run.bag_until = now + timedelta(minutes=self.rng.uniform(2, 10))
                else:
                    party = party_for(len(table.seat_ids), self.rng)
                    run.party, run.seated_at = party, now
                    run.leaves_at = now + timedelta(minutes=stay_minutes(party, self.rng))
            for index, seat in enumerate(table.seat_ids):
                if index < run.party:
                    state = "occupied"
                elif index == 0 and run.bag_until is not None:
                    state = "held"
                else:
                    state = "free"
                self._set(run, seat, state, run.seated_at if state == "occupied" and run.seated_at else now)

    def idle(self) -> bool:
        return all(r.party == 0 and r.bag_until is None and r.plates_until is None for r in self.runs.values())

    def next_open(self, at: datetime) -> datetime:
        local = at.astimezone(self.tz)
        opening = local.replace(hour=OPEN_HOUR, minute=0, second=0, microsecond=0)
        if local.hour >= OPEN_HOUR:
            opening += timedelta(days=1)
        return opening.astimezone(at.tzinfo)

    def run_until(self, start: datetime, end: datetime) -> None:
        at = start
        while at <= end:
            hour = at.astimezone(self.tz).hour
            if not OPEN_HOUR <= hour < CLOSE_HOUR and self.idle():
                at = min(self.next_open(at), end + STEP)
                continue
            self.step(at)
            at += STEP

    def seats(self, now: datetime) -> list[dict[str, Any]]:
        out = []
        for table in self.tables:
            run = self.runs[table.table_id]
            for seat in table.seat_ids:
                state = run.states.get(seat, "free")
                since = run.since.get(seat, now)
                out.append(
                    {
                        "seat_id": seat,
                        "zone_id": table.zone_id,
                        "state": state,
                        "for_s": max(0.0, (now - since).total_seconds()),
                        "since": since,
                        "free_soon": state == "free" and run.plates_until is not None,
                    }
                )
        return out


def zone_summaries(seats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    zones: dict[str, dict[str, Any]] = {}
    for seat in seats:
        zone = zones.setdefault(
            seat["zone_id"],
            {"zone_id": seat["zone_id"], "free": 0, "occupied": 0, "held": 0, "unknown": 0, "free_soon": 0},
        )
        zone[seat["state"]] += 1
        zone["free_soon"] += int(seat["free_soon"])
    return list(zones.values())


def tables_from_config(config: dict[str, Any]) -> list[SimTable]:
    out = []
    for zone in config.get("zones", []):
        groups: dict[str, list[str]] = {}
        for seat in zone.get("seats", []):
            groups.setdefault(str(seat["seat_id"]).split("-")[0], []).append(str(seat["seat_id"]))
        out.extend(SimTable(name, str(zone["zone_id"]), tuple(seats)) for name, seats in groups.items())
    return out


def run(settings: Settings, rng: random.Random) -> None:
    client = ApiClient(settings.simulator_api_url, settings.simulator_token)
    device_id = settings.cafe_simulator_device
    sim: CafeSim | None = None
    offset = timedelta(0)
    while True:
        try:
            if sim is None:
                status, body, _ = client._request("GET", f"/devices/{device_id}/config")
                if status == 200 and body:
                    offset = datetime.fromisoformat(body["server_time"]) - datetime.now(UTC)
                    sim = CafeSim(tables_from_config(body), ZoneInfo(settings.cafe_timezone), rng)
                    now = datetime.now(UTC) + offset
                    sim.run_until(now - timedelta(hours=2), now)
            if sim is not None:
                now = datetime.now(UTC) + offset
                sim.step(now)
                seats = sim.seats(now)
                payload = {
                    "captured_at": datetime.now(UTC).isoformat(),
                    "zones": zone_summaries(seats),
                    "seats": [{k: v for k, v in s.items() if k != "since"} for s in seats],
                }
                client._request("POST", f"/devices/{device_id}/seats", payload)
                log.info("%s: posted %d simulated seats", device_id, len(seats))
        except (OSError, RuntimeError, KeyError) as exc:
            log.warning("%s: %s", device_id, exc)
            sim = None
        systime.sleep(settings.cafe_simulator_interval_s)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = get_settings()
    log.info(
        "Sample café simulator posting seat snapshots for %s (stored as simulated)", settings.cafe_simulator_device
    )
    run(settings, random.Random())
    return 0


if __name__ == "__main__":
    sys.exit(main())

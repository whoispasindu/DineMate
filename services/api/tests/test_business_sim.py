import random
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.business.sim import CLOSE_HOUR, OPEN_HOUR, CafeSim, SimTable, tables_from_config, zone_summaries

TZ = ZoneInfo("Asia/Colombo")
TABLES = [SimTable("T1", "z1", ("T1-1", "T1-2")), SimTable("T4", "z1", ("T4-1", "T4-2", "T4-3", "T4-4"))]


def run_day() -> CafeSim:
    sim = CafeSim(TABLES, TZ, random.Random(7))
    start = datetime(2026, 11, 19, 0, 0, tzinfo=TZ).astimezone(UTC)
    sim.run_until(start, start + timedelta(days=1))
    return sim


def test_a_day_produces_visits_only_while_open_and_within_table_size() -> None:
    sim = run_day()
    assert len(sim.visits) > 10
    seats = {t.table_id: len(t.seat_ids) for t in TABLES}
    for visit in sim.visits:
        local = visit.started_at.astimezone(TZ)
        assert OPEN_HOUR <= local.hour < CLOSE_HOUR
        assert 1 <= visit.party_size <= seats[visit.table_id]
        assert visit.ended_at > visit.started_at


def test_seat_snapshot_matches_zone_summary() -> None:
    sim = CafeSim(TABLES, TZ, random.Random(3))
    lunch = datetime(2026, 11, 20, 12, 0, tzinfo=TZ).astimezone(UTC)
    sim.run_until(lunch - timedelta(hours=2), lunch)
    seats = sim.seats(lunch)
    assert {s["seat_id"] for s in seats} == {sid for t in TABLES for sid in t.seat_ids}
    (zone,) = zone_summaries(seats)
    assert zone["free"] + zone["occupied"] + zone["held"] + zone["unknown"] == 6
    assert all(s["for_s"] >= 0 for s in seats)


def test_tables_are_grouped_from_seat_ids_in_the_device_config() -> None:
    config = {
        "zones": [
            {"zone_id": "z1", "seats": [{"seat_id": "T1-1"}, {"seat_id": "T1-2"}, {"seat_id": "T2-1"}]},
            {"zone_id": "z2", "seats": [{"seat_id": "T9-1"}]},
        ]
    }
    tables = tables_from_config(config)
    assert [(t.table_id, t.zone_id, len(t.seat_ids)) for t in tables] == [
        ("T1", "z1", 2),
        ("T2", "z1", 1),
        ("T9", "z2", 1),
    ]

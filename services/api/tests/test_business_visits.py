from datetime import UTC, datetime, timedelta

from app.business.tables import TableView
from app.business.visits import GRACE, OpenVisit, step

NOW = datetime(2026, 11, 20, 7, 0, tzinfo=UTC)
SEATED = NOW - timedelta(minutes=10)


def view(state: str, party: int = 0) -> TableView:
    return TableView(state=state, party_size=party, since=SEATED if state == "occupied" else None, plates_left=False)  # type: ignore[arg-type]


def visit(last_seen_ago: timedelta = timedelta(0), party: int = 2) -> OpenVisit:
    return OpenVisit(started_at=SEATED, last_seen_at=NOW - last_seen_ago, party_size=party)


def test_people_sitting_at_a_free_table_start_a_visit_when_they_sat_down() -> None:
    result = step(None, view("occupied", 3), NOW)
    assert result.kind == "start"
    assert result.started_at == SEATED
    assert result.party_size == 3


def test_open_visit_keeps_the_largest_party_seen() -> None:
    result = step(visit(party=4), view("occupied", 2), NOW)
    assert result.kind == "extend"
    assert result.party_size == 4
    assert result.last_seen_at == NOW


def test_standing_up_briefly_does_not_end_the_visit() -> None:
    assert step(visit(timedelta(seconds=30)), view("free"), NOW).kind == "none"


def test_empty_table_after_the_grace_period_ends_at_last_seen() -> None:
    last = GRACE + timedelta(seconds=5)
    result = step(visit(last), view("needs_clearing"), NOW)
    assert result.kind == "end"
    assert result.ended_at == NOW - last


def test_bag_left_on_the_seat_keeps_the_visit_going() -> None:
    result = step(visit(timedelta(minutes=5)), view("held"), NOW)
    assert result.kind == "extend"


def test_bag_alone_does_not_start_a_visit() -> None:
    assert step(None, view("held"), NOW).kind == "none"


def test_camera_gap_never_ends_a_visit() -> None:
    assert step(visit(timedelta(minutes=8)), view("unknown"), NOW).kind == "none"

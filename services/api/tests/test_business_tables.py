from datetime import UTC, datetime, timedelta

from app.business.tables import SeatView, table_state

NOW = datetime(2026, 11, 20, 7, 0, tzinfo=UTC)


def seat(state: str, minutes_ago: float = 5, free_soon: bool = False, updated_ago: float = 0) -> SeatView:
    return SeatView(
        state=state,
        since=NOW - timedelta(minutes=minutes_ago),
        free_soon=free_soon,
        updated_at=NOW - timedelta(minutes=updated_ago),
    )


def test_any_occupied_seat_makes_the_table_occupied_with_party_size() -> None:
    view = table_state([seat("occupied", 20), seat("occupied", 12), seat("free"), seat("held")], NOW)
    assert view.state == "occupied"
    assert view.party_size == 2
    assert view.since == NOW - timedelta(minutes=20)


def test_bag_without_people_is_held() -> None:
    view = table_state([seat("held", 9), seat("free")], NOW)
    assert view.state == "held"
    assert view.party_size == 0


def test_plates_left_on_an_empty_table_needs_clearing() -> None:
    view = table_state([seat("free", 4, free_soon=True), seat("free", 4)], NOW)
    assert view.state == "needs_clearing"
    assert view.plates_left


def test_marking_cleared_after_guests_left_frees_the_table() -> None:
    cleared = NOW - timedelta(minutes=1)
    view = table_state([seat("free", 4, free_soon=True)], NOW, cleared_at=cleared)
    assert view.state == "free"


def test_old_clear_does_not_hide_new_plates() -> None:
    cleared = NOW - timedelta(minutes=30)
    view = table_state([seat("free", 4, free_soon=True)], NOW, cleared_at=cleared)
    assert view.state == "needs_clearing"


def test_hidden_or_stale_seats_make_the_table_unknown() -> None:
    assert table_state([seat("unknown"), seat("unknown")], NOW).state == "unknown"
    assert table_state([seat("occupied", updated_ago=11)], NOW).state == "unknown"
    assert table_state([], NOW).state == "unknown"


def test_hidden_seats_are_ignored_when_others_are_seen() -> None:
    view = table_state([seat("unknown"), seat("occupied", 3)], NOW)
    assert view.state == "occupied"
    assert view.party_size == 1

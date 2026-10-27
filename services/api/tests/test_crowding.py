from datetime import UTC, datetime, timedelta
from itertools import pairwise

from app.services.crowding import (
    CrowdThresholds,
    LevelState,
    OpenAlert,
    decide,
    raw_level,
    step,
)

T = CrowdThresholds()
START = datetime(2026, 11, 20, 6, 0, tzinfo=UTC)


def at(seconds: float) -> datetime:
    return START + timedelta(seconds=seconds)


def test_raw_level_uses_hysteresis_only_on_the_way_down() -> None:
    assert raw_level(79, T, "normal") == "busy"
    assert raw_level(80, T, "busy") == "crowded"
    assert raw_level(77, T, "crowded") == "crowded"
    assert raw_level(74.9, T, "crowded") == "busy"
    assert raw_level(96, T, "normal") == "near_capacity"


def test_level_changes_only_after_dwell() -> None:
    state = LevelState()
    assert step(state, 85, at(0), T) is None
    assert step(state, 85, at(60), T) is None
    assert step(state, 85, at(120), T) == "crowded"
    assert state.level == "crowded"


def test_a_brief_spike_does_not_change_level() -> None:
    state = LevelState()
    step(state, 85, at(0), T)
    step(state, 50, at(30), T)
    assert step(state, 85, at(120), T) is None
    assert state.level == "normal"


def test_flapping_around_80_for_an_hour_opens_one_alert() -> None:
    state = LevelState(level="busy")
    alert: OpenAlert | None = None
    opened = 0
    changes: list[datetime] = []
    for i in range(120):
        now = at(i * 30)
        percent = 80 + (3 if i % 2 == 0 else -3)
        if step(state, percent, now, T):
            changes.append(now)
        action = decide(alert, state.level, True, now, None, T)
        if action.kind == "open":
            opened += 1
            alert = OpenAlert(state.level, "open")
        elif action.kind == "resolve":
            alert = None
    assert opened <= 1
    for earlier, later in pairwise(changes):
        assert later - earlier >= T.dwell


def test_alert_lifecycle() -> None:
    now = at(0)
    assert decide(None, "busy", True, now, None, T).kind == "none"
    assert decide(None, "crowded", True, now, None, T).kind == "open"
    open_alert = OpenAlert("crowded", "open")
    assert decide(open_alert, "near_capacity", True, now, None, T).kind == "escalate"
    assert decide(OpenAlert("crowded", "acknowledged"), "near_capacity", True, now, None, T).kind == "reopen"
    assert decide(OpenAlert("near_capacity", "acknowledged"), "crowded", True, now, None, T).kind == "deescalate"
    assert decide(open_alert, "crowded", True, now, None, T).kind == "none"
    assert decide(open_alert, "busy", True, now, None, T).kind == "resolve"


def test_stale_data_suspends_and_never_resolves() -> None:
    now = at(0)
    open_alert = OpenAlert("crowded", "open")
    assert decide(open_alert, "crowded", False, now, None, T).kind == "suspend"
    suspended = OpenAlert("crowded", "suspended")
    assert decide(suspended, "normal", False, now, None, T).kind == "none"
    assert decide(suspended, "crowded", True, now, None, T).kind == "resume"
    assert decide(suspended, "busy", True, now, None, T).kind == "resolve"
    assert decide(None, "crowded", False, now, None, T).kind == "none"


def test_cooldown_after_resolve_unless_near_capacity() -> None:
    resolved = at(0)
    assert decide(None, "crowded", True, at(300), resolved, T).kind == "none"
    assert decide(None, "near_capacity", True, at(300), resolved, T).kind == "open"
    assert decide(None, "crowded", True, at(601), resolved, T).kind == "open"

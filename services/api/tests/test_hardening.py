from datetime import UTC, datetime, timedelta

from app.core.security import after_failure, throttle_key
from app.services.livehosts import live_url_allowed

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
LOCK = timedelta(minutes=15)


def test_live_view_addresses_stay_on_the_local_network() -> None:
    for good in (
        "http://192.168.1.20:8090/live",
        "http://localhost:8100/live",
        "http://cafe-pc:8091/live",
        "http://till.local:8090/live",
        "http://[::1]:8090/live",
    ):
        assert live_url_allowed(good), good
    for bad in (
        "http://evil.example/live",
        "http://8.8.8.8:8090/live",
        "http://192.168.1.20:8090/other",
        "http://192.168.1.20:8090/live?next=x",
        "http://user:pw@192.168.1.20:8090/live",
        "ftp://192.168.1.20/live",
        "http://192.168.1.20:99999/live",
    ):
        assert not live_url_allowed(bad), bad
    assert live_url_allowed("https://cams.cafe.example/live", ["cams.cafe.example"])


def test_wrong_passwords_lock_after_the_limit_and_reset_after_the_window() -> None:
    failures, first, locked = 0, NOW, None
    for attempt in range(1, 4):
        failures, first, locked = after_failure(failures, first, NOW + timedelta(seconds=attempt), 3, LOCK)
    assert failures == 3 and locked == NOW + timedelta(seconds=3) + LOCK
    later = NOW + timedelta(minutes=40)
    assert after_failure(failures, first, later, 3, LOCK) == (1, later, None)
    assert throttle_key(" Admin@DineMate.test ") == throttle_key("admin@dinemate.test")

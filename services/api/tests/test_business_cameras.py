import pytest

from app.business.cameras import check_source, is_removed, label_of, source_hint
from app.core.config import Settings


def test_sources_are_camera_addresses_or_usb_numbers() -> None:
    assert (
        check_source(" rtsp://admin:secret@192.168.1.50:554/stream1 ") == "rtsp://admin:secret@192.168.1.50:554/stream1"
    )
    assert check_source("0") == "0"
    assert check_source("https://youtu.be/abc") == "https://youtu.be/abc"
    for bad in ("C:/videos/a.mp4", "ftp://cam/x", "rtsp://", "camera"):
        with pytest.raises(ValueError):
            check_source(bad)


def test_hints_never_show_passwords_or_paths() -> None:
    assert source_hint("rtsp://admin:secret@192.168.1.50:554/stream1") == "rtsp://192.168.1.50:554/…"
    assert source_hint("http://192.168.1.20:8080") == "http://192.168.1.20:8080"
    assert source_hint("https://www.youtube.com/watch?v=abc") == "https://www.youtube.com/…"
    assert source_hint("1") == "USB camera 1"
    assert source_hint(None) is None


def test_labels_and_removed_flags() -> None:
    assert label_of({"label": "Counter"}, "cam-1") == "Counter"
    assert label_of({}, "cam-1") == "cam-1"
    assert is_removed({"removed": True}) and not is_removed(None)


def test_cookies_follow_the_environment_unless_set() -> None:
    secret = "x" * 40
    assert Settings(environment="development").secure_cookies is False
    assert Settings(environment="production", jwt_secret=secret).secure_cookies is True
    assert Settings(environment="production", jwt_secret=secret, cookie_secure=False).secure_cookies is False
    assert Settings(environment="production", jwt_secret=secret, cookie_secure="").secure_cookies is True

import re

import pytest

from app.business.cameras import check_source, source_hint
from app.testfeeds.videos import is_test_source, is_youtube, source_for, stored_name, video_name


def test_uploads_get_safe_unique_names() -> None:
    name = stored_name("C:\\Clips\\Lunch Rush (cam 2).MP4")
    assert re.fullmatch(r"lunch-rush-cam-2-[0-9a-f]{6}\.mp4", name)
    assert stored_name("Lunch.mp4") != stored_name("Lunch.mp4")
    assert stored_name("....mov").startswith("video-")
    with pytest.raises(ValueError):
        stored_name("notes.txt")


def test_video_sources_only_name_stored_files() -> None:
    good = source_for(stored_name("a.mp4"))
    assert video_name(good) == good.removeprefix("video:")
    assert check_source(good) == good
    for bad in ("video:../etc/passwd", "video:a.mp4", "video:/data/x-abcdef.mp4"):
        assert video_name(bad) is None
        with pytest.raises(ValueError):
            check_source(bad)
    assert source_hint(good) == f"Test video · {video_name(good)}"


def test_youtube_links_count_as_test_sources() -> None:
    assert is_youtube("https://youtu.be/abc") and is_youtube("https://www.youtube.com/live/xyz?si=1")
    assert not is_youtube("https://youtube.com.evil.test/x") and not is_youtube("rtsp://cam/1")
    assert is_test_source("video:a-abcdef.mp4") and not is_test_source(None)

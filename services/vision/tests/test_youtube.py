import pytest

from vision.youtube import is_youtube, pick


@pytest.mark.parametrize(
    "link",
    [
        "https://www.youtube.com/live/YWs0HMRVCBY?si=abc",
        "https://youtu.be/vls4DGvdqgM?si=abc",
        "https://www.youtube.com/watch?v=vls4DGvdqgM",
        "http://m.youtube.com/watch?v=x",
    ],
)
def test_youtube_links_are_recognised(link: str) -> None:
    assert is_youtube(link)


@pytest.mark.parametrize(
    "spec", ["0", "data/videos/canteen.mp4", "rtsp://192.168.1.20/stream", "https://example.com/live.m3u8"]
)
def test_other_sources_are_not_youtube(spec: str) -> None:
    assert not is_youtube(spec)


def test_pick_uses_the_direct_url_or_the_video_part_of_a_split_format() -> None:
    live = pick({"url": "https://hls/x.m3u8", "title": "Street cam", "is_live": True})
    assert live.url == "https://hls/x.m3u8" and live.is_live and live.title == "Street cam"
    split = pick(
        {
            "requested_formats": [{"url": "https://v", "vcodec": "avc1"}, {"url": "https://a", "vcodec": "none"}],
            "is_live": False,
        }
    )
    assert split.url == "https://v" and not split.is_live
    with pytest.raises(OSError):
        pick({"requested_formats": [{"url": "https://a", "vcodec": "none"}]})

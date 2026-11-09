import pytest

from vision.youtube import is_network_stream, is_youtube, pick


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


@pytest.mark.parametrize(
    "spec",
    ["rtsp://user:pass@192.168.1.20:554/stream1", "http://192.168.1.31:8080/video", "HTTPS://cam.local/live.m3u8"],
)
def test_camera_urls_are_network_streams(spec: str) -> None:
    assert is_network_stream(spec)


@pytest.mark.parametrize("spec", ["0", "data/videos/canteen.mp4", "https://youtu.be/vls4DGvdqgM"])
def test_files_webcams_and_youtube_are_not_network_streams(spec: str) -> None:
    assert not is_network_stream(spec)


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

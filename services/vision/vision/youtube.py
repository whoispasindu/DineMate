import re
from dataclasses import dataclass
from typing import Any

YOUTUBE = re.compile(r"^https?://(www\.|m\.)?(youtube\.com/(watch|live/|shorts/)|youtu\.be/)", re.IGNORECASE)
FORMAT = (
    "bestvideo[height<=720][vcodec^=avc1]/best[height<=720][vcodec^=avc1]/bestvideo[height<=720]/best[height<=720]/best"
)


@dataclass(frozen=True)
class RemoteStream:
    url: str
    title: str
    is_live: bool


def is_youtube(spec: str) -> bool:
    return bool(YOUTUBE.match(spec.strip()))


def pick(info: dict[str, Any]) -> RemoteStream:
    url = info.get("url")
    if not url:
        formats = [f for f in info.get("requested_formats") or [] if f.get("vcodec") not in (None, "none")]
        url = formats[0]["url"] if formats else None
    if not url:
        raise OSError("YouTube gave no playable video stream for this link.")
    return RemoteStream(str(url), str(info.get("title") or "YouTube video"), bool(info.get("is_live")))


def resolve(link: str) -> RemoteStream:
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
    except ImportError as exc:
        raise OSError("YouTube sources need yt-dlp: uv run --with yt-dlp python -m vision.worker ...") from exc
    options = {"format": FORMAT, "quiet": True, "no_warnings": True, "noplaylist": True}
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(link, download=False)
    except DownloadError as exc:
        raise OSError(f"Could not open the YouTube link: {exc}") from exc
    if not isinstance(info, dict):
        raise OSError("YouTube gave no details for this link.")
    return pick(info)

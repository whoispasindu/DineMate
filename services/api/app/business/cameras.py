import re
from typing import Any
from urllib.parse import urlsplit

from app.testfeeds.videos import check_video_source, is_video_source, video_hint

SCHEMES = ("rtsp", "rtsps", "http", "https")
USB = re.compile(r"^\d{1,2}$")
WAITING = "waiting for zones"


def check_source(source: str) -> str:
    value = source.strip()
    if is_video_source(value):
        return check_video_source(value)
    if USB.match(value):
        return value
    parts = urlsplit(value)
    if parts.scheme.lower() not in SCHEMES or not parts.hostname:
        raise ValueError("Use an rtsp://, http:// or https:// camera address, or a USB camera number like 0.")
    return value


def source_hint(source: str | None) -> str | None:
    if not source:
        return None
    if is_video_source(source):
        return video_hint(source)
    if USB.match(source):
        return f"USB camera {source}"
    parts = urlsplit(source)
    if not parts.hostname:
        return None
    port = f":{parts.port}" if parts.port else ""
    tail = "/…" if parts.path.strip("/") or parts.query else ""
    return f"{parts.scheme}://{parts.hostname}{port}{tail}"


DETAIL_SIZES: dict[str, int | None] = {"auto": None, "standard": 640, "high": 1280}


def detail_of(config: dict[str, Any] | None) -> str:
    size = (config or {}).get("imgsz")
    return next((name for name, value in DETAIL_SIZES.items() if value == size), "auto")


def with_detail(config: dict[str, Any], detail: str | None) -> dict[str, Any]:
    if detail is None:
        return config
    updated = {key: value for key, value in config.items() if key != "imgsz"}
    if DETAIL_SIZES[detail] is not None:
        updated["imgsz"] = DETAIL_SIZES[detail]
    return updated


def is_removed(config: dict[str, Any] | None) -> bool:
    return bool((config or {}).get("removed"))


def label_of(config: dict[str, Any] | None, device_id: str) -> str:
    return str((config or {}).get("label") or device_id)

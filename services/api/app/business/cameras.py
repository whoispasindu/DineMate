import re
from typing import Any
from urllib.parse import urlsplit

SCHEMES = ("rtsp", "rtsps", "http", "https")
USB = re.compile(r"^\d{1,2}$")
WAITING = "waiting for zones"


def check_source(source: str) -> str:
    value = source.strip()
    if USB.match(value):
        return value
    parts = urlsplit(value)
    if parts.scheme.lower() not in SCHEMES or not parts.hostname:
        raise ValueError("Use an rtsp://, http:// or https:// camera address, or a USB camera number like 0.")
    return value


def source_hint(source: str | None) -> str | None:
    if not source:
        return None
    if USB.match(source):
        return f"USB camera {source}"
    parts = urlsplit(source)
    if not parts.hostname:
        return None
    port = f":{parts.port}" if parts.port else ""
    tail = "/…" if parts.path.strip("/") or parts.query else ""
    return f"{parts.scheme}://{parts.hostname}{port}{tail}"


def is_removed(config: dict[str, Any] | None) -> bool:
    return bool((config or {}).get("removed"))


def label_of(config: dict[str, Any] | None, device_id: str) -> str:
    return str((config or {}).get("label") or device_id)

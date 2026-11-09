from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas import Schema, Timestamped


class UploadedVideo(Timestamped):
    source: str
    name: str
    size_mb: float


class VideoFeedIn(Schema):
    label: str = Field(min_length=1, max_length=40)
    source: str = Field(min_length=1, max_length=500)


class VideoFeed(Schema):
    id: str
    canteen_id: str
    canteen_name: str
    label: str
    source_hint: str | None
    status: Literal["ok", "waiting_for_zones", "starting", "offline"]
    last_seen_at: datetime | None
    fps: float | None
    zones: list[str]
    has_layout: bool


class VideoFeedList(Timestamped):
    items: list[VideoFeed]
    max_feeds: int


class VideoFeedResult(Timestamped):
    feed: VideoFeed


class VideoFeedRemoved(Timestamped):
    device_id: str

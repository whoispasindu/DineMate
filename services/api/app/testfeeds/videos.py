import re
import secrets
from pathlib import Path, PurePath

PREFIX = "video:"
EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")
STORED = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}-[0-9a-f]{6}\.(mp4|mov|mkv|avi|webm|m4v)$")
SLUG = re.compile(r"[^a-z0-9]+")
YOUTUBE_HOSTS = ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be")


def stored_name(filename: str) -> str:
    path = PurePath(filename.replace("\\", "/"))
    extension = path.suffix.lower()
    if extension not in EXTENSIONS:
        raise ValueError(f"Upload a video file ({', '.join(EXTENSIONS)}).")
    slug = SLUG.sub("-", path.stem.lower()).strip("-")[:40].strip("-") or "video"
    return f"{slug}-{secrets.token_hex(3)}{extension}"


def is_video_source(source: str | None) -> bool:
    return bool(source) and str(source).startswith(PREFIX)


def video_name(source: str | None) -> str | None:
    if not is_video_source(source):
        return None
    name = str(source)[len(PREFIX) :]
    return name if STORED.match(name) else None


def source_for(name: str) -> str:
    return f"{PREFIX}{name}"


def check_video_source(source: str) -> str:
    if video_name(source) is None:
        raise ValueError("That test video is not on this computer. Upload it again.")
    return source


def video_hint(source: str) -> str:
    return f"Test video · {video_name(source) or 'missing'}"


def is_youtube(source: str | None) -> bool:
    if not source:
        return False
    match = re.match(r"^https?://([^/:?#]+)", source.strip(), re.IGNORECASE)
    return bool(match) and match.group(1).lower() in YOUTUBE_HOSTS


def is_test_source(source: str | None) -> bool:
    return is_video_source(source) or is_youtube(source)


def video_path(folder: Path, source: str | None) -> Path | None:
    name = video_name(source)
    return folder / name if name else None

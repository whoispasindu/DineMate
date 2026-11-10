from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.core.config import Settings
from app.core.errors import ApiError
from app.testfeeds.videos import is_video_source, video_path

ORPHAN_AFTER_S = 3600.0


def videos_dir(settings: Settings) -> Path:
    folder = Path(settings.test_videos_dir)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def require_video(settings: Settings, source: str) -> str:
    path = video_path(videos_dir(settings), source)
    if is_video_source(source) and (path is None or not path.is_file()):
        raise ApiError(422, "validation_error", "That test video is not on this computer. Upload it again.")
    return source


def sources_in_use(session: Session) -> set[str]:
    rows = session.scalars(select(models.Device.config).where(models.Device.kind == "camera"))
    return {str(config["source"]) for config in rows if config and config.get("source") and not config.get("removed")}


def purge_orphans(session: Session, settings: Settings, now_ts: float, older_than_s: float = ORPHAN_AFTER_S) -> int:
    used = {video_path(videos_dir(settings), source) for source in sources_in_use(session)}
    removed = 0
    for path in videos_dir(settings).iterdir():
        if path.is_file() and path not in used and now_ts - path.stat().st_mtime > older_than_s:
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def forget_video(session: Session, settings: Settings, source: str | None) -> None:
    if not is_video_source(source) or source in sources_in_use(session):
        return
    path = video_path(videos_dir(settings), source)
    if path is not None:
        path.unlink(missing_ok=True)

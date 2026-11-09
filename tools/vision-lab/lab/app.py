import csv
import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lab.session import VIDEO_TYPES, VIDEOS, Lab, LabError, RunSettings, list_videos, safe_name

STATIC = Path(__file__).resolve().parents[1] / "static"
STREAM_MAX_S = 3600
MAX_UPLOAD = 4 * 1024**3


class OpenIn(BaseModel):
    source: str
    at_s: float = Field(default=5.0, ge=0)


class ZonesIn(BaseModel):
    zones: list[dict[str, Any]]


class LayoutIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class RunIn(BaseModel):
    dwell_s: float = Field(default=20.0, ge=0, le=300)
    smoothing_s: float = Field(default=15.0, ge=1, le=300)
    fps: float = Field(default=4.0, ge=0.5, le=15)
    blur: bool = True
    min_gap_s: float = Field(default=30.0, ge=1, le=3600)


class BadgeIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    code: int = Field(ge=0, le=249)


class EnrolIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    consent: bool = False


class MarkIn(BaseModel):
    zone: str
    delta: int | None = None
    count: int | None = Field(default=None, ge=0, le=500)


def create_app(lab: Lab) -> FastAPI:
    app = FastAPI(title="DineMate vision lab", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.exception_handler(LabError)
    def lab_error(_: Request, exc: LabError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(OSError)
    def os_error(_: Request, exc: OSError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.get("/api/videos")
    def videos() -> dict[str, Any]:
        return {"folder": "data/videos", "items": list_videos()}

    @app.put("/api/videos/{name}")
    async def upload(name: str, request: Request) -> dict[str, Any]:
        file = safe_name(name, VIDEO_TYPES)
        VIDEOS.mkdir(parents=True, exist_ok=True)
        target, size = VIDEOS / file, 0
        partial = target.with_suffix(target.suffix + ".part")
        with partial.open("wb") as handle:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_UPLOAD:
                    handle.close()
                    partial.unlink(missing_ok=True)
                    raise HTTPException(413, "That video is over 4 GB.")
                handle.write(chunk)
        partial.replace(target)
        return {"name": file, "bytes": size}

    @app.post("/api/open")
    def open_source(body: OpenIn) -> dict[str, Any]:
        return lab.open(body.source, body.at_s)

    @app.get("/api/still.jpg")
    def still() -> Response:
        if lab.still is None:
            raise HTTPException(404, "Open a source first.")
        return Response(lab.still, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.put("/api/zones")
    def zones(body: ZonesIn) -> dict[str, Any]:
        return {"zones": lab.set_zones(body.zones)}

    @app.get("/api/layouts")
    def layouts() -> dict[str, Any]:
        return {"items": lab.layouts()}

    @app.post("/api/layouts")
    def save_layout(body: LayoutIn) -> dict[str, Any]:
        return {"file": lab.save_layout(body.name)}

    @app.get("/api/layouts/{file}")
    def load_layout(file: str) -> dict[str, Any]:
        return {"zones": lab.load_layout(file)}

    @app.post("/api/run")
    def run(body: RunIn) -> dict[str, Any]:
        lab.start(RunSettings(body.dwell_s, body.smoothing_s, body.fps, body.blur, body.min_gap_s))
        return lab.state()

    @app.post("/api/pause")
    def pause() -> dict[str, Any]:
        lab.pause(True)
        return lab.state()

    @app.post("/api/resume")
    def resume() -> dict[str, Any]:
        lab.pause(False)
        return lab.state()

    @app.post("/api/stop")
    def stop() -> dict[str, Any]:
        lab.stop()
        return lab.state()

    @app.get("/api/state")
    def state() -> dict[str, Any]:
        return lab.state()

    @app.post("/api/staff/badge")
    def badge(body: BadgeIn) -> dict[str, Any]:
        lab.add_badge(body.name, body.code)
        return {"staff": lab.staff_view()}

    @app.post("/api/staff/enrol")
    def enrol(body: EnrolIn) -> dict[str, Any]:
        return {"note": lab.request_enrol(body.name, body.x, body.y, body.consent)}

    @app.delete("/api/staff/{staff_id}")
    def remove_staff(staff_id: str) -> dict[str, Any]:
        lab.remove_staff(staff_id)
        return {"staff": lab.staff_view()}

    @app.post("/api/mark")
    def mark(body: MarkIn) -> dict[str, Any]:
        return {"counts": lab.mark(body.zone, body.delta, body.count)}

    @app.get("/api/report")
    def report(skip_s: float = 0.0) -> dict[str, Any]:
        return lab.report(max(0.0, skip_s))

    @app.get("/api/export.csv")
    def export() -> Response:
        buffer = io.StringIO()
        csv.writer(buffer).writerows(lab.csv())
        return Response(
            buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="vision-lab-counts.csv"'},
        )

    @app.get("/api/stream.mjpeg")
    def stream() -> StreamingResponse:
        from vision.stream import BOUNDARY, part

        def frames() -> Iterator[bytes]:
            import time

            lab.hub.join()
            started, sequence = time.monotonic(), 0
            try:
                while time.monotonic() - started < STREAM_MAX_S:
                    fresh, jpeg = lab.hub.wait(sequence, 2.0)
                    if fresh != sequence and jpeg is not None:
                        yield part(jpeg)
                    sequence = fresh
            finally:
                lab.hub.leave()

        return StreamingResponse(
            frames(),
            media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
            headers={"Cache-Control": "no-store"},
        )

    return app

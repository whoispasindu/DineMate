import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lab.compare import Mark, Sample, compare, csv_rows

REPO = Path(__file__).resolve().parents[3]
VISION = REPO / "services" / "vision"
VIDEOS = REPO / "data" / "videos"
LAYOUTS = VISION / "layouts"
VIDEO_TYPES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
SAMPLE_EVERY_S = 1.0
PREVIEW_LIMITS = (1280, 720)

log = logging.getLogger("vision-lab")


class LabError(Exception):
    pass


@dataclass
class RunSettings:
    dwell_s: float = 20.0
    smoothing_s: float = 15.0
    fps: float = 4.0
    blur: bool = True


def safe_name(name: str, suffixes: set[str] | None = None) -> str:
    clean = re.sub(r"[^A-Za-z0-9._ -]", "", Path(name).name).strip()
    if not clean or clean.startswith("."):
        raise LabError("That file name is not allowed.")
    if suffixes is not None and Path(clean).suffix.lower() not in suffixes:
        raise LabError(f"Use one of: {', '.join(sorted(suffixes))}.")
    return clean


def list_videos() -> list[str]:
    if not VIDEOS.is_dir():
        return []
    return sorted(p.name for p in VIDEOS.iterdir() if p.suffix.lower() in VIDEO_TYPES)


def resolve_source(spec: str) -> str:
    spec = spec.strip()
    if not spec:
        raise LabError("Paste a link or pick a video.")
    if spec.startswith(("http://", "https://", "rtsp://")) or spec.isdigit():
        return spec
    path = VIDEOS / safe_name(spec, VIDEO_TYPES)
    if not path.is_file():
        raise LabError(f"{path.name} is not in data/videos.")
    return str(path)


def zone_config(zones: list[dict[str, Any]], settings: RunSettings) -> dict[str, Any]:
    from vision.worker import DEFAULT_SETTINGS

    seating = [z for z in zones if z["kind"] == "seating"]
    queues = [z for z in zones if z["kind"] == "queue"]
    return {
        "zones": [
            {"zone_id": z["id"], "name": z["name"], "capacity": int(z["capacity"]), "points": z["points"], "seats": []}
            for z in seating
        ],
        "ignore": [{"type": "queue", "points": z["points"]} for z in queues],
        "work": [],
        "settings": {
            **DEFAULT_SETTINGS,
            "dwell_s": settings.dwell_s,
            "smoothing_s": settings.smoothing_s,
            "fps": settings.fps,
        },
    }


def check_zones(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise LabError("Zones must be a list.")
    zones = []
    for index, z in enumerate(raw):
        points = [[float(x), float(y)] for x, y in z.get("points", [])]
        if len(points) < 3 or not all(0 <= v <= 1 for p in points for v in p):
            raise LabError(f"Zone {index + 1} needs at least 3 points inside the frame.")
        kind = z.get("kind", "seating")
        if kind not in ("seating", "queue"):
            raise LabError("A zone is either seating or queue.")
        zones.append(
            {
                "id": str(z.get("id") or f"z{index + 1}"),
                "name": str(z.get("name") or f"Zone {index + 1}")[:40],
                "kind": kind,
                "capacity": max(1, int(z.get("capacity") or 10)),
                "points": points,
            }
        )
    return zones


class Lab:
    def __init__(self, model: Path, pose_model: Path) -> None:
        from vision.stream import FrameHub

        self.model, self.pose_model = model, pose_model
        self.lock = threading.Lock()
        self.hub = FrameHub()
        self.spec: str | None = None
        self.label = ""
        self.is_live = False
        self.still: bytes | None = None
        self.size = (0, 0)
        self.zones: list[dict[str, Any]] = []
        self.thread: threading.Thread | None = None
        self.stop_flag = threading.Event()
        self.paused = False
        self.status = "idle"
        self.error: str | None = None
        self.t = 0.0
        self.ours: dict[str, float] = {}
        self.ours_now: dict[str, int] = {}
        self.samples: list[Sample] = []
        self.marks: list[Mark] = []
        self.counts: dict[str, int] = {}
        self.fps_seen = 0.0

    def open(self, spec: str, at_s: float = 5.0) -> dict[str, Any]:
        import cv2

        from vision.source import grab_still
        from vision.youtube import is_youtube, resolve

        source = resolve_source(spec)
        self.stop()
        title, live = Path(source).name, source.isdigit()
        if is_youtube(source):
            remote = resolve(source)
            title, live = remote.title, remote.is_live
        image = grab_still(source, 0.0 if live else at_s)
        ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise LabError("Could not read a frame from that source.")
        with self.lock:
            self.spec, self.label, self.is_live = source, title, live
            self.still = jpeg.tobytes()
            self.size = (int(image.shape[1]), int(image.shape[0]))
            self.zones, self.status, self.error = [], "ready", None
            self._reset_counts()
        return self.info()

    def info(self) -> dict[str, Any]:
        return {
            "source": self.spec,
            "title": self.label,
            "is_live": self.is_live,
            "width": self.size[0],
            "height": self.size[1],
        }

    def _reset_counts(self) -> None:
        self.t, self.ours, self.ours_now = 0.0, {}, {}
        self.samples, self.marks, self.counts = [], [], {}

    def set_zones(self, raw: Any) -> list[dict[str, Any]]:
        zones = check_zones(raw)
        with self.lock:
            if self.status == "running":
                raise LabError("Stop the run before changing zones.")
            self.zones = zones
        return zones

    def save_layout(self, name: str) -> str:
        file = f"test-lab-{safe_name(name).replace(' ', '-').lower()}.json"
        LAYOUTS.mkdir(parents=True, exist_ok=True)
        (LAYOUTS / file).write_text(json.dumps({"lab_zones": self.zones}, indent=2), encoding="utf-8")
        return file

    @staticmethod
    def layouts() -> list[str]:
        return sorted(p.name for p in LAYOUTS.glob("test-lab-*.json")) if LAYOUTS.is_dir() else []

    @staticmethod
    def load_layout(file: str) -> list[dict[str, Any]]:
        path = LAYOUTS / safe_name(file, {".json"})
        if not path.name.startswith("test-lab-") or not path.is_file():
            raise LabError("Layout not found.")
        return check_zones(json.loads(path.read_text(encoding="utf-8")).get("lab_zones", []))

    def start(self, settings: RunSettings) -> None:
        with self.lock:
            if self.spec is None:
                raise LabError("Open a source first.")
            if not self.zones:
                raise LabError("Draw at least one zone first.")
            if self.status == "running":
                raise LabError("Already running.")
            self._reset_counts()
            self.stop_flag.clear()
            self.paused, self.status, self.error = False, "running", None
            self.thread = threading.Thread(target=self._run, args=(self.spec, list(self.zones), settings), daemon=True)
            self.thread.start()

    def stop(self) -> None:
        self.stop_flag.set()
        thread = self.thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=10)
        with self.lock:
            if self.status in ("running", "paused"):
                self.status = "stopped"

    def pause(self, paused: bool) -> None:
        with self.lock:
            if self.status not in ("running", "paused"):
                raise LabError("Nothing is running.")
            self.paused = paused
            self.status = "paused" if paused else "running"

    def mark(self, zone: str, delta: int | None, count: int | None) -> dict[str, int]:
        with self.lock:
            if zone not in {z["id"] for z in self.zones}:
                raise LabError("Unknown zone.")
            if self.status not in ("running", "paused"):
                raise LabError("Start the run, then count.")
            value = count if count is not None else self.counts.get(zone, 0) + (delta or 0)
            value = max(0, int(value))
            self.counts[zone] = value
            self.marks.append(Mark(self.t, zone, value))
            return dict(self.counts)

    def state(self) -> dict[str, Any]:
        with self.lock:
            return {
                "status": self.status,
                "error": self.error,
                "t": round(self.t, 1),
                "fps": round(self.fps_seen, 1),
                "zones": [
                    {
                        "id": z["id"],
                        "name": z["name"],
                        "kind": z["kind"],
                        "ours": self.ours.get(z["id"]),
                        "ours_now": self.ours_now.get(z["id"]),
                        "yours": self.counts.get(z["id"]),
                    }
                    for z in self.zones
                ],
            }

    def report(self, skip_s: float) -> dict[str, Any]:
        with self.lock:
            samples, marks, zones = list(self.samples), list(self.marks), list(self.zones)
        names = {z["id"]: z["name"] for z in zones}
        results = compare(samples, marks, [z["id"] for z in zones], skip_s)
        return {"zones": [{**r.summary(), "name": names[r.zone]} for r in results], "marks": len(marks)}

    def csv(self) -> list[list[object]]:
        with self.lock:
            return csv_rows(list(self.samples), list(self.marks), [z["id"] for z in self.zones])

    def _run(self, spec: str, zones: list[dict[str, Any]], settings: RunSettings) -> None:
        try:
            self._loop(spec, zones, settings)
            with self.lock:
                if self.status in ("running", "paused"):
                    self.status = "stopped" if self.stop_flag.is_set() else "finished"
        except Exception as exc:
            log.exception("run failed")
            with self.lock:
                self.status, self.error = "failed", f"{exc.__class__.__name__}: {exc}"

    def _loop(self, spec: str, zones: list[dict[str, Any]], settings: RunSettings) -> None:
        import cv2

        from vision.overlay import draw
        from vision.pipeline import Models, Pipeline
        from vision.source import FrameSource
        from vision.staff import QueueCounter, StaffSettings
        from vision.stream import blur, blur_boxes

        pipeline = Pipeline(zone_config(zones, settings), Models(str(self.model), str(self.pose_model), None))
        queue_settings = StaffSettings(queue_window_s=settings.smoothing_s)
        queues = {
            z["id"]: QueueCounter([[(x, y) for x, y in z["points"]]], queue_settings)
            for z in zones
            if z["kind"] == "queue"
        }
        source = FrameSource(spec, fps=settings.fps, realtime=True)
        first: float | None = None
        last_sample = -SAMPLE_EVERY_S
        rate_at, rate_frames = time.monotonic(), 0
        try:
            for frame in source.frames():
                if self.stop_flag.is_set():
                    break
                if self.paused:
                    paused_at = time.monotonic()
                    while self.paused and not self.stop_flag.is_set():
                        time.sleep(0.1)
                    source.resume_after_pause(time.monotonic() - paused_at)
                    continue
                first = frame.at if first is None else first
                t = frame.at - first
                assignments = pipeline.process(frame.image, frame.at)
                height, width = frame.image.shape[:2]
                ours: dict[str, float] = {r["zone_id"]: r["estimated_occupied"] for r in pipeline.readings()}
                now_counts = {z["id"]: 0 for z in zones}
                for a in assignments:
                    if a.counted and a.zone_id in now_counts:
                        now_counts[a.zone_id] += 1
                for zone_id, counter in queues.items():
                    now_counts[zone_id] = counter.update(pipeline.people_seen, width, height, frame.at, set())
                    reading = counter.reading()
                    if reading is not None:
                        ours[zone_id] = reading["people"]
                rate_frames += 1
                with self.lock:
                    self.t, self.ours, self.ours_now = t, ours, now_counts
                    if t - last_sample >= SAMPLE_EVERY_S:
                        last_sample = t
                        self.samples.append(Sample(t, dict(ours)))
                    elapsed = time.monotonic() - rate_at
                    if elapsed >= 2:
                        self.fps_seen, rate_at, rate_frames = rate_frames / elapsed, time.monotonic(), 0
                if self.hub.wanted(time.monotonic()):
                    image = (
                        blur(frame.image, blur_boxes(pipeline.people_seen, set(), width, height))
                        if settings.blur
                        else frame.image
                    )
                    shown = {r["zone_id"]: r for r in pipeline.readings()}
                    canvas = draw(
                        image,
                        pipeline.zones,
                        pipeline.ignore,
                        assignments,
                        shown,
                        f"t = {t:.0f} s",
                        PREVIEW_LIMITS,
                        pipeline.seat_states(),
                        None,
                        pipeline.work,
                        None,
                        pipeline.stay_labels(),
                    )
                    ok, jpeg = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    if ok:
                        self.hub.publish(jpeg.tobytes(), time.monotonic())
        finally:
            source.close()

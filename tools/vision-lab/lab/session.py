import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lab.compare import Mark, Sample, compare, csv_rows
from lab.workers import AREAS, Coverage, Enrolment, WorkerBook

REPO = Path(__file__).resolve().parents[3]
VISION = REPO / "services" / "vision"
VIDEOS = REPO / "data" / "videos"
LAYOUTS = VISION / "layouts"
VIDEO_TYPES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
SAMPLE_EVERY_S = 1.0
ENROL_EVERY_S = 0.5
COUNTED_KINDS = ("queue", "work")
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
    min_gap_s: float = 30.0


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
        "work": [{"area": z["area"], "points": z["points"]} for z in zones if z["kind"] == "work"],
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
        if kind not in ("seating", "queue", "work"):
            raise LabError("A zone is seating, queue or a work area.")
        area = z.get("area") if kind == "work" else None
        if kind == "work" and area not in AREAS:
            raise LabError("A work area is counter, kitchen or floor.")
        zones.append(
            {
                "id": str(z.get("id") or f"z{index + 1}"),
                "name": str(z.get("name") or f"Zone {index + 1}")[:40],
                "kind": kind,
                "area": area,
                "capacity": max(1, int(z.get("capacity") or 10)),
                "points": points,
            }
        )
    return zones


FOOT_IN = (0, 140, 255)
FOOT_OUT = (160, 160, 160)


def mark_feet(
    canvas: Any, people: list[Any], work: list[Any], width: int, height: int, area_of: Any, foot: Any
) -> None:
    import cv2

    scale_x, scale_y = canvas.shape[1] / width, canvas.shape[0] / height
    for person in people:
        x, y = foot(person, width, height)
        centre = (round(x * width * scale_x), round(y * height * scale_y))
        inside = area_of(work, x, y) is not None
        cv2.circle(canvas, centre, 7, FOOT_IN if inside else FOOT_OUT, -1, cv2.LINE_AA)
        cv2.circle(canvas, centre, 7, (255, 255, 255), 1, cv2.LINE_AA)


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
        self.staff: list[Any] = []
        self.staff_version = 0
        self.enrolment: Enrolment | None = None
        self.enrol_note: str | None = None
        self.last_people: list[Any] = []
        self.last_size = (1, 1)
        self.book: WorkerBook | None = None

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
            self.staff, self.staff_version, self.enrolment, self.enrol_note = [], self.staff_version + 1, None, None
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
        self.book = None

    @staticmethod
    def faces_ready() -> bool:
        from vision.faces import MODELS_DIR, models_ready

        return models_ready(MODELS_DIR)

    def add_badge(self, name: str, code: int) -> None:
        from vision.staff import StaffMember

        with self.lock:
            if any(s.badge_code == code for s in self.staff):
                raise LabError(f"Badge {code} is already used.")
            self.staff.append(StaffMember(f"lab-badge-{code}", name, "badge", code))
            self.staff_version += 1

    def remove_staff(self, staff_id: str) -> None:
        with self.lock:
            self.staff = [s for s in self.staff if s.staff_id != staff_id]
            self.staff_version += 1

    def request_enrol(self, name: str, x: float, y: float, consent: bool) -> str:
        if not consent:
            raise LabError("Only enrol people who agreed to be recognised. Tick the consent box first.")
        if not self.faces_ready():
            raise LabError("Face models are missing. Run: uv run python -m vision.fetch_models")
        with self.lock:
            if self.status not in ("running", "paused"):
                raise LabError("Start the run, then click a worker.")
            width, height = self.last_size
            px, py = x * width, y * height
            hits = [d for d in self.last_people if d.track_id is not None and d.x1 <= px <= d.x2 and d.y1 <= py <= d.y2]
            if not hits:
                raise LabError("No tracked person there. Click inside a box.")
            target = min(hits, key=lambda d: (d.x2 - d.x1) * (d.y2 - d.y1))
            self.enrolment = Enrolment(name, target.track_id, self.t)
            self.enrol_note = f"Enrolling {name}: hold on while they face the camera."
            return self.enrol_note

    def staff_view(self) -> list[dict[str, Any]]:
        return [
            {"id": s.staff_id, "name": s.display_name, "method": s.method, "badge_code": s.badge_code}
            for s in self.staff
        ]

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
            book = self.book
            return {
                "status": self.status,
                "error": self.error,
                "t": round(self.t, 1),
                "fps": round(self.fps_seen, 1),
                "workers": [
                    {"label": w.shown, "area": w.area, "total": round(sum(w.seconds.values()), 1)}
                    for w in (book.tracks.values() if book and self.status in ("running", "paused") else [])
                ],
                "coverage": book.coverage.summary(self.t) if book and book.coverage.open_s > 0 else None,
                "staff": self.staff_view(),
                "enrol": self.enrol_note,
                "faces_ready": self.faces_ready(),
                "zones": [
                    {
                        "id": z["id"],
                        "name": z["name"],
                        "kind": z["kind"],
                        "area": z.get("area"),
                        "capacity": z["capacity"],
                        "points": z["points"],
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
            workers = self.book.summary(self.t) if self.book else None
        names = {z["id"]: z["name"] for z in zones}
        results = compare(samples, marks, [z["id"] for z in zones], skip_s)
        return {
            "zones": [{**r.summary(), "name": names[r.zone]} for r in results],
            "marks": len(marks),
            "workers": workers,
        }

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

        from vision.faces import MODELS_DIR, FaceEmbedder, largest_face, models_ready
        from vision.identity import build_reader, crop, head_box
        from vision.overlay import draw
        from vision.pipeline import Models, Pipeline
        from vision.source import FrameSource
        from vision.staff import QueueCounter, StaffMember, StaffSettings, area_of, foot_point
        from vision.stream import blur, blur_boxes

        has_work = any(z["kind"] == "work" for z in zones)
        identity = build_reader(MODELS_DIR, faces=models_ready(MODELS_DIR), badges=True) if has_work else None
        with self.lock:
            staff, staff_version = list(self.staff), self.staff_version
        pipeline = Pipeline(
            zone_config(zones, settings),
            Models(str(self.model), str(self.pose_model), None),
            identity=identity,
            staff=staff,
        )
        queue_settings = StaffSettings(queue_window_s=settings.smoothing_s)
        queues = {
            z["id"]: QueueCounter([[(x, y) for x, y in z["points"]]], queue_settings)
            for z in zones
            if z["kind"] in COUNTED_KINDS
        }
        book = WorkerBook(coverage=Coverage(min_gap_s=settings.min_gap_s))
        has_counter = any(z.get("area") == "counter" for z in zones)
        with self.lock:
            self.book = book
        embedder: Any = None
        last_embed = -ENROL_EVERY_S
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
                with self.lock:
                    if self.staff_version != staff_version:
                        staff, staff_version = list(self.staff), self.staff_version
                        pipeline.set_staff(staff)
                assignments = pipeline.process(frame.image, frame.at)
                height, width = frame.image.shape[:2]
                names = {s.staff_id: s.display_name for s in staff}
                named = (
                    {track: names.get(sid, "") for track, (sid, _) in pipeline.named.items()}
                    if pipeline.staff_mode
                    else {}
                )
                views = pipeline.matcher.workers(pipeline.people_seen, pipeline.work, width, height) if has_work else []
                with self.lock:
                    book.update(
                        [
                            (v.detection.track_id, v.area, *foot_point(v.detection, width, height))
                            for v in views
                            if v.detection.track_id is not None
                        ],
                        named,
                        t,
                        has_counter,
                    )
                    worker_labels = book.labels()
                    enrolment = self.enrolment
                if enrolment is not None and t - last_embed >= ENROL_EVERY_S:
                    last_embed = t
                    target = next((d for d in pipeline.people_seen if d.track_id == enrolment.track), None)
                    box = head_box(target, width, height) if target is not None else None
                    if box is not None:
                        embedder = embedder or FaceEmbedder(MODELS_DIR)
                        region = crop(frame.image, box)
                        face = largest_face(embedder.faces(region), 32)
                        if face is not None:
                            enrolment.add(embedder.embed(region, face))
                    with self.lock:
                        self.enrol_note = (
                            f"Enrolling {enrolment.name}: {len(enrolment.samples)}/{enrolment.needed} shots"
                        )
                        if enrolment.done(t):
                            template = enrolment.template()
                            self.enrolment = None
                            if template is None:
                                self.enrol_note = (
                                    f"Could not enrol {enrolment.name}: not enough clear face shots. Try again."
                                )
                            else:
                                member_id = f"lab-face-{len(self.staff) + 1}-{int(t)}"
                                self.staff.append(StaffMember(member_id, enrolment.name, "face", None, tuple(template)))
                                self.staff_version += 1
                                self.enrol_note = f"Enrolled {enrolment.name} for this session (memory only)."

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
                    self.last_people, self.last_size = list(pipeline.people_seen), (width, height)
                    if t - last_sample >= SAMPLE_EVERY_S:
                        last_sample = t
                        self.samples.append(Sample(t, dict(ours)))
                    elapsed = time.monotonic() - rate_at
                    if elapsed >= 2:
                        self.fps_seen, rate_at, rate_frames = rate_frames / elapsed, time.monotonic(), 0
                if self.hub.wanted(time.monotonic()):
                    image = (
                        blur(frame.image, blur_boxes(pipeline.people_seen, pipeline.staff_tracks(), width, height))
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
                        [(d, worker_labels[d.track_id]) for d in pipeline.people_seen if d.track_id in worker_labels],
                        pipeline.stay_labels(),
                    )
                    if has_work:
                        mark_feet(canvas, pipeline.people_seen, pipeline.work, width, height, area_of, foot_point)
                    ok, jpeg = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 75])
                    if ok:
                        self.hub.publish(jpeg.tobytes(), time.monotonic())
        finally:
            with self.lock:
                book.coverage.finish(self.t)
            source.close()

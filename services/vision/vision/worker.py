import argparse
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from vision.client import ApiError, DeviceClient
from vision.counting import Assignment
from vision.envfile import load_env_file
from vision.pipeline import Models, Pipeline
from vision.source import FrameSource
from vision.staff import staff_from_response, work_areas_from_config
from vision.stream import LiveServer, blur, blur_boxes, local_address

PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_DIR / ".env"
DEFAULT_MODEL = PROJECT_DIR / "models" / "yolo11s.pt"
DEFAULT_POSE_MODEL = PROJECT_DIR / "models" / "yolo11s-pose.pt"
CONFIG_REFRESH_S = 30.0
HEARTBEAT_S = 30.0
WAITING = "waiting for zones"
LIVE_LIMITS = (1280, 720)
DEFAULT_SETTINGS = {
    "post_every_s": 15.0,
    "smoothing_s": 60.0,
    "dwell_s": 20.0,
    "fps": 4.0,
    "min_confidence": 0.25,
    "objects_every_s": 5.0,
}

log = logging.getLogger("dinemate.vision")


def layout_config(path: str) -> dict[str, Any]:
    layout = json.loads(Path(path).read_text(encoding="utf-8"))
    zones = [
        {
            "zone_id": z.get("zone_id", z["name"]),
            "name": z["name"],
            "capacity": z["capacity"],
            "points": z["points"],
            "seats": z.get("seats", []),
        }
        for z in layout["zones"]
    ]
    return {
        "zones": zones,
        "ignore": layout.get("ignore", []),
        "work": layout.get("work", []),
        "settings": {**DEFAULT_SETTINGS, **layout.get("settings", {})},
    }


def apply_overrides(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    overrides = {
        key: value
        for key, value in (
            ("dwell_s", args.dwell_s),
            ("smoothing_s", args.smoothing_s),
            ("post_every_s", args.post_every_s),
        )
        if value is not None
    }
    settings = {**DEFAULT_SETTINGS, **config.get("settings", {}), **overrides}
    return {**config, "settings": settings}


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count seated people per zone and post counts to DineMate. Frames never leave memory."
    )
    parser.add_argument(
        "--source",
        default=os.environ.get("DINEMATE_SOURCE", "0"),
        help="webcam index (0), a video file path, or a YouTube link (needs yt-dlp)",
    )
    parser.add_argument("--api", default=os.environ.get("DINEMATE_API_URL", "http://localhost:8000/api/v1"))
    parser.add_argument("--device", default=os.environ.get("DINEMATE_DEVICE_ID"))
    parser.add_argument("--token", default=os.environ.get("DINEMATE_DEVICE_TOKEN"))
    parser.add_argument("--layout", help="layout JSON for --dry-run instead of fetching config from the API")
    parser.add_argument("--model", default=os.environ.get("DINEMATE_MODEL", str(DEFAULT_MODEL)))
    parser.add_argument(
        "--pose-model",
        default=os.environ.get("DINEMATE_POSE_MODEL", str(DEFAULT_POSE_MODEL)),
        help="pose model used when the layout has seats",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        help="YOLO input size; default picks 1280 for sources 1920 px wide or more, else 640",
    )
    parser.add_argument("--loop", action="store_true", help="restart a video file when it ends")
    parser.add_argument(
        "--fast", action="store_true", help="process a video file as fast as possible instead of in real time"
    )
    parser.add_argument(
        "--preview", action="store_true", help="show a local window with zones and detections (nothing is saved)"
    )
    parser.add_argument("--dry-run", action="store_true", help="print readings instead of posting them")
    parser.add_argument("--dwell-s", type=float, help="seconds someone must stay in a zone before counting")
    parser.add_argument("--smoothing-s", type=float, help="length of the median window in seconds")
    parser.add_argument("--post-every-s", type=float, help="seconds between readings")
    parser.add_argument("--no-faces", action="store_true", help="name staff by badge only")
    parser.add_argument("--no-badges", action="store_true", help="name staff by face only")
    parser.add_argument(
        "--stream-port",
        type=int,
        default=int(os.environ.get("DINEMATE_STREAM_PORT", "0")) or None,
        help="serve a signed live view on this port, café network only (customer faces blurred, nothing saved)",
    )
    parser.add_argument("--stream-host", help="address owners' browsers use to reach this computer (default: auto)")
    args = parser.parse_args(argv)
    if args.dry_run and not args.layout and not (args.device and args.token):
        parser.error("--dry-run needs --layout, or --device and --token to read the layout from the API")
    if not args.dry_run and not (args.device and args.token):
        parser.error("set --device and --token (or DINEMATE_DEVICE_ID / DINEMATE_DEVICE_TOKEN in services/vision/.env)")
    return args


class Preview:
    WINDOW = "DineMate vision (local preview, nothing is saved)"

    def __init__(self) -> None:
        import cv2

        from vision.overlay import screen_limits

        self.cv2 = cv2
        self.limits = screen_limits()
        cv2.namedWindow(self.WINDOW, cv2.WINDOW_AUTOSIZE)

    def show(
        self,
        image: Any,
        pipeline: Pipeline,
        assignments: list[Assignment],
        readings: dict[str, dict[str, Any]],
        status: str,
    ) -> bool:
        from vision.overlay import draw

        canvas = draw(
            image,
            pipeline.zones,
            pipeline.ignore,
            assignments,
            readings,
            status,
            self.limits,
            pipeline.seat_states(),
            pipeline.labels(),
            pipeline.work,
            pipeline.staff_labels(),
            pipeline.stay_labels(),
        )
        self.cv2.imshow(self.WINDOW, canvas)
        return self.cv2.waitKey(1) & 0xFF not in (ord("q"), 27)

    def close(self) -> None:
        self.cv2.destroyAllWindows()


def live_canvas(image: Any, pipeline: Pipeline, assignments: list[Assignment], shown: dict[str, Any]) -> Any:
    from vision.overlay import draw

    height, width = image.shape[:2]
    private = blur(image, blur_boxes(pipeline.people_seen, pipeline.staff_tracks(), width, height))
    return draw(
        private,
        pipeline.zones,
        pipeline.ignore,
        assignments,
        shown,
        "DineMate live - customer faces blurred, nothing saved",
        LIVE_LIMITS,
        pipeline.seat_states(),
        pipeline.labels(),
        pipeline.work,
        pipeline.staff_labels(),
        pipeline.stay_labels(),
    )


def identity_reader(args: argparse.Namespace, config: dict[str, Any]) -> Any:
    if not work_areas_from_config(config):
        return None
    from vision.faces import MODELS_DIR
    from vision.identity import build_reader

    return build_reader(MODELS_DIR, faces=not args.no_faces, badges=not args.no_badges)


def start_live(args: argparse.Namespace) -> tuple[LiveServer | None, str | None]:
    if not args.stream_port:
        return None, None
    if not (args.device and args.token):
        log.warning("--stream-port needs --device and --token to check live links; live view is off")
        return None, None
    server = LiveServer(args.stream_port, args.device, args.token)
    server.start()
    return server, f"http://{args.stream_host or local_address()}:{server.port}/live"


def refresh_staff(client: DeviceClient, pipeline: Pipeline) -> bool:
    if not pipeline.work:
        pipeline.set_staff([])
        return True
    was_on = pipeline.staff_mode
    try:
        pipeline.set_staff(staff_from_response(client.staff_templates()))
    except ApiError as exc:
        if exc.status == 404:
            pipeline.set_staff([])
            log.warning("this API has no staff endpoint yet; staff mode is off")
            return False
        log.warning("staff list refresh failed: %s", exc)
    except httpx.HTTPError as exc:
        log.warning("staff list refresh failed: %s", exc)
    if pipeline.staff_mode and not was_on:
        log.info(
            "Staff mode on: %d enrolled worker(s), %d work area(s)", len(pipeline.matcher.staff), len(pipeline.work)
        )
        if pipeline.identity is None:
            log.warning("no face or badge reader installed yet; workers stay unnamed, the queue is still counted")
    elif was_on and not pipeline.staff_mode:
        log.info("Staff mode off")
    return True


def has_areas(config: dict[str, Any] | None) -> bool:
    return bool(config and (config.get("zones") or work_areas_from_config(config)))


def describe(pipeline: Pipeline, settings: dict[str, Any]) -> None:
    log.info("Counting %d zone(s): %s", len(pipeline.zones), ", ".join(z.name for z in pipeline.zones))
    if pipeline.seat_mode:
        log.info("Tracking %d seat(s) with pose keypoints and belongings", len(pipeline.tracker.seats))
    log.info(
        "Dwell %ss, smoothing %ss, a reading every %ss",
        settings["dwell_s"],
        settings["smoothing_s"],
        settings["post_every_s"],
    )


def run(args: argparse.Namespace) -> int:
    client = DeviceClient(args.api, args.device, args.token) if args.device and args.token else None
    config = layout_config(args.layout) if args.layout else client.config() if client else None
    if not has_areas(config) and (args.layout or args.dry_run or client is None):
        log.error("No zones to count. Register the device with a layout first (see services/vision/README.md).")
        return 1
    config = apply_overrides(config or {}, args)
    pipeline = Pipeline(config, Models(args.model, args.pose_model, args.imgsz), identity=identity_reader(args, config))
    settings = config["settings"]
    waiting = not has_areas(config)
    if waiting:
        log.info("No zones yet, %s: live view and heartbeats only, nothing is posted", WAITING)
    else:
        describe(pipeline, settings)
    source = FrameSource(args.source, fps=float(settings["fps"]), loop=args.loop, realtime=not args.fast)
    preview = Preview() if args.preview else None
    posting = client is not None and not args.dry_run
    seats_endpoint = True
    staff_endpoint = refresh_staff(client, pipeline) if client else False
    live, stream_url = start_live(args)
    epoch_offset = time.time() - time.monotonic()
    last_config = last_beat = time.monotonic()
    if stream_url or waiting:
        last_beat -= HEARTBEAT_S
    last_post: float | None = None
    sized: int | None = None
    fps = 0.0
    latency_ms = 0
    shown: dict[str, dict[str, Any]] = {}
    try:
        for frame in source.frames():
            watched = live is not None and live.hub.wanted(time.monotonic())
            if waiting and not watched:
                assignments: list[Assignment] = []
            else:
                started = time.perf_counter()
                assignments = pipeline.process(frame.image, frame.at)
                latency_ms = round((time.perf_counter() - started) * 1000)
                fps = 0.9 * fps + 0.1 * (1000 / max(latency_ms, 1)) if fps else 1000 / max(latency_ms, 1)
            height, width = frame.image.shape[:2]
            if last_post is None:
                last_post = frame.at
            if pipeline.imgsz is not None and pipeline.imgsz != sized:
                sized = pipeline.imgsz
                picked = "set for this camera" if pipeline.wanted_imgsz() else f"auto for a {width}px-wide source"
                chosen = "set by --imgsz" if args.imgsz else picked
                log.info("Source is %dx%d; detecting at %s px (%s)", width, height, pipeline.imgsz, chosen)
            if not waiting and frame.at - last_post >= float(settings["post_every_s"]):
                readings = pipeline.readings()
                snapshot = pipeline.snapshot(frame.at)
                staff = pipeline.staff_snapshot(epoch_offset)
                shown = {r["zone_id"]: r for r in readings}
                last_post = frame.at
                summary = ", ".join(
                    f"{z.name} ~{shown[z.zone_id]['estimated_occupied'] if z.zone_id in shown else 0}"
                    for z in pipeline.zones
                )
                if posting and client:
                    if pipeline.zones:
                        try:
                            client.post_occupancy(readings)
                            log.info("posted %s (detect %d ms)", summary, latency_ms)
                        except (ApiError, httpx.HTTPError) as exc:
                            log.warning("post failed, will retry: %s", exc)
                    if snapshot and seats_endpoint:
                        try:
                            client.post_seats(snapshot)
                        except ApiError as exc:
                            if exc.status == 404:
                                seats_endpoint = False
                                log.warning("this API has no seat endpoint yet; posting zone counts only")
                            else:
                                log.warning("seat post failed: %s", exc)
                        except httpx.HTTPError as exc:
                            log.warning("seat post failed: %s", exc)
                    if staff and staff_endpoint:
                        try:
                            client.post_staff(staff)
                        except ApiError as exc:
                            if exc.status == 404:
                                staff_endpoint = False
                                pipeline.set_staff([])
                                log.warning("this API has no staff endpoint yet; staff mode is off")
                            else:
                                log.warning("staff post failed, will retry: %s", exc)
                        except httpx.HTTPError as exc:
                            log.warning("staff post failed, will retry: %s", exc)
                else:
                    log.info("dry run: %s", json.dumps(readings))
                    if snapshot:
                        log.info("dry run seats: %s", json.dumps(snapshot["zones"]))
                    if staff:
                        log.info("dry run staff: %s", json.dumps(staff))
            now = time.monotonic()
            if client and not args.layout and now - last_config >= CONFIG_REFRESH_S:
                last_config = now
                try:
                    fresh = client.config()
                    if fresh is not None:
                        fresh = apply_overrides(fresh, args)
                        pipeline.configure(fresh)
                        settings = fresh["settings"]
                        log.info("layout updated to version %s", fresh.get("layout_version"))
                        ready = has_areas(fresh)
                        if waiting and ready:
                            if pipeline.identity is None:
                                pipeline.identity = identity_reader(args, fresh)
                            describe(pipeline, settings)
                            last_post = frame.at
                        elif not waiting and not ready:
                            log.info("No zones left, %s: nothing is posted", WAITING)
                        waiting = not ready
                except (ApiError, httpx.HTTPError) as exc:
                    log.warning("config refresh failed: %s", exc)
                if staff_endpoint:
                    staff_endpoint = refresh_staff(client, pipeline)
            if posting and client and now - last_beat >= HEARTBEAT_S:
                last_beat = now
                try:
                    client.heartbeat(
                        "ok" if source.stream_ok else "degraded",
                        None if waiting else round(fps, 1),
                        None if waiting else latency_ms,
                        source.stream_ok,
                        WAITING if waiting else None,
                        stream_url,
                    )
                except (ApiError, httpx.HTTPError) as exc:
                    log.warning("heartbeat failed: %s", exc)
            if live is not None:
                live.offer(live_canvas(frame.image, pipeline, assignments, shown), now)
            if preview and not preview.show(
                frame.image, pipeline, assignments, shown, "Live preview - Q to quit (nothing is saved)"
            ):
                break
    except KeyboardInterrupt:
        log.info("stopping")
    finally:
        source.close()
        if live is not None:
            live.close()
        if preview:
            preview.close()
        if client:
            client.close()
    return 0


def interrupt(signum: int, frame: Any) -> None:
    raise KeyboardInterrupt


def main(argv: list[str] | None = None) -> int:
    signal.signal(signal.SIGTERM, interrupt)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    load_env_file(ENV_FILE)
    args = parse_args(argv)
    try:
        return run(args)
    except (OSError, ApiError, httpx.HTTPError) as exc:
        log.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())

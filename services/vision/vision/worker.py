import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from vision.client import ApiError, DeviceClient
from vision.counting import Assignment, ZoneCounter, zones_from_config
from vision.source import FrameSource

PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_DIR / ".env"
DEFAULT_MODEL = PROJECT_DIR / "models" / "yolo11n.pt"
CONFIG_REFRESH_S = 30.0
HEARTBEAT_S = 30.0
DEFAULT_SETTINGS = {"post_every_s": 15.0, "smoothing_s": 60.0, "dwell_s": 20.0, "fps": 4.0, "min_confidence": 0.25}

log = logging.getLogger("dinemate.vision")


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def layout_config(path: str) -> dict[str, Any]:
    layout = json.loads(Path(path).read_text(encoding="utf-8"))
    zones = [
        {"zone_id": z.get("zone_id", z["name"]), "name": z["name"], "capacity": z["capacity"], "points": z["points"]}
        for z in layout["zones"]
    ]
    return {
        "zones": zones,
        "ignore": layout.get("ignore", []),
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
        "--source", default=os.environ.get("DINEMATE_SOURCE", "0"), help="webcam index (0) or a video file path"
    )
    parser.add_argument("--api", default=os.environ.get("DINEMATE_API_URL", "http://localhost:8000/api/v1"))
    parser.add_argument("--device", default=os.environ.get("DINEMATE_DEVICE_ID"))
    parser.add_argument("--token", default=os.environ.get("DINEMATE_DEVICE_TOKEN"))
    parser.add_argument("--layout", help="layout JSON for --dry-run instead of fetching config from the API")
    parser.add_argument("--model", default=os.environ.get("DINEMATE_MODEL", str(DEFAULT_MODEL)))
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
        counter: ZoneCounter,
        assignments: list[Assignment],
        readings: dict[str, dict[str, Any]],
        status: str,
    ) -> bool:
        from vision.overlay import draw

        canvas = draw(image, counter.zones, counter.ignore, assignments, readings, status, self.limits)
        self.cv2.imshow(self.WINDOW, canvas)
        return self.cv2.waitKey(1) & 0xFF not in (ord("q"), 27)

    def close(self) -> None:
        self.cv2.destroyAllWindows()


def run(args: argparse.Namespace) -> int:
    from vision.detector import YoloDetector

    client = DeviceClient(args.api, args.device, args.token) if args.device and args.token else None
    config = layout_config(args.layout) if args.layout else client.config() if client else None
    if not config or not config.get("zones"):
        log.error("No zones to count. Register the device with a layout first (see services/vision/README.md).")
        return 1
    config = apply_overrides(config, args)
    counter = ZoneCounter(*zones_from_config(config))
    settings = config["settings"]
    log.info("Counting %d zone(s): %s", len(counter.zones), ", ".join(z.name for z in counter.zones))
    log.info(
        "Dwell %ss, smoothing %ss, a reading every %ss",
        settings["dwell_s"],
        settings["smoothing_s"],
        settings["post_every_s"],
    )
    detector = YoloDetector(args.model, imgsz=args.imgsz, confidence=float(settings["min_confidence"]))
    source = FrameSource(args.source, fps=float(settings["fps"]), loop=args.loop, realtime=not args.fast)
    preview = Preview() if args.preview else None
    posting = client is not None and not args.dry_run
    last_config = last_beat = time.monotonic()
    last_post: float | None = None
    fps = 0.0
    latency_ms = 0
    shown: dict[str, dict[str, Any]] = {}
    try:
        for frame in source.frames():
            started = time.perf_counter()
            detections = detector.detect(frame.image)
            latency_ms = round((time.perf_counter() - started) * 1000)
            fps = 0.9 * fps + 0.1 * (1000 / max(latency_ms, 1)) if fps else 1000 / max(latency_ms, 1)
            height, width = frame.image.shape[:2]
            assignments = counter.update(detections, width, height, frame.at)
            if last_post is None:
                last_post = frame.at
                chosen = "set by --imgsz" if args.imgsz else f"auto for a {width}px-wide source"
                log.info("Source is %dx%d; detecting at %d px (%s)", width, height, detector.imgsz, chosen)
            if frame.at - last_post >= float(settings["post_every_s"]):
                readings = counter.readings()
                shown = {r["zone_id"]: r for r in readings}
                last_post = frame.at
                summary = ", ".join(
                    f"{z.name} ~{shown[z.zone_id]['estimated_occupied'] if z.zone_id in shown else 0}"
                    for z in counter.zones
                )
                if posting and client:
                    try:
                        client.post_occupancy(readings)
                        log.info("posted %s (detect %d ms)", summary, latency_ms)
                    except (ApiError, httpx.HTTPError) as exc:
                        log.warning("post failed, will retry: %s", exc)
                else:
                    log.info("dry run: %s", json.dumps(readings))
            now = time.monotonic()
            if client and now - last_config >= CONFIG_REFRESH_S:
                last_config = now
                try:
                    fresh = client.config()
                    if fresh is not None:
                        fresh = apply_overrides(fresh, args)
                        counter.reconfigure(*zones_from_config(fresh))
                        settings = fresh["settings"]
                        log.info("layout updated to version %s", fresh.get("layout_version"))
                except (ApiError, httpx.HTTPError) as exc:
                    log.warning("config refresh failed: %s", exc)
            if posting and client and now - last_beat >= HEARTBEAT_S:
                last_beat = now
                try:
                    client.heartbeat(
                        "ok" if source.stream_ok else "degraded", round(fps, 1), latency_ms, source.stream_ok, None
                    )
                except (ApiError, httpx.HTTPError) as exc:
                    log.warning("heartbeat failed: %s", exc)
            if preview and not preview.show(
                frame.image, counter, assignments, shown, "Live preview - Q to quit (nothing is saved)"
            ):
                break
    except KeyboardInterrupt:
        log.info("stopping")
    finally:
        source.close()
        if preview:
            preview.close()
        if client:
            client.close()
    return 0


def main(argv: list[str] | None = None) -> int:
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

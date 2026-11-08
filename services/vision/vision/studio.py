import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from vision.overlay import draw, screen_limits, status_bar, zone_label
from vision.pipeline import Models, Pipeline
from vision.source import FrameSource, grab_still, is_camera, open_capture
from vision.worker import DEFAULT_MODEL, DEFAULT_POSE_MODEL, apply_overrides, layout_config
from vision.zone_tool import edit_zones, save_layout

WINDOW = "DineMate studio (local only, nothing is saved)"
LAYOUT_DIR = Path(__file__).resolve().parents[1] / "layouts"
SHORT_CLIP_S = 90.0
SHORT_TIMINGS = {"dwell_s": 3.0, "smoothing_s": 6.0, "post_every_s": 3.0}
PLAYING = "Z edit zones | Space pause | Q quit"
PAUSED = "Paused - Space resume | Z edit zones | Q quit"


def default_layout(source: str) -> Path:
    return LAYOUT_DIR / ("webcam.json" if is_camera(source) else f"{Path(source).stem}.json")


def clip_seconds(source: str) -> float | None:
    if is_camera(source):
        return None
    capture = open_capture(source)
    try:
        fps = capture.get(cv2.CAP_PROP_FPS) or 0
        frames = capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        return frames / fps if fps else None
    finally:
        capture.release()


def read_layout(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Draw zones on a video or webcam, then watch it play with live counting. Only the zones are saved."
    )
    parser.add_argument("source", nargs="?", default="0", help="video file path, or 0 for the webcam")
    parser.add_argument("--layout", help="zones file; defaults to layouts/<video name>.json")
    parser.add_argument("--redraw", action="store_true", help="edit saved zones before playing")
    parser.add_argument("--at", type=float, default=1.0, help="seconds into the video for the frame you draw on")
    parser.add_argument("--imgsz", type=int, help="YOLO input size; default 1280 for sources 1920 px wide or more")
    parser.add_argument("--fast", action="store_true", help="process as fast as possible instead of in real time")
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--pose-model", default=str(DEFAULT_POSE_MODEL), help="pose model used for seats")
    parser.add_argument("--dwell-s", type=float, help="seconds someone must stay in a zone before counting")
    parser.add_argument("--smoothing-s", type=float, help="length of the median window in seconds")
    parser.add_argument("--post-every-s", type=float, help="seconds between readings")
    return parser.parse_args(argv)


class Player:
    def __init__(self, args: argparse.Namespace, layout_path: Path) -> None:
        self.args = args
        self.layout_path = layout_path
        self.config = apply_overrides(layout_config(str(layout_path)), args)
        self.pipeline = Pipeline(self.config, Models(args.model, args.pose_model, args.imgsz))
        self.settings = self.config["settings"]
        self.source = FrameSource(
            args.source, fps=float(self.settings["fps"]), loop=not is_camera(args.source), realtime=not args.fast
        )
        self.limits = screen_limits()
        self.readings: dict[str, dict[str, Any]] = {}

    def reload_zones(self, layout: dict[str, Any]) -> None:
        save_layout(layout, self.layout_path)
        self.config = apply_overrides(layout_config(str(self.layout_path)), self.args)
        self.pipeline.configure(self.config)
        self.readings = {}
        print(f"Zones updated and saved to {self.layout_path}.")

    def handle(self, key: int, image: np.ndarray, canvas: np.ndarray) -> str | None:
        char = chr(key).lower() if 32 <= key < 127 else ""
        if char == "q" or key == 27:
            return "quit"
        if char == "z":
            started = time.monotonic()
            layout = edit_zones(WINDOW, image, read_layout(self.layout_path))
            if layout is not None:
                self.reload_zones(layout)
            self.source.resume_after_pause(time.monotonic() - started)
        elif char == " ":
            started = time.monotonic()
            paused = canvas.copy()
            status_bar(paused, PAUSED)
            while True:
                cv2.imshow(WINDOW, paused)
                inner = cv2.waitKey(50) & 0xFF
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    return "quit"
                if inner == ord(" "):
                    break
                if inner in (ord("q"), ord("Q"), 27, ord("z"), ord("Z")):
                    self.source.resume_after_pause(time.monotonic() - started)
                    return self.handle(inner, image, canvas)
            self.source.resume_after_pause(time.monotonic() - started)
        return None

    def run(self) -> None:
        last_post: float | None = None
        cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
        try:
            for frame in self.source.frames():
                assignments = self.pipeline.process(frame.image, frame.at)
                height, width = frame.image.shape[:2]
                if last_post is None:
                    last_post = frame.at
                    print(f"Playing {width}x{height}, detecting at {self.pipeline.imgsz} px.")
                    if self.pipeline.seat_mode:
                        print(f"Tracking {len(self.pipeline.tracker.seats)} seat(s).")
                if frame.at - last_post >= float(self.settings["post_every_s"]):
                    last_post = frame.at
                    self.readings = {r["zone_id"]: r for r in self.pipeline.readings()}
                    labels = self.pipeline.labels()
                    print(
                        "  "
                        + ", ".join(
                            labels.get(z.zone_id) or zone_label(z, self.readings.get(z.zone_id))
                            for z in self.pipeline.zones
                        )
                    )
                canvas = draw(
                    frame.image,
                    self.pipeline.zones,
                    self.pipeline.ignore,
                    assignments,
                    self.readings,
                    f"{PLAYING} | detecting at {self.pipeline.imgsz}px",
                    self.limits,
                    self.pipeline.seat_states(),
                    self.pipeline.labels(),
                )
                cv2.imshow(WINDOW, canvas)
                key = cv2.waitKey(1) & 0xFF
                if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break
                if key != 255 and self.handle(key, frame.image, canvas) == "quit":
                    break
        finally:
            self.source.close()
            cv2.destroyAllWindows()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    layout_path = Path(args.layout) if args.layout else default_layout(args.source)
    try:
        existing = read_layout(layout_path)
        if existing is None or args.redraw:
            print(
                "Draw your zones in the window. Prompts appear on the dark bar at the top; S saves and starts playing."
            )
            layout = edit_zones(WINDOW, grab_still(args.source, args.at), existing)
            if layout is None:
                cv2.destroyAllWindows()
                print("Closed without saving zones.")
                return 0
            save_layout(layout, layout_path)
            print(f"Saved zones to {layout_path}.")
        else:
            print(f"Using saved zones from {layout_path}. Press Z while playing to change them, or run with --redraw.")
        length = clip_seconds(args.source)
        if length is not None and length < SHORT_CLIP_S:
            changed = False
            for key, value in SHORT_TIMINGS.items():
                if getattr(args, key) is None:
                    setattr(args, key, value)
                    changed = True
            if changed:
                print(f"Clip is {length:.0f} s long: people count after 3 s (normally 20 s), readings every 3 s.")
        Player(args, layout_path).run()
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

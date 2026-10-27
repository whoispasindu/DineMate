import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass

import cv2
import numpy as np

WEBCAM_WARMUP_FRAMES = 10


@dataclass
class Frame:
    image: np.ndarray
    at: float


def is_camera(spec: str) -> bool:
    return spec.isdigit()


def open_capture(spec: str) -> cv2.VideoCapture:
    if is_camera(spec):
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        capture = cv2.VideoCapture(int(spec), backend)
    else:
        capture = cv2.VideoCapture(spec)
    if not capture.isOpened():
        raise OSError(f"Could not open video source '{spec}'.")
    return capture


def grab_still(spec: str, at_seconds: float = 0.0) -> np.ndarray:
    capture = open_capture(spec)
    try:
        if is_camera(spec):
            for _ in range(WEBCAM_WARMUP_FRAMES):
                capture.read()
        elif at_seconds > 0:
            capture.set(cv2.CAP_PROP_POS_MSEC, at_seconds * 1000)
        ok, image = capture.read()
        if not ok:
            raise OSError(f"Could not read a frame from '{spec}'.")
        return image
    finally:
        capture.release()


class FrameSource:
    def __init__(self, spec: str, fps: float, loop: bool = False, realtime: bool = True) -> None:
        self.spec = spec
        self.fps = fps
        self.loop = loop
        self.realtime = realtime
        self.capture = open_capture(spec)
        self.stream_ok = True

    def close(self) -> None:
        self.capture.release()

    def _camera_frames(self) -> Iterator[Frame]:
        interval = 1.0 / self.fps
        last = 0.0
        failures = 0
        while True:
            ok, image = self.capture.read()
            if not ok:
                failures += 1
                self.stream_ok = False
                if failures > 50:
                    raise OSError("Camera stopped delivering frames.")
                time.sleep(0.1)
                continue
            failures = 0
            self.stream_ok = True
            now = time.monotonic()
            if now - last >= interval:
                last = now
                yield Frame(image, now)

    def _file_frames(self) -> Iterator[Frame]:
        video_fps = self.capture.get(cv2.CAP_PROP_FPS) or 25.0
        step = max(1, round(video_fps / self.fps))
        started = time.monotonic()
        index = 0
        played = 0.0
        while True:
            ok, image = self.capture.read()
            if not ok:
                if not self.loop:
                    return
                self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                played += index / video_fps
                index = 0
                continue
            index += 1
            if index % step:
                continue
            video_time = played + index / video_fps
            if self.realtime:
                delay = started + video_time - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                yield Frame(image, time.monotonic())
            else:
                yield Frame(image, started + video_time)

    def frames(self) -> Iterator[Frame]:
        return self._camera_frames() if is_camera(self.spec) else self._file_frames()

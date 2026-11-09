import hashlib
import hmac
import logging
import socket
import threading
import time
from collections.abc import Callable, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import numpy as np

from vision.counting import Detection
from vision.identity import Box, head_box

LIVE_PATH = "/live"
MAX_LINK_AHEAD_S = 300
MAX_SESSION_S = 600
FRAME_EVERY_S = 0.2
BOUNDARY = "frame"

log = logging.getLogger("dinemate.vision.stream")


def sign(token_hash: str, device_id: str, expires: int) -> str:
    return hmac.new(token_hash.encode(), f"{device_id}:{expires}".encode(), hashlib.sha256).hexdigest()


def verify(token_hash: str, device_id: str, expires: str | None, signature: str | None, now: float) -> bool:
    if not expires or not signature:
        return False
    try:
        at = int(expires)
    except ValueError:
        return False
    if at < now or at - now > MAX_LINK_AHEAD_S:
        return False
    return hmac.compare_digest(sign(token_hash, device_id, at), signature)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def blur_boxes(detections: Sequence[Detection], staff_tracks: set[int], width: int, height: int) -> list[Box]:
    boxes = []
    for d in detections:
        if d.track_id is not None and d.track_id in staff_tracks:
            continue
        box = head_box(d, width, height)
        if box is not None:
            boxes.append(box)
    return boxes


def blur(image: np.ndarray, boxes: Sequence[Box]) -> np.ndarray:
    import cv2

    canvas = image.copy()
    for x1, y1, x2, y2 in boxes:
        region = canvas[y1:y2, x1:x2]
        small = cv2.resize(region, (max(1, (x2 - x1) // 12), max(1, (y2 - y1) // 12)), interpolation=cv2.INTER_LINEAR)
        canvas[y1:y2, x1:x2] = cv2.resize(small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
    return canvas


def local_address() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("10.255.255.255", 1))
            return str(probe.getsockname()[0])
        except OSError:
            return "127.0.0.1"


def part(jpeg: bytes) -> bytes:
    head = f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\n\r\n".encode()
    return head + jpeg + b"\r\n"


class FrameHub:
    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.jpeg: bytes | None = None
        self.sequence = 0
        self.viewers = 0
        self.last_publish = 0.0

    def wanted(self, now: float) -> bool:
        return self.viewers > 0 and now - self.last_publish >= FRAME_EVERY_S

    def publish(self, jpeg: bytes, now: float) -> None:
        with self.condition:
            self.jpeg, self.sequence, self.last_publish = jpeg, self.sequence + 1, now
            self.condition.notify_all()

    def wait(self, after: int, timeout: float) -> tuple[int, bytes | None]:
        with self.condition:
            self.condition.wait_for(lambda: self.sequence != after, timeout)
            return self.sequence, self.jpeg

    def join(self) -> None:
        with self.condition:
            self.viewers += 1

    def leave(self) -> None:
        with self.condition:
            self.viewers -= 1
            if self.viewers == 0:
                self.jpeg = None


def make_handler(device_id: str, key: str, hub: FrameHub, clock: Callable[[], float]) -> type[BaseHTTPRequestHandler]:
    class LiveHandler(BaseHTTPRequestHandler):
        server_version = "DineMateLive"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _refuse(self, status: int, text: str) -> None:
            body = text.encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            url = urlparse(self.path)
            if url.path != LIVE_PATH:
                self._refuse(404, "Not found")
                return
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            if not verify(key, device_id, query.get("exp"), query.get("sig"), time.time()):
                self._refuse(403, "This live link has expired. Open the camera again in DineMate Business.")
                return
            self.send_response(200)
            self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY}")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            hub.join()
            started = clock()
            sequence = 0
            try:
                while clock() - started < MAX_SESSION_S:
                    fresh, jpeg = hub.wait(sequence, 2.0)
                    if fresh != sequence and jpeg is not None:
                        self.wfile.write(part(jpeg))
                    sequence = fresh
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            finally:
                hub.leave()

    return LiveHandler


class LiveServer:
    def __init__(
        self, port: int, device_id: str, token: str, host: str = "0.0.0.0", clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.hub = FrameHub()
        self.server = ThreadingHTTPServer((host, port), make_handler(device_id, token_hash(token), self.hub, clock))
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, name="dinemate-live", daemon=True)

    @property
    def port(self) -> int:
        return int(self.server.server_address[1])

    def start(self) -> None:
        self.thread.start()
        log.info("live view on port %d (café network only, frames stay in memory)", self.port)

    def offer(self, canvas: np.ndarray, now: float, quality: int = 70) -> None:
        if not self.hub.wanted(now):
            return
        import cv2

        ok, encoded = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if ok:
            self.hub.publish(encoded.tobytes(), now)

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()

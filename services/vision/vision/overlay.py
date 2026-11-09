import sys
from typing import Any

import cv2
import numpy as np

from vision.counting import Assignment, Detection, Zone
from vision.seats import Seat, SeatSettings
from vision.staff import WorkArea

FALLBACK_SCREEN = (1600, 900)
SCREEN_USE = (0.92, 0.82)
BAR_HEIGHT = 34
ZONE_COLOR = (69, 160, 31)
IGNORE_COLOR = (170, 170, 170)
REASON_COLORS = {
    "counted": (60, 200, 80),
    "seated": (60, 200, 80),
    "waiting for dwell": (30, 200, 240),
    "unsure": (30, 200, 240),
    "standing": (230, 140, 60),
}
SEAT_COLORS = {
    "free": (80, 200, 80),
    "occupied": (60, 60, 230),
    "held": (0, 170, 255),
    "unknown": (150, 150, 150),
}
OTHER_COLOR = (150, 150, 150)
WORK_COLORS = {"counter": (200, 90, 40), "kitchen": (40, 110, 200), "floor": (180, 80, 160)}
STAFF_COLOR = (255, 200, 60)
STAY_COLOR = (90, 230, 90)


def tag(canvas: np.ndarray, text: str, spot: tuple[int, int], color: tuple[int, int, int]) -> None:
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    x, y = spot
    cv2.rectangle(canvas, (x - 3, y - th - 5), (x + tw + 3, y + 4), (24, 24, 24), -1)
    cv2.putText(canvas, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)


def screen_limits() -> tuple[int, int]:
    if sys.platform == "win32":
        try:
            import ctypes

            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
            if width > 0 and height > 0:
                return round(width * SCREEN_USE[0]), round(height * SCREEN_USE[1])
        except (AttributeError, OSError):
            pass
    return FALLBACK_SCREEN


def fit(image: np.ndarray, limits: tuple[int, int]) -> tuple[np.ndarray, float]:
    height, width = image.shape[:2]
    scale = min(limits[0] / width, limits[1] / height, 1.0)
    if scale >= 1.0:
        return image.copy(), 1.0
    size = (round(width * scale), round(height * scale))
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA), scale


def _pixels(points: list[tuple[float, float]], width: int, height: int) -> np.ndarray:
    return np.array([[round(x * width), round(y * height)] for x, y in points], dtype=np.int32)


def status_bar(canvas: np.ndarray, text: str) -> None:
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], BAR_HEIGHT), (24, 24, 24), -1)
    cv2.putText(canvas, text, (10, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)


def zone_label(zone: Zone, reading: dict[str, Any] | None) -> str:
    if reading is None:
        return f"{zone.name}: counting... / {zone.capacity}"
    return (
        f"{zone.name}: ~{reading['estimated_occupied']} "
        f"({reading['occupied_low']}-{reading['occupied_high']}) / {zone.capacity}"
    )


def draw(
    image: np.ndarray,
    zones: list[Zone],
    ignore: list[list[tuple[float, float]]],
    assignments: list[Assignment],
    readings: dict[str, dict[str, Any]],
    status: str,
    limits: tuple[int, int],
    seat_states: list[tuple[Seat, str]] | None = None,
    labels: dict[str, str] | None = None,
    work: list[WorkArea] | None = None,
    staff: list[tuple[Detection, str]] | None = None,
    stays: dict[int, str] | None = None,
) -> np.ndarray:
    canvas, scale = fit(image, limits)
    height, width = canvas.shape[:2]
    for area in ignore:
        cv2.polylines(canvas, [_pixels(area, width, height)], True, IGNORE_COLOR, 1)
    for area in work or []:
        pts = _pixels(area.points, width, height)
        color = WORK_COLORS.get(area.area, OTHER_COLOR)
        cv2.polylines(canvas, [pts], True, color, 2)
        corner = (int(pts[:, 0].min()) + 6, int(pts[:, 1].max()) - 8)
        cv2.putText(canvas, f"work: {area.area}", corner, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    for zone in zones:
        pts = _pixels(zone.points, width, height)
        overlay = canvas.copy()
        cv2.fillPoly(overlay, [pts], ZONE_COLOR)
        canvas = cv2.addWeighted(overlay, 0.12, canvas, 0.88, 0)
        cv2.polylines(canvas, [pts], True, ZONE_COLOR, 2)
    radius = max(round(SeatSettings().seat_radius * width), 4)
    for seat, state in seat_states or []:
        centre = (round(seat.x * width), round(seat.y * height))
        color = SEAT_COLORS.get(state, OTHER_COLOR)
        cv2.circle(canvas, centre, radius, color, 2, cv2.LINE_AA)
        cv2.putText(
            canvas, state, (centre[0] - radius, centre[1] + radius + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1
        )
    for a in assignments:
        d = a.detection
        color = REASON_COLORS.get(a.reason, OTHER_COLOR)
        top_left = (round(d.x1 * scale), round(d.y1 * scale))
        bottom_right = (round(d.x2 * scale), round(d.y2 * scale))
        cv2.rectangle(canvas, top_left, bottom_right, color, 2)
        stay = (stays or {}).get(d.track_id) if d.track_id is not None else None
        spot = (top_left[0], max(top_left[1] - 6, BAR_HEIGHT + 12))
        if stay:
            tag(canvas, stay, spot, STAY_COLOR)
        else:
            cv2.putText(canvas, a.reason, spot, cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)
    for d, text in staff or []:
        top_left = (round(d.x1 * scale), round(d.y1 * scale))
        bottom_right = (round(d.x2 * scale), round(d.y2 * scale))
        cv2.rectangle(canvas, top_left, bottom_right, STAFF_COLOR, 2)
        spot = (top_left[0], min(bottom_right[1] + 16, height - 4))
        cv2.putText(canvas, text, spot, cv2.FONT_HERSHEY_SIMPLEX, 0.5, STAFF_COLOR, 1, cv2.LINE_AA)
    for zone in zones:
        pts = _pixels(zone.points, width, height)
        x, y = int(pts[:, 0].min()) + 6, int(pts[:, 1].min()) + 22
        label = (labels or {}).get(zone.zone_id) or zone_label(zone, readings.get(zone.zone_id))
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        cv2.rectangle(canvas, (x - 4, y - th - 6), (x + tw + 4, y + 6), (24, 24, 24), -1)
        cv2.putText(canvas, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (120, 230, 120), 2, cv2.LINE_AA)
    status_bar(canvas, status)
    return canvas

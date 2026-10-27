import sys
from typing import Any

import cv2
import numpy as np

from vision.counting import Assignment, Zone

FALLBACK_SCREEN = (1600, 900)
SCREEN_USE = (0.92, 0.82)
BAR_HEIGHT = 34
ZONE_COLOR = (69, 160, 31)
IGNORE_COLOR = (170, 170, 170)
REASON_COLORS = {
    "counted": (60, 200, 80),
    "waiting for dwell": (30, 200, 240),
    "standing": (230, 140, 60),
}
OTHER_COLOR = (150, 150, 150)


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
) -> np.ndarray:
    canvas, scale = fit(image, limits)
    height, width = canvas.shape[:2]
    for area in ignore:
        cv2.polylines(canvas, [_pixels(area, width, height)], True, IGNORE_COLOR, 1)
    for zone in zones:
        pts = _pixels(zone.points, width, height)
        overlay = canvas.copy()
        cv2.fillPoly(overlay, [pts], ZONE_COLOR)
        canvas = cv2.addWeighted(overlay, 0.12, canvas, 0.88, 0)
        cv2.polylines(canvas, [pts], True, ZONE_COLOR, 2)
    for a in assignments:
        d = a.detection
        color = REASON_COLORS.get(a.reason, OTHER_COLOR)
        top_left = (round(d.x1 * scale), round(d.y1 * scale))
        bottom_right = (round(d.x2 * scale), round(d.y2 * scale))
        cv2.rectangle(canvas, top_left, bottom_right, color, 2)
        cv2.putText(
            canvas,
            a.reason,
            (top_left[0], max(top_left[1] - 6, BAR_HEIGHT + 12)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )
    for zone in zones:
        pts = _pixels(zone.points, width, height)
        x, y = int(pts[:, 0].min()) + 6, int(pts[:, 1].min()) + 22
        label = zone_label(zone, readings.get(zone.zone_id))
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        cv2.rectangle(canvas, (x - 4, y - th - 6), (x + tw + 4, y + 6), (24, 24, 24), -1)
        cv2.putText(canvas, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (120, 230, 120), 2, cv2.LINE_AA)
    status_bar(canvas, status)
    return canvas

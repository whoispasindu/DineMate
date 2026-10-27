import argparse
import json
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from vision.overlay import fit, screen_limits, status_bar
from vision.source import grab_still
from vision.zone_editor import ZoneEditor

WINDOW = "DineMate zones (frame is not saved)"
COLORS = {"seating": (69, 160, 31), "queue": (30, 140, 230), "walkway": (170, 170, 170), "ignore": (60, 60, 220)}


def render(base: np.ndarray, editor: ZoneEditor) -> np.ndarray:
    canvas = base.copy()
    w, h = editor.width, editor.height

    def pixels(points: list[tuple[float, float]]) -> np.ndarray:
        return np.array([[round(x * w), round(y * h)] for x, y in points], dtype=np.int32)

    for shape in editor.shapes:
        pts = pixels(shape["points"])
        color = COLORS[shape["type"]]
        overlay = canvas.copy()
        cv2.fillPoly(overlay, [pts], color)
        canvas = cv2.addWeighted(overlay, 0.18, canvas, 0.82, 0)
        cv2.polylines(canvas, [pts], True, color, 2)
        label = f"{shape['name']} ({shape['capacity']})" if shape["type"] == "seating" else shape["type"]
        cv2.putText(canvas, label, (int(pts[0][0]) + 6, int(pts[0][1]) + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    if editor.current:
        pts = pixels(editor.current)
        cv2.polylines(canvas, [pts], editor.mode != "points", (255, 255, 255), 2)
        for px, py in pts:
            cv2.circle(canvas, (int(px), int(py)), 5, (255, 255, 255), -1)
            cv2.circle(canvas, (int(px), int(py)), 5, (0, 0, 0), 1)
    status_bar(canvas, editor.prompt())
    return canvas


def edit_zones(window: str, frame: np.ndarray, existing: dict[str, Any] | None = None) -> dict[str, Any] | None:
    display, _ = fit(frame, screen_limits())
    height, width = display.shape[:2]
    editor = ZoneEditor(width, height)
    if existing:
        editor.load(existing)
    cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(
        window, lambda event, x, y, _flags, _param: editor.click(x, y) if event == cv2.EVENT_LBUTTONDOWN else None
    )
    while True:
        cv2.imshow(window, render(display, editor))
        action = editor.key(cv2.waitKeyEx(30) & 0xFF)
        if cv2.getWindowProperty(window, cv2.WND_PROP_VISIBLE) < 1 or action == "quit":
            return None
        if action == "save":
            cv2.setMouseCallback(window, lambda *_args: None)
            return editor.layout()


def save_layout(layout: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(layout, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Draw seating zones on one frame and save them as a layout file.")
    parser.add_argument("--source", default="0", help="webcam index (0) or a video file path")
    parser.add_argument("--at", type=float, default=0.0, help="seconds into a video to grab the frame from")
    parser.add_argument("--out", required=True, help="where to write the layout JSON, e.g. layouts/webcam.json")
    args = parser.parse_args(argv)
    out = Path(args.out)
    try:
        frame = grab_still(args.source, args.at)
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    existing = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
    print("Draw in the window: all prompts appear on the dark bar at its top.")
    layout = edit_zones(WINDOW, frame, existing)
    cv2.destroyAllWindows()
    if layout is None:
        print("Closed without saving.")
        return 0
    save_layout(layout, out)
    print(f"Saved {len(layout['zones'])} seating zone(s) and {len(layout['ignore'])} ignored area(s) to {out}.")
    print("The frame itself was not saved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from vision.source import grab_still

WINDOW = "DineMate zones - click points, Enter closes a shape, U undo, S save, Q quit (frame is not saved)"
AREA_TYPES = {"s": "seating", "q": "queue", "w": "walkway", "i": "ignore"}
COLORS = {"seating": (69, 122, 31), "queue": (30, 140, 230), "walkway": (150, 150, 150), "ignore": (60, 60, 200)}


class ZoneEditor:
    def __init__(self, image: np.ndarray) -> None:
        self.image = image
        self.height, self.width = image.shape[:2]
        self.current: list[tuple[float, float]] = []
        self.shapes: list[dict[str, Any]] = []

    def on_mouse(self, event: int, x: int, y: int, _flags: int, _param: object) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            self.current.append((round(x / self.width, 4), round(y / self.height, 4)))

    def _pixels(self, points: list[tuple[float, float]]) -> np.ndarray:
        return np.array([[round(px * self.width), round(py * self.height)] for px, py in points], dtype=np.int32)

    def render(self) -> np.ndarray:
        canvas = self.image.copy()
        for shape in self.shapes:
            pts = self._pixels(shape["points"])
            color = COLORS[shape["type"]]
            cv2.polylines(canvas, [pts], True, color, 2)
            label = f"{shape['name']} ({shape['capacity']})" if shape["type"] == "seating" else shape["type"]
            cv2.putText(
                canvas, label, (int(pts[0][0]) + 6, int(pts[0][1]) + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
            )
        if self.current:
            pts = self._pixels(self.current)
            cv2.polylines(canvas, [pts], False, (255, 255, 255), 1)
            for px, py in pts:
                cv2.circle(canvas, (int(px), int(py)), 4, (255, 255, 255), -1)
        return canvas

    def close_shape(self) -> None:
        if len(self.current) < 3:
            print("A shape needs at least 3 points.")
            return
        kind = input("Type: (s)eating, (q)ueue, (w)alkway, (i)gnore [s]: ").strip().lower()[:1] or "s"
        area = AREA_TYPES.get(kind, "seating")
        shape: dict[str, Any] = {"type": area, "points": self.current}
        if area == "seating":
            shape["name"] = input("Zone name (e.g. Desk zone): ").strip() or f"Zone {len(self.shapes) + 1}"
            capacity = input("Seats in this zone [4]: ").strip()
            shape["capacity"] = int(capacity) if capacity.isdigit() and int(capacity) > 0 else 4
        self.shapes.append(shape)
        self.current = []
        print(f"Added {area}{' ' + shape['name'] if area == 'seating' else ''}.")

    def layout(self) -> dict[str, Any]:
        return {
            "zones": [
                {"name": s["name"], "capacity": s["capacity"], "points": [list(p) for p in s["points"]]}
                for s in self.shapes
                if s["type"] == "seating"
            ],
            "ignore": [
                {"type": s["type"], "points": [list(p) for p in s["points"]]}
                for s in self.shapes
                if s["type"] != "seating"
            ],
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Draw seating zones on one frame and save them as a layout file.")
    parser.add_argument("--source", default="0", help="webcam index (0) or a video file path")
    parser.add_argument("--at", type=float, default=0.0, help="seconds into a video to grab the frame from")
    parser.add_argument("--out", required=True, help="where to write the layout JSON, e.g. layouts/webcam.json")
    args = parser.parse_args(argv)
    try:
        editor = ZoneEditor(grab_still(args.source, args.at))
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    cv2.namedWindow(WINDOW)
    cv2.setMouseCallback(WINDOW, editor.on_mouse)
    print("Click the corners of a seating area, then press Enter. Mark queues and walkways too so they are ignored.")
    while True:
        cv2.imshow(WINDOW, editor.render())
        key = cv2.waitKey(30) & 0xFF
        if key in (13, 10, 32):
            editor.close_shape()
        elif key == ord("u") and editor.current:
            editor.current.pop()
        elif key == ord("s"):
            layout = editor.layout()
            if not layout["zones"]:
                print("Add at least one seating zone before saving.")
                continue
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(layout, indent=2) + "\n", encoding="utf-8")
            print(f"Saved {len(layout['zones'])} zone(s) to {out}. The frame itself was not saved.")
            break
        elif key in (ord("q"), 27):
            print("Quit without saving.")
            break
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())

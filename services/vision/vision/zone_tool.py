import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

from vision.source import grab_still
from vision.zone_editor import ZoneEditor

WINDOW = "DineMate zones (frame is not saved)"
COLORS = {"seating": (69, 160, 31), "queue": (30, 140, 230), "walkway": (170, 170, 170), "ignore": (60, 60, 220)}
BAR_HEIGHT = 34


def fit(image: np.ndarray, max_width: int, max_height: int) -> np.ndarray:
    height, width = image.shape[:2]
    scale = min(max_width / width, max_height / height, 1.0)
    if scale == 1.0:
        return image
    return cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)


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
        closed = editor.mode != "points"
        cv2.polylines(canvas, [pts], closed, (255, 255, 255), 2)
        for px, py in pts:
            cv2.circle(canvas, (int(px), int(py)), 5, (255, 255, 255), -1)
            cv2.circle(canvas, (int(px), int(py)), 5, (0, 0, 0), 1)
    cv2.rectangle(canvas, (0, 0), (w, BAR_HEIGHT), (24, 24, 24), -1)
    cv2.putText(canvas, editor.prompt(), (10, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return canvas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Draw seating zones on one frame and save them as a layout file.")
    parser.add_argument("--source", default="0", help="webcam index (0) or a video file path")
    parser.add_argument("--at", type=float, default=0.0, help="seconds into a video to grab the frame from")
    parser.add_argument("--out", required=True, help="where to write the layout JSON, e.g. layouts/webcam.json")
    parser.add_argument("--max-width", type=int, default=1600, help="largest window width; big frames are scaled down")
    parser.add_argument("--max-height", type=int, default=900, help="largest window height")
    args = parser.parse_args(argv)
    try:
        frame = fit(grab_still(args.source, args.at), args.max_width, args.max_height)
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    height, width = frame.shape[:2]
    editor = ZoneEditor(width, height)
    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(
        WINDOW, lambda event, x, y, _flags, _param: editor.click(x, y) if event == cv2.EVENT_LBUTTONDOWN else None
    )
    print("Draw in the window: all prompts appear on the dark bar at its top.")
    while True:
        cv2.imshow(WINDOW, render(frame, editor))
        action = editor.key(cv2.waitKeyEx(30) & 0xFF)
        if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
            print("Window closed without saving.")
            break
        if action == "save":
            layout = editor.layout()
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(layout, indent=2) + "\n", encoding="utf-8")
            print(f"Saved {len(layout['zones'])} seating zone(s) and {len(layout['ignore'])} ignored area(s) to {out}.")
            print("The frame itself was not saved.")
            break
        if action == "quit":
            print("Quit without saving.")
            break
    cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(main())

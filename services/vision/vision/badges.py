import argparse
import sys
import time
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from vision.identity import Throttle, crop, person_box, tracks_of
from vision.staff import Evidence, WorkerView

BADGE_CODES = 250
READ_EVERY_S = 1.0


def badges_supported() -> bool:
    import cv2

    return hasattr(cv2, "aruco") and hasattr(cv2.aruco, "ArucoDetector")


def badge_codes(ids: Iterable[Any] | None) -> list[int]:
    if ids is None:
        return []
    return [int(v) for v in np.asarray(ids).flatten() if 0 <= int(v) < BADGE_CODES]


def pick_badge(codes: Sequence[int]) -> int | None:
    distinct = set(codes)
    return distinct.pop() if len(distinct) == 1 else None


def _dictionary() -> Any:
    import cv2

    return cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_250)


class BadgeReader:
    def __init__(self, every_s: float = READ_EVERY_S, clock: Callable[[], float] = time.monotonic) -> None:
        import cv2

        self.cv2 = cv2
        self.detector = cv2.aruco.ArucoDetector(_dictionary(), cv2.aruco.DetectorParameters())
        self.throttle = Throttle(every_s)
        self.clock = clock

    def read(self, image: np.ndarray, people: Sequence[WorkerView]) -> list[Evidence]:
        now = self.clock()
        height, width = image.shape[:2]
        found = []
        for view in people:
            track = view.detection.track_id
            if track is None or not self.throttle.due(track, now):
                continue
            box = person_box(view.detection, width, height)
            if box is None:
                continue
            gray = self.cv2.cvtColor(crop(image, box), self.cv2.COLOR_BGR2GRAY)
            _, ids, _ = self.detector.detectMarkers(gray)
            code = pick_badge(badge_codes(ids))
            if code is not None:
                found.append(Evidence(track, badge_code=code))
        self.throttle.keep(tracks_of(people))
        return found


def save_badge(code: int, path: Path, size: int = 600) -> None:
    import cv2

    if not 0 <= code < BADGE_CODES:
        raise ValueError(f"badge codes run from 0 to {BADGE_CODES - 1}")
    marker = cv2.aruco.generateImageMarker(_dictionary(), code, size)
    border = size // 6
    page = cv2.copyMakeBorder(marker, border, border * 2, border, border, cv2.BORDER_CONSTANT, value=255)
    cv2.putText(
        page,
        f"DineMate staff badge {code}",
        (border, size + border + border),
        cv2.FONT_HERSHEY_SIMPLEX,
        size / 600,
        0,
        2,
        cv2.LINE_AA,
    )
    if not cv2.imwrite(str(path), page):
        raise OSError(f"could not write {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print a DineMate staff badge (ArUco 4x4, codes 0-249)")
    parser.add_argument("code", type=int, help="the badge code set for the worker in Privacy & consent")
    parser.add_argument("--out", type=Path, help="PNG file to write (default: badge-<code>.png)")
    parser.add_argument("--size", type=int, default=600, help="marker size in pixels")
    args = parser.parse_args(argv)
    path = args.out or Path(f"badge-{args.code}.png")
    try:
        save_badge(args.code, path, args.size)
    except (ValueError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Saved {path}. Print it at about 6 cm and wear it on the chest, facing the camera.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

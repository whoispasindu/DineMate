import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

import numpy as np

from vision.counting import Detection
from vision.staff import Evidence, IdentityReader, WorkerView, similarity

Box = tuple[int, int, int, int]

log = logging.getLogger("dinemate.vision.identity")


def clamp_box(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> Box | None:
    box = (max(0, int(x1)), max(0, int(y1)), min(width, int(x2)), min(height, int(y2)))
    return box if box[2] - box[0] > 1 and box[3] - box[1] > 1 else None


def person_box(d: Detection, width: int, height: int) -> Box | None:
    return clamp_box(d.x1, d.y1, d.x2, d.y2, width, height)


def head_box(d: Detection, width: int, height: int, share: float = 0.4, pad: float = 0.1) -> Box | None:
    w, h = d.x2 - d.x1, d.y2 - d.y1
    if w <= 1 or h <= 1:
        return None
    return clamp_box(d.x1 - w * pad, d.y1 - h * 0.05, d.x2 + w * pad, d.y1 + h * share, width, height)


def crop(image: np.ndarray, box: Box) -> np.ndarray:
    x1, y1, x2, y2 = box
    return np.ascontiguousarray(image[y1:y2, x1:x2])


@dataclass
class Throttle:
    every_s: float
    last: dict[int, float] = field(default_factory=dict)

    def due(self, key: int, now: float) -> bool:
        at = self.last.get(key)
        if at is not None and now - at < self.every_s:
            return False
        self.last[key] = now
        return True

    def keep(self, keys: set[int]) -> None:
        self.last = {k: v for k, v in self.last.items() if k in keys}


def tracks_of(people: Sequence[WorkerView]) -> set[int]:
    return {v.detection.track_id for v in people if v.detection.track_id is not None}


def average_template(embeddings: Sequence[Sequence[float]]) -> list[float]:
    if not embeddings:
        raise ValueError("no face samples")
    units = []
    for vector in embeddings:
        array = np.asarray(vector, dtype=np.float64)
        norm = float(np.linalg.norm(array))
        if norm == 0:
            raise ValueError("empty face sample")
        units.append(array / norm)
    mean = np.mean(units, axis=0)
    norm = float(np.linalg.norm(mean))
    if norm == 0:
        raise ValueError("face samples cancel out")
    return [float(v) for v in mean / norm]


def samples_agree(embeddings: Sequence[Sequence[float]], minimum: float) -> bool:
    if len(embeddings) < 2:
        return False
    return all(similarity(a, b) >= minimum for a, b in combinations(embeddings, 2))


def merge(evidence: Sequence[Evidence]) -> list[Evidence]:
    merged: dict[int, Evidence] = {}
    for item in evidence:
        before = merged.get(item.track_id)
        if before is None or (item.badge_code is not None and before.badge_code is None):
            merged[item.track_id] = item
    return list(merged.values())


class CombinedReader:
    def __init__(self, readers: Sequence[IdentityReader]) -> None:
        self.readers = list(readers)

    def read(self, image: np.ndarray, people: Sequence[WorkerView]) -> list[Evidence]:
        return merge([item for reader in self.readers for item in reader.read(image, people)])


def build_reader(
    models_dir: Path,
    faces: bool = True,
    badges: bool = True,
    clock: Callable[[], float] = time.monotonic,
) -> IdentityReader | None:
    readers: list[IdentityReader] = []
    if badges:
        from vision.badges import BadgeReader, badges_supported

        if badges_supported():
            readers.append(BadgeReader(clock=clock))
        else:
            log.warning("this OpenCV build has no ArUco module; badges are off")
    if faces:
        from vision.faces import FaceEmbedder, FaceReader, models_ready

        if models_ready(models_dir):
            readers.append(FaceReader(FaceEmbedder(models_dir), clock=clock))
        else:
            log.warning("face models not found in %s; run: uv run python -m vision.fetch_models", models_dir)
    if not readers:
        return None
    return readers[0] if len(readers) == 1 else CombinedReader(readers)

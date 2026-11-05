from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from vision.counting import Detection
from vision.seats import BELONGINGS, TABLEWARE, ObjectDetection

PERSON_CLASS = 0
DEFAULT_IMGSZ = 640
LARGE_IMGSZ = 1280
LARGE_SOURCE_WIDTH = 1920
OBJECT_LABELS = BELONGINGS | TABLEWARE


def pick_imgsz(source_width: int, requested: int | None = None) -> int:
    if requested is not None:
        return requested
    return LARGE_IMGSZ if source_width >= LARGE_SOURCE_WIDTH else DEFAULT_IMGSZ


def people_from(
    boxes: Sequence[Sequence[float]],
    confidences: Sequence[float],
    track_ids: Sequence[int | None],
    keypoints: Sequence[Sequence[Sequence[float]]] | None,
) -> list[Detection]:
    result = []
    for index, ((x1, y1, x2, y2), conf, track_id) in enumerate(zip(boxes, confidences, track_ids, strict=True)):
        points = tuple((float(p[0]), float(p[1]), float(p[2])) for p in keypoints[index]) if keypoints else None
        result.append(Detection(track_id, x1, y1, x2, y2, conf, points))
    return result


def objects_from(
    boxes: Sequence[Sequence[float]],
    classes: Iterable[int],
    confidences: Sequence[float],
    names: dict[int, str],
) -> list[ObjectDetection]:
    return [
        ObjectDetection(names[int(c)], x1, y1, x2, y2, conf)
        for (x1, y1, x2, y2), c, conf in zip(boxes, classes, confidences, strict=True)
        if names.get(int(c)) in OBJECT_LABELS
    ]


def _load(model: str) -> Any:
    from ultralytics import YOLO, settings

    settings.update({"sync": False})
    Path(model).parent.mkdir(parents=True, exist_ok=True)
    return YOLO(model)


class YoloDetector:
    def __init__(self, model: str, imgsz: int | None = None, confidence: float = 0.25) -> None:
        self.model = _load(model)
        self.requested_imgsz = imgsz
        self.imgsz: int | None = None
        self.confidence = confidence

    def detect(self, image: np.ndarray) -> list[Detection]:
        if self.imgsz is None:
            self.imgsz = pick_imgsz(image.shape[1], self.requested_imgsz)
        result = self.model.track(
            image,
            persist=True,
            classes=[PERSON_CLASS],
            conf=self.confidence,
            imgsz=self.imgsz,
            tracker="bytetrack.yaml",
            verbose=False,
        )[0]
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return []
        ids = boxes.id.int().tolist() if boxes.id is not None else [None] * len(boxes)
        keypoints = result.keypoints.data.tolist() if getattr(result, "keypoints", None) is not None else None
        return people_from(boxes.xyxy.tolist(), boxes.conf.tolist(), ids, keypoints)


class ObjectDetector:
    def __init__(self, model: str, imgsz: int | None = None, confidence: float = 0.25) -> None:
        self.model = _load(model)
        self.classes = [i for i, name in self.model.names.items() if name in OBJECT_LABELS]
        self.requested_imgsz = imgsz
        self.imgsz: int | None = None
        self.confidence = confidence

    def detect(self, image: np.ndarray) -> list[ObjectDetection]:
        if self.imgsz is None:
            self.imgsz = pick_imgsz(image.shape[1], self.requested_imgsz)
        result = self.model.predict(image, classes=self.classes, conf=self.confidence, imgsz=self.imgsz, verbose=False)[
            0
        ]
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return []
        return objects_from(boxes.xyxy.tolist(), boxes.cls.int().tolist(), boxes.conf.tolist(), result.names)

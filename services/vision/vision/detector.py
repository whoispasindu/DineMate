from pathlib import Path

import numpy as np

from vision.counting import Detection

PERSON_CLASS = 0
DEFAULT_IMGSZ = 640
LARGE_IMGSZ = 1280
LARGE_SOURCE_WIDTH = 1920


def pick_imgsz(source_width: int, requested: int | None = None) -> int:
    if requested is not None:
        return requested
    return LARGE_IMGSZ if source_width >= LARGE_SOURCE_WIDTH else DEFAULT_IMGSZ


class YoloDetector:
    def __init__(self, model: str, imgsz: int | None = None, confidence: float = 0.25) -> None:
        from ultralytics import YOLO, settings

        settings.update({"sync": False})
        Path(model).parent.mkdir(parents=True, exist_ok=True)
        self.model = YOLO(model)
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
        return [
            Detection(track_id, x1, y1, x2, y2, conf)
            for (x1, y1, x2, y2), conf, track_id in zip(boxes.xyxy.tolist(), boxes.conf.tolist(), ids, strict=True)
        ]

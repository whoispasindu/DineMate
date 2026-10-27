from pathlib import Path

import numpy as np

from vision.counting import Detection

PERSON_CLASS = 0


class YoloDetector:
    def __init__(self, model: str, imgsz: int = 640, confidence: float = 0.25) -> None:
        from ultralytics import YOLO, settings

        settings.update({"sync": False})
        Path(model).parent.mkdir(parents=True, exist_ok=True)
        self.model = YOLO(model)
        self.imgsz = imgsz
        self.confidence = confidence

    def detect(self, image: np.ndarray) -> list[Detection]:
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

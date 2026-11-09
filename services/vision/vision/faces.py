import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from vision.identity import Throttle, crop, head_box, tracks_of
from vision.staff import Evidence, WorkerView

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
DETECTOR_FILE = "face_detection_yunet_2023mar.onnx"
RECOGNIZER_FILE = "face_recognition_sface_2021dec.onnx"
MIN_FACE_PX = 40
EMBED_EVERY_S = 2.0


def models_ready(models_dir: Path = MODELS_DIR) -> bool:
    return (models_dir / DETECTOR_FILE).is_file() and (models_dir / RECOGNIZER_FILE).is_file()


def largest_face(faces: np.ndarray | None, min_size: float = MIN_FACE_PX) -> np.ndarray | None:
    if faces is None or len(faces) == 0:
        return None
    big = [f for f in faces if min(f[2], f[3]) >= min_size]
    return max(big, key=lambda f: float(f[2] * f[3])) if big else None


class FaceEmbedder:
    def __init__(self, models_dir: Path = MODELS_DIR, score: float = 0.8) -> None:
        import cv2

        self.detector: Any = cv2.FaceDetectorYN.create(str(models_dir / DETECTOR_FILE), "", (320, 320), score, 0.3, 50)
        self.recognizer: Any = cv2.FaceRecognizerSF.create(str(models_dir / RECOGNIZER_FILE), "")

    def faces(self, image: np.ndarray) -> np.ndarray | None:
        height, width = image.shape[:2]
        self.detector.setInputSize((width, height))
        _, faces = self.detector.detect(image)
        return faces

    def embed(self, image: np.ndarray, face: np.ndarray) -> tuple[float, ...]:
        aligned = self.recognizer.alignCrop(image, face)
        return tuple(float(v) for v in self.recognizer.feature(aligned).flatten())


class FaceReader:
    def __init__(
        self,
        embedder: FaceEmbedder,
        every_s: float = EMBED_EVERY_S,
        min_face_px: int = MIN_FACE_PX,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.embedder = embedder
        self.throttle = Throttle(every_s)
        self.min_face_px = min_face_px
        self.clock = clock

    def read(self, image: np.ndarray, people: Sequence[WorkerView]) -> list[Evidence]:
        now = self.clock()
        height, width = image.shape[:2]
        found = []
        for view in people:
            track = view.detection.track_id
            if track is None or not self.throttle.due(track, now):
                continue
            box = head_box(view.detection, width, height)
            if box is None:
                continue
            region = crop(image, box)
            face = largest_face(self.embedder.faces(region), self.min_face_px)
            if face is not None:
                found.append(Evidence(track, embedding=self.embedder.embed(region, face)))
        self.throttle.keep(tracks_of(people))
        return found

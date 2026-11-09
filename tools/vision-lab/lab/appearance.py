from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np

H_BINS = 18
S_BINS = 6
MIN_VALUE = 40
MIN_HEIGHT = 48
PARTS = ((0.12, 0.5), (0.5, 0.92))
SIDE = (0.18, 0.82)


def hs_histogram(hsv: np.ndarray) -> np.ndarray:
    pixels = hsv.reshape(-1, 3)
    keep = pixels[pixels[:, 2] > MIN_VALUE]
    hist, _, _ = np.histogram2d(keep[:, 0], keep[:, 1], bins=(H_BINS, S_BINS), range=((0, 180), (0, 256)))
    total = hist.sum()
    flat = hist.ravel().astype(np.float64)
    return flat / total if total else flat


def signature_from_hsv(hsv: np.ndarray) -> np.ndarray | None:
    height, width = hsv.shape[:2]
    if height < MIN_HEIGHT or width < 8:
        return None
    left, right = int(width * SIDE[0]), max(int(width * SIDE[1]), int(width * SIDE[0]) + 1)
    parts = [hs_histogram(hsv[int(height * top) : int(height * bottom), left:right]) for top, bottom in PARTS]
    if any(p.sum() == 0 for p in parts):
        return None
    return np.concatenate(parts) / len(parts)


def signature(person_bgr: np.ndarray) -> np.ndarray | None:
    import cv2

    return signature_from_hsv(cv2.cvtColor(person_bgr, cv2.COLOR_BGR2HSV))


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.minimum(a, b).sum())


def mean_signature(samples: Sequence[np.ndarray]) -> np.ndarray:
    stacked = np.mean(np.stack(samples), axis=0)
    return stacked / stacked.sum()


def blend(old: np.ndarray, new: np.ndarray, rate: float = 0.1) -> np.ndarray:
    mixed = (1 - rate) * old + rate * new
    return mixed / mixed.sum()


@dataclass
class Gallery:
    threshold: float = 0.62
    margin: float = 0.06
    looks: dict[str, np.ndarray] = field(default_factory=dict)

    def scores(self, sig: np.ndarray, exclude: set[str]) -> list[tuple[float, str]]:
        return sorted(
            ((similarity(sig, look), name) for name, look in self.looks.items() if name not in exclude), reverse=True
        )

    def accept(self, sig: np.ndarray, exclude: set[str]) -> tuple[str | None, float]:
        ranked = self.scores(sig, exclude)
        if not ranked:
            return None, 0.0
        best, name = ranked[0]
        second = ranked[1][0] if len(ranked) > 1 else 0.0
        if best >= self.threshold and best - second >= self.margin:
            return name, best
        return None, best

    def refresh(self, name: str, sig: np.ndarray) -> None:
        look = self.looks.get(name)
        if look is not None and similarity(look, sig) >= self.threshold:
            self.looks[name] = blend(look, sig)


@dataclass
class ReIdentifier:
    gallery: Gallery
    needed: int = 3
    tries: dict[int, tuple[str | None, int]] = field(default_factory=dict)

    def observe(self, track: int, sig: np.ndarray, exclude: set[str]) -> str | None:
        name, _ = self.gallery.accept(sig, exclude)
        previous = self.tries.get(track)
        count = (previous[1] + 1 if previous and previous[0] == name else 1) if name else 0
        self.tries[track] = (name, count)
        return name if name and count >= self.needed else None

    def keep(self, tracks: set[int]) -> None:
        self.tries = {t: v for t, v in self.tries.items() if t in tracks}


@dataclass
class LookEnrolment:
    name: str
    track: int
    started: float
    needed: int = 6
    timeout_s: float = 15.0
    agree: float = 0.55
    samples: list[np.ndarray] = field(default_factory=list)
    photo: bytes | None = None

    def add(self, sig: np.ndarray) -> None:
        self.samples.append(sig)

    def done(self, t: float) -> bool:
        return len(self.samples) >= self.needed or t - self.started > self.timeout_s

    def look(self) -> np.ndarray | None:
        if len(self.samples) < 3:
            return None
        pairs = [similarity(a, b) for a, b in combinations(self.samples, 2)]
        if sum(pairs) / len(pairs) < self.agree:
            return None
        return mean_signature(self.samples)

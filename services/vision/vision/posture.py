from collections.abc import Sequence
from dataclasses import dataclass
from math import acos, degrees, hypot
from typing import Literal

Posture = Literal["seated", "standing", "unsure"]
Keypoint = tuple[float, float, float]
Box = tuple[float, float, float, float]

MIN_KEYPOINT_CONFIDENCE = 0.5
SHOULDERS = (5, 6)
HIPS = (11, 12)
LEGS = ((11, 13, 15), (12, 14, 16))
SEATED_KNEE_MAX_DEG = 140.0
STANDING_KNEE_MIN_DEG = 160.0
HIPS_ABOVE_SEAT_TORSOS = 0.6
TORSO_FRACTION = 0.3
BOX_HIP_FRACTION = 0.75


@dataclass(frozen=True)
class PostureSettings:
    seated_ratio: float = 0.7
    h_stand_a: float | None = None
    h_stand_b: float | None = None


def _visible(keypoints: Sequence[Keypoint] | None, index: int) -> tuple[float, float] | None:
    if keypoints is None or index >= len(keypoints):
        return None
    x, y, confidence = keypoints[index]
    return (x, y) if confidence >= MIN_KEYPOINT_CONFIDENCE else None


def _mean(points: list[tuple[float, float]]) -> tuple[float, float] | None:
    if not points:
        return None
    return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)


def _group(keypoints: Sequence[Keypoint] | None, indices: tuple[int, ...]) -> tuple[float, float] | None:
    return _mean([p for i in indices if (p := _visible(keypoints, i)) is not None])


def knee_angle(hip: tuple[float, float], knee: tuple[float, float], ankle: tuple[float, float]) -> float:
    ax, ay = hip[0] - knee[0], hip[1] - knee[1]
    bx, by = ankle[0] - knee[0], ankle[1] - knee[1]
    lengths = hypot(ax, ay) * hypot(bx, by)
    if lengths == 0:
        return 180.0
    cosine = max(-1.0, min(1.0, (ax * bx + ay * by) / lengths))
    return degrees(acos(cosine))


def hip_point(box: Box, keypoints: Sequence[Keypoint] | None) -> tuple[float, float]:
    hips = _group(keypoints, HIPS)
    if hips is not None:
        return hips
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2, y1 + (y2 - y1) * BOX_HIP_FRACTION


def _leg_vote(keypoints: Sequence[Keypoint] | None) -> Posture | None:
    angles = []
    for indices in LEGS:
        hip, knee, ankle = (_visible(keypoints, i) for i in indices)
        if hip and knee and ankle:
            angles.append(knee_angle(hip, knee, ankle))
    if not angles:
        return None
    angle = sorted(angles)[len(angles) // 2]
    if angle <= SEATED_KNEE_MAX_DEG:
        return "seated"
    if angle >= STANDING_KNEE_MIN_DEG:
        return "standing"
    return None


def _seat_vote(keypoints: Sequence[Keypoint] | None, seat_y: float | None) -> Posture | None:
    if seat_y is None:
        return None
    shoulders, hips = _group(keypoints, SHOULDERS), _group(keypoints, HIPS)
    if shoulders is None or hips is None:
        return None
    torso = hips[1] - shoulders[1]
    if torso <= 0:
        return None
    return "standing" if hips[1] < seat_y - HIPS_ABOVE_SEAT_TORSOS * torso else "seated"


def _height_vote(box: Box, frame_height: float, settings: PostureSettings) -> Posture | None:
    a, b = settings.h_stand_a, settings.h_stand_b
    if a is None or b is None:
        return None
    _, y1, _, y2 = box
    anchor_y = (y1 + (y2 - y1) * TORSO_FRACTION) / frame_height
    expected = a * anchor_y + b
    if expected <= 0:
        return None
    return "seated" if (y2 - y1) / frame_height < settings.seated_ratio * expected else "standing"


def classify(
    box: Box,
    keypoints: Sequence[Keypoint] | None,
    frame_height: float,
    settings: PostureSettings,
    seat_y: float | None = None,
) -> Posture:
    votes = {v for v in (_leg_vote(keypoints), _seat_vote(keypoints, seat_y)) if v is not None}
    if not votes:
        height = _height_vote(box, frame_height, settings)
        return height if height is not None else "unsure"
    return votes.pop() if len(votes) == 1 else "unsure"

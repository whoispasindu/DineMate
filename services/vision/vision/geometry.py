from collections.abc import Sequence

Point = tuple[float, float]


def contains(polygon: Sequence[Sequence[float]], x: float, y: float) -> bool:
    inside = False
    count = len(polygon)
    for i in range(count):
        x1, y1 = polygon[i][0], polygon[i][1]
        x2, y2 = polygon[(i + 1) % count][0], polygon[(i + 1) % count][1]
        if (y1 > y) != (y2 > y):
            crossing = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < crossing:
                inside = not inside
    return inside


def to_pixels(polygon: Sequence[Sequence[float]], width: int, height: int) -> list[tuple[int, int]]:
    return [(round(p[0] * width), round(p[1] * height)) for p in polygon]

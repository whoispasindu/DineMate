import math
from datetime import datetime

from app.services.timeutil import CAMPUS_TZ

QUIET = 0.1
PEAKS = ((8.25, 0.6, 0.3), (12.75, 0.9, 0.9), (19.0, 0.8, 0.45))
WEEKEND_SCALE = 0.4


def daily_shape(at: datetime) -> float:
    local = at.astimezone(CAMPUS_TZ)
    hours = local.hour + local.minute / 60
    value = QUIET + sum(height * math.exp(-(((hours - centre) / width) ** 2)) for centre, width, height in PEAKS)
    return value * (WEEKEND_SCALE if local.weekday() >= 5 else 1.0)

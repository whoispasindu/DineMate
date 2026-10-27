from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

Level = Literal["normal", "busy", "crowded", "near_capacity"]
ORDER: tuple[Level, ...] = ("normal", "busy", "crowded", "near_capacity")
AlertStatus = Literal["open", "acknowledged", "suspended", "resolved"]
ActionKind = Literal["none", "open", "escalate", "deescalate", "reopen", "resolve", "suspend", "resume"]

COOLDOWN = timedelta(minutes=10)


@dataclass(frozen=True)
class CrowdThresholds:
    busy: float = 60
    crowded: float = 80
    near_capacity: float = 95
    hysteresis: float = 5
    dwell: timedelta = timedelta(minutes=2)
    alert_from: Level = "crowded"

    def enter(self, level: Level) -> float:
        return {"busy": self.busy, "crowded": self.crowded, "near_capacity": self.near_capacity}.get(level, 0.0)


@dataclass
class LevelState:
    level: Level = "normal"
    candidate: Level | None = None
    candidate_since: datetime | None = None


@dataclass(frozen=True)
class OpenAlert:
    level: Level
    status: AlertStatus


@dataclass(frozen=True)
class AlertAction:
    kind: ActionKind
    level: Level | None = None


def rank(level: Level) -> int:
    return ORDER.index(level)


def raw_level(percent: float, thresholds: CrowdThresholds, current: Level) -> Level:
    level: Level = "normal"
    for name in ORDER[1:]:
        limit = thresholds.enter(name)
        if rank(name) <= rank(current):
            limit -= thresholds.hysteresis
        if percent >= limit:
            level = name
    return level


def step(state: LevelState, percent: float, now: datetime, thresholds: CrowdThresholds) -> Level | None:
    target = raw_level(percent, thresholds, state.level)
    if target == state.level:
        state.candidate = None
        state.candidate_since = None
        return None
    if state.candidate != target or state.candidate_since is None:
        state.candidate, state.candidate_since = target, now
        return None
    if now - state.candidate_since >= thresholds.dwell:
        state.level, state.candidate, state.candidate_since = target, None, None
        return target
    return None


def decide(
    alert: OpenAlert | None,
    level: Level,
    live: bool,
    now: datetime,
    last_resolved_at: datetime | None,
    thresholds: CrowdThresholds,
) -> AlertAction:
    needs_alert = rank(level) >= rank(thresholds.alert_from)
    if alert is None:
        if not live or not needs_alert:
            return AlertAction("none")
        cooling = last_resolved_at is not None and now - last_resolved_at < COOLDOWN
        if cooling and level != "near_capacity":
            return AlertAction("none")
        return AlertAction("open", level)
    if not live:
        return AlertAction("none") if alert.status == "suspended" else AlertAction("suspend")
    if alert.status == "suspended":
        return AlertAction("resume", level) if needs_alert else AlertAction("resolve")
    if not needs_alert:
        return AlertAction("resolve")
    if rank(level) > rank(alert.level):
        return AlertAction("reopen" if alert.status == "acknowledged" else "escalate", level)
    if rank(level) < rank(alert.level):
        return AlertAction("deescalate", level)
    return AlertAction("none")

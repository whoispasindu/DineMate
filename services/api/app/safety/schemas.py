from datetime import datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StringConstraints

from app.schemas import SafetyEvent, Schema, Timestamped

IncomingType = Literal["fire_alarm", "evacuation", "test_notice"]
EventType = Literal["fire_alarm", "evacuation", "test_notice", "integration_offline"]
Severity = Literal["critical", "warning", "info"]
Status = Literal["active", "acknowledged", "resolved"]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
RequiredNote = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class EventLocation(Schema):
    canteen_id: str | None = None
    zone_id: str | None = None


class SafetyEventIn(Schema):
    external_event_id: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    event_type: IncomingType
    location: EventLocation = Field(default_factory=EventLocation)
    occurred_at: AwareDatetime
    is_simulation: bool


class SafetyEventAccepted(Timestamped):
    id: str
    status: Status
    is_simulation: bool
    severity: Severity
    repeat_count: int
    merged: bool
    label: str | None


class SourceHeartbeatIn(Schema):
    status: Literal["ok", "degraded"] = "ok"
    message: Note | None = None


class SourceHeartbeatAccepted(Timestamped):
    source_id: str


class SimulateIn(Schema):
    event_type: IncomingType = "fire_alarm"
    canteen_id: str | None = None
    zone_id: str | None = None
    note: Note | None = None


class AcknowledgeIn(Schema):
    note: Note | None = None


class ResolveIn(Schema):
    note: RequiredNote


class SafetyAck(Schema):
    user_name: str
    acknowledged_at: datetime
    note: str | None


class StaffSafetyEvent(Schema):
    id: str
    event_type: EventType
    title: str
    severity: Severity
    status: Status
    is_simulation: bool
    label: str | None
    canteen_id: str | None
    canteen_name: str | None
    zone_name: str | None
    source_id: str
    source_name: str
    source_kind: Literal["simulator", "approved_integration"]
    occurred_at: datetime
    received_at: datetime
    last_seen_at: datetime
    repeat_count: int
    note: str | None
    instructions: str
    acks: list[SafetyAck]
    resolved_by_name: str | None
    resolved_at: datetime | None
    resolution_note: str | None


class StaffSafetyEventList(Timestamped):
    simulation_mode: bool
    items: list[StaffSafetyEvent]


class StaffSafetyEventResult(Timestamped):
    event: StaffSafetyEvent


class SafetySourceHealth(Schema):
    id: str
    name: str
    kind: Literal["simulator", "approved_integration"]
    is_enabled: bool
    last_heartbeat_at: datetime | None
    state: Literal["online", "offline", "never_connected"]


class SafetySourceList(Timestamped):
    items: list[SafetySourceHealth]


class SafetyActive(Timestamped):
    active: bool
    events: list[SafetyEvent]

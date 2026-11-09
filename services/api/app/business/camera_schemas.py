from pydantic import Field

from app.schemas import Schema, Timestamped
from app.schemas_config import EditableZone


class CameraIn(Schema):
    label: str = Field(min_length=1, max_length=40)
    source: str = Field(min_length=1, max_length=500)


class CameraPatch(Schema):
    label: str | None = Field(default=None, min_length=1, max_length=40)
    source: str | None = Field(default=None, min_length=1, max_length=500)
    enabled: bool | None = None


class CameraOut(Schema):
    id: str
    venue_id: str
    label: str
    source_hint: str | None
    enabled: bool


class CameraResult(Timestamped):
    camera: CameraOut


class CameraRemoved(Timestamped):
    device_id: str


class AreaIn(Schema):
    name: str = Field(min_length=1, max_length=40)


class AreaResult(Timestamped):
    zone: EditableZone


class HubCamera(Schema):
    device_id: str
    venue_id: str
    label: str
    source: str
    enabled: bool


class HubCameras(Timestamped):
    hub_id: str
    cameras: list[HubCamera]


class HubTokensIn(Schema):
    device_ids: list[str] = Field(max_length=32)


class HubToken(Schema):
    device_id: str
    token: str


class HubTokens(Timestamped):
    tokens: list[HubToken]

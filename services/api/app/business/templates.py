import math
import struct
from collections.abc import Sequence

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings

DIM = 128
FORMAT = f"<{DIM}f"


class TemplatesUnavailable(Exception):
    pass


def normalise(vector: Sequence[float]) -> list[float]:
    if len(vector) != DIM or not all(math.isfinite(v) for v in vector):
        raise ValueError(f"A face template has {DIM} finite numbers.")
    length = math.sqrt(sum(v * v for v in vector))
    if length == 0:
        raise ValueError("A face template cannot be all zeros.")
    return [v / length for v in vector]


class TemplateVault:
    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode())

    def seal(self, vector: Sequence[float]) -> bytes:
        return self._fernet.encrypt(struct.pack(FORMAT, *normalise(vector)))

    def open(self, sealed: bytes) -> list[float]:
        try:
            return list(struct.unpack(FORMAT, self._fernet.decrypt(sealed)))
        except (InvalidToken, struct.error) as exc:
            raise TemplatesUnavailable("Stored face template cannot be read with this key.") from exc


def vault_for(settings: Settings) -> TemplateVault:
    if settings.deployment != "local":
        raise TemplatesUnavailable("Face templates are only kept on a café's local server.")
    if not settings.template_key:
        raise TemplatesUnavailable("Set DINEMATE_TEMPLATE_KEY on the local server to enable face enrolment.")
    try:
        return TemplateVault(settings.template_key)
    except ValueError as exc:
        raise TemplatesUnavailable("DINEMATE_TEMPLATE_KEY is not a valid Fernet key.") from exc

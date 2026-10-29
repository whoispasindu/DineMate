import json
import logging
import random
import sys
import time as systime
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import Settings, get_settings
from app.sim_shape import daily_shape

DRIFT = 4
STEPS = (-1, 0, 0, 1)
CATCH_UP = 3

log = logging.getLogger("dinemate.sim")


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def target_for(base: int, at: datetime) -> int:
    return round(base * daily_shape(at))


def next_occupancy(previous: int | None, target: int, capacity: int, rng: random.Random) -> int:
    start = target if previous is None else previous
    if abs(start - target) > DRIFT:
        start += CATCH_UP if target > start else -CATCH_UP
        return _clamp(start, 0, capacity)
    return _clamp(_clamp(start + rng.choice(STEPS), target - DRIFT, target + DRIFT), 0, capacity)


@dataclass
class SimulatedDevice:
    device_id: str
    etag: str | None = None
    config: dict[str, Any] | None = None
    occupancy: dict[str, int] = field(default_factory=dict)
    server_offset: timedelta = timedelta(0)


class ApiClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _request(
        self, method: str, path: str, body: dict[str, Any] | None = None, etag: str | None = None
    ) -> tuple[int, dict[str, Any] | None, str | None]:
        headers = {"Authorization": f"Device {self.token}", "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if etag:
            headers["If-None-Match"] = etag
        request = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read() or b"null"), response.headers.get("ETag")
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                return 304, None, etag
            detail = exc.read().decode(errors="replace")[:300]
            raise RuntimeError(f"{method} {path} → {exc.code}: {detail}") from exc

    def config(self, device: SimulatedDevice) -> None:
        status, body, etag = self._request("GET", f"/devices/{device.device_id}/config", etag=device.etag)
        if status == 200 and body is not None:
            device.config, device.etag = body, etag
            device.server_offset = datetime.fromisoformat(body["server_time"]) - datetime.now(UTC)

    def post(self, device_id: str, readings: list[dict[str, Any]]) -> None:
        payload = {"captured_at": datetime.now(UTC).isoformat(), "readings": readings}
        self._request("POST", f"/devices/{device_id}/occupancy", payload)


def readings_for(device: SimulatedDevice, rng: random.Random) -> list[dict[str, Any]]:
    config = device.config or {}
    profiles: dict[str, dict[str, int]] = config.get("simulation") or {}
    server_now = datetime.now(UTC) + device.server_offset
    readings = []
    for zone in config.get("zones", []):
        profile = profiles.get(zone["zone_id"])
        if profile is None:
            continue
        target = target_for(profile["base"], server_now)
        occupied = next_occupancy(device.occupancy.get(zone["zone_id"]), target, zone["capacity"], rng)
        device.occupancy[zone["zone_id"]] = occupied
        readings.append(
            {
                "zone_id": zone["zone_id"],
                "estimated_occupied": occupied,
                "occupied_low": max(0, occupied - profile["below"]),
                "occupied_high": min(zone["capacity"], occupied + profile["above"]),
                "confidence": "medium",
            }
        )
    return readings


def run(settings: Settings, rng: random.Random) -> None:
    client = ApiClient(settings.simulator_api_url, settings.simulator_token)
    devices = [SimulatedDevice(device_id) for device_id in settings.simulator_devices]
    while True:
        for device in devices:
            try:
                client.config(device)
                readings = readings_for(device, rng)
                if readings:
                    client.post(device.device_id, readings)
                log.info("%s: posted %d simulated readings", device.device_id, len(readings))
            except (OSError, RuntimeError) as exc:
                log.warning("%s: %s", device.device_id, exc)
        systime.sleep(settings.simulator_interval_s)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = get_settings()
    log.info(
        "Occupancy simulator posting to %s every %.0f s for %s (readings are stored as simulated)",
        settings.simulator_api_url,
        settings.simulator_interval_s,
        ", ".join(settings.simulator_devices),
    )
    run(settings, random.Random())
    return 0


if __name__ == "__main__":
    sys.exit(main())

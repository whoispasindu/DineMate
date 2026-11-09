from collections import deque
from datetime import UTC, datetime
from typing import Any

import httpx

MAX_QUEUED_POSTS = 20


class ApiError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class DeviceClient:
    def __init__(self, base_url: str, device_id: str, token: str, timeout: float = 5.0) -> None:
        self.device_id = device_id
        self.http = httpx.Client(
            base_url=base_url.rstrip("/"), headers={"Authorization": f"Device {token}"}, timeout=timeout
        )
        self.etag: str | None = None
        self.queue: deque[dict[str, Any]] = deque(maxlen=MAX_QUEUED_POSTS)
        self.staff_queue: deque[dict[str, Any]] = deque(maxlen=MAX_QUEUED_POSTS)

    def close(self) -> None:
        self.http.close()

    def _check(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            try:
                message = response.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                message = response.text[:200]
            raise ApiError(
                f"{response.request.method} {response.request.url.path} → {response.status_code}: {message}",
                response.status_code,
            )

    def config(self) -> dict[str, Any] | None:
        headers = {"If-None-Match": self.etag} if self.etag else {}
        response = self.http.get(f"/devices/{self.device_id}/config", headers=headers)
        if response.status_code == 304:
            return None
        self._check(response)
        self.etag = response.headers.get("ETag")
        return response.json()

    def _send_queued(self, path: str, queue: deque[dict[str, Any]]) -> int:
        sent = 0
        while queue:
            response = self.http.post(path, json=queue[0])
            if 400 <= response.status_code < 500:
                queue.popleft()
            self._check(response)
            if response.status_code < 400:
                queue.popleft()
            sent += 1
        return sent

    def post_occupancy(self, readings: list[dict[str, Any]]) -> int:
        self.queue.append({"captured_at": datetime.now(UTC).isoformat(), "readings": readings})
        return self._send_queued(f"/devices/{self.device_id}/occupancy", self.queue)

    def staff_templates(self) -> dict[str, Any] | list[dict[str, Any]]:
        response = self.http.get(f"/devices/{self.device_id}/staff-templates")
        self._check(response)
        return response.json()

    def post_staff(self, snapshot: dict[str, Any]) -> int:
        self.staff_queue.append({"captured_at": datetime.now(UTC).isoformat(), **snapshot})
        return self._send_queued(f"/devices/{self.device_id}/staff", self.staff_queue)

    def post_seats(self, snapshot: dict[str, Any]) -> None:
        payload = {"captured_at": datetime.now(UTC).isoformat(), **snapshot}
        self._check(self.http.post(f"/devices/{self.device_id}/seats", json=payload))

    def heartbeat(
        self,
        status: str,
        fps: float | None,
        latency_ms: int | None,
        stream_ok: bool,
        message: str | None,
        stream_url: str | None = None,
    ) -> None:
        payload = {"status": status, "fps": fps, "latency_ms": latency_ms, "stream_ok": stream_ok, "message": message}
        if stream_url:
            payload["stream_url"] = stream_url
        self._check(self.http.post(f"/devices/{self.device_id}/heartbeat", json=payload))

import argparse
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Protocol

import httpx

from vision.client import ApiError
from vision.envfile import load_env_file

PROJECT_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_DIR / ".env"
DEFAULT_MODEL = PROJECT_DIR / "models" / "yolo11s.pt"
DEFAULT_VIDEOS = PROJECT_DIR.parent / "api" / "test-videos"
VIDEO_PREFIX = "video:"
VIDEO_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,120}$")
DEFAULT_API = "http://localhost:8000/api/v1"
POLL_S = 15.0
TICK_S = 1.0
BACKOFF_S = (5.0, 15.0, 60.0)
HEALTHY_S = 120.0
STOP_WAIT_S = 5.0
MAX_CAMERAS = 8
HUB_ONLY_ENV = ("DINEMATE_HUB_TOKEN", "DINEMATE_HUB_ID")
USERINFO = re.compile(r"(?<=://)\S*@")

log = logging.getLogger("dinemate.hub")


@dataclass(frozen=True)
class Camera:
    device_id: str
    label: str
    source: str
    enabled: bool = True


@dataclass
class RunningCamera:
    camera: Camera
    slot: int
    started_at: float
    exited_at: float | None = None
    failures: int = 0

    @property
    def retry_at(self) -> float | None:
        return None if self.exited_at is None else self.exited_at + backoff(self.failures)


@dataclass(frozen=True)
class Start:
    camera: Camera
    slot: int


@dataclass(frozen=True)
class Plan:
    start: list[Start] = field(default_factory=list)
    stop: list[str] = field(default_factory=list)
    restart: list[Camera] = field(default_factory=list)
    no_slot: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HubSettings:
    api: str
    stream_host: str = "localhost"
    first_port: int = 8090
    max_cameras: int = MAX_CAMERAS
    model: str = str(DEFAULT_MODEL)
    videos_dir: str = str(DEFAULT_VIDEOS)


class Process(Protocol):
    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


class CameraSource(Protocol):
    def cameras(self) -> list[Camera]: ...

    def tokens(self, device_ids: Iterable[str]) -> dict[str, str]: ...


Spawn = Callable[[list[str], dict[str, str], str], Process]


def mask_source(text: str) -> str:
    return USERINFO.sub("***@", text)


def backoff(failures: int) -> float:
    return BACKOFF_S[min(max(failures, 1), len(BACKOFF_S)) - 1]


def record_exit(running: RunningCamera, now: float) -> None:
    running.failures = 1 if now - running.started_at >= HEALTHY_S else running.failures + 1
    running.exited_at = now


def active_cameras(wanted: Iterable[Camera]) -> dict[str, Camera]:
    active: dict[str, Camera] = {}
    for camera in wanted:
        if camera.enabled and camera.source.strip() and camera.device_id not in active:
            active[camera.device_id] = camera
    return active


def plan(running: dict[str, RunningCamera], wanted: list[Camera], now: float, slots: int = MAX_CAMERAS) -> Plan:
    active = active_cameras(wanted)
    stop = [device_id for device_id in running if device_id not in active]
    restart = [
        camera
        for device_id, camera in active.items()
        if (current := running.get(device_id)) is not None
        and (camera.source != current.camera.source or (current.retry_at is not None and now >= current.retry_at))
    ]
    taken = {current.slot for device_id, current in running.items() if device_id in active}
    free = [slot for slot in range(slots) if slot not in taken]
    start: list[Start] = []
    no_slot: list[str] = []
    for device_id, camera in active.items():
        if device_id in running:
            continue
        if free:
            start.append(Start(camera, free.pop(0)))
        else:
            no_slot.append(device_id)
    return Plan(start, stop, restart, no_slot)


def cameras_from_response(data: Any) -> list[Camera]:
    rows = data.get("cameras") if isinstance(data, dict) else None
    cameras = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        device_id = str(row.get("device_id") or "").strip()
        if not device_id:
            continue
        cameras.append(
            Camera(
                device_id,
                str(row.get("label") or device_id),
                str(row.get("source") or "").strip(),
                bool(row.get("enabled", True)),
            )
        )
    return cameras


def tokens_from_response(data: Any) -> dict[str, str]:
    rows = data.get("tokens") if isinstance(data, dict) else None
    return {
        str(row["device_id"]): str(row["token"])
        for row in (rows if isinstance(rows, list) else [])
        if isinstance(row, dict) and row.get("device_id") and row.get("token")
    }


def worker_source(source: str, videos_dir: str) -> str:
    if not source.startswith(VIDEO_PREFIX):
        return source
    name = source[len(VIDEO_PREFIX) :]
    if not VIDEO_NAME.match(name):
        raise ValueError(f"unsafe test video name {name!r}")
    return str(Path(videos_dir) / name)


def worker_command(settings: HubSettings, camera: Camera, port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "vision.worker",
        "--api",
        settings.api,
        "--device",
        camera.device_id,
        "--stream-port",
        str(port),
        "--stream-host",
        settings.stream_host,
        "--model",
        settings.model,
        "--loop",
    ]


def worker_threads(cpus: int, cameras: int) -> int:
    return max(1, cpus // max(1, cameras))


def worker_env(base: Mapping[str, str], token: str, source: str, threads: int | None = None) -> dict[str, str]:
    env = {key: value for key, value in base.items() if key not in HUB_ONLY_ENV}
    env.update(
        DINEMATE_DEVICE_TOKEN=token,
        DINEMATE_SOURCE=source,
        PYTHONUNBUFFERED="1",
        PYTHONIOENCODING="utf-8",
    )
    if threads is not None and "OMP_NUM_THREADS" not in base:
        env["OMP_NUM_THREADS"] = str(threads)
    return env


def relay(name: str, stream: IO[str] | None) -> None:
    if stream is None:
        return
    for line in stream:
        sys.stdout.write(f"{name} | {mask_source(line.rstrip())}\n")
        sys.stdout.flush()


def spawn_worker(command: list[str], env: dict[str, str], name: str) -> Process:
    process = subprocess.Popen(
        command,
        env=env,
        cwd=PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    threading.Thread(target=relay, args=(name, process.stdout), name=f"relay-{name}", daemon=True).start()
    return process


def end(process: Process) -> None:
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(STOP_WAIT_S)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


class HubClient:
    def __init__(self, base_url: str, hub_id: str, token: str, timeout: float = 10.0) -> None:
        self.hub_id = hub_id
        self.http = httpx.Client(
            base_url=base_url.rstrip("/"), headers={"Authorization": f"Device {token}"}, timeout=timeout
        )

    def close(self) -> None:
        self.http.close()

    def _json(self, response: httpx.Response) -> Any:
        if response.status_code >= 400:
            try:
                message = response.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                message = response.reason_phrase
            raise ApiError(
                f"{response.request.method} {response.request.url.path} → {response.status_code}: {message}",
                response.status_code,
            )
        return response.json()

    def cameras(self) -> list[Camera]:
        return cameras_from_response(self._json(self.http.get(f"/devices/{self.hub_id}/hub/cameras")))

    def tokens(self, device_ids: Iterable[str]) -> dict[str, str]:
        response = self.http.post(f"/devices/{self.hub_id}/hub/tokens", json={"device_ids": list(device_ids)})
        return tokens_from_response(self._json(response))


class Hub:
    def __init__(
        self,
        client: CameraSource,
        settings: HubSettings,
        hub_id: str = "hub-local",
        spawn: Spawn = spawn_worker,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.hub_id = hub_id
        self.spawn = spawn
        self.environ = os.environ if environ is None else environ
        self.running: dict[str, RunningCamera] = {}
        self.processes: dict[str, Process] = {}
        self.wanted: list[Camera] = []
        self.stopping = threading.Event()
        self.next_poll = 0.0
        self.hold_until = 0.0
        self.trouble: str | None = None
        self.unplaced: set[str] = set()

    def request_stop(self, signum: int = 0, frame: Any = None) -> None:
        self.stopping.set()

    def run(self) -> None:
        try:
            while not self.stopping.is_set():
                self.tick(time.monotonic())
                self.stopping.wait(TICK_S)
        finally:
            self.stop_all()

    def tick(self, now: float) -> None:
        self.reap(now)
        if now >= self.next_poll:
            self.next_poll = now + POLL_S
            cameras = self.call("camera list", self.client.cameras)
            if cameras is not None:
                self.wanted = cameras
        decided = plan(self.running, self.wanted, now, self.settings.max_cameras)
        for device_id in decided.stop:
            self.stop(device_id, "removed or turned off")
        for device_id in set(decided.no_slot) - self.unplaced:
            log.warning("%s waits: this hub runs at most %d cameras", device_id, self.settings.max_cameras)
        self.unplaced = set(decided.no_slot)
        launches = [*decided.restart, *(item.camera for item in decided.start)]
        if not launches or now < self.hold_until:
            return
        tokens = self.call("camera tokens", lambda: self.client.tokens([c.device_id for c in launches]))
        if tokens is None:
            self.hold_until = now + POLL_S
            return
        missing = [camera.device_id for camera in launches if camera.device_id not in tokens]
        if missing:
            log.warning("the API sent no token for %s; retrying in %.0f s", ", ".join(missing), POLL_S)
            self.hold_until = now + POLL_S
        for camera in decided.restart:
            if camera.device_id not in tokens:
                continue
            previous = self.running[camera.device_id]
            changed = camera.source != previous.camera.source
            self.stop(camera.device_id, "source changed" if changed else None)
            self.launch(camera, previous.slot, tokens[camera.device_id], now, 0 if changed else previous.failures)
        for item in decided.start:
            if item.camera.device_id in tokens:
                self.launch(item.camera, item.slot, tokens[item.camera.device_id], now, 0)

    def call[T](self, what: str, action: Callable[[], T]) -> T | None:
        try:
            result = action()
        except ApiError as exc:
            self.problem(f"{what} failed: {self.explain(exc)}")
            return None
        except httpx.HTTPError as exc:
            self.problem(f"{what} failed: cannot reach the API ({type(exc).__name__}); retrying")
            return None
        except ValueError:
            self.problem(f"{what} failed: the API sent an unreadable reply; retrying")
            return None
        if self.trouble:
            log.info("the API is reachable again")
            self.trouble = None
        return result

    def explain(self, exc: ApiError) -> str:
        if exc.status == 401:
            return "the API refused the hub token (401); check DINEMATE_HUB_TOKEN. Retrying"
        if exc.status == 404:
            return f"the API does not know hub '{self.hub_id}' or has no hub endpoints yet (404). Retrying"
        return f"{exc}. Retrying"

    def problem(self, text: str) -> None:
        if text != self.trouble:
            log.warning("%s", text)
            self.trouble = text

    def reap(self, now: float) -> None:
        for device_id, running in self.running.items():
            process = self.processes.get(device_id)
            if running.exited_at is not None or process is None:
                continue
            code = process.poll()
            if code is None:
                continue
            record_exit(running, now)
            log.warning(
                "%s (%s) stopped with code %s; restarting in %.0f s",
                device_id,
                running.camera.label,
                code,
                backoff(running.failures),
            )

    def launch(self, camera: Camera, slot: int, token: str, now: float, failures: int) -> None:
        port = self.settings.first_port + slot
        running = RunningCamera(camera, slot, now, failures=failures)
        self.running[camera.device_id] = running
        try:
            process = self.spawn(
                worker_command(self.settings, camera, port),
                worker_env(
                    self.environ,
                    token,
                    worker_source(camera.source, self.settings.videos_dir),
                    worker_threads(os.cpu_count() or 1, len(active_cameras(self.wanted))),
                ),
                camera.device_id,
            )
        except (OSError, ValueError) as exc:
            record_exit(running, now)
            log.warning("could not start %s (%s): %s", camera.device_id, camera.label, exc)
            return
        self.processes[camera.device_id] = process
        log.info(
            "started %s (%s) from %s, live view on port %d",
            camera.device_id,
            camera.label,
            mask_source(camera.source),
            port,
        )

    def stop(self, device_id: str, reason: str | None) -> None:
        running = self.running.pop(device_id, None)
        process = self.processes.pop(device_id, None)
        if process is not None:
            end(process)
        if running is not None and reason:
            log.info("stopped %s (%s): %s", device_id, running.camera.label, reason)

    def stop_all(self) -> None:
        for process in self.processes.values():
            if process.poll() is None:
                process.terminate()
        for device_id in list(self.running):
            self.stop(device_id, "hub stopping")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one DineMate vision worker per camera added in DineMate Business. Frames never leave memory."
    )
    parser.add_argument("--api", default=os.environ.get("DINEMATE_API_URL", DEFAULT_API))
    parser.add_argument("--hub-id", default=os.environ.get("DINEMATE_HUB_ID", "hub-local"))
    parser.add_argument("--token", default=os.environ.get("DINEMATE_HUB_TOKEN"))
    parser.add_argument(
        "--stream-host",
        default=os.environ.get("DINEMATE_STREAM_HOST", "localhost"),
        help="address owners' browsers use to reach the live views",
    )
    parser.add_argument("--first-port", type=int, default=int(os.environ.get("DINEMATE_STREAM_FIRST_PORT", "8090")))
    parser.add_argument("--max-cameras", type=int, default=MAX_CAMERAS)
    parser.add_argument("--model", default=os.environ.get("DINEMATE_MODEL", str(DEFAULT_MODEL)))
    parser.add_argument(
        "--videos-dir",
        default=os.environ.get("DINEMATE_TEST_VIDEOS_DIR", str(DEFAULT_VIDEOS)),
        help="folder holding test videos uploaded from the dashboards",
    )
    args = parser.parse_args(argv)
    if not args.token:
        parser.error("set --token or DINEMATE_HUB_TOKEN to the hub token")
    if args.max_cameras < 1:
        parser.error("--max-cameras must be at least 1")
    return args


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    load_env_file(ENV_FILE)
    args = parse_args(argv)
    settings = HubSettings(args.api, args.stream_host, args.first_port, args.max_cameras, args.model, args.videos_dir)
    client = HubClient(args.api, args.hub_id, args.token)
    hub = Hub(client, settings, args.hub_id)
    signal.signal(signal.SIGINT, hub.request_stop)
    signal.signal(signal.SIGTERM, hub.request_stop)
    log.info(
        "camera hub %s on %s; live views on ports %d-%d",
        args.hub_id,
        mask_source(args.api),
        args.first_port,
        args.first_port + args.max_cameras - 1,
    )
    try:
        hub.run()
    finally:
        client.close()
    log.info("camera hub stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())

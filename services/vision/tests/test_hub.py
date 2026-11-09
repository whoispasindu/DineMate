import logging
from collections.abc import Iterable
from pathlib import Path

import httpx
import pytest

from vision.client import ApiError
from vision.hub import (
    BACKOFF_S,
    DEFAULT_VIDEOS,
    HEALTHY_S,
    Camera,
    Hub,
    HubSettings,
    RunningCamera,
    backoff,
    cameras_from_response,
    mask_source,
    plan,
    record_exit,
    tokens_from_response,
    worker_command,
    worker_env,
    worker_source,
)

RTSP = "rtsp://admin:s3cret@192.168.1.20:554/stream1"


def cam(device_id: str, source: str = "rtsp://192.168.1.20/a", enabled: bool = True) -> Camera:
    return Camera(device_id, f"Label {device_id}", source, enabled)


def running(
    camera: Camera, slot: int, started_at: float = 0.0, exited_at: float | None = None, failures: int = 0
) -> RunningCamera:
    return RunningCamera(camera, slot, started_at, exited_at, failures)


@pytest.mark.parametrize(
    ("source", "shown"),
    [
        (RTSP, "rtsp://***@192.168.1.20:554/stream1"),
        ("rtsp://192.168.1.20/stream1", "rtsp://192.168.1.20/stream1"),
        ("http://user:p@ss@cam.local/video", "http://***@cam.local/video"),
        ("0", "0"),
        ("https://youtu.be/vls4DGvdqgM", "https://youtu.be/vls4DGvdqgM"),
        (
            f"Could not open video source '{RTSP}'.",
            "Could not open video source 'rtsp://***@192.168.1.20:554/stream1'.",
        ),
    ],
)
def test_mask_source_hides_credentials(source: str, shown: str) -> None:
    assert mask_source(source) == shown


def test_new_cameras_get_the_first_free_slots() -> None:
    result = plan({}, [cam("a"), cam("b"), cam("c", enabled=False)], 0.0)
    assert [(s.camera.device_id, s.slot) for s in result.start] == [("a", 0), ("b", 1)]
    assert result.stop == [] and result.restart == []


def test_running_cameras_keep_their_slot() -> None:
    current = {"b": running(cam("b"), 1)}
    result = plan(current, [cam("a"), cam("b"), cam("c")], 10.0)
    assert [(s.camera.device_id, s.slot) for s in result.start] == [("a", 0), ("c", 2)]
    assert result.restart == []


def test_removed_and_disabled_cameras_stop_and_free_their_slot() -> None:
    current = {"a": running(cam("a"), 0), "b": running(cam("b"), 1)}
    result = plan(current, [cam("b", enabled=False), cam("c")], 10.0, slots=1)
    assert sorted(result.stop) == ["a", "b"]
    assert [(s.camera.device_id, s.slot) for s in result.start] == [("c", 0)]


def test_source_change_restarts_at_once() -> None:
    current = {"a": running(cam("a", "rtsp://old/x"), 3)}
    result = plan(current, [cam("a", "rtsp://new/x")], 1.0)
    assert result.restart == [cam("a", "rtsp://new/x")]
    assert result.start == [] and result.stop == []


def test_exited_worker_waits_for_its_backoff() -> None:
    current = {"a": running(cam("a"), 0, exited_at=100.0, failures=2)}
    assert plan(current, [cam("a")], 100.0 + BACKOFF_S[1] - 0.1).restart == []
    assert plan(current, [cam("a")], 100.0 + BACKOFF_S[1]).restart == [cam("a")]


def test_cameras_beyond_capacity_wait_for_a_slot() -> None:
    result = plan({}, [cam("a"), cam("b"), cam("c")], 0.0, slots=2)
    assert [s.camera.device_id for s in result.start] == ["a", "b"]
    assert result.no_slot == ["c"]


def test_duplicates_and_empty_sources_are_ignored() -> None:
    result = plan({}, [cam("a"), cam("a", "rtsp://other/x"), cam("b", "  ")], 0.0)
    assert [(s.camera.source, s.slot) for s in result.start] == [("rtsp://192.168.1.20/a", 0)]


def test_backoff_grows_then_caps() -> None:
    assert [backoff(n) for n in (1, 2, 3, 4, 10)] == [5.0, 15.0, 60.0, 60.0, 60.0]


def test_record_exit_counts_quick_failures_and_resets_after_a_healthy_run() -> None:
    quick = running(cam("a"), 0, started_at=0.0, failures=2)
    record_exit(quick, 10.0)
    assert quick.failures == 3 and quick.retry_at == 10.0 + 60.0
    healthy = running(cam("a"), 0, started_at=0.0, failures=3)
    record_exit(healthy, HEALTHY_S + 1)
    assert healthy.failures == 1 and healthy.retry_at == HEALTHY_S + 1 + 5.0


def test_camera_list_is_read_leniently() -> None:
    data = {
        "server_time": "2026-11-11T10:00:00Z",
        "hub_id": "hub-local",
        "cameras": [
            {"device_id": "cam-1a2b", "label": "Counter", "source": RTSP, "enabled": True},
            {"device_id": "cam-2", "source": "0", "enabled": False},
            {"label": "no id"},
            "junk",
        ],
    }
    assert cameras_from_response(data) == [
        Camera("cam-1a2b", "Counter", RTSP, True),
        Camera("cam-2", "cam-2", "0", False),
    ]
    assert cameras_from_response({"cameras": None}) == []
    assert cameras_from_response([]) == []


def test_tokens_are_read_by_device() -> None:
    data = {"server_time": "x", "tokens": [{"device_id": "cam-1", "token": "t1"}, {"device_id": "cam-2"}]}
    assert tokens_from_response(data) == {"cam-1": "t1"}
    assert tokens_from_response({}) == {}


def test_worker_gets_token_and_source_only_through_its_environment() -> None:
    settings = HubSettings("http://api:8000/api/v1", "cafe-pc", 8090, 8, "models/yolo11n.pt")
    command = worker_command(settings, cam("a", RTSP), 8092)
    assert "secret-token" not in " ".join(command) and RTSP not in command
    assert command[command.index("--device") + 1] == "a"
    assert command[command.index("--stream-port") + 1] == "8092"
    assert command[command.index("--stream-host") + 1] == "cafe-pc"
    env = worker_env({"PATH": "/bin", "DINEMATE_HUB_TOKEN": "hub-secret"}, "secret-token", RTSP)
    assert env["DINEMATE_DEVICE_TOKEN"] == "secret-token" and env["DINEMATE_SOURCE"] == RTSP
    assert "DINEMATE_HUB_TOKEN" not in env and env["PATH"] == "/bin"


def test_test_videos_play_from_the_shared_folder_on_a_loop() -> None:
    expected = str(Path("/data/test-videos") / "lunch-abcdef.mp4")
    assert worker_source("video:lunch-abcdef.mp4", "/data/test-videos") == expected
    assert worker_source(RTSP, "/data/test-videos") == RTSP
    for bad in ("video:../x.mp4", "video:", "video:.hidden.mp4", "video:a/b.mp4", "video:a\\b.mp4", "video:C:x.mp4"):
        with pytest.raises(ValueError):
            worker_source(bad, "/data/test-videos")
    assert "--loop" in worker_command(HubSettings("http://api/api/v1"), cam("a", RTSP), 8090)
    hub, _, spawn = make_hub([cam("a", "video:../../etc/passwd"), cam("b", "video:clip-abcdef.mp4")])
    hub.tick(0.0)
    assert [env["DINEMATE_SOURCE"] for _, env, _ in spawn.started] == [str(Path(DEFAULT_VIDEOS) / "clip-abcdef.mp4")]
    assert hub.running["a"].exited_at == 0.0


class FakeProcess:
    def __init__(self) -> None:
        self.code: int | None = None
        self.terminated = False

    def poll(self) -> int | None:
        return self.code

    def terminate(self) -> None:
        self.terminated = True
        self.code = -15

    def kill(self) -> None:
        self.code = -9

    def wait(self, timeout: float | None = None) -> int:
        return self.code if self.code is not None else 0


class FakeApi:
    def __init__(self, cameras: list[Camera]) -> None:
        self.list = cameras
        self.error: Exception | None = None
        self.token_calls: list[list[str]] = []

    def cameras(self) -> list[Camera]:
        if self.error:
            raise self.error
        return self.list

    def tokens(self, device_ids: Iterable[str]) -> dict[str, str]:
        ids = list(device_ids)
        self.token_calls.append(ids)
        return {device_id: f"token-{device_id}-{len(self.token_calls)}" for device_id in ids}


class FakeSpawn:
    def __init__(self) -> None:
        self.started: list[tuple[list[str], dict[str, str], FakeProcess]] = []

    def __call__(self, command: list[str], env: dict[str, str], name: str) -> FakeProcess:
        process = FakeProcess()
        self.started.append((command, env, process))
        return process


class RefusingApi(FakeApi):
    def tokens(self, device_ids: Iterable[str]) -> dict[str, str]:
        self.token_calls.append(list(device_ids))
        raise ApiError("POST /devices/hub-local/hub/tokens → 500: boom", 500)


def make_hub(cameras: list[Camera], api: FakeApi | None = None) -> tuple[Hub, FakeApi, FakeSpawn]:
    api, spawn = api or FakeApi(cameras), FakeSpawn()
    hub = Hub(api, HubSettings("http://api/api/v1"), spawn=spawn, environ={"PATH": "/bin"})
    return hub, api, spawn


def test_hub_starts_each_camera_once_with_a_fresh_token() -> None:
    hub, api, spawn = make_hub([cam("a"), cam("b")])
    hub.tick(0.0)
    hub.tick(1.0)
    hub.tick(20.0)
    assert api.token_calls == [["a", "b"]]
    assert [env["DINEMATE_DEVICE_TOKEN"] for _, env, _ in spawn.started] == ["token-a-1", "token-b-1"]
    assert {r.slot for r in hub.running.values()} == {0, 1}


def test_hub_restarts_an_exited_worker_after_backoff_on_the_same_port() -> None:
    hub, api, spawn = make_hub([cam("a")])
    hub.tick(0.0)
    spawn.started[0][2].code = 1
    hub.tick(1.0)
    hub.tick(1.0 + BACKOFF_S[0] - 0.5)
    assert len(spawn.started) == 1
    hub.tick(1.0 + BACKOFF_S[0])
    assert api.token_calls == [["a"], ["a"]]
    first, second = spawn.started[0][0], spawn.started[1][0]
    assert first[first.index("--stream-port") + 1] == second[second.index("--stream-port") + 1] == "8090"
    assert hub.running["a"].failures == 1


def test_hub_stops_removed_cameras_and_restarts_on_source_change() -> None:
    hub, api, spawn = make_hub([cam("a"), cam("b")])
    hub.tick(0.0)
    api.list = [cam("b", "rtsp://new/x")]
    hub.tick(16.0)
    assert spawn.started[0][2].terminated and spawn.started[1][2].terminated
    assert list(hub.running) == ["b"] and hub.running["b"].slot == 1
    assert spawn.started[2][1]["DINEMATE_SOURCE"] == "rtsp://new/x"


def test_hub_keeps_workers_and_warns_once_when_the_api_fails(caplog: pytest.LogCaptureFixture) -> None:
    hub, api, spawn = make_hub([cam("a")])
    hub.tick(0.0)
    api.error = ApiError("GET /devices/hub-local/hub/cameras → 401: nope", 401)
    with caplog.at_level(logging.WARNING, logger="dinemate.hub"):
        hub.tick(16.0)
        hub.tick(32.0)
        api.error = httpx.ConnectError("refused")
        hub.tick(48.0)
    assert list(hub.running) == ["a"] and not spawn.started[0][2].terminated
    warnings = [r.getMessage() for r in caplog.records]
    assert len(warnings) == 2 and "401" in warnings[0] and "cannot reach" in warnings[1]
    assert all("token-" not in m for m in warnings)


def test_hub_holds_starts_when_tokens_fail() -> None:
    hub, api, spawn = make_hub([], RefusingApi([cam("a")]))
    hub.tick(0.0)
    hub.tick(1.0)
    hub.tick(2.0)
    assert len(api.token_calls) == 1 and spawn.started == []


def test_stop_all_ends_every_worker() -> None:
    hub, _, spawn = make_hub([cam("a"), cam("b")])
    hub.tick(0.0)
    hub.stop_all()
    assert hub.running == {} and all(p.terminated for _, _, p in spawn.started)

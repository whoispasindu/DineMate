import hashlib
import http.client
import threading
import time
from pathlib import Path

import httpx
import numpy as np
import pytest

from vision.badges import badge_codes, pick_badge
from vision.counting import Detection
from vision.enrol import EnrolError, choose, ready_to_enrol
from vision.faces import FaceReader, largest_face
from vision.fetch_models import ModelFile, fetch, is_valid
from vision.identity import CombinedReader, Throttle, average_template, head_box, merge, samples_agree
from vision.staff import Evidence, WorkerView, similarity
from vision.stream import FrameHub, LiveServer, blur_boxes, part, sign, token_hash, verify


def person(track: int | None, x1: float = 100, y1: float = 100, x2: float = 200, y2: float = 400) -> Detection:
    return Detection(track, x1, y1, x2, y2, 0.9)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls = 0

    def faces(self, image: np.ndarray) -> np.ndarray:
        self.calls += 1
        return np.array([[2, 2, 60, 60, *([0] * 10), 0.95], [1, 1, 10, 10, *([0] * 10), 0.9]], dtype=np.float32)

    def embed(self, image: np.ndarray, face: np.ndarray) -> tuple[float, ...]:
        return (1.0, 0.0, float(image.shape[1]))


def test_head_box_takes_the_top_of_the_person_and_stays_in_frame() -> None:
    box = head_box(person(1, 0, 0, 100, 300), 640, 480)
    assert box is not None
    x1, y1, x2, y2 = box
    assert (x1, y1) == (0, 0) and x2 <= 640 and y2 == 120
    assert head_box(person(1, 10, 10, 10.5, 50), 640, 480) is None


def test_throttle_waits_per_track_and_forgets_lost_tracks() -> None:
    throttle = Throttle(2.0)
    assert throttle.due(1, 0.0) and throttle.due(2, 0.5)
    assert not throttle.due(1, 1.0)
    assert throttle.due(1, 2.1)
    throttle.keep({1})
    assert set(throttle.last) == {1}


def test_average_template_is_a_unit_vector_and_samples_must_agree() -> None:
    template = average_template([(3.0, 0.0, 0.0), (0.0, 4.0, 0.0)])
    assert pytest.approx(sum(v * v for v in template)) == 1.0
    assert similarity(template, (1, 1, 0)) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        average_template([])
    assert samples_agree([(1, 0.1), (1, 0.0), (0.9, 0.1)], 0.9)
    assert not samples_agree([(1, 0), (0, 1)], 0.5)
    assert not samples_agree([(1, 0)], 0.5)


def test_largest_face_ignores_small_faces() -> None:
    faces = np.array([[0, 0, 30, 30, *([0] * 11)], [0, 0, 50, 45, *([0] * 11)], [0, 0, 90, 20, *([0] * 11)]])
    best = largest_face(faces, 40)
    assert best is not None and best[2] == 50
    assert largest_face(None) is None
    assert largest_face(faces, 100) is None


def test_face_reader_only_embeds_workers_it_is_given_and_throttles_them() -> None:
    clock = Clock()
    embedder = FakeEmbedder()
    reader = FaceReader(embedder, every_s=2.0, clock=clock)  # type: ignore[arg-type]
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    workers = [WorkerView(person(7), "counter"), WorkerView(person(None), "counter")]
    found = reader.read(image, workers)
    assert [e.track_id for e in found] == [7] and found[0].embedding is not None
    assert reader.read(image, workers) == []
    clock.now = 2.5
    assert len(reader.read(image, workers)) == 1
    assert embedder.calls == 2


def test_badges_need_one_clear_code() -> None:
    assert badge_codes(None) == []
    assert badge_codes(np.array([[11], [300], [12]])) == [11, 12]
    assert pick_badge([11, 11]) == 11
    assert pick_badge([11, 12]) is None
    assert pick_badge([]) is None


def test_merge_prefers_a_badge_over_a_face_for_the_same_track() -> None:
    face = Evidence(3, embedding=(1.0,))
    badge = Evidence(3, badge_code=11)
    other = Evidence(4, embedding=(0.5,))
    merged = {e.track_id: e for e in merge([face, other, badge])}
    assert merged[3].badge_code == 11 and merged[4] is other

    class Fixed:
        def __init__(self, items: list[Evidence]) -> None:
            self.items = items

        def read(self, image: np.ndarray, people: object) -> list[Evidence]:
            return self.items

    combined = CombinedReader([Fixed([face]), Fixed([badge])])
    assert combined.read(np.zeros((1, 1, 3)), []) == [badge]


def test_live_links_are_signed_short_lived_and_bound_to_the_device() -> None:
    key = token_hash("camera-token")
    assert key == hashlib.sha256(b"camera-token").hexdigest()
    signature = sign(key, "cam-1", 1060)
    assert verify(key, "cam-1", "1060", signature, 1000)
    assert not verify(key, "cam-1", "1060", signature, 1061)
    assert not verify(key, "cam-2", "1060", signature, 1000)
    assert not verify(key, "cam-1", "1061", signature, 1000)
    assert not verify(key, "cam-1", "9999", sign(key, "cam-1", 9999), 1000)
    assert not verify(key, "cam-1", "soon", signature, 1000)
    assert not verify(key, "cam-1", None, signature, 1000)


def test_every_face_except_named_staff_is_blurred() -> None:
    people = [person(1), person(2, 300, 50, 400, 350), person(None, 500, 100, 600, 400)]
    boxes = blur_boxes(people, {1}, 640, 480)
    assert len(boxes) == 2
    assert all(b[0] >= 290 for b in boxes)


def test_frame_hub_hands_out_only_new_frames() -> None:
    hub = FrameHub()
    assert not hub.wanted(10.0)
    hub.join()
    assert hub.wanted(10.0)
    hub.publish(b"a", 10.0)
    assert not hub.wanted(10.1)
    assert hub.wait(0, 0.01) == (1, b"a")
    assert hub.wait(1, 0.01) == (1, b"a")
    hub.leave()
    assert hub.jpeg is None
    assert part(b"xy").endswith(b"\r\n\r\nxy\r\n")


def test_live_server_refuses_bad_links_and_streams_good_ones() -> None:
    server = LiveServer(0, "cam-1", "camera-token", host="127.0.0.1")
    server.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
        connection.request("GET", "/live?exp=1&sig=bad")
        assert connection.getresponse().status == 403
        connection.close()

        expires = int(time.time()) + 60
        signature = sign(token_hash("camera-token"), "cam-1", expires)
        connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
        connection.request("GET", f"/live?exp={expires}&sig={signature}")
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader("Content-Type", "").startswith("multipart/x-mixed-replace")
        publisher = threading.Timer(0.2, lambda: server.hub.publish(b"jpeg-bytes", 1.0))
        publisher.start()
        chunk = response.read(20)
        assert b"--frame" in chunk
        connection.close()
    finally:
        server.close()


def test_fetch_checks_size_and_checksum(tmp_path: Path) -> None:
    body = b"model-bytes"
    good = ModelFile("m.onnx", "https://example.test/m.onnx", hashlib.sha256(body).hexdigest(), len(body))
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body)))
    path = fetch(good, tmp_path, client)
    assert is_valid(path, good)
    bad = ModelFile("x.onnx", "https://example.test/x.onnx", "0" * 64, len(body))
    with pytest.raises(ValueError):
        fetch(bad, tmp_path, client)
    assert not (tmp_path / "x.onnx").exists() and not (tmp_path / "x.part").exists()


def test_enrolment_lists_only_consented_face_staff() -> None:
    signed = "2026-11-01"
    items = [
        {"id": "a", "display_name": "Barista 1", "role_label": "Barista", "method": "face", "consent_at": signed},
        {"id": "b", "display_name": "Cashier 1", "role_label": "Cashier", "method": "badge", "consent_at": signed},
        {"id": "c", "display_name": "Kitchen 1", "role_label": "Kitchen", "method": "face", "consent_at": None},
    ]
    ready = ready_to_enrol(items)
    assert [s["id"] for s in ready] == ["a"]
    assert choose(ready, "Barista 1")["id"] == "a"
    with pytest.raises(EnrolError):
        choose(ready, "Kitchen 1")
    with pytest.raises(EnrolError):
        choose([], None)

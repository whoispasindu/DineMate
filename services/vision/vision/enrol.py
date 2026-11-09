import argparse
import getpass
import os
import sys
import time
from typing import Any

import httpx

from vision.faces import MODELS_DIR, FaceEmbedder, largest_face, models_ready
from vision.identity import average_template, samples_agree

SHOTS = 5
SHOT_GAP_S = 0.8
AGREE = 0.45
WINDOW = "DineMate face enrolment (nothing is saved)"


class EnrolError(Exception):
    pass


def ready_to_enrol(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s for s in items if s.get("method") == "face" and s.get("consent_at") and s.get("active", True)]


def choose(items: list[dict[str, Any]], wanted: str | None) -> dict[str, Any]:
    if not items:
        raise EnrolError("No one is ready. Record consent and set the method to Face in Privacy & consent first.")
    if wanted:
        match = [s for s in items if wanted in (s["id"], s["display_name"])]
        if not match:
            raise EnrolError(f"{wanted} has no recorded consent or does not use face recognition.")
        return match[0]
    for index, staff in enumerate(items, start=1):
        enrolled = " (enrolled, will replace)" if staff.get("has_template") else ""
        print(f"  {index}. {staff['display_name']} – {staff['role_label']}{enrolled}")
    picked = input("Who is in front of the camera? Number: ").strip()
    if not picked.isdigit() or not 1 <= int(picked) <= len(items):
        raise EnrolError("No one picked.")
    return items[int(picked) - 1]


class Api:
    def __init__(self, base: str) -> None:
        self.http = httpx.Client(base_url=base.rstrip("/"), timeout=15)

    def _json(self, response: httpx.Response) -> Any:
        if response.status_code >= 400:
            try:
                message = response.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                message = response.text[:200]
            raise EnrolError(f"{response.status_code}: {message}")
        return response.json()

    def login(self, email: str, password: str) -> None:
        body = self._json(self.http.post("/auth/login", json={"email": email, "password": password}))
        self.http.headers["Authorization"] = f"Bearer {body['access_token']}"

    def venue(self, wanted: str | None) -> str:
        items = self._json(self.http.get("/business/venues"))["items"]
        ids = [v["id"] for v in items]
        if wanted:
            if wanted not in ids:
                raise EnrolError(f"Venue {wanted} is not in your organisation.")
            return wanted
        if not ids:
            raise EnrolError("Your organisation has no venues.")
        return str(ids[0])

    def staff(self, venue: str) -> list[dict[str, Any]]:
        return list(self._json(self.http.get(f"/business/venues/{venue}/staff"))["items"])

    def save(self, staff_id: str, template: list[float]) -> dict[str, Any]:
        return dict(self._json(self.http.post(f"/business/staff/{staff_id}/face", json={"template": template})))


def capture(source: str, shots: int) -> list[tuple[float, ...]]:
    import cv2

    embedder = FaceEmbedder(MODELS_DIR)
    camera = cv2.VideoCapture(int(source) if source.isdigit() else source)
    if not camera.isOpened():
        raise EnrolError(f"Could not open camera {source}.")
    samples: list[tuple[float, ...]] = []
    last = 0.0
    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    try:
        while len(samples) < shots:
            ok, frame = camera.read()
            if not ok:
                raise EnrolError("The camera stopped sending frames.")
            faces = embedder.faces(frame)
            face = largest_face(faces, 80)
            several = faces is not None and len(faces) > 1
            view = frame.copy()
            note = "Only one person in view, please" if several else "Look at the camera"
            if face is not None and not several:
                x, y, w, h = (int(v) for v in face[:4])
                cv2.rectangle(view, (x, y), (x + w, y + h), (120, 200, 60), 2)
                now = time.monotonic()
                if now - last >= SHOT_GAP_S:
                    samples.append(embedder.embed(frame, face))
                    last = now
                note = f"Hold still, turn slightly between shots ({len(samples)}/{shots})"
            cv2.putText(view, note, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(view, "Esc to cancel", (16, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1, cv2.LINE_AA)
            cv2.imshow(WINDOW, view)
            if cv2.waitKey(1) & 0xFF == 27:
                raise EnrolError("Cancelled. Nothing was sent.")
    finally:
        camera.release()
        cv2.destroyAllWindows()
    return samples


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Enrol a consented worker's face. Only a 128-number template is sent; no photo is kept."
    )
    parser.add_argument("--api", default=os.environ.get("DINEMATE_API_URL", "http://localhost:8000/api/v1"))
    parser.add_argument("--email", required=True, help="owner sign-in email")
    parser.add_argument("--venue", help="venue id (default: your first venue)")
    parser.add_argument("--staff", help="staff id or display name (default: pick from a list)")
    parser.add_argument("--camera", default="0", help="camera index or stream URL")
    parser.add_argument("--shots", type=int, default=SHOTS)
    args = parser.parse_args(argv)
    if not models_ready(MODELS_DIR):
        print("Face models are missing. Run: uv run python -m vision.fetch_models", file=sys.stderr)
        return 1
    api = Api(args.api)
    try:
        api.login(args.email, getpass.getpass(f"Password for {args.email}: "))
        staff = choose(ready_to_enrol(api.staff(api.venue(args.venue))), args.staff)
        print(f"Enrolling {staff['display_name']}. Ask them to face the camera.")
        samples = capture(args.camera, max(2, args.shots))
        if not samples_agree(samples, AGREE):
            raise EnrolError("The shots do not look like one person. Try again with better light. Nothing was sent.")
        saved = api.save(staff["id"], average_template(samples))
    except (EnrolError, httpx.HTTPError) as exc:
        print(exc, file=sys.stderr)
        return 1
    finally:
        api.http.close()
    print(f"Saved a face template for {saved['staff']['display_name']}. No photos were kept.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# DineMate vision worker

Counts seated people per seating zone from a webcam or a video file and posts **counts only** to the API. Frames stay in memory and are never written to disk; the optional preview window is local and saves nothing.

Pipeline (plan Section 7.3): YOLO11n person detection → ByteTrack IDs → torso point inside a zone polygon → walkway/queue areas dropped → optional seated filter → dwell (default 20 s) → 60 s median → uncertainty band → `POST /devices/{id}/occupancy` every 15 s, heartbeat every 30 s, layout re-read every 30 s.

## Webcam demo (about 10 minutes)

Run everything from `services/vision` unless noted. The API must be running (`pnpm stack:up` from the repo root).

1. **Install** (first time; downloads PyTorch CPU and YOLO):

   ```bash
   uv sync
   ```

2. **Draw your zones** on one webcam frame. Click the corners of a seating area, press Enter, answer the prompts (type, name, seats). Mark walkways too. Press S to save.

   ```bash
   uv run python -m vision.zone_tool --source 0 --out layouts/webcam.json
   ```

3. **Register the camera** (from `services/api`, or inside the API container). This creates the canteen and zones and prints the device token once. A short dwell makes desk testing quicker.

   ```bash
   uv run python -m app.devices_cli register --id cam-webcam --canteen pilot --canteen-name "Pilot (webcam)" --layout ../vision/layouts/webcam.json --dwell-s 10
   ```

4. **Save the token**: copy `.env.example` to `.env` and paste the token. `.env` is git-ignored.

5. **Run the worker** with a local preview window (Q to quit):

   ```bash
   uv run python -m vision.worker --preview
   ```

6. Open the student app in API mode (`pnpm dev:student:api` from the repo root). Sit in a zone: after the dwell and the next post, "Pilot (webcam)" shows about one seat taken. Stop the worker: the zone turns grey after 2 min and shows "No info right now" after 10 min.

## Canteen videos

Keep videos in `data/videos/` at the repo root (git-ignored). Use the same steps with `--source path/to/video.mp4`; add `--loop` to keep a short clip running, or `--fast` to process it as fast as the CPU allows. Draw zones from a frame of the same video (`--at 12` picks the frame 12 s in).

Offline check without the API (prints readings instead of posting):

```bash
uv run python -m vision.worker --source ../../data/videos/lunch.mp4 --layout layouts/lunch.json --dry-run --fast
```

## Settings

Per-device settings live in the device config served by the API (`dwell_s`, `post_every_s`, `smoothing_s`, `fps`, `min_confidence`, `seated_ratio`, `h_stand_a`, `h_stand_b`). Set the first four with `devices_cli register`. The seated filter stays off until `h_stand_a`/`h_stand_b` are calibrated (Phase 3).

## Tests

```bash
uv run pytest -q
```

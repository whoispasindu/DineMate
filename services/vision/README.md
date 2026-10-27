# DineMate vision worker

Counts seated people per seating zone from a webcam or a video file and posts **counts only** to the API. Frames stay in memory and are never written to disk; the optional preview window is local and saves nothing.

Pipeline (plan Section 7.3): YOLO11n person detection → ByteTrack IDs → torso point inside a zone polygon → walkway/queue areas dropped → optional seated filter → dwell (default 20 s) → 60 s median → uncertainty band → `POST /devices/{id}/occupancy` every 15 s, heartbeat every 30 s, layout re-read every 30 s.

## Webcam demo (about 10 minutes)

Run everything from `services/vision` unless noted. The API must be running (`pnpm stack:up` from the repo root).

1. **Install** (first time; downloads PyTorch CPU and YOLO):

   ```bash
   uv sync
   ```

2. **Draw your zones** on one webcam frame. Everything happens in the window; prompts appear on the dark bar at the top. Click the corners of a seating area and press Enter, then press S (seating), type a name and press Enter, then type the number of seats and press Enter. Mark queues (Q) and walkways (W) the same way. U undoes a point, Esc clears the shape in progress, S saves, Q quits. Large frames (Full HD, 4K) are scaled to fit the screen.

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

A ready-made zone covering most of the frame is in `layouts/webcam-desk.json` if you want to skip step 2.

**Camera won't open on Windows** ("can't be used to capture by index"): open Settings → Privacy & security → Camera and turn on both **Camera access** and **Let desktop apps access your camera** (near the bottom of the page). Also close other apps using the camera.

## Canteen videos

Keep videos in `data/videos/` at the repo root (git-ignored). Use the same steps with `--source path/to/video.mp4`; add `--loop` to keep a short clip running, or `--fast` to process it as fast as the CPU allows. Draw zones from a frame of the same video (`--at 12` picks the frame 12 s in).

Offline check without the API (prints readings instead of posting). The zone tool only draws and saves; this is the step that tracks people. For clips shorter than about a minute, shorten the timings so people are counted before the clip ends:

```bash
uv run python -m vision.worker --source ../../data/videos/lunch.mp4 --layout layouts/lunch.json --dry-run --preview --loop --dwell-s 3 --smoothing-s 6 --post-every-s 3
```

`--preview` plays the video with boxes: green = counted, yellow = waiting for the dwell, grey = outside zones. Add `--fast` to skip real-time playback.

## Settings

Detection size: the worker uses YOLO at 1280 px for sources 1920 px wide or more (Full HD, 4K) and 640 px otherwise; people in high-resolution canteen footage are too small at 640. Override with `--imgsz`. The chosen size is logged at start.

Per-device settings live in the device config served by the API (`dwell_s`, `post_every_s`, `smoothing_s`, `fps`, `min_confidence`, `seated_ratio`, `h_stand_a`, `h_stand_b`). Set the first four with `devices_cli register`. The seated filter stays off until `h_stand_a`/`h_stand_b` are calibrated (Phase 3).

## Tests

```bash
uv run pytest -q
```

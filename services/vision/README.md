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

Keep videos in `data/videos/` at the repo root (git-ignored), or anywhere on disk.

**Easiest: the studio.** One window: draw zones on the first frame, press S, and the video starts playing with tracking boxes and live counts. Everything is scaled to fit the screen, and nothing is saved except the zones.

```bash
uv run python -m vision.studio "C:\path\to\lunch.mp4"
```

- Zones are saved to `layouts/<video name>.json` and reused next time; press **Z** while playing to edit them (or start with `--redraw`).
- **Space** pauses, **Q** quits. The video loops.
- Clips shorter than 90 s automatically count people after 3 s and post every 3 s; override with `--dwell-s`, `--smoothing-s`, `--post-every-s`.
- Counts are also printed in the terminal. Use `--at 12` to draw on the frame 12 s in, `--fast` to skip real-time playback.
- `uv run python -m vision.studio` with no path uses the webcam.

**Same thing through the API** (counts appear in the student app): register the video as a device with the zones file (step 3 above), then run the worker with `--source path/to/video.mp4 --loop --preview`.

Offline check from the terminal only (prints readings, no window unless `--preview`):

```bash
uv run python -m vision.worker --source ../../data/videos/lunch.mp4 --layout layouts/lunch.json --dry-run --preview --loop --dwell-s 3 --smoothing-s 6 --post-every-s 3
```

Boxes in the studio and in `--preview`: green = counted, yellow = waiting for the dwell, grey = outside zones or in a walkway. Both windows scale to fit the screen.

## Checking accuracy against your own counts (plan Section 7.6)

1. Draw zones for each video with the studio (names matter: they go in the CSV).
2. Pause the video at a few moments (every 10–30 s works) and count the **seated** people in each zone yourself. Better still, have two people count separately and use the average.
3. Write the counts in a CSV like `validation/counts.example.csv`:

   ```csv
   video,layout,t_seconds,zone,count
   ../../../data/videos/lunch-1.mp4,,30,Front tables,12
   ```

   `video` and `layout` are relative to the CSV file. Leave `layout` empty to use `layouts/<video name>.json`.

4. Run it (use the same `--dwell-s` / `--smoothing-s` you'd use live; short clips need short values):

   ```bash
   uv run python -m vision.validate validation/counts.csv --out validation/results.csv
   ```

It prints, per video and overall: **MAE** (average seats off), **bias** (+ means over-counting), **±2** (share within 2 seats), **in range** (share where your count falls inside the shown range; aim for about 80%) and **level ok** (same status word). The plan's targets: MAE ≤ 3 seats and ≥ 80% within ±3 on a 24–48-seat zone (Section 20). Keep counts files out of git if they name real places or times you don't want shared; `validation/*.csv` other than the example is ignored.

## Settings

Detection size: the worker uses YOLO at 1280 px for sources 1920 px wide or more (Full HD, 4K) and 640 px otherwise; people in high-resolution canteen footage are too small at 640. Override with `--imgsz`. The chosen size is logged at start.

Per-device settings live in the device config served by the API (`dwell_s`, `post_every_s`, `smoothing_s`, `fps`, `min_confidence`, `seated_ratio`, `h_stand_a`, `h_stand_b`). Set the first four with `devices_cli register`. The seated filter stays off until `h_stand_a`/`h_stand_b` are calibrated (Phase 3).

## Tests

```bash
uv run pytest -q
```

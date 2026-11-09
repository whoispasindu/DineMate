# DineMate vision worker

Counts seated people per seating zone from a webcam or a video file and posts **counts only** to the API. Frames stay in memory and are never written to disk; the optional preview window is local and saves nothing.

With seats placed, the worker tracks each seat instead (see Seats below). Without seats, the pipeline (plan Section 7.3) is: YOLO11s person detection → ByteTrack IDs → torso point inside a zone polygon → walkway/queue areas dropped → optional seated filter → dwell (default 20 s) → 60 s median → uncertainty band → `POST /devices/{id}/occupancy` every 15 s, heartbeat every 30 s, layout re-read every 30 s.

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

## YouTube streams and videos (testing)

Public YouTube streams and videos give extra angles, lighting and crowd sizes for testing counts, seats and queues. `--source` accepts a YouTube link. The worker resolves it with yt-dlp to a 720p (or lower) H.264 stream and reads it in memory; nothing is downloaded or saved. For a live stream it fetches a fresh link when the stream drops, up to 5 times in a row.

```bash
uv run --with yt-dlp python -m vision.worker --source "https://youtu.be/<id>" --layout layouts/test-youtube-cafe.json --dry-run
```

Draw a layout for each feed with the zone tool (`--source` takes the same link), and keep it as `layouts/test*.json`, which is git-ignored. With `--layout`, the worker keeps that layout and does not take one from the API.

Use these feeds for counting only. Never enrol or recognise anyone in them, keep screenshots blurred, and don't publish anything that identifies the place or people. YouTube's terms don't allow downloading, so keep clips out of `data/videos/` unless the video's licence allows reuse.

## Seats (Phase 7)

A zone can also hold **seats**: one point per chair. With seats, the worker tracks every seat instead of counting people in the zone, so it can tell sitting from standing and a bag from a person.

| State    | Meaning                                                            |
| -------- | ------------------------------------------------------------------ |
| free     | Empty chair seen clearly for 30 s, nothing on it or in front of it |
| occupied | A seated person stayed for the dwell time (shown as "taken")       |
| held     | Belongings on or in front of the seat, nobody sitting              |
| unknown  | The seat is hidden (crowd, standing people, poor view)             |

Only free seats are ever counted as free. Held and hidden seats count as taken in the zone reading, so the student app never shows a seat it can't see.

**Placing seats.** In the zone tool or the studio, draw the seating zones as before, then press **T** and click each chair where a seated person's hips would be. **U** removes the last seat, **T** finishes. A zone's capacity becomes its seat count. The console's Zones page has the same thing: select a seating shape and press **Place seats**.

**How a seat is decided** (`vision/posture.py`, `vision/seats.py`, both unit-tested without YOLO):

- People come from the pose model (`--pose-model`, default `models/yolo11s-pose.pt`, downloaded on first use). Bent knees mean sitting, straight legs mean standing, and hips well above the seat point mean standing. When legs are hidden the height calibration is used; conflicting signals are "unsure".
- Belongings and table items (backpack, handbag, suitcase, laptop, book, cup, bowl, bottle, cutlery, food) come from the normal model every `objects_every_s` (5 s).
- A person who leaves a bag behind turns the seat **held** straight away; it turns **occupied** again within 3 s when they come back. A bag on an empty seat holds it after 20 s.
- A seat hidden by standing people keeps its last state for up to 2 minutes, so a crowd walking past never creates a free seat. A free seat that stays hidden for 10 s turns **unknown**.
- Plates left with nobody there mark the seat **free soon**; after 5 minutes it turns free.
- A zone is **crowded** when 40% or more of its seats are hidden, or when many people are standing in it.

Seat circles in the studio and `--preview`: green free, red taken, amber held, grey hidden. The worker posts the zone readings as before plus a seat snapshot to `POST /devices/{id}/seats` (states and how long each has lasted, never images or identities).

## Staff mode (DineMate Business, Phase 9)

For cafés and restaurants, the worker can also time consented staff in their **work areas** and count the queue. It is on only when the layout has work areas **and** `GET /devices/{id}/staff-templates` returns enrolled staff; otherwise nothing changes.

**Marking work areas.** In the zone tool or the studio, outline an area, press Enter, then **K** (counter), **H** (kitchen) or **F** (floor). Work areas are saved under `work` in the layout file and never hide anyone from seat counting. Queue areas (**Q**) are reused for queue length.

**How it works** (`vision/staff.py`, unit-tested without YOLO):

- Only tracks whose foot point is inside a work area are ever passed to the identity reader. Customers elsewhere are never matched or named, and a worker who steps out of every work area loses their name at once.
- Evidence comes from an `IdentityReader` (face embedding or badge code per track). A track is named after 3 consistent matches above the face threshold (0.45 cosine, SFace) or the same badge code; a different match restarts the count, and 5 misses in a row remove the name. One worker names one track at a time.
- A lost track forgets its identity after 3 s. Templates live in memory only and are re-read with the layout; no frames or embeddings are stored.
- Presence: an area interval opens after 10 s in that area and closes 30 s after the worker was last seen there (the end time is the last sighting).
- Queue: people whose feet are in a queue area, median over 15 s, named staff excluded.

Every reading cycle the worker posts `POST /devices/{id}/staff` with `presence` (open intervals with `ended_at: null`, plus any that closed since the last post) and `queue` (`{"people": n}`, or `null` without a queue area). Failed posts are retried in order; on a 404 the worker turns staff mode off and carries on. Settings in the device config: `face_threshold`, `confirm_matches`, `release_misses`, `lost_after_s`, `staff_dwell_s`, `staff_absence_s`, `queue_window_s`.

**Naming staff: badges or faces.** Each worker uses one method, set by the owner in Privacy & consent after recording consent.

- **Badge** (`vision/badges.py`): an ArUco 4x4 marker (codes 0–249) worn on the chest. Print one with `uv run python -m vision.badges 11` (writes `badge-11.png`; print at about 6 cm). Only the person crop of a worker inside a work area is searched, once a second; two different codes in one crop count as no read.
- **Face** (`vision/faces.py`): OpenCV Zoo YuNet (detector) and SFace (128-number embedding), Apache-2.0. Fetch them once into the git-ignored `models/` folder (about 39 MB, checked against pinned SHA-256 sums):

  ```bash
  uv run python -m vision.fetch_models
  ```

  Only the head area of workers inside work areas is embedded, every 2 s per track. Embeddings are compared in memory and dropped. Face templates are only accepted by a server running with `DINEMATE_DEPLOYMENT=local` and `DINEMATE_TEMPLATE_KEY`; in cloud mode the worker gets badges only.

The worker loads whichever readers are available (`--no-faces` or `--no-badges` to turn one off). Without the face models it logs how to fetch them and uses badges only.

**Enrolling a face** (`vision/enrol.py`, run by the owner on the café computer, after consent is recorded):

```bash
uv run python -m vision.enrol --email owner@example.com --camera 0
```

It asks for the owner's password, lists consented workers set to Face, and takes 5 shots of one person (it waits while more than one face is in view). If the shots agree it averages them into one template and sends only those 128 numbers to `POST /business/staff/{id}/face`. No photo is saved or sent; Esc cancels and sends nothing.

**Live view** (`vision/stream.py`): start the worker with `--stream-port 8090` (or `DINEMATE_STREAM_PORT`). It serves `http://<this computer>:8090/live` on the café network and reports that URL in its heartbeat (`--stream-host` sets the address if the automatic one is wrong). The Cameras page asks the API for a link signed with the device token that is valid for 60 s; the worker checks the signature and expiry before streaming, and one viewing lasts at most 10 minutes. Frames are drawn with zones, tables and named staff, every other person's face is pixelated before encoding, frames are only encoded while someone is watching, and nothing is written to disk. Browsers block an `http` stream inside an `https` page, so open the business app over `http` on the café network or put the worker behind a local TLS proxy.

## Camera hub (local server, Phase 10)

`vision/hub.py` runs every camera the owner adds in DineMate Business (RTSP cameras, phone camera app URLs, a USB webcam index, or a YouTube link for demos). Every 15 s it reads the camera list from `GET /devices/{hub_id}/hub/cameras` and keeps one worker per enabled camera. Each worker gets a stable live-view port (`8090`, `8091`, … up to 8 cameras), so the owner can open it and draw zones. A worker whose layout has no zones yet runs in setup mode: it serves the live view, sends heartbeats with "waiting for zones", posts nothing, and starts counting as soon as zones are saved. A worker that exits is restarted after 5 s, 15 s, then every 60 s; one whose source changes restarts at once; removed or turned-off cameras stop. Ctrl+C or `docker stop` stops them all.

| Variable | Default | Meaning |
| --- | --- | --- |
| `DINEMATE_API_URL` | `http://localhost:8000/api/v1` | API the hub and its workers talk to |
| `DINEMATE_HUB_ID` | `hub-local` | the hub's device ID |
| `DINEMATE_HUB_TOKEN` | (required) | the hub's device token |
| `DINEMATE_STREAM_HOST` | `localhost` | address owners' browsers use to reach the live views |
| `DINEMATE_STREAM_FIRST_PORT` | `8090` | first live-view port |
| `DINEMATE_MODEL` | `models/yolo11s.pt` | detector; downloaded on first run if missing. On a café video at 640 px on a 12-core CPU, YOLO11s took about 104 ms a frame and found about 30% more people than YOLO11n (49 ms). Use `models/yolo11n.pt` on slow PCs or with many cameras |

In Docker the image (`services/vision/Dockerfile`) starts the hub by default. USB webcams cannot reach a Docker container on Windows, so for a webcam run the hub natively on the café PC instead (stop the Docker hub first so the ports are free):

```bash
uv run python -m vision.hub --api http://localhost:8000/api/v1 --token <hub token>
```

`DINEMATE_HUB_TOKEN` can also go in `services/vision/.env`. The hub asks the API for a fresh token for a camera only when it (re)starts that camera's worker, which invalidates the previous one. Tokens reach workers through their environment, never the command line, and are never logged; camera passwords in source URLs are shown as `***` in all hub and worker output.

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

### Checking seat states

Label seats by hand at a few moments and compare (states: `free`, `occupied` or `held`):

```csv
video,layout,t_seconds,seat,state
../../../data/videos/staged-bags.mp4,,90,seat-3,held
```

```bash
uv run python -m vision.validate --seats validation/seats.csv
```

It prints how often DineMate agrees with you, the **false free** rate (shown free when it was taken or held; this should be close to 0), how often a seat was hidden, and a table of your labels against DineMate's states. See `validation/seats.example.csv`.

## Settings

Detection size: the worker uses YOLO at 1280 px for sources 1920 px wide or more (Full HD, 4K) and 640 px otherwise; people in high-resolution canteen footage are too small at 640. Override with `--imgsz`. The chosen size is logged at start.

Per-device settings live in the device config served by the API (`dwell_s`, `post_every_s`, `smoothing_s`, `fps`, `min_confidence`, `seated_ratio`, `h_stand_a`, `h_stand_b`). Set the first four with `devices_cli register`. The seated filter stays off until `h_stand_a`/`h_stand_b` are calibrated (Phase 3).

Seat settings, also in the device config: `clear_s` (30), `held_after_s` (20), `hidden_free_s` (10), `hidden_hold_s` (120), `abandoned_s` (300), `seat_radius` (0.06 of the frame width) and `objects_every_s` (5).

## Tests

```bash
uv run pytest -q
```

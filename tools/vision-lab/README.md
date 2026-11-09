# Vision lab (testing only)

A small local web page for checking the vision counts by hand. Open a YouTube link, a stream or a local video, draw zones on a frame, start the run, and press + or − whenever the number of people in a zone changes. The lab plays the video through the real DineMate pipeline (`services/vision`) and compares its counts with yours every second.

Nothing here is used by the apps, the API or the worker. Nothing is posted to DineMate.

## Run

From the repo root:

```bash
cd services/vision
uv run --with yt-dlp --with fastapi --with uvicorn python ../../tools/vision-lab/run.py
```

It opens http://127.0.0.1:8765 in your browser and listens on this computer only. Stop it with Ctrl+C.

## Use

1. **Source:** paste a YouTube or stream link, or pick a video from `data/videos/` (git-ignored). "Add a video" copies a file there. "Still at" picks the frame you draw on.
2. **Zones:** click points on the frame where people's feet are, then double-click, press Enter or press **Finish zone**. Pick the kind:
   - **Seating** counts seated people after the dwell time.
   - **Queue** counts everyone in it, standing or not.
   - **Work area** (counter, kitchen or floor) tracks the workers inside it. Its card counts the people in it, so you can hand-count staff at the counter too.

   Save the zones to reuse them. They go to `services/vision/layouts/test-lab-*.json`, which is git-ignored.

3. **Run and count:** set dwell, smoothing and FPS, then **Start**. The live view shows boxes, how long each seated customer has stayed, and blurred faces. Press **+** or **−** on a zone card, or use the keys 1–9 to pick a zone and + or − to change the count. Your count stays until you change it, so you only press when someone sits down or leaves. **Pause** holds a video while you catch up (a live stream skips ahead instead).
4. **Results:** for each zone you get:
   - the average error
   - the bias (above 0 means we count too many)
   - how often we are within ±1, and how often we are exact
   - a chart of ours against yours

   Our count lags a change by about the dwell plus half the smoothing, so use "Ignore the first (s)" to skip the warm-up. **Download CSV** saves `t_s, zone, ours, yours` for docs/RESULTS.md.

## Workers

Everyone whose feet are inside a work area is tracked as **Worker 1**, **Worker 2** and so on, without being identified. The live view shows each worker's area and time. The Workers panel shows:

- who is in a work area now
- how much of the run the counter was staffed
- counter gaps longer than "Counter gap (s)"

The results list time per area for each worker. Sightings under 3 s are hidden, because they are usually a track that broke for a moment.

**Named workers** are optional and last for this session only. Nothing is written to disk.

- **Badge:** type a name and an ArUco badge code (print one with `uv run python -m vision.badges 11` in services/vision). The worker is named when the badge is seen inside a work area.
- **Face:** only for footage where the people filmed agreed to be recognised. Tick the consent box, type a name, press **Enrol by face**, then click that worker in the live view (pause first if they move a lot). The lab takes 5 shots of their face over a few seconds and averages them. It needs the face models: `uv run python -m vision.fetch_models` in services/vision.

Never enrol customers or people in public footage. Keep "Blur faces" on; named workers are the only faces left unblurred.

## Tests

```bash
cd tools/vision-lab
uv run --no-project --with pytest pytest -q
```

## Remove

The lab is self-contained. To remove it completely:

1. Delete the `tools/vision-lab/` folder.
2. Optionally delete any `services/vision/layouts/test-lab-*.json` files and the videos you added to `data/videos/`. Both are git-ignored.

Nothing else in the repo refers to it.

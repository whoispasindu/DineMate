# Test videos (temporary)

Play a YouTube link or a recorded video as a pretend camera, so the real vision pipeline counts people while no live camera is available. Use only footage you have permission to use. This is a testing and demo tool; remove it before a real deployment if you no longer need it.

## Campus console

1. Start the stack with the camera hub: `pnpm stack:cameras` (Postgres, API, simulators, and a hub with live views on ports 8100–8107).
2. Start the console on the real API: `pnpm dev:console:api`, and sign in as a campus admin.
3. Open **Devices**. In **Add a test video**, pick a canteen, name the feed, then paste a YouTube link or choose a video file (up to 1 GB). The feed joins the device list with a **Test video** tag.
4. Within a minute its status reads **Draw zones next**.
5. Press **Open in Zones**. The zone editor shows the live video behind the canvas, with tracking boxes and blurred faces. Add a seating shape, link it to a zone, place seats if you want seat states, and save.
6. While the video runs, its counts replace the simulator for that zone. When the feed stops for more than 2 minutes, the simulator takes the zone back.

## DineMate Business

On **Cameras**, choose **Test video** in **Add a camera**, then paste a YouTube link or choose a file. Then press **Set up zones** as for a real camera. This works with `pnpm stack:cameras` plus `pnpm dev:business:api`, and on the local server installed with `infra/install-business.ps1` (start its hub with `infra\business.ps1 start`).

## How it works

- `POST /test-videos?filename=…` streams the file into `DINEMATE_TEST_VIDEOS_DIR` (a Docker volume shared read-only with the hub) and returns a `video:<name>` source.
- Campus feeds are camera devices marked `test` (`/manage/test-feeds`). Business test videos are ordinary cameras whose source is a YouTube link or `video:<name>`.
- The hub runs every video on a loop. The dev stack's hub `hub-dev` serves both campus and business cameras; the API creates it on start from `DINEMATE_HUB_TOKEN`.
- Removing a feed or camera deletes its uploaded file once no other camera uses it.
- Simulators skip zones that an enabled camera covered in its last 2 minutes (`camera_zones` in `app/routers/devices.py`). This rule also helps real cameras, so it can stay.

## Removing the feature

- API: delete `services/api/app/testfeeds/`, its router line in `app/main.py`, the `test_videos_*` settings, the `video:` branches in `app/business/cameras.py` and `app/business/camera_router.py` (`require_video`, `forget_video`), the hub-setup lines in `docker-entrypoint.sh` and the `/data/test-videos` line in the Dockerfile. Delete `tests/test_video_sources.py` and `tests/integration/test_video_feeds.py`, then run `pnpm api:types`.
- Vision: remove `worker_source`, `VIDEO_*` and `--videos-dir` from `vision/hub.py` and their test.
- Web: delete `apps/console/src/testVideo.tsx` and `apps/business/src/testVideo.tsx`. On the console Devices page, remove the **Add a test video** panel, the test-video tag and the Remove button. Remove the live picture toggle in the console zone editor and the **Test video** mode in the business camera form. The Devices page itself stays. Remove the test-feed calls, types, hooks and contract entries in `packages/api-client`.
- Infra: remove the `hub` service, `DINEMATE_HUB_TOKEN`, `DINEMATE_TEST_VIDEOS_DIR` and the `test-videos` volume from both compose files, the `/api/v1/test-videos` block in `infra/business-web/nginx.conf`, and the `stack:cameras` script.

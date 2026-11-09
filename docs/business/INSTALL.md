# Installing DineMate Business on a café PC

DineMate Business runs on one Windows PC in the café. The database, dashboard and cameras all stay on that PC and the café network; nothing is sent to a cloud service. Phones and laptops on the café Wi-Fi open the dashboard in a browser.

## What you need

- A Windows 10 or 11 PC that stays on during opening hours: 8 GB of memory (16 GB for 4 or more cameras), a recent 4-core processor and 30 GB free disk. The PC uses its processor for the cameras; no graphics card is needed.
- [Docker Desktop](https://www.docker.com/products/docker-desktop/), installed and running.
- This repository on the PC (download it as a zip, or `git clone`).
- Cameras on the same network: IP cameras with an RTSP address, or a phone running an IP camera app. One PC runs up to 8 cameras.

## Install

1. Open PowerShell in the repository folder and run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File infra\install-business.ps1
   ```

   - Add `-SampleCafe` to also load the labelled Sample Café for demos.
   - Add `-Port 8081` if port 8080 is taken.

2. Answer the questions: business name, venue name, owner email and password. The password is typed hidden and is never written to a file.
3. The first install builds everything and takes 10–20 minutes. When it finishes, it prints two addresses:
   - `http://localhost:8080` on this PC
   - `http://<this PC's address>:8080` for phones and laptops on the café Wi-Fi
4. In Docker Desktop, turn on **Settings → General → Start Docker Desktop when you sign in**, so DineMate starts with the PC.

The install creates `infra\.env.business` with the server's secrets. Keep it private, and back it up together with your backups.

If phones can't open the dashboard, Windows Firewall is blocking it. Allow inbound connections on ports 8080 and 8090–8097 on private networks, or ask whoever looks after the PC.

## Add cameras

1. Sign in, open **Cameras**, and fill in **Add a camera** with a name and the camera's address:

   | Camera                      | Address                                                                                      |
   | --------------------------- | -------------------------------------------------------------------------------------------- |
   | IP camera (RTSP)            | `rtsp://user:password@192.168.1.50:554/stream1` (see the camera's manual for the exact path) |
   | Phone with an IP camera app | `http://192.168.1.20:8080/video`                                                             |
   | Demo video                  | a YouTube link                                                                               |

2. Within a minute the camera service starts the camera, and its status changes to **Waiting for zones**.
3. Press **Set up zones**. On top of the live picture, add and drag shapes:
   - **Seating** for each area with tables. Pick or create the area, then **Place seats** and click every chair.
   - **Counter**, **Kitchen** or **Staff floor** where staff work.
   - **Queue** where customers wait, and **Ignore** for TV screens, mirrors or doors.
4. Press **Save layout**, then group the seats into tables in **Settings → Tables**. Live floor starts showing tables as soon as the camera reports.

Camera addresses stay on the PC. The dashboard only ever shows the camera's network address, never its password.

**USB webcams.** Docker on Windows can't use USB cameras. For a USB webcam:

1. Run the install again with `-NoCameras`, so the camera service no longer runs in Docker.
2. Add the webcam with the address `0` (or `1` for a second webcam).
3. Run the camera service on the PC itself:

```powershell
cd services\vision
uv run python -m vision.hub --api http://localhost:8080/api/v1 --token <DINEMATE_HUB_TOKEN from infra\.env.business>
```

## Day to day

```powershell
powershell -ExecutionPolicy Bypass -File infra\business.ps1 status
```

| Command  | What it does                                                                    |
| -------- | ------------------------------------------------------------------------------- |
| `start`  | Starts everything, and updates the PC's network address for the live view       |
| `stop`   | Stops everything; your data is kept                                             |
| `status` | Shows what is running                                                           |
| `logs`   | Shows recent messages, for example `logs hub` for the cameras                   |
| `backup` | Saves the database to `backups\dinemate-<date>.dump`                            |
| `update` | Rebuilds after you download a new version; database changes apply automatically |

Back up weekly, and copy the newest `.dump` file and `infra\.env.business` off the PC. To restore on a fresh install, ask the DineMate team; restoring replaces all data.

## What stays on this PC

- **Video and photos:** never stored. Frames are processed in memory, and the live view streams only on the café network.
- **Customer visits:** anonymous, and deleted after the retention set in **Settings**.
- **Staff data and face templates:** only for staff who consented, encrypted, and deleted with the worker. See [privacy/README.md](privacy/README.md).
- **Camera addresses and passwords:** in the database on this PC only.

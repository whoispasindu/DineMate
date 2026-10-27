import argparse
import csv
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

import cv2

from vision.counting import ZoneCounter, zones_from_config
from vision.metrics import Sample, Summary, summarize, table
from vision.worker import DEFAULT_MODEL, apply_overrides, layout_config

LAYOUT_DIR = Path(__file__).resolve().parents[1] / "layouts"
COLUMNS = ("video", "t_seconds", "zone", "count")


def read_counts(path: Path) -> dict[tuple[Path, Path], list[dict[str, str]]]:
    groups: dict[tuple[Path, Path], list[dict[str, str]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path} is missing column(s): {', '.join(missing)}")
        for row in reader:
            if not row["video"].strip():
                continue
            video = Path(row["video"].strip())
            video = video if video.is_absolute() else (path.parent / video).resolve()
            layout_cell = (row.get("layout") or "").strip()
            layout = Path(layout_cell) if layout_cell else LAYOUT_DIR / f"{video.stem}.json"
            layout = layout if layout.is_absolute() else (path.parent / layout).resolve() if layout_cell else layout
            groups[(video, layout)].append(row)
    return groups


def run_video(video: Path, layout: Path, rows: list[dict[str, str]], args: argparse.Namespace) -> list[Sample]:
    from vision.detector import YoloDetector

    if not video.exists():
        raise OSError(f"Video not found: {video}")
    if not layout.exists():
        raise OSError(f"Zones file not found for {video.name}: {layout} (draw it with vision.studio first)")
    config = apply_overrides(layout_config(str(layout)), args)
    counter = ZoneCounter(*zones_from_config(config))
    zones = {z.name: z for z in counter.zones}
    unknown = sorted({r["zone"] for r in rows} - set(zones))
    if unknown:
        raise ValueError(f"{video.name}: zone(s) {', '.join(unknown)} are not in {layout.name} ({', '.join(zones)})")
    targets = sorted({float(r["t_seconds"]) for r in rows})
    detector = YoloDetector(args.model, imgsz=args.imgsz, confidence=float(config["settings"]["min_confidence"]))
    capture = cv2.VideoCapture(str(video))
    video_fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, round(video_fps / float(config["settings"]["fps"])))
    snapshots: dict[float, dict[str, dict[str, int]]] = {}
    index = 0
    try:
        while targets:
            ok, image = capture.read()
            if not ok:
                break
            t = index / video_fps
            index += 1
            if (index - 1) % step:
                continue
            height, width = image.shape[:2]
            counter.update(detector.detect(image), width, height, t)
            while targets and t >= targets[0]:
                snapshots[targets.pop(0)] = {r["zone_id"]: r for r in counter.readings()}
    finally:
        capture.release()
    if targets:
        print(
            f"  {video.name}: video ended before t = {', '.join(f'{x:g}' for x in targets)} s; those rows are skipped"
        )
    samples = []
    for row in rows:
        t = float(row["t_seconds"])
        reading = snapshots.get(t, {}).get(zones[row["zone"]].zone_id)
        if reading is None:
            continue
        samples.append(
            Sample(
                video=video.name,
                t_seconds=t,
                zone=row["zone"],
                truth=int(row["count"]),
                estimate=reading["estimated_occupied"],
                low=reading["occupied_low"],
                high=reading["occupied_high"],
                capacity=zones[row["zone"]].capacity,
            )
        )
    return samples


def write_samples(path: Path, samples: list[Sample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*asdict(samples[0]), "error"])
        writer.writeheader()
        for s in samples:
            writer.writerow({**asdict(s), "error": s.estimate - s.truth})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare the worker's estimates with seated people you counted by hand (plan Section 7.6)."
    )
    parser.add_argument("counts", help="CSV with columns video, t_seconds, zone, count (and optional layout)")
    parser.add_argument("--out", help="write every compared sample to this CSV")
    parser.add_argument("--model", default=str(DEFAULT_MODEL))
    parser.add_argument("--imgsz", type=int, help="YOLO input size; default 1280 for sources 1920 px wide or more")
    parser.add_argument("--dwell-s", type=float, help="seconds someone must stay in a zone before counting")
    parser.add_argument("--smoothing-s", type=float, help="length of the median window in seconds")
    parser.add_argument("--post-every-s", type=float, help="ignored here; readings are taken at your timestamps")
    args = parser.parse_args(argv)
    try:
        groups = read_counts(Path(args.counts))
        all_samples: list[Sample] = []
        summaries: list[Summary] = []
        for (video, layout), rows in groups.items():
            print(f"Checking {video.name} ({len(rows)} counts) with zones from {layout.name} ...")
            samples = run_video(video, layout, rows, args)
            all_samples.extend(samples)
            summaries.append(summarize(video.name, samples))
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    if not all_samples:
        print("No samples could be compared.")
        return 1
    if len(summaries) > 1:
        summaries.append(summarize("All videos", all_samples))
    print()
    print(table(summaries))
    print("\nMAE = average seats off; bias > 0 means over-counting; ±2 = share within 2 seats;")
    print("in range = share where your count is inside the shown range (aim ~80%); level ok = same status word.")
    if args.out:
        write_samples(Path(args.out), all_samples)
        print(f"\nWrote {len(all_samples)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

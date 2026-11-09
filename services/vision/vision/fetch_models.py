import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

from vision.faces import DETECTOR_FILE, MODELS_DIR, RECOGNIZER_FILE

ZOO = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models"


@dataclass(frozen=True)
class ModelFile:
    name: str
    url: str
    sha256: str
    size: int


MODELS = (
    ModelFile(
        DETECTOR_FILE,
        f"{ZOO}/face_detection_yunet/{DETECTOR_FILE}",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        232_589,
    ),
    ModelFile(
        RECOGNIZER_FILE,
        f"{ZOO}/face_recognition_sface/{RECOGNIZER_FILE}",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        38_696_353,
    ),
)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def is_valid(path: Path, model: ModelFile) -> bool:
    return path.is_file() and path.stat().st_size == model.size and sha256_of(path) == model.sha256


def fetch(model: ModelFile, folder: Path, client: httpx.Client) -> Path:
    target = folder / model.name
    if is_valid(target, model):
        return target
    partial = target.with_suffix(".part")
    with client.stream("GET", model.url) as response:
        response.raise_for_status()
        with partial.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    if not is_valid(partial, model):
        partial.unlink(missing_ok=True)
        raise ValueError(f"{model.name}: checksum does not match, the file was deleted")
    partial.replace(target)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download the YuNet and SFace face models (OpenCV Zoo, Apache-2.0)")
    parser.add_argument("--dir", type=Path, default=MODELS_DIR, help="folder for the models (git-ignored)")
    args = parser.parse_args(argv)
    args.dir.mkdir(parents=True, exist_ok=True)
    total = sum(m.size for m in MODELS) / 1_000_000
    print(f"Downloading {len(MODELS)} files (about {total:.0f} MB) from the OpenCV model zoo into {args.dir}")
    try:
        with httpx.Client(follow_redirects=True, timeout=60) as client:
            for model in MODELS:
                path = fetch(model, args.dir, client)
                print(f"  ok  {path.name}  sha256 {model.sha256[:12]}…")
    except (httpx.HTTPError, ValueError, OSError) as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1
    print("Face models ready. Templates stay on the café computer and the local DineMate server.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

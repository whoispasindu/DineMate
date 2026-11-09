import argparse
import logging
import sys
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
VISION = HERE.parents[1] / "services" / "vision"
sys.path[:0] = [str(HERE), str(VISION)]


def main() -> int:
    parser = argparse.ArgumentParser(description="DineMate vision lab: draw zones on a video, count by hand, compare.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1", help="keep 127.0.0.1 unless you need the lab on another device")
    parser.add_argument("--model", default=str(VISION / "models" / "yolo11n.pt"))
    parser.add_argument("--pose-model", default=str(VISION / "models" / "yolo11n-pose.pt"))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    import uvicorn

    from lab.app import create_app
    from lab.session import Lab

    app = create_app(Lab(Path(args.model), Path(args.pose_model)))
    url = f"http://{args.host}:{args.port}"
    print(f"Vision lab on {url} (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())

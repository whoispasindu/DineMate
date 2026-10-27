import json
import sys
from pathlib import Path

from app.main import app


def main(argv: list[str]) -> int:
    spec = json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"
    if len(argv) > 1:
        Path(argv[1]).write_text(spec, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(spec)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

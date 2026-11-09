import argparse
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.core.device_auth import hash_token
from app.services.audit import record

HUB_ID = "hub-dev"


def parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or refresh the development camera hub that plays test videos for campus and business."
    )
    parser.add_argument("--hub-id", default=HUB_ID)
    parser.add_argument("--token-env", default="DINEMATE_HUB_TOKEN", help="environment variable holding the hub token")
    return parser.parse_args(argv)


def ensure_hub(session: Session, hub_id: str, token: str, now: datetime) -> str:
    canteens = select(models.Canteen.id).where(models.Canteen.kind == models.CANTEEN)
    home = session.scalar(canteens.order_by(models.Canteen.id))
    if home is None:
        raise LookupError("No campus canteen yet. Seed the database first.")
    device = session.get(models.Device, hub_id)
    created = device is None
    if device is None:
        device = models.Device(id=hub_id, canteen_id=home, kind="hub")
        session.add(device)
    elif device.kind != "hub":
        raise LookupError(f"Device {hub_id} exists and is not a hub.")
    device.token_hash = hash_token(token)
    device.config = {"label": "Test video hub", "scope": "all"}
    device.is_enabled = True
    session.flush()
    record(session, now, "testfeeds.hub.setup", "device", hub_id, device_id=hub_id, after={"scope": "all"})
    return "created" if created else "refreshed"


def main(argv: list[str] | None = None) -> int:
    args = parse(argv)
    token = os.environ.get(args.token_env, "")
    if len(token) < 12:
        print(f"Set {args.token_env} to a hub token of at least 12 characters.", file=sys.stderr)
        return 1
    engine = create_engine(get_settings().database_url)
    try:
        with Session(engine) as session:
            done = ensure_hub(session, args.hub_id, token, datetime.now(UTC))
            session.commit()
    except LookupError as exc:
        print(f"Hub setup stopped: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    print(f"  ok  test video hub {args.hub_id} {done}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

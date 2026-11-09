import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, time

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import models
from app.business.seed import ORG_ID as SAMPLE_ORG
from app.business.seed import VENUE_ID as SAMPLE_VENUE
from app.business.seed import seed_sample_cafe
from app.core.auth import OWNER, VENUE_MANAGER
from app.core.config import get_settings
from app.core.device_auth import hash_token
from app.users_cli import create_user, find

HUB_ID = "hub-local"
SAMPLE_ACCOUNTS = (
    ("owner@dinemate.test", "Sample Café owner", OWNER),
    ("manager@dinemate.test", "Sample Café manager", VENUE_MANAGER),
)


class SetupError(Exception):
    pass


@dataclass(frozen=True)
class Place:
    organization_id: str
    venue_id: str
    created: list[str]


def slug(text: str, limit: int = 30) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:limit].strip("-")
    if not value:
        raise SetupError("Use a name with letters or numbers.")
    return value


def parse_hour(text: str) -> time:
    try:
        hour, minute = (int(part) for part in text.split(":"))
        return time(hour, minute)
    except ValueError as exc:
        raise SetupError(f"Use HH:MM for opening hours, not {text!r}.") from exc


def secret_from(env: str, what: str) -> str:
    value = os.environ.get(env, "")
    if not value:
        raise SetupError(f"Set {env} to the {what} first.")
    return value


def ensure_place(session: Session, org_name: str, venue_name: str, opens: time, closes: time) -> Place:
    organization_id, venue_id = f"org-{slug(org_name)}", f"v-{slug(venue_name)}"
    created: list[str] = []
    org = session.get(models.Organization, organization_id)
    if org is None:
        session.add(models.Organization(id=organization_id, name=org_name.strip(), kind="business"))
        session.flush()
        created.append(f"organization {organization_id}")
    elif org.kind != "business":
        raise SetupError(f"{organization_id} is not a business organization.")
    venue = session.get(models.Canteen, venue_id)
    if venue is None:
        session.add(
            models.Canteen(
                id=venue_id, name=venue_name.strip(), organization_id=organization_id, kind=models.VENUE, sort_order=0
            )
        )
        session.add_all(
            models.CanteenHours(canteen_id=venue_id, weekday=day, opens=opens, closes=closes) for day in range(7)
        )
        session.flush()
        session.add(
            models.SeatingZone(canteen_id=venue_id, name="Main floor", capacity=1, sort_order=0, is_monitored=True)
        )
        created.append(f"venue {venue_id}")
    elif venue.organization_id != organization_id:
        raise SetupError(f"{venue_id} belongs to another organization.")
    return Place(organization_id, venue_id, created)


def ensure_owner(session: Session, place: Place, email: str, name: str, password: str) -> bool:
    user = find(session, email)
    if user is not None:
        if user.organization_id != place.organization_id:
            raise SetupError(f"{email} already belongs to another organization.")
        return False
    try:
        create_user(session, email, name, OWNER, password, [], [], place.organization_id)
    except ValueError as exc:
        raise SetupError(str(exc)) from exc
    return True


def ensure_hub(session: Session, venue_id: str, token: str) -> None:
    hub = session.get(models.Device, HUB_ID)
    if hub is None:
        session.add(models.Device(id=HUB_ID, canteen_id=venue_id, kind="hub", config={}, token_hash=hash_token(token)))
        return
    if hub.kind != "hub":
        raise SetupError(f"Device {HUB_ID} exists and is not a hub.")
    hub.canteen_id, hub.token_hash, hub.is_enabled = venue_id, hash_token(token), True


def create(session: Session, args: argparse.Namespace) -> list[str]:
    place = ensure_place(session, args.org, args.venue, parse_hour(args.opens), parse_hour(args.closes))
    done = list(place.created)
    if ensure_owner(
        session, place, args.owner_email, args.owner_name, secret_from(args.password_env, "owner password")
    ):
        done.append(f"owner {args.owner_email}")
    ensure_hub(session, place.venue_id, secret_from(args.hub_token_env, "hub token"))
    done.append(f"camera hub {HUB_ID}")
    return done


def sample(session: Session, args: argparse.Namespace) -> list[str]:
    done = []
    if seed_sample_cafe(session, datetime.now(UTC)):
        done.append(f"labelled Sample Café ({SAMPLE_VENUE})")
    password = secret_from(args.password_env, "sample account password")
    for email, name, role in SAMPLE_ACCOUNTS:
        if find(session, email) is None:
            canteens = [SAMPLE_VENUE] if role == VENUE_MANAGER else []
            try:
                create_user(session, email, name, role, password, canteens, [], SAMPLE_ORG)
            except ValueError as exc:
                raise SetupError(str(exc)) from exc
            done.append(f"sample account {email}")
    return done


def hub_token(session: Session, args: argparse.Namespace) -> list[str]:
    hub = session.get(models.Device, HUB_ID)
    if hub is None or hub.kind != "hub":
        raise SetupError("Run setup create first.")
    hub.token_hash = hash_token(secret_from(args.hub_token_env, "hub token"))
    return ["new hub token saved"]


def status(session: Session, _: argparse.Namespace) -> list[str]:
    orgs = session.scalars(select(models.Organization).where(models.Organization.kind == "business"))
    return [f"{o.id}: {o.name}{' (sample)' if o.is_sample else ''}" for o in orgs] or ["no business yet"]


def parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="First-run setup for a DineMate Business local server")
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("create", help="create the business, its venue, the owner account and the camera hub")
    make.add_argument("--org", required=True, help="business name, e.g. 'Green Leaf Cafés'")
    make.add_argument("--venue", required=True, help="venue name, e.g. 'Green Leaf Kandy'")
    make.add_argument("--owner-email", required=True)
    make.add_argument("--owner-name", default="Owner")
    make.add_argument("--password-env", required=True, help="environment variable holding the owner password")
    make.add_argument("--hub-token-env", required=True, help="environment variable holding the camera hub token")
    make.add_argument("--opens", default="07:00")
    make.add_argument("--closes", default="21:00")
    demo = sub.add_parser("sample", help="add the labelled Sample Café and its owner and manager accounts")
    demo.add_argument("--password-env", required=True)
    token = sub.add_parser("hub-token", help="store a new camera hub token")
    token.add_argument("--hub-token-env", required=True)
    sub.add_parser("status", help="list business organizations")
    return parser.parse_args(argv)


COMMANDS = {"create": create, "sample": sample, "hub-token": hub_token, "status": status}


def main(argv: list[str] | None = None) -> int:
    args = parse(argv)
    engine = create_engine(get_settings().database_url)
    try:
        with Session(engine) as session:
            done = COMMANDS[args.command](session, args)
            session.commit()
    except SetupError as exc:
        print(f"Setup stopped: {exc}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    for line in done:
        print(f"  ok  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

import argparse
import getpass
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.core.db import get_engine
from app.core.security import hash_password
from app.models.users import ROLES
from app.services.audit import record

MIN_PASSWORD = 10


def _password(args: argparse.Namespace) -> str:
    if args.password_env:
        value = os.environ.get(args.password_env, "")
        if not value:
            raise ValueError(f"Environment variable {args.password_env} is empty.")
        return value
    first = getpass.getpass("New password: ")
    if first != getpass.getpass("Repeat password: "):
        raise ValueError("Passwords did not match.")
    return first


def _check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"Use at least {MIN_PASSWORD} characters.")


def find(session: Session, email: str) -> models.User | None:
    return session.scalars(select(models.User).where(func.lower(models.User.email) == email.strip().lower())).first()


def create_user(
    session: Session,
    email: str,
    name: str,
    role: str,
    password: str,
    canteens: list[str],
    shops: list[str],
) -> models.User:
    if role not in ROLES:
        raise ValueError(f"Role must be one of: {', '.join(ROLES)}.")
    _check_password(password)
    if find(session, email) is not None:
        raise ValueError(f"A user with email {email} already exists.")
    for canteen in canteens:
        if session.get(models.Canteen, canteen) is None:
            raise ValueError(f"Canteen '{canteen}' does not exist.")
    for shop in shops:
        if session.get(models.Shop, shop) is None:
            raise ValueError(f"Shop '{shop}' does not exist.")
    user = models.User(email=email.strip(), display_name=name, role=role, password_hash=hash_password(password))
    user.canteen_scopes = [models.UserCanteenScope(canteen_id=c) for c in canteens]
    user.shop_scopes = [models.UserShopScope(shop_id=s) for s in shops]
    session.add(user)
    session.flush()
    record(session, datetime.now(UTC), "user.create", "user", str(user.id), after={"email": email, "role": role})
    return user


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage DineMate staff accounts (there is no public sign-up).")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="create a staff account")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--role", required=True, choices=ROLES)
    create.add_argument("--canteen", action="append", default=[], help="canteen id this user manages (repeatable)")
    create.add_argument("--shop", action="append", default=[], help="shop id this user manages (repeatable)")
    create.add_argument("--password-env", help="read the password from this environment variable instead of prompting")
    reset = sub.add_parser("set-password", help="set a new password")
    reset.add_argument("--email", required=True)
    reset.add_argument("--password-env")
    toggle = sub.add_parser("disable", help="disable an account and sign it out")
    toggle.add_argument("--email", required=True)
    enable = sub.add_parser("enable", help="re-enable an account")
    enable.add_argument("--email", required=True)
    sub.add_parser("list", help="list accounts")
    args = parser.parse_args(argv)
    now = datetime.now(UTC)
    try:
        with Session(get_engine()) as session:
            if args.command == "list":
                for u in session.scalars(select(models.User).order_by(models.User.role, models.User.email)):
                    scopes = ", ".join(sorted(u.canteen_ids | u.shop_ids)) or "-"
                    state = "active" if u.is_active else "disabled"
                    print(f"{u.email:<32} {u.role:<16} {state:<9} scopes: {scopes}")
                return 0
            if args.command == "create":
                user = create_user(session, args.email, args.name, args.role, _password(args), args.canteen, args.shop)
                session.commit()
                print(f"Created {user.role} {user.email}.")
                return 0
            user = find(session, args.email)
            if user is None:
                raise ValueError(f"No user with email {args.email}.")
            if args.command == "set-password":
                password = _password(args)
                _check_password(password)
                user.password_hash = hash_password(password)
                record(session, now, "user.set_password", "user", str(user.id))
            else:
                user.is_active = args.command == "enable"
                if not user.is_active:
                    for token in session.scalars(
                        select(models.RefreshToken).where(
                            models.RefreshToken.user_id == user.id, models.RefreshToken.revoked_at.is_(None)
                        )
                    ):
                        token.revoked_at = token.expires_at = now
                record(session, now, f"user.{args.command}", "user", str(user.id))
            session.commit()
            print(f"Updated {user.email}.")
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

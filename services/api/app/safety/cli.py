import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.device_auth import hash_token, new_token
from app.safety.models import EVENT_TYPES, SafetyInstruction, SafetySource
from app.safety.signing import INGEST_PER_SECOND, signature
from app.services.audit import record

INCOMING = [t for t in EVENT_TYPES if t != "integration_offline"]


def signed_post(api: str, token: str, path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode("utf-8")
    stamp = datetime.now(UTC).isoformat()
    request = urllib.request.Request(
        f"{api.rstrip('/')}{path}",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Device {token}",
            "X-Timestamp": stamp,
            "X-Signature": signature(token, stamp, body),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def trigger(args: argparse.Namespace, token: str) -> int:
    event_id = args.event_id or f"sim-{uuid.uuid4().hex[:10]}"
    payload = {
        "external_event_id": event_id,
        "event_type": args.type,
        "location": {"canteen_id": args.canteen, "zone_id": args.zone},
        "occurred_at": datetime.now(UTC).isoformat(),
        "is_simulation": not args.claim_real,
    }
    result: dict[str, Any] = {}
    for i in range(args.repeat):
        status, result = signed_post(args.api, token, "/safety/events", payload)
        if status >= 300:
            print(f"Rejected ({status}): {result.get('error', {}).get('message', result)}", file=sys.stderr)
            return 1
        if i + 1 < args.repeat:
            time.sleep(1.05 / INGEST_PER_SECOND)
    label = "SIMULATION" if result.get("is_simulation") else "REAL EVENT"
    print(f"{label}: event {result['id']} status={result['status']} repeat_count={result['repeat_count']}")
    return 0


def heartbeat(args: argparse.Namespace, token: str) -> int:
    sent = 0
    while args.count == 0 or sent < args.count:
        status, result = signed_post(args.api, token, "/safety/heartbeat", {"status": "ok"})
        if status >= 300:
            print(f"Heartbeat rejected ({status}): {result}", file=sys.stderr)
            return 1
        sent += 1
        print(f"heartbeat {sent} accepted at {result['server_time']}")
        if args.count == 0 or sent < args.count:
            time.sleep(args.every)
    return 0


def register(args: argparse.Namespace) -> int:
    token = new_token()
    with Session(get_engine()) as session:
        if session.get(SafetySource, args.id) is not None:
            print(f"Safety source '{args.id}' already exists.", file=sys.stderr)
            return 1
        session.add(SafetySource(id=args.id, name=args.name, kind=args.kind, token_hash=hash_token(token)))
        record(
            session, datetime.now(UTC), "safety.source_register", "safety_source", args.id, after={"kind": args.kind}
        )
        session.commit()
    print(f"Registered {args.id}. Token (shown once, store it on the gateway): {token}")
    return 0


def toggle(args: argparse.Namespace) -> int:
    with Session(get_engine()) as session:
        source = session.get(SafetySource, args.id)
        if source is None:
            print(f"Safety source '{args.id}' does not exist.", file=sys.stderr)
            return 1
        source.is_enabled = args.command == "enable-source"
        record(session, datetime.now(UTC), f"safety.{args.command}", "safety_source", args.id)
        session.commit()
    print(f"Updated {args.id}.")
    return 0


def instruction(args: argparse.Namespace) -> int:
    with Session(get_engine()) as session:
        row = SafetyInstruction(
            canteen_id=args.canteen,
            event_type=args.event_type,
            body=args.body,
            approved_by_name=args.approved_by,
            approved_at=datetime.now(UTC),
            is_active=True,
        )
        session.add(row)
        session.flush()
        record(
            session,
            datetime.now(UTC),
            "safety.instruction_add",
            "safety_instruction",
            str(row.id),
            after={"event_type": args.event_type, "canteen_id": args.canteen, "approved_by": args.approved_by},
        )
        session.commit()
    print("Saved the approved instruction.")
    return 0


def parser() -> argparse.ArgumentParser:
    settings = get_settings()
    root = argparse.ArgumentParser(
        description="DineMate safety simulator and source admin. Simulated events are always labelled."
    )
    sub = root.add_subparsers(dest="command", required=True)
    for name, helptext in (
        ("trigger", "send a signed simulated event"),
        ("heartbeat", "send signed source heartbeats"),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--api", default=settings.simulator_api_url)
        p.add_argument(
            "--token-env", default="DINEMATE_SAFETY_SIMULATOR_TOKEN", help="env var holding the source token"
        )
        if name == "trigger":
            p.add_argument("--type", choices=INCOMING, default="fire_alarm")
            p.add_argument("--canteen")
            p.add_argument("--zone")
            p.add_argument("--event-id")
            p.add_argument("--repeat", type=int, default=1, help="send the same event N times (burst test)")
            p.add_argument(
                "--claim-real",
                action="store_true",
                help="send is_simulation=false (a simulator is still stored as simulation)",
            )
        else:
            p.add_argument("--every", type=float, default=20.0)
            p.add_argument("--count", type=int, default=0, help="0 = until stopped")
    reg = sub.add_parser("register-source", help="register an approved integration and print its token once")
    reg.add_argument("--id", required=True)
    reg.add_argument("--name", required=True)
    reg.add_argument("--kind", choices=["approved_integration", "simulator"], default="approved_integration")
    for name in ("enable-source", "disable-source"):
        sub.add_parser(name).add_argument("--id", required=True)
    ins = sub.add_parser("add-instruction", help="store university-approved instruction text")
    ins.add_argument("--event-type", choices=INCOMING, required=True)
    ins.add_argument("--body", required=True)
    ins.add_argument("--approved-by", required=True, help="name and role of the approver")
    ins.add_argument("--canteen")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command in ("trigger", "heartbeat"):
        token = os.environ.get(args.token_env) or get_settings().safety_simulator_token
        return trigger(args, token) if args.command == "trigger" else heartbeat(args, token)
    if args.command == "register-source":
        return register(args)
    if args.command == "add-instruction":
        return instruction(args)
    return toggle(args)


if __name__ == "__main__":
    raise SystemExit(main())

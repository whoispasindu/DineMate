import argparse
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import models
from app.core import clock
from app.core.config import get_settings
from app.core.db import get_engine
from app.core.device_auth import hash_token
from app.services.timeutil import at_local, local_date

ALL_DAY = ("breakfast", "lunch", "dinner")
LUNCH = ("lunch",)
LUNCH_DINNER = ("lunch", "dinner")
WEEKDAYS = range(5)


@dataclass
class ZoneSeed:
    name: str
    capacity: int
    occupied: int
    below: int
    above: int
    device: str
    offline_for_s: int | None = None


@dataclass
class CanteenSeed:
    id: str
    name: str
    hours: tuple[str, str]
    reading_age_s: int
    zones: list[ZoneSeed]


@dataclass
class ItemSeed:
    name: str
    price: int
    category: str | None
    vegetarian: bool = False
    periods: tuple[str, ...] = ALL_DAY
    sold_out: bool = False


@dataclass
class ShopSeed:
    id: str
    canteen_id: str
    name: str
    kind: str
    hours: tuple[str, str]
    menu_updated: str | None
    items: list[ItemSeed] = field(default_factory=list)
    today_hours: tuple[str, str, str] | None = None
    closed_until_tomorrow: str | None = None


CANTEENS = [
    CanteenSeed(
        "a",
        "Canteen A",
        ("07:00", "18:00"),
        40,
        [
            ZoneSeed("Indoor hall", 36, 30, 3, 3, "sim-a"),
            ZoneSeed("Terrace", 40, 30, 4, 3, "sim-a"),
            ZoneSeed("Balcony", 24, 12, 2, 2, "cam-a-balcony", offline_for_s=858),
        ],
    ),
    CanteenSeed(
        "b",
        "Canteen B",
        ("07:00", "18:00"),
        25,
        [
            ZoneSeed("Garden side", 32, 14, 3, 3, "sim-b"),
            ZoneSeed("Indoor hall", 28, 14, 3, 3, "sim-b"),
        ],
    ),
    CanteenSeed(
        "c",
        "Canteen C",
        ("07:30", "17:00"),
        30,
        [
            ZoneSeed("Main hall", 48, 43, 3, 2, "sim-c"),
            ZoneSeed("Upper deck", 24, 20, 1, 2, "sim-c"),
        ],
    ),
]

WALKS = [("a", "b", 4), ("a", "c", 5), ("b", "c", 6)]

SHOPS = [
    ShopSeed(
        "s-rice",
        "a",
        "Rice & Curry Stall",
        "rice",
        ("07:00", "15:00"),
        "09:10",
        [
            ItemSeed("String hoppers & curry", 220, None, True, ("breakfast",)),
            ItemSeed("Milk rice & lunu miris", 180, "rice", True, ("breakfast",)),
            ItemSeed("Vegetable rice & curry", 350, "rice", True, LUNCH),
            ItemSeed("Chicken rice & curry", 450, "rice", False, LUNCH),
            ItemSeed("Fish rice & curry", 480, "rice", False, LUNCH, sold_out=True),
            ItemSeed("Egg fried rice", 400, "rice", False, LUNCH),
            ItemSeed("Dhal & papadam (add-on)", 120, None, True, LUNCH),
            ItemSeed("Vegetable fried rice", 380, "rice", True, LUNCH),
        ],
    ),
    ShopSeed(
        "s-kottu",
        "a",
        "Kottu Corner",
        "kottu",
        ("11:00", "18:00"),
        "10:45",
        [
            ItemSeed("Chicken kottu", 550, "kottu", False, LUNCH_DINNER),
            ItemSeed("Vegetable kottu", 450, "kottu", True, LUNCH_DINNER),
            ItemSeed("Egg kottu", 500, "kottu", False, LUNCH_DINNER),
            ItemSeed("Cheese kottu", 650, "kottu", False, LUNCH_DINNER, sold_out=True),
        ],
    ),
    ShopSeed(
        "s-shorteats",
        "a",
        "Short Eats Counter",
        "short_eats",
        ("07:30", "17:00"),
        "08:05",
        [
            ItemSeed("Fish bun", 100, "short_eats"),
            ItemSeed("Vegetable roti", 80, "short_eats", True),
            ItemSeed("Chicken roll", 120, "short_eats"),
            ItemSeed("Samosa", 90, "short_eats", True),
            ItemSeed("Plain tea", 60, "drinks", True),
        ],
    ),
    ShopSeed("s-tea", "a", "Tea Kiosk", "tea", ("15:00", "18:00"), None),
    ShopSeed(
        "s-noodle",
        "b",
        "Noodle Bar",
        "noodles",
        ("11:00", "16:00"),
        "10:30",
        [
            ItemSeed("Chicken noodles", 480, None, False, LUNCH),
            ItemSeed("Vegetable noodles", 400, None, True, LUNCH),
            ItemSeed("Devilled chicken noodles", 560, None, False, LUNCH),
        ],
        today_hours=("11:00", "13:00", "earlier than usual today"),
    ),
    ShopSeed(
        "s-bakery",
        "b",
        "Bakery Corner",
        "bakery",
        ("07:00", "17:00"),
        "07:20",
        [
            ItemSeed("Egg sandwich", 250, "short_eats"),
            ItemSeed("Butter cake slice", 150, "short_eats", True),
            ItemSeed("Iced coffee", 320, "drinks", True),
        ],
    ),
    ShopSeed(
        "s-smoothie",
        "b",
        "Smoothie Stand",
        "drinks",
        ("15:00", "18:00"),
        "08:00",
        [
            ItemSeed("Mango smoothie", 300, "drinks", True, LUNCH_DINNER),
            ItemSeed("Papaya juice", 220, "drinks", True, LUNCH_DINNER),
        ],
    ),
    ShopSeed(
        "s-friedrice",
        "c",
        "Fried Rice Counter",
        "rice",
        ("11:00", "16:00"),
        "10:55",
        [
            ItemSeed("Chicken fried rice", 520, "rice", False, LUNCH),
            ItemSeed("Vegetable fried rice", 420, "rice", True, LUNCH),
            ItemSeed("Nasi goreng", 580, "rice", False, LUNCH, sold_out=True),
        ],
    ),
    ShopSeed(
        "s-juice",
        "c",
        "Juice & Snacks",
        "drinks",
        ("08:00", "17:00"),
        "08:15",
        [
            ItemSeed("Lime juice", 150, "drinks", True),
            ItemSeed("Wood apple juice", 180, "drinks", True),
        ],
        closed_until_tomorrow="Restocking — back tomorrow",
    ),
]

MEALS = [("breakfast", "07:00", "09:30"), ("lunch", "11:30", "14:00"), ("dinner", "18:00", "20:30")]
SATURDAY_MEALS = [("lunch", "11:30", "13:30")]

TABLES = [
    "occupancy_readings",
    "zone_layouts",
    "devices",
    "menu_item_periods",
    "menu_items",
    "shop_hour_exceptions",
    "shop_hours",
    "shops",
    "schedule_overrides",
    "meal_schedules",
    "walking_times",
    "seating_zones",
    "canteen_hours",
    "canteens",
]


def t(value: str) -> time:
    return time.fromisoformat(value)


def _zone_polygon(index: int, count: int) -> list[list[float]]:
    width = 0.9 / count
    left = 0.05 + index * width
    return [
        [round(left, 3), 0.42],
        [round(left + width - 0.02, 3), 0.42],
        [round(left + width - 0.02, 3), 0.95],
        [round(left, 3), 0.95],
    ]


def _seed_canteens(session: Session, now: datetime) -> None:
    devices: dict[str, models.Device] = {}
    layouts: dict[str, list[tuple[uuid.UUID, ZoneSeed]]] = {}
    for order, c in enumerate(CANTEENS):
        session.add(models.Canteen(id=c.id, name=c.name, sort_order=order, is_sample=True))
        session.add_all(
            models.CanteenHours(canteen_id=c.id, weekday=wd, opens=t(c.hours[0]), closes=t(c.hours[1]))
            for wd in WEEKDAYS
        )
        session.flush()
        for zone_order, z in enumerate(c.zones):
            zone = models.SeatingZone(
                canteen_id=c.id, name=z.name, capacity=z.capacity, sort_order=zone_order, is_monitored=True
            )
            session.add(zone)
            session.flush()
            if z.device not in devices:
                kind = "simulator" if z.device.startswith("sim-") else "camera"
                devices[z.device] = models.Device(
                    id=z.device,
                    canteen_id=c.id,
                    kind=kind,
                    config={"profiles": {}},
                    is_enabled=z.offline_for_s is None,
                    token_hash=hash_token(get_settings().simulator_token) if kind == "simulator" else None,
                )
                session.add(devices[z.device])
            profiles = dict(devices[z.device].config["profiles"])
            profiles[str(zone.id)] = {"base": z.occupied, "below": z.below, "above": z.above}
            devices[z.device].config = {"profiles": profiles}
            layouts.setdefault(z.device, []).append((zone.id, z))
            session.flush()
            age = z.offline_for_s if z.offline_for_s is not None else c.reading_age_s
            session.add(
                models.OccupancyReading(
                    zone_id=zone.id,
                    device_id=z.device,
                    captured_at=now - timedelta(seconds=age),
                    estimated_occupied=z.occupied,
                    occupied_low=z.occupied - z.below,
                    occupied_high=z.occupied + z.above,
                    capacity_snapshot=z.capacity,
                    confidence="medium",
                    is_simulated=True,
                )
            )
    for device_id, zones in layouts.items():
        polygons: list[dict[str, object]] = [
            {"type": "seating", "zone_id": str(zone_id), "points": _zone_polygon(i, len(zones))}
            for i, (zone_id, _) in enumerate(zones)
        ]
        polygons.append({"type": "queue", "points": [[0.4, 0.08], [0.6, 0.08], [0.6, 0.34], [0.4, 0.34]]})
        session.add(models.ZoneLayout(device_id=device_id, version=1, polygons=polygons, is_current=True))
    for a, b, minutes in WALKS:
        session.add_all(
            [
                models.WalkingTime(from_canteen_id=a, to_canteen_id=b, minutes=minutes),
                models.WalkingTime(from_canteen_id=b, to_canteen_id=a, minutes=minutes),
            ]
        )


def _seed_shops(session: Session, now: datetime) -> None:
    today = local_date(now)
    for order, s in enumerate(SHOPS):
        shop = models.Shop(
            id=s.id,
            canteen_id=s.canteen_id,
            name=s.name,
            kind=s.kind,
            sort_order=order,
            is_sample=True,
            menu_updated_at=at_local(today, t(s.menu_updated)) if s.menu_updated else None,
        )
        if s.closed_until_tomorrow:
            shop.temporarily_closed_until = at_local(today + timedelta(days=1), t("07:00"))
            shop.closure_reason = s.closed_until_tomorrow
        session.add(shop)
        session.flush()
        session.add_all(
            models.ShopHours(shop_id=s.id, weekday=wd, opens=t(s.hours[0]), closes=t(s.hours[1])) for wd in WEEKDAYS
        )
        if s.today_hours:
            opens, closes, reason = s.today_hours
            session.add(
                models.ShopHourException(shop_id=s.id, date=today, opens=t(opens), closes=t(closes), reason=reason)
            )
        for item_order, item in enumerate(s.items):
            session.add(
                models.MenuItem(
                    shop_id=s.id,
                    name=item.name,
                    category=item.category,
                    price_cents=item.price * 100,
                    dietary_tags=["vegetarian"] if item.vegetarian else [],
                    sort_order=item_order,
                    is_available=not item.sold_out,
                    availability_updated_at=at_local(today, t("12:10")) if item.sold_out else now,
                    is_published=True,
                    periods=[models.MenuItemPeriod(period=p) for p in item.periods],
                )
            )


def _seed_schedules(session: Session) -> None:
    for weekday in WEEKDAYS:
        session.add_all(models.MealSchedule(weekday=weekday, period=p, starts=t(s), ends=t(e)) for p, s, e in MEALS)
    session.add_all(models.MealSchedule(weekday=5, period=p, starts=t(s), ends=t(e)) for p, s, e in SATURDAY_MEALS)


def seed(session: Session, now: datetime) -> None:
    _seed_canteens(session, now)
    _seed_shops(session, now)
    _seed_schedules(session)
    session.commit()


def reset(session: Session) -> None:
    session.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    session.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load labelled sample data into the DineMate database.")
    parser.add_argument("--reset", action="store_true", help="delete existing data first")
    parser.add_argument("--if-empty", action="store_true", help="do nothing when data already exists")
    args = parser.parse_args(argv)
    settings = get_settings()
    with Session(get_engine()) as session:
        has_data = bool(session.scalar(select(func.count()).select_from(models.Canteen)))
        if has_data and not args.reset:
            if args.if_empty:
                print("Sample data already present; skipping seed.")
                return 0
            print("Data already present. Re-run with --reset to replace it.", file=sys.stderr)
            return 1
        if args.reset:
            reset(session)
        if settings.demo_clock_start is not None:
            clock.reset_demo_clock(session, settings.demo_clock_start)
        seed(session, clock.now(settings))
    print("Seeded sample canteens, zones, shops, menus and meal schedules.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

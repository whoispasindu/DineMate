import csv
import io
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

COLUMNS = ("order_id", "time", "cashier", "item", "qty", "unit_price")
MAX_ROWS = 20_000
MAX_ERRORS = 20


@dataclass(frozen=True)
class OrderLine:
    name: str
    qty: int
    unit_price: Decimal


@dataclass
class ParsedOrder:
    order_ref: str
    at: datetime
    cashier: str | None
    lines: list[OrderLine] = field(default_factory=list)

    @property
    def total(self) -> Decimal:
        return sum((line.unit_price * line.qty for line in self.lines), Decimal(0))


@dataclass
class ParseResult:
    orders: list[ParsedOrder]
    errors: list[str]
    rows: int


@dataclass(frozen=True)
class SalesSummary:
    orders: int
    items: int
    revenue: Decimal
    average_order: Decimal | None
    by_hour: dict[int, int]
    by_cashier: dict[str, dict[str, int]]
    top_items: list[tuple[str, int]]


def _parse_time(value: str, tz: ZoneInfo) -> datetime:
    text = value.strip().replace("T", " ")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=tz)


def parse_csv(text: str, tz: ZoneInfo) -> ParseResult:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    header = [h.strip().lower() for h in reader.fieldnames or []]
    missing = [c for c in COLUMNS if c not in header]
    if missing:
        return ParseResult([], [f"Missing columns: {', '.join(missing)}. Expected: {', '.join(COLUMNS)}."], 0)
    reader.fieldnames = header
    orders: dict[str, ParsedOrder] = {}
    errors: list[str] = []
    rows = 0
    for line_no, row in enumerate(reader, start=2):
        rows += 1
        if rows > MAX_ROWS:
            errors.append(f"More than {MAX_ROWS} rows; split the file.")
            break
        ref = (row.get("order_id") or "").strip()
        name = (row.get("item") or "").strip()
        cashier = (row.get("cashier") or "").strip() or None
        try:
            at = _parse_time(row.get("time") or "", tz)
            qty = int((row.get("qty") or "").strip())
            price = Decimal((row.get("unit_price") or "").strip())
        except (ValueError, InvalidOperation):
            errors.append(f"Line {line_no}: time, qty or unit_price is not valid.")
            continue
        if not ref or not name:
            errors.append(f"Line {line_no}: order_id and item are required.")
            continue
        if qty <= 0 or price < 0:
            errors.append(f"Line {line_no}: qty must be above 0 and unit_price 0 or more.")
            continue
        order = orders.get(ref)
        if order is None:
            order = orders[ref] = ParsedOrder(ref, at, cashier)
        elif order.cashier != cashier:
            errors.append(f"Line {line_no}: order {ref} has more than one cashier.")
            continue
        order.lines.append(OrderLine(name, qty, price))
        if len(errors) >= MAX_ERRORS:
            break
    return ParseResult(list(orders.values()), errors, rows)


def summarize(orders: Sequence[ParsedOrder], tz: ZoneInfo) -> SalesSummary:
    by_hour: Counter[int] = Counter()
    by_cashier: dict[str, Counter[str]] = defaultdict(Counter)
    items: Counter[str] = Counter()
    revenue = Decimal(0)
    for order in orders:
        by_hour[order.at.astimezone(tz).hour] += 1
        revenue += order.total
        for line in order.lines:
            items[line.name] += line.qty
            by_cashier[order.cashier or "unknown"][line.name] += line.qty
    count = len(orders)
    return SalesSummary(
        orders=count,
        items=sum(items.values()),
        revenue=revenue,
        average_order=(revenue / count).quantize(Decimal("0.01")) if count else None,
        by_hour=dict(sorted(by_hour.items())),
        by_cashier={k: dict(v.most_common()) for k, v in sorted(by_cashier.items())},
        top_items=items.most_common(10),
    )

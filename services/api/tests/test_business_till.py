from decimal import Decimal
from zoneinfo import ZoneInfo

from app.business.till import parse_csv, summarize

TZ = ZoneInfo("Asia/Colombo")

GOOD = """order_id,time,cashier,item,qty,unit_price
A1,2026-11-20 08:05,C1,Latte,2,650
A1,2026-11-20 08:05,C1,Croissant,1,400
A2,2026-11-20T08:40,C2,Latte,1,650
A3,2026-11-20 09:10+05:30,C1,Black coffee,3,450
"""


def test_good_file_groups_lines_into_orders() -> None:
    result = parse_csv(GOOD, TZ)
    assert result.errors == []
    assert result.rows == 4
    assert [o.order_ref for o in result.orders] == ["A1", "A2", "A3"]
    assert result.orders[0].total == Decimal(1700)
    assert result.orders[0].at.utcoffset() is not None


def test_summary_counts_items_per_cashier_and_orders_per_hour() -> None:
    summary = summarize(parse_csv(GOOD, TZ).orders, TZ)
    assert summary.orders == 3
    assert summary.items == 7
    assert summary.by_cashier == {"C1": {"Black coffee": 3, "Latte": 2, "Croissant": 1}, "C2": {"Latte": 1}}
    assert summary.by_hour == {8: 2, 9: 1}
    assert summary.average_order == Decimal("1233.33")
    assert summary.top_items[0] == ("Latte", 3)


def test_missing_columns_are_reported_once() -> None:
    result = parse_csv("order_id,item\nA1,Latte\n", TZ)
    assert result.orders == []
    assert result.errors and "Missing columns" in result.errors[0]


def test_bad_rows_are_skipped_with_line_numbers() -> None:
    text = GOOD + "A4,yesterday,C1,Tea,1,300\nA5,2026-11-20 10:00,C1,Tea,0,300\nA1,2026-11-20 08:05,C9,Tea,1,300\n"
    result = parse_csv(text, TZ)
    assert len(result.orders) == 3
    assert [e.split(":")[0] for e in result.errors] == ["Line 6", "Line 7", "Line 8"]


def test_byte_order_mark_and_upper_case_headers_are_fine() -> None:
    text = "﻿ORDER_ID,TIME,CASHIER,ITEM,QTY,UNIT_PRICE\nB1,2026-11-20 12:00,,Tea,1,300\n"
    result = parse_csv(text, TZ)
    assert result.errors == []
    assert result.orders[0].cashier is None
    assert summarize(result.orders, TZ).by_cashier == {"unknown": {"Tea": 1}}

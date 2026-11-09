import type { AuditList, ItemCount, SalesDay, StaffList, StaffMember, StaffReport, StaffSheet, WorkerDay } from "../types";
import { SAMPLE_VENUE_ID } from "./business";
import { addDays, colomboDate, iso, todayAt } from "./time";

const MIN = 60_000;
const DAY = 86_400_000;

interface StaffSeed {
  id: string;
  name: string;
  role: string;
  method: "face" | "badge";
  badge: number | null;
  till: string | null;
  start: string;
  minutes: [number, number, number];
  items: [string, number][];
  orders: number;
}

const STAFF: StaffSeed[] = [
  {
    id: "sample-staff-b1",
    name: "Barista 1",
    role: "Barista",
    method: "face",
    badge: null,
    till: "B1",
    start: "06:58",
    minutes: [262, 34, 47],
    items: [
      ["Latte", 41],
      ["Cappuccino", 27],
      ["Black coffee", 19],
      ["Croissant", 14],
      ["Iced coffee", 9],
    ],
    orders: 74,
  },
  {
    id: "sample-staff-b2",
    name: "Barista 2",
    role: "Barista",
    method: "face",
    badge: null,
    till: "B2",
    start: "10:57",
    minutes: [83, 6, 14],
    items: [
      ["Latte", 16],
      ["Iced coffee", 11],
      ["Cake slice", 7],
      ["Tea", 5],
    ],
    orders: 27,
  },
  {
    id: "sample-staff-c1",
    name: "Cashier 1",
    role: "Cashier",
    method: "badge",
    badge: 11,
    till: "C1",
    start: "07:59",
    minutes: [251, 0, 24],
    items: [
      ["Sandwich", 22],
      ["Tea", 18],
      ["Croissant", 15],
      ["Latte", 12],
      ["Cake slice", 9],
    ],
    orders: 61,
  },
  {
    id: "sample-staff-k1",
    name: "Kitchen 1",
    role: "Kitchen",
    method: "face",
    badge: null,
    till: null,
    start: "07:02",
    minutes: [41, 268, 0],
    items: [],
    orders: 0,
  },
  {
    id: "sample-staff-f1",
    name: "Floor 1",
    role: "Floor",
    method: "badge",
    badge: 12,
    till: null,
    start: "11:01",
    minutes: [17, 0, 82],
    items: [],
    orders: 0,
  },
];

function member(s: StaffSeed, now: number): StaffMember {
  return {
    id: s.id,
    display_name: s.name,
    role_label: s.role,
    method: s.method,
    badge_code: s.badge,
    till_code: s.till,
    consent_at: iso(now - 18 * DAY),
    consent_version: "sample-notice-v1",
    has_template: s.method === "face",
    active: true,
    is_sample: true,
  };
}

export function sampleStaff(venueId: string, now: number): StaffList | undefined {
  if (venueId !== SAMPLE_VENUE_ID) return undefined;
  return { server_time: iso(now), venue_id: SAMPLE_VENUE_ID, items: STAFF.map((s) => member(s, now)) };
}

function items(list: [string, number][]): ItemCount[] {
  return list.map(([name, qty]) => ({ name, qty }));
}

function worker(s: StaffSeed, now: number): WorkerDay {
  const [counter, kitchen, floor] = s.minutes;
  return {
    staff_id: s.id,
    display_name: s.name,
    role_label: s.role,
    method: s.method,
    first_seen: iso(todayAt(now, s.start)),
    last_seen: iso(now - 40_000),
    minutes: { counter, kitchen, floor },
    orders: s.orders,
    items: items(s.items),
    total_items: s.items.reduce((sum, [, qty]) => sum + qty, 0),
  };
}

export function sampleStaffReport(venueId: string, now: number): StaffReport | undefined {
  if (venueId !== SAMPLE_VENUE_ID) return undefined;
  const openMin = Math.max(0, Math.round((now - todayAt(now, "07:00")) / MIN));
  const gaps = [
    { start: iso(todayAt(now, "09:42")), end: iso(todayAt(now, "09:51")), minutes: 9 },
    { start: iso(todayAt(now, "10:58")), end: iso(todayAt(now, "11:06")), minutes: 8 },
  ];
  const covered = openMin - gaps.reduce((sum, g) => sum + g.minutes, 0);
  return {
    server_time: iso(now),
    venue_id: SAMPLE_VENUE_ID,
    day: colomboDate(now),
    is_sample: true,
    coverage: { open_min: openMin, covered_min: covered, share: openMin > 0 ? covered / openMin : null, gaps },
    queue_alerts: [{ start: iso(todayAt(now, "12:14")), end: iso(todayAt(now, "12:19")), peak: 7 }],
    workers: STAFF.map((s) => worker(s, now)),
  };
}

export function sampleStaffSheet(staffId: string, now: number): StaffSheet | undefined {
  const seed = STAFF.find((s) => s.id === staffId);
  if (!seed) return undefined;
  const today = colomboDate(now);
  const [counter, kitchen, floor] = seed.minutes;
  const total = seed.items.reduce((sum, [, qty]) => sum + qty, 0);
  return {
    server_time: iso(now),
    staff: member(seed, now),
    venue_name: "Sample Café",
    kept_days: 60,
    days: Array.from({ length: 7 }, (_, i) => {
      const scale = i === 6 ? 1 : 1.25 + ((i * 7) % 5) / 10;
      return {
        day: addDays(today, i - 6),
        minutes: { counter: Math.round(counter * scale), kitchen: Math.round(kitchen * scale), floor: Math.round(floor * scale) },
        items: Math.round(total * scale),
      };
    }),
  };
}

const ORDERS_BY_HOUR = [0, 0, 0, 0, 0, 0, 0, 14, 24, 29, 22, 25, 48, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];

export function sampleSales(venueId: string, now: number): SalesDay | undefined {
  if (venueId !== SAMPLE_VENUE_ID) return undefined;
  const cashiers = STAFF.filter((s) => s.till !== null);
  const byCashier = cashiers.map((s) => ({
    cashier: s.till ?? "",
    staff_id: s.id,
    staff_name: s.name,
    items: items(s.items),
    total_items: s.items.reduce((sum, [, qty]) => sum + qty, 0),
    orders: s.orders,
  }));
  const totals = new Map<string, number>();
  for (const s of cashiers) for (const [name, qty] of s.items) totals.set(name, (totals.get(name) ?? 0) + qty);
  const orders = byCashier.reduce((sum, c) => sum + c.orders, 0);
  const revenue = 199_850;
  return {
    server_time: iso(now),
    venue_id: SAMPLE_VENUE_ID,
    day: colomboDate(now),
    is_sample: true,
    orders,
    items: byCashier.reduce((sum, c) => sum + c.total_items, 0),
    revenue,
    average_order: Math.round((revenue / orders) * 100) / 100,
    by_hour: ORDERS_BY_HOUR.map((count, hour) => ({ hour, orders: count })),
    by_cashier: byCashier,
    top_items: [...totals.entries()]
      .map(([name, qty]) => ({ name, qty }))
      .sort((a, b) => b.qty - a.qty)
      .slice(0, 6),
  };
}

export function sampleAudit(now: number): AuditList {
  return {
    server_time: iso(now),
    items: [
      { at: iso(now - 26 * MIN), actor: "Sample Café owner", action: "business.staff_report.view", entity_id: SAMPLE_VENUE_ID },
      { at: iso(now - DAY - 3 * 60 * MIN), actor: "Sample Café owner", action: "business.staff_report.view", entity_id: "sample-staff-c1" },
      { at: iso(now - 3 * DAY), actor: "Sample Café owner", action: "business.staff_report.view", entity_id: SAMPLE_VENUE_ID },
    ],
  };
}

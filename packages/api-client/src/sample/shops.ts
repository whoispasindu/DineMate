import type { MealPeriod, MenuItem, MenuTag, Shop, ShopKind, ShopStatus } from "../types";
import { colomboDate, colomboHM, iso, todayAt, weekdayIndex } from "./time";

type Interval = [string, string];

interface ItemSeed {
  name: string;
  price: number;
  tags: MenuTag[];
  periods?: MealPeriod[];
  soldOut?: boolean;
}

interface ShopSeed {
  id: string;
  name: string;
  canteenId: string;
  canteenName: string;
  kind: ShopKind;
  hoursLabel: string;
  weekly: Interval[][];
  todayOverride?: Interval[];
  temporarilyClosed?: string;
  menuUpdatedAt?: string;
  items: ItemSeed[];
}

const CLOSES_SOON_MIN = 30;

function weekdays(...intervals: Interval[]): Interval[][] {
  return [intervals, intervals, intervals, intervals, intervals, [], []];
}

const ALL_DAY: MealPeriod[] = ["breakfast", "lunch", "dinner"];
const LUNCH: MealPeriod[] = ["lunch"];
const LUNCH_DINNER: MealPeriod[] = ["lunch", "dinner"];

const SHOPS: ShopSeed[] = [
  {
    id: "s-rice",
    name: "Rice & Curry Stall",
    canteenId: "a",
    canteenName: "Canteen A",
    kind: "rice",
    hoursLabel: "Mon–Fri 7:00 a.m.–3:00 p.m.",
    weekly: weekdays(["07:00", "15:00"]),
    menuUpdatedAt: "09:10",
    items: [
      { name: "String hoppers & curry", price: 220, tags: ["vegetarian"], periods: ["breakfast"] },
      { name: "Milk rice & lunu miris", price: 180, tags: ["rice", "vegetarian"], periods: ["breakfast"] },
      { name: "Vegetable rice & curry", price: 350, tags: ["rice", "vegetarian"], periods: LUNCH },
      { name: "Chicken rice & curry", price: 450, tags: ["rice"], periods: LUNCH },
      { name: "Fish rice & curry", price: 480, tags: ["rice"], periods: LUNCH, soldOut: true },
      { name: "Egg fried rice", price: 400, tags: ["rice"], periods: LUNCH },
      { name: "Dhal & papadam (add-on)", price: 120, tags: ["vegetarian"], periods: LUNCH },
      { name: "Vegetable fried rice", price: 380, tags: ["rice", "vegetarian"], periods: LUNCH },
    ],
  },
  {
    id: "s-kottu",
    name: "Kottu Corner",
    canteenId: "a",
    canteenName: "Canteen A",
    kind: "kottu",
    hoursLabel: "Mon–Fri 11:00 a.m.–6:00 p.m.",
    weekly: weekdays(["11:00", "18:00"]),
    menuUpdatedAt: "10:45",
    items: [
      { name: "Chicken kottu", price: 550, tags: ["kottu"], periods: LUNCH_DINNER },
      { name: "Vegetable kottu", price: 450, tags: ["kottu", "vegetarian"], periods: LUNCH_DINNER },
      { name: "Egg kottu", price: 500, tags: ["kottu"], periods: LUNCH_DINNER },
      { name: "Cheese kottu", price: 650, tags: ["kottu"], periods: LUNCH_DINNER, soldOut: true },
    ],
  },
  {
    id: "s-shorteats",
    name: "Short Eats Counter",
    canteenId: "a",
    canteenName: "Canteen A",
    kind: "short_eats",
    hoursLabel: "Mon–Fri 7:30 a.m.–5:00 p.m.",
    weekly: weekdays(["07:30", "17:00"]),
    menuUpdatedAt: "08:05",
    items: [
      { name: "Fish bun", price: 100, tags: ["short_eats"], periods: ALL_DAY },
      { name: "Vegetable roti", price: 80, tags: ["short_eats", "vegetarian"], periods: ALL_DAY },
      { name: "Chicken roll", price: 120, tags: ["short_eats"], periods: ALL_DAY },
      { name: "Samosa", price: 90, tags: ["short_eats", "vegetarian"], periods: ALL_DAY },
      { name: "Plain tea", price: 60, tags: ["drinks", "vegetarian"], periods: ALL_DAY },
    ],
  },
  {
    id: "s-tea",
    name: "Tea Kiosk",
    canteenId: "a",
    canteenName: "Canteen A",
    kind: "tea",
    hoursLabel: "Mon–Fri 3:00 p.m.–6:00 p.m.",
    weekly: weekdays(["15:00", "18:00"]),
    items: [],
  },
  {
    id: "s-noodle",
    name: "Noodle Bar",
    canteenId: "b",
    canteenName: "Canteen B",
    kind: "noodles",
    hoursLabel: "Mon–Fri 11:00 a.m.–4:00 p.m.",
    weekly: weekdays(["11:00", "16:00"]),
    todayOverride: [["11:00", "13:00"]],
    menuUpdatedAt: "10:30",
    items: [
      { name: "Chicken noodles", price: 480, tags: [], periods: LUNCH },
      { name: "Vegetable noodles", price: 400, tags: ["vegetarian"], periods: LUNCH },
      { name: "Devilled chicken noodles", price: 560, tags: [], periods: LUNCH },
    ],
  },
  {
    id: "s-bakery",
    name: "Bakery Corner",
    canteenId: "b",
    canteenName: "Canteen B",
    kind: "bakery",
    hoursLabel: "Mon–Fri 7:00 a.m.–5:00 p.m.",
    weekly: weekdays(["07:00", "17:00"]),
    menuUpdatedAt: "07:20",
    items: [
      { name: "Egg sandwich", price: 250, tags: ["short_eats"], periods: ALL_DAY },
      { name: "Butter cake slice", price: 150, tags: ["short_eats", "vegetarian"], periods: ALL_DAY },
      { name: "Iced coffee", price: 320, tags: ["drinks", "vegetarian"], periods: ALL_DAY },
    ],
  },
  {
    id: "s-smoothie",
    name: "Smoothie Stand",
    canteenId: "b",
    canteenName: "Canteen B",
    kind: "drinks",
    hoursLabel: "Mon–Fri 3:00 p.m.–6:00 p.m.",
    weekly: weekdays(["15:00", "18:00"]),
    menuUpdatedAt: "08:00",
    items: [
      { name: "Mango smoothie", price: 300, tags: ["drinks", "vegetarian"], periods: LUNCH_DINNER },
      { name: "Papaya juice", price: 220, tags: ["drinks", "vegetarian"], periods: LUNCH_DINNER },
    ],
  },
  {
    id: "s-friedrice",
    name: "Fried Rice Counter",
    canteenId: "c",
    canteenName: "Canteen C",
    kind: "rice",
    hoursLabel: "Mon–Fri 11:00 a.m.–4:00 p.m.",
    weekly: weekdays(["11:00", "16:00"]),
    menuUpdatedAt: "10:55",
    items: [
      { name: "Chicken fried rice", price: 520, tags: ["rice"], periods: LUNCH },
      { name: "Vegetable fried rice", price: 420, tags: ["rice", "vegetarian"], periods: LUNCH },
      { name: "Nasi goreng", price: 580, tags: ["rice"], periods: LUNCH, soldOut: true },
    ],
  },
  {
    id: "s-juice",
    name: "Juice & Snacks",
    canteenId: "c",
    canteenName: "Canteen C",
    kind: "drinks",
    hoursLabel: "Mon–Fri 8:00 a.m.–5:00 p.m.",
    weekly: weekdays(["08:00", "17:00"]),
    temporarilyClosed: "Restocking — back tomorrow",
    menuUpdatedAt: "08:15",
    items: [
      { name: "Lime juice", price: 150, tags: ["drinks", "vegetarian"], periods: ALL_DAY },
      { name: "Wood apple juice", price: 180, tags: ["drinks", "vegetarian"], periods: ALL_DAY },
    ],
  },
];

function statusAt(seed: ShopSeed, now: number): ShopStatus {
  const base = { closes_at_local: null, opens_at_local: null, reason: null };
  if (seed.temporarilyClosed) {
    return { ...base, state: "temporarily_closed", reason: seed.temporarilyClosed };
  }
  const intervals = seed.todayOverride ?? seed.weekly[weekdayIndex(colomboDate(now))] ?? [];
  if (seed.weekly.every((d) => d.length === 0)) {
    return { ...base, state: "unknown" };
  }
  const nowHM = colomboHM(now);
  for (const [opens, closes] of intervals) {
    if (nowHM >= opens && nowHM < closes) {
      const minutesLeft = (todayAt(now, closes) - now) / 60_000;
      return {
        ...base,
        state: minutesLeft <= CLOSES_SOON_MIN ? "closes_soon" : "open",
        closes_at_local: closes,
        reason: seed.todayOverride ? "earlier than usual today" : null,
      };
    }
    if (nowHM < opens) {
      return { ...base, state: "closed", opens_at_local: opens };
    }
  }
  return { ...base, state: "closed" };
}

function toShop(seed: ShopSeed, now: number): Shop {
  return {
    id: seed.id,
    name: seed.name,
    canteen_id: seed.canteenId,
    canteen_name: seed.canteenName,
    kind: seed.kind,
    is_sample: true,
    status: statusAt(seed, now),
    hours_label: seed.hoursLabel,
    menu_updated_at: seed.menuUpdatedAt ? iso(todayAt(now, seed.menuUpdatedAt)) : null,
  };
}

export function shopsFor(canteenId: string, now: number): Shop[] {
  return SHOPS.filter((s) => s.canteenId === canteenId).map((s) => toShop(s, now));
}

export function shopById(id: string, now: number): Shop | undefined {
  const seed = SHOPS.find((s) => s.id === id);
  return seed ? toShop(seed, now) : undefined;
}

export function featuredShops(now: number): Shop[] {
  return ["s-rice", "s-kottu", "s-noodle", "s-juice"]
    .map((id) => shopById(id, now))
    .filter((s): s is Shop => s !== undefined);
}

export function menuItems(shopId: string): MenuItem[] {
  const seed = SHOPS.find((s) => s.id === shopId);
  return (seed?.items ?? []).map((item, i) => ({
    id: `${shopId}-${i + 1}`,
    name: item.name,
    price_lkr: item.price,
    tags: item.tags,
    periods: item.periods ?? ALL_DAY,
    is_available: !item.soldOut,
  }));
}

export function isOpenNow(shop: Shop): boolean {
  return shop.status.state === "open" || shop.status.state === "closes_soon";
}

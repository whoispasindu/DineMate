import type { MealPeriod, MealStatus, MealWindow, WeekDay, WeekDayKind } from "../types";
import { addDays, atLocal, colomboDate, iso, weekdayIndex, weekdayName } from "./time";

interface Slot {
  period: MealPeriod;
  starts: string;
  ends: string;
}

interface DayPlan {
  kind: WeekDayKind;
  slots: Slot[];
  note: string | null;
}

const REGULAR: DayPlan = {
  kind: "regular",
  note: null,
  slots: [
    { period: "breakfast", starts: "07:00", ends: "09:30" },
    { period: "lunch", starts: "11:30", ends: "14:00" },
    { period: "dinner", starts: "18:00", ends: "20:30" },
  ],
};

const CAMPUS_WEEK: DayPlan[] = [
  REGULAR,
  REGULAR,
  REGULAR,
  REGULAR,
  REGULAR,
  {
    kind: "special",
    note: "special hours — lunch only, 11:30 a.m. – 1:30 p.m.",
    slots: [{ period: "lunch", starts: "11:30", ends: "13:30" }],
  },
  { kind: "closed", note: "canteens closed", slots: [] },
];

function planFor(date: string): DayPlan {
  return CAMPUS_WEEK[weekdayIndex(date)] ?? REGULAR;
}

function windowsFor(date: string): MealWindow[] {
  return planFor(date).slots.map((s) => ({
    period: s.period,
    starts: iso(atLocal(date, s.starts)),
    ends: iso(atLocal(date, s.ends)),
  }));
}

export function mealStatus(now: number): MealStatus {
  const today = colomboDate(now);
  const upcoming: MealWindow[] = [];
  for (let offset = 0; offset < 8; offset += 1) {
    upcoming.push(...windowsFor(addDays(today, offset)));
  }
  const index = upcoming.findIndex((w) => Date.parse(w.ends) > now);
  const first = index >= 0 ? upcoming[index] : undefined;
  const isActive = first !== undefined && Date.parse(first.starts) <= now;
  const monday = addDays(today, -weekdayIndex(today));
  const week: WeekDay[] = Array.from({ length: 7 }, (_, i) => {
    const date = addDays(monday, i);
    const plan = planFor(date);
    return {
      date,
      weekday: weekdayName(date),
      day: Number(date.slice(8, 10)),
      kind: plan.kind,
      note: plan.note,
      is_today: date === today,
    };
  });
  return {
    server_time: iso(now),
    timezone: "Asia/Colombo",
    is_sample: true,
    state: first === undefined ? "none" : isActive ? "active" : "upcoming",
    current: isActive ? (first ?? null) : null,
    next: (isActive ? upcoming[index + 1] : first) ?? null,
    today: windowsFor(today),
    week,
  };
}

import type { AlertFeed } from "@dinemate/api-client";
import { storedValue } from "./stored";

const NEW_WINDOW_MS = 10 * 60_000;

export const welcomeSeen = storedValue("welcome-seen", false);
export const favourites = storedValue<string[]>("favourite-canteens", []);
export const alertsSeenAt = storedValue<string | null>("alerts-seen-at", null);
export const safetySeen = storedValue<string[]>("safety-seen", []);

export interface NotificationPrefs {
  crowding: boolean;
  meals: boolean;
  closing: boolean;
  soldOut: boolean;
}

export const notificationPrefs = storedValue<NotificationPrefs>("notification-prefs", {
  crowding: true,
  meals: true,
  closing: false,
  soldOut: false,
});

export function isNew(at: string, seenAt: string | null, now: number): boolean {
  const cutoff = seenAt === null ? now - NEW_WINDOW_MS : Date.parse(seenAt);
  return Date.parse(at) > cutoff;
}

export function unreadCount(feed: AlertFeed | undefined, seenAt: string | null, now: number): number {
  if (!feed) return 0;
  const safety = feed.safety.events.filter((e) => isNew(e.occurred_at, seenAt, now)).length;
  return safety + feed.notices.filter((n) => isNew(n.at, seenAt, now)).length;
}

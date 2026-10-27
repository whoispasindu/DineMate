import { useEffect, useState } from "react";

let offsetMs = 0;
const listeners = new Set<() => void>();

export function syncServerTime(serverTimeIso: string, receivedAtMs = Date.now()): void {
  const next = Date.parse(serverTimeIso) - receivedAtMs;
  if (Number.isNaN(next) || Math.abs(next - offsetMs) < 250) return;
  offsetMs = next;
  listeners.forEach((listener) => listener());
}

export function serverNow(): number {
  return Date.now() + offsetMs;
}

export function useServerNow(intervalMs = 1000): number {
  const [now, setNow] = useState(serverNow);
  useEffect(() => {
    const tick = () => setNow(serverNow());
    const id = window.setInterval(tick, intervalMs);
    listeners.add(tick);
    document.addEventListener("visibilitychange", tick);
    tick();
    return () => {
      window.clearInterval(id);
      listeners.delete(tick);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [intervalMs]);
  return now;
}

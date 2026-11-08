import { useSafetyActive, useServerNow, type SafetyEvent } from "@dinemate/api-client";
import { useEffect, useState } from "react";
import { safetySeen } from "../lib/prefs";
import { SafetyBanner, SafetyCompact, SafetyUnknown } from "./common";

const STALE_MS = 15_000;

export function useSafety(): { events: SafetyEvent[]; unknown: boolean } {
  const safety = useSafetyActive();
  useServerNow(1000);
  const stale = safety.dataUpdatedAt > 0 && Date.now() - safety.dataUpdatedAt > STALE_MS;
  return { events: safety.data?.events ?? [], unknown: safety.isError || stale };
}

export function SafetySlot({ layout }: { layout: "mobile" | "web" }) {
  const { events, unknown } = useSafety();
  const [seen] = useState(() => safetySeen.get());
  const ids = events.map((e) => e.id).join(",");
  useEffect(() => {
    if (!ids) return;
    safetySeen.set((prev) => {
      const fresh = ids.split(",").filter((id) => !prev.includes(id));
      return fresh.length > 0 ? [...prev, ...fresh].slice(-50) : prev;
    });
  }, [ids]);
  return (
    <>
      {unknown ? <SafetyUnknown /> : null}
      {events.map((event) =>
        layout === "mobile" && event.is_simulation && seen.includes(event.id) ? (
          <SafetyCompact key={event.id} event={event} />
        ) : (
          <SafetyBanner key={event.id} event={event} layout={layout} />
        ),
      )}
    </>
  );
}

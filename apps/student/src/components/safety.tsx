import { useSafetyActive, useServerNow, type SafetyEvent } from "@dinemate/api-client";
import { SafetyBanner, SafetyUnknown } from "./common";

const STALE_MS = 15_000;

export function useSafety(): { events: SafetyEvent[]; unknown: boolean } {
  const safety = useSafetyActive();
  useServerNow(1000);
  const stale = safety.dataUpdatedAt > 0 && Date.now() - safety.dataUpdatedAt > STALE_MS;
  return { events: safety.data?.events ?? [], unknown: safety.isError || stale };
}

export function SafetySlot({ layout }: { layout: "mobile" | "web" }) {
  const { events, unknown } = useSafety();
  return (
    <>
      {unknown ? <SafetyUnknown /> : null}
      {events.map((event) => (
        <SafetyBanner key={event.id} event={event} layout={layout} />
      ))}
    </>
  );
}

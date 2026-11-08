import { useVenues, type VenueSummary } from "@dinemate/api-client";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

const STORE_KEY = "dinemate-business:venue";

interface VenueState {
  venues: VenueSummary[];
  venue: VenueSummary | undefined;
  select: (id: string) => void;
  loading: boolean;
}

const VenueContext = createContext<VenueState>({ venues: [], venue: undefined, select: () => undefined, loading: true });

function stored(): string | null {
  try {
    return window.localStorage.getItem(STORE_KEY);
  } catch {
    return null;
  }
}

export function VenueProvider({ children }: { children: ReactNode }) {
  const list = useVenues();
  const [picked, setPicked] = useState<string | null>(stored);
  const venues = list.data?.items ?? [];
  const venue = venues.find((v) => v.id === picked) ?? venues[0];
  useEffect(() => {
    if (!picked) return;
    try {
      window.localStorage.setItem(STORE_KEY, picked);
    } catch {}
  }, [picked]);
  return <VenueContext.Provider value={{ venues, venue, select: setPicked, loading: list.isPending }}>{children}</VenueContext.Provider>;
}

export function useVenue(): VenueState {
  return useContext(VenueContext);
}

export function useIsWide(): boolean {
  const query = "(min-width: 768px)";
  const [wide, setWide] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setWide(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return wide;
}

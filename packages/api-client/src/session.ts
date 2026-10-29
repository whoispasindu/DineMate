import { useSyncExternalStore } from "react";
import type { StaffUser } from "./types";

export type SessionState = { status: "unknown" } | { status: "signed_out" } | { status: "signed_in"; user: StaffUser; sample: boolean };

interface Held {
  token: string | null;
  expiresAt: number;
}

let state: SessionState = { status: "unknown" };
let held: Held = { token: null, expiresAt: 0 };
const listeners = new Set<() => void>();

export function sessionState(): SessionState {
  return state;
}

export function heldToken(): Held {
  return held;
}

export function setSession(next: SessionState, token: Held = { token: null, expiresAt: 0 }): void {
  state = next;
  held = token;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useStaffSession(): SessionState {
  return useSyncExternalStore(subscribe, sessionState);
}

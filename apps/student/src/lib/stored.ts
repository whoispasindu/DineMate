import { useSyncExternalStore } from "react";

export interface StoredValue<T> {
  get: () => T;
  set: (next: T | ((prev: T) => T)) => void;
  use: () => T;
}

export function storedValue<T>(key: string, fallback: T): StoredValue<T> {
  const storageKey = `dinemate:${key}`;
  const listeners = new Set<() => void>();
  let cached: T = read();

  function read(): T {
    try {
      const raw = window.localStorage.getItem(storageKey);
      return raw === null ? fallback : (JSON.parse(raw) as T);
    } catch {
      return fallback;
    }
  }

  function set(next: T | ((prev: T) => T)): void {
    cached = typeof next === "function" ? (next as (prev: T) => T)(cached) : next;
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(cached));
    } catch {}
    listeners.forEach((l) => l());
  }

  function subscribe(listener: () => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  return {
    get: () => cached,
    set,
    use: () => useSyncExternalStore(subscribe, () => cached),
  };
}

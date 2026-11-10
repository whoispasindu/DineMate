import { afterEach, describe, expect, it, vi } from "vitest";
import { nextSeatId } from "../layout";
import { reachableStream } from "../stream";
import { formatClock, formatClock24, formatLocalHM } from "../time";

describe("time", () => {
  it("shows Sri Lanka time whatever the device time zone is", () => {
    expect(formatClock("2026-11-20T07:11:00Z")).toBe("12:41 p.m.");
    expect(formatClock24("2026-11-20T18:35:00Z")).toBe("00:05");
    expect(formatClock(Date.parse("2026-11-20T18:30:00Z"))).toBe("12:00 a.m.");
  });

  it("formats local hours and minutes", () => {
    expect(formatLocalHM("07:00")).toBe("7:00 a.m.");
    expect(formatLocalHM("12:05")).toBe("12:05 p.m.");
  });
});

describe("nextSeatId", () => {
  it("skips ids already used in any shape", () => {
    const shapes = [
      { points: [], seats: [{ seat_id: "seat-1", x: 0, y: 0 }] },
      { points: [], seats: [{ seat_id: "seat-3", x: 0, y: 0 }] },
    ];
    expect(nextSeatId(shapes as never)).toBe("seat-4");
    expect(nextSeatId([] as never, "T")).toBe("T-1");
  });
});

describe("reachableStream", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("points a loopback live link at the dashboard's host on another device", () => {
    vi.stubGlobal("window", { location: { hostname: "192.168.1.20" } });
    expect(reachableStream("http://localhost:8090/live?exp=1&sig=a")).toBe("http://192.168.1.20:8090/live?exp=1&sig=a");
    expect(reachableStream("http://192.168.1.50:8090/live")).toBe("http://192.168.1.50:8090/live");
  });

  it("keeps loopback links on the same computer and passes bad input through", () => {
    vi.stubGlobal("window", { location: { hostname: "localhost" } });
    expect(reachableStream("http://127.0.0.1:8090/live")).toBe("http://127.0.0.1:8090/live");
    expect(reachableStream("not a url")).toBe("not a url");
  });
});

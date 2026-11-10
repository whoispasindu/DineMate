import { describe, expect, it } from "vitest";
import { hasTestVideo, isTestHint, labelFromFile, NO_TEST_VIDEO } from "../testVideo";

describe("test video helpers", () => {
  it("knows when a link or a file was chosen", () => {
    expect(hasTestVideo(NO_TEST_VIDEO)).toBe(false);
    expect(hasTestVideo({ link: "  ", file: null })).toBe(false);
    expect(hasTestVideo({ link: "https://youtu.be/abc", file: null })).toBe(true);
    expect(hasTestVideo({ link: "", file: { name: "a.mp4" } as File })).toBe(true);
  });

  it("tags uploaded videos and YouTube links, not real cameras", () => {
    expect(isTestHint("Test video · lunch-abcdef.mp4")).toBe(true);
    expect(isTestHint("https://youtu.be/…")).toBe(true);
    expect(isTestHint("https://www.youtube.com/…")).toBe(true);
    expect(isTestHint("rtsp://192.168.1.50:554/…")).toBe(false);
    expect(isTestHint(null)).toBe(false);
  });

  it("names a camera after its file", () => {
    expect(labelFromFile({ name: "Lunch rush.final.MOV" } as File)).toBe("Lunch rush.final");
    expect(labelFromFile({ name: ".mp4" } as File)).toBe("Test video");
    expect(labelFromFile({ name: `${"x".repeat(60)}.mp4` } as File)).toHaveLength(40);
  });
});

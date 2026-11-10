import { useTestFeedLive, useUploadTestVideo, type CameraDetail } from "@dinemate/api-client";
import { Icon, reachableStream } from "@dinemate/ui";
import { useCallback, useEffect, useState } from "react";
import { Button, Field, Select, TextInput } from "./kit";

export interface TestVideoChoice {
  link: string;
  file: File | null;
}

export const NO_TEST_VIDEO: TestVideoChoice = { link: "", file: null };

export function hasTestVideo(choice: TestVideoChoice): boolean {
  return choice.file !== null || choice.link.trim() !== "";
}

export function labelFromFile(file: File): string {
  return file.name.replace(/\.[^.]+$/, "").slice(0, 40) || "Test video";
}

export function useTestVideoSource() {
  const upload = useUploadTestVideo();
  const resolve = useCallback(
    async (choice: TestVideoChoice): Promise<string> => (choice.file ? (await upload.mutateAsync(choice.file)).source : choice.link.trim()),
    [upload],
  );
  return { resolve, uploading: upload.isPending };
}

export function DetailSelect({ value, onChange }: { value: CameraDetail; onChange: (next: CameraDetail) => void }) {
  return (
    <Field label="Detail" hint="High finds more people in big, crowded rooms but needs a faster computer.">
      <Select value={value} onChange={(e) => onChange(e.target.value as CameraDetail)}>
        <option value="auto">Auto</option>
        <option value="standard">Standard</option>
        <option value="high">High</option>
      </Select>
    </Field>
  );
}

export function TestVideoInput({ value, onChange }: { value: TestVideoChoice; onChange: (next: TestVideoChoice) => void }) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-dashed border-dash bg-page p-3">
      <Field label="YouTube link" hint="A live stream or a normal video. It plays on a loop.">
        <TextInput
          value={value.link}
          maxLength={500}
          placeholder="https://www.youtube.com/watch?v=…"
          disabled={value.file !== null}
          onChange={(e) => onChange({ link: e.target.value, file: null })}
          autoComplete="off"
        />
      </Field>
      <Field label="Or a video file from this computer" hint="MP4, MOV, MKV, AVI, WEBM or M4V, up to 1 GB.">
        <input
          key={value.file ? "chosen" : "empty"}
          type="file"
          accept="video/*,.mp4,.mov,.mkv,.avi,.webm,.m4v"
          className="text-sm file:mr-3 file:min-h-9 file:rounded-xl file:border-0 file:bg-chip file:px-3 file:font-semibold"
          onChange={(e) => onChange({ link: "", file: e.target.files?.[0] ?? null })}
        />
      </Field>
      <p className="m-0 text-xs text-muted">
        For testing and demos only. Use footage you have permission to use. An uploaded file stays on the DineMate server and is deleted
        when you remove the test feed.
      </p>
    </div>
  );
}

export function LiveBackdrop({ deviceId }: { deviceId: string }) {
  const link = useTestFeedLive(deviceId);
  const [broken, setBroken] = useState(false);
  const { isError, refetch } = link;
  useEffect(() => {
    if (!isError && !broken) return;
    const timer = window.setInterval(() => {
      setBroken(false);
      void refetch();
    }, 10_000);
    return () => window.clearInterval(timer);
  }, [isError, broken, refetch]);
  if (link.data && !broken) {
    return (
      <img
        src={reachableStream(link.data.url)}
        alt="Live view from this test video"
        className="absolute inset-0 h-full w-full rounded-xl object-fill"
        onError={() => setBroken(true)}
      />
    );
  }
  return (
    <div className="absolute inset-0 flex items-center justify-center rounded-xl bg-[#1b2420] p-6 text-center text-sm text-white/80">
      <span className="flex max-w-md flex-col items-center gap-2">
        <Icon name="camera" size={26} />
        {link.isPending
          ? "Connecting to the test video…"
          : "No picture yet. It appears by itself once the video starts, usually within a minute. You can draw already."}
        {!link.isPending ? (
          <Button
            className="min-h-8"
            onClick={() => {
              setBroken(false);
              void link.refetch();
            }}
          >
            Try again
          </Button>
        ) : null}
      </span>
    </div>
  );
}

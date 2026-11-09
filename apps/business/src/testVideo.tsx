import { useUploadTestVideo } from "@dinemate/api-client";
import { useCallback } from "react";
import { Field, TextInput } from "./kit";

export interface TestVideoChoice {
  link: string;
  file: File | null;
}

export const NO_TEST_VIDEO: TestVideoChoice = { link: "", file: null };

export function hasTestVideo(choice: TestVideoChoice): boolean {
  return choice.file !== null || choice.link.trim() !== "";
}

export function isTestHint(hint: string | null | undefined): boolean {
  return !!hint && (hint.startsWith("Test video") || /youtube\.com|youtu\.be/.test(hint));
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
        For testing and demos only. Use footage you have permission to use. An uploaded file stays on the café computer and is deleted when
        you remove the camera.
      </p>
    </div>
  );
}

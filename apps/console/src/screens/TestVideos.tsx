import {
  apiMode,
  useAddTestFeed,
  useManagedDevices,
  useRemoveTestFeed,
  useServerNow,
  useTestFeedLive,
  useTestFeeds,
  type VideoFeed,
} from "@dinemate/api-client";
import { cx, formatAgo, Icon, reachableStream } from "@dinemate/ui";
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { Banner, Button, errorText, Field, Page, Panel, Select, TextInput } from "../kit";
import { hasTestVideo, labelFromFile, NO_TEST_VIDEO, TestVideoInput, useTestVideoSource, type TestVideoChoice } from "../testVideo";

const STATUS: Record<VideoFeed["status"], { label: string; dot: string; text: string }> = {
  ok: { label: "Counting", dot: "bg-ok-mark", text: "text-ok" },
  waiting_for_zones: { label: "Draw zones next", dot: "bg-busy-mark", text: "text-busy" },
  starting: { label: "Starting…", dot: "bg-dash", text: "text-muted" },
  offline: { label: "Camera computer off", dot: "bg-dash", text: "text-muted" },
};

function LiveView({ feed }: { feed: VideoFeed }) {
  const streaming = feed.status === "ok" || feed.status === "waiting_for_zones";
  const link = useTestFeedLive(streaming ? feed.id : undefined);
  const [broken, setBroken] = useState(false);
  if (!streaming) {
    return (
      <div className="flex aspect-video flex-col items-center justify-center gap-3 rounded-xl bg-[#1b2420] p-6 text-center text-sm text-white/80">
        <Icon name="camera" size={26} />
        <span className="max-w-md">
          {feed.status === "starting"
            ? "Starting the video. The first picture takes up to a minute while the model loads."
            : "The camera computer is not running. Start it with pnpm stack:cameras."}
        </span>
      </div>
    );
  }
  if (link.isError || broken) {
    return (
      <div className="flex aspect-video flex-col items-center justify-center gap-3 rounded-xl bg-[#1b2420] p-6 text-center text-sm text-white/80">
        <Icon name="camera" size={26} />
        <span className="max-w-md">{link.isError ? errorText(link.error) : "The camera computer didn't answer."}</span>
        <Button
          className="min-h-8"
          onClick={() => {
            setBroken(false);
            void link.refetch();
          }}
        >
          Try again
        </Button>
      </div>
    );
  }
  if (!link.data) return <div aria-busy="true" className="aspect-video w-full rounded-xl bg-line-soft motion-safe:animate-pulse" />;
  return (
    <img
      src={reachableStream(link.data.url)}
      alt={`Live view of ${feed.label} with tracking boxes`}
      className="aspect-video w-full rounded-xl bg-[#1b2420] object-contain"
      onError={() => setBroken(true)}
    />
  );
}

function AddFeed({ canteens }: { canteens: { id: string; name: string }[] }) {
  const add = useAddTestFeed();
  const video = useTestVideoSource();
  const [canteen, setCanteen] = useState("");
  const [label, setLabel] = useState("");
  const [clip, setClip] = useState<TestVideoChoice>(NO_TEST_VIDEO);
  const [problem, setProblem] = useState<string | null>(null);
  const canteenId = canteen || canteens[0]?.id || "";
  const busy = add.isPending || video.uploading;
  return (
    <Panel title="Add a test video">
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setProblem(null);
          void (async () => {
            try {
              const source = await video.resolve(clip);
              await add.mutateAsync({ canteenId, body: { label: label.trim(), source } });
              setLabel("");
              setClip(NO_TEST_VIDEO);
            } catch (error) {
              setProblem(errorText(error));
            }
          })();
        }}
      >
        <div className="flex flex-wrap gap-3">
          <Field label="Canteen">
            <Select value={canteenId} onChange={(e) => setCanteen(e.target.value)}>
              {canteens.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Name" className="min-w-[200px] flex-1">
            <TextInput value={label} maxLength={40} placeholder="Lunch rush clip" onChange={(e) => setLabel(e.target.value)} />
          </Field>
        </div>
        <TestVideoInput
          value={clip}
          onChange={(next) => {
            setClip(next);
            if (next.file && !label.trim()) setLabel(labelFromFile(next.file));
          }}
        />
        {problem ? <Banner tone="error">{problem}</Banner> : null}
        {add.isSuccess && !problem ? (
          <Banner tone="ok">Added. The camera computer starts it within a minute. Then draw its zones.</Banner>
        ) : null}
        <div>
          <Button type="submit" tone="primary" disabled={!canteenId || !label.trim() || !hasTestVideo(clip) || busy}>
            {video.uploading ? "Uploading video…" : "Add test video"}
          </Button>
        </div>
      </form>
    </Panel>
  );
}

function FeedRow({ feed, now, chosen, onChoose }: { feed: VideoFeed; now: number; chosen: boolean; onChoose: () => void }) {
  const remove = useRemoveTestFeed();
  const [confirm, setConfirm] = useState(false);
  const look = STATUS[feed.status];
  return (
    <li className={cx("flex flex-col gap-2 rounded-xl p-3", chosen ? "bg-ok-bg" : "bg-page")}>
      <div className="flex items-start justify-between gap-3">
        <span className="flex items-start gap-3">
          <span aria-hidden="true" className={cx("mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full", look.dot)} />
          <span className="flex flex-col">
            <span className="text-[15px] font-bold">{feed.label}</span>
            <span className="text-[13px] text-muted">
              {feed.canteen_name} · {feed.source_hint ?? "no source"}
            </span>
            <span className="text-[13px] text-muted">{feed.zones.length > 0 ? feed.zones.join(" · ") : "No zones yet"}</span>
          </span>
        </span>
        <span className="flex flex-col items-end">
          <span className={cx("text-sm font-bold", look.text)}>{look.label}</span>
          <span className="text-xs text-muted">
            {feed.last_seen_at ? `seen ${formatAgo(feed.last_seen_at, now)}` : "never seen"}
            {feed.fps !== null ? ` · ${feed.fps.toFixed(0)} fps` : ""}
          </span>
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button className="min-h-9" aria-pressed={chosen} onClick={onChoose}>
          Live view<span className="sr-only"> of {feed.label}</span>
        </Button>
        <Link
          to={`/zones?device=${encodeURIComponent(feed.id)}`}
          className="inline-flex min-h-9 items-center rounded-[10px] bg-brand px-3 text-sm font-bold text-white no-underline hover:bg-brand-mid"
        >
          Draw zones<span className="sr-only"> for {feed.label}</span>
        </Link>
        {confirm ? (
          <>
            <Button className="min-h-9" disabled={remove.isPending} onClick={() => remove.mutate(feed.id)}>
              Remove {feed.label}
            </Button>
            <Button className="min-h-9" onClick={() => setConfirm(false)}>
              Keep
            </Button>
          </>
        ) : (
          <Button className="min-h-9" onClick={() => setConfirm(true)}>
            Remove<span className="sr-only"> {feed.label}</span>
          </Button>
        )}
      </div>
      {remove.isError ? <span className="text-[13px] text-crowd">{errorText(remove.error)}</span> : null}
    </li>
  );
}

export function TestVideosScreen() {
  const live = apiMode() === "api";
  const feeds = useTestFeeds(live);
  const devices = useManagedDevices();
  const now = useServerNow(5000);
  const [chosen, setChosen] = useState<string | null>(null);
  const items = feeds.data?.items ?? [];
  const shown = items.find((f) => f.id === chosen) ?? items.find((f) => f.status !== "offline") ?? items[0];
  const canteens = useMemo(() => {
    const seen = new Map<string, string>();
    for (const d of devices.data?.items ?? []) seen.set(d.canteen_id, d.canteen_name);
    return [...seen].map(([id, name]) => ({ id, name }));
  }, [devices.data]);
  return (
    <Page title="Test videos" sub="Temporary: play a YouTube link or a recorded video as a pretend camera, then draw zones on it.">
      {!live ? <Banner>Test videos need the real API. Start it with pnpm stack:cameras, then pnpm dev:console:api.</Banner> : null}
      {feeds.isError ? <Banner tone="error">{errorText(feeds.error)}</Banner> : null}
      {live ? (
        <div className="flex flex-wrap items-start gap-5">
          <Panel title={shown ? `Live view · ${shown.label}` : "Live view"} className="min-w-[320px] flex-[1.6_1_560px]">
            {shown ? (
              <LiveView key={`${shown.id}-${shown.status === "starting" || shown.status === "offline" ? "off" : "on"}`} feed={shown} />
            ) : (
              <p className="m-0 text-sm text-muted">Add a test video to see it here with tracking boxes.</p>
            )}
            <ol className="m-0 flex flex-col gap-1 pl-5 text-[13px] text-ink-2">
              <li>Add a YouTube link or upload a clip. The camera computer starts it within a minute.</li>
              <li>Press Draw zones, link a seating shape to a zone and place seats on the live picture.</li>
              <li>Counts from the video replace the simulator for that zone while the video runs.</li>
            </ol>
          </Panel>
          <div className="flex min-w-[320px] flex-[1_1_380px] flex-col gap-5">
            <Panel title="Test feeds">
              {feeds.data && items.length === 0 ? <p className="m-0 text-sm text-muted">No test videos yet.</p> : null}
              <ul className="m-0 flex list-none flex-col gap-2 p-0">
                {items.map((f) => (
                  <FeedRow key={f.id} feed={f} now={now} chosen={f.id === shown?.id} onChoose={() => setChosen(f.id)} />
                ))}
              </ul>
            </Panel>
            <AddFeed canteens={canteens} />
          </div>
        </div>
      ) : null}
    </Page>
  );
}

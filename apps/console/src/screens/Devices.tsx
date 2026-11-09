import {
  apiMode,
  useAddTestFeed,
  useManagedDevices,
  useRemoveTestFeed,
  useServerNow,
  useTestFeeds,
  type ManagedDevice,
  type VideoFeed,
} from "@dinemate/api-client";
import { cx, formatAgo } from "@dinemate/ui";
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { Banner, Button, errorText, Field, Page, Panel, Select, TextInput } from "../kit";
import { hasTestVideo, labelFromFile, NO_TEST_VIDEO, TestVideoInput, useTestVideoSource, type TestVideoChoice } from "../testVideo";

const ONLINE_MS = 120_000;

interface Look {
  label: string;
  dot: string;
  text: string;
}

const FEED_LOOK: Record<VideoFeed["status"], Look> = {
  ok: { label: "Counting", dot: "bg-ok-mark", text: "text-ok" },
  waiting_for_zones: { label: "Draw zones next", dot: "bg-busy-mark", text: "text-busy" },
  starting: { label: "Starting…", dot: "bg-dash", text: "text-muted" },
  offline: { label: "Camera computer off", dot: "bg-dash", text: "text-muted" },
};
const ONLINE: Look = { label: "Online", dot: "bg-ok-mark", text: "text-ok" };
const OFFLINE: Look = { label: "Offline", dot: "bg-dash", text: "text-muted" };

function deviceLook(device: ManagedDevice, feed: VideoFeed | undefined, now: number): Look {
  if (feed) return FEED_LOOK[feed.status];
  const seen = device.last_heartbeat_at ? Date.parse(device.last_heartbeat_at) : null;
  return device.is_enabled && seen !== null && now - seen < ONLINE_MS ? ONLINE : OFFLINE;
}

function AddTestVideo({ canteens }: { canteens: { id: string; name: string }[] }) {
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
      <p className="m-0 text-sm text-ink-2">
        Temporary: play a YouTube link or a recorded clip as a pretend camera. Then open it in Zones to see it live and draw its zones.
      </p>
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
          <Banner tone="ok">Added. The camera computer starts it within a minute. Then press Open in Zones.</Banner>
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

function DeviceRow({ device, feed, now, first }: { device: ManagedDevice; feed?: VideoFeed; now: number; first: boolean }) {
  const remove = useRemoveTestFeed();
  const [confirm, setConfirm] = useState(false);
  const look = deviceLook(device, feed, now);
  const name = device.label ?? device.id;
  const detail = feed
    ? `${feed.source_hint ?? "no source"} · ${feed.zones.length > 0 ? feed.zones.join(" · ") : "no zones yet"}`
    : device.layout_version
      ? `layout v${device.layout_version}`
      : "no layout yet";
  return (
    <li className={cx("flex flex-col gap-2 py-3", !first && "border-t border-line-soft")}>
      <div className="flex items-start justify-between gap-3">
        <span className="flex items-start gap-3">
          <span aria-hidden="true" className={cx("mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full", look.dot)} />
          <span className="flex flex-col">
            <span className="text-[15px] font-bold">
              {name}
              {feed ? (
                <span className="ml-2 rounded-full bg-busy-bg px-2 py-0.5 text-xs font-semibold text-busy">Test video</span>
              ) : (
                <span className="ml-2 rounded-full bg-chip px-2 py-0.5 text-xs font-semibold text-neutral-ink">
                  {device.kind === "simulator" ? "Simulator" : "Camera"}
                </span>
              )}
            </span>
            <span className="text-[13px] text-muted">
              {device.canteen_name} · {detail}
            </span>
          </span>
        </span>
        <span className="flex flex-col items-end">
          <span className={cx("text-sm font-bold", look.text)}>{look.label}</span>
          <span className="text-xs text-muted">
            {device.last_heartbeat_at ? `seen ${formatAgo(device.last_heartbeat_at, now)}` : "never seen"}
            {feed?.fps != null ? ` · ${feed.fps.toFixed(0)} fps` : ""}
          </span>
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Link
          to={`/zones?device=${encodeURIComponent(device.id)}`}
          className="inline-flex min-h-9 items-center rounded-[10px] border border-line bg-card px-3 text-sm font-bold text-ink no-underline hover:bg-page"
        >
          Open in Zones<span className="sr-only"> for {name}</span>
        </Link>
        {feed ? (
          confirm ? (
            <>
              <Button className="min-h-9" disabled={remove.isPending} onClick={() => remove.mutate(feed.id)}>
                Remove {name}
              </Button>
              <Button className="min-h-9" onClick={() => setConfirm(false)}>
                Keep
              </Button>
            </>
          ) : (
            <Button className="min-h-9" onClick={() => setConfirm(true)}>
              Remove<span className="sr-only"> {name}</span>
            </Button>
          )
        ) : null}
      </div>
      {remove.isError ? <span className="text-[13px] text-crowd">{errorText(remove.error)}</span> : null}
    </li>
  );
}

export function DevicesScreen() {
  const live = apiMode() === "api";
  const devices = useManagedDevices();
  const feeds = useTestFeeds(live);
  const now = useServerNow(5000);
  const items = useMemo(() => devices.data?.items ?? [], [devices.data]);
  const byId = useMemo(() => new Map((feeds.data?.items ?? []).map((f) => [f.id, f])), [feeds.data]);
  const canteens = useMemo(() => {
    const seen = new Map<string, string>();
    for (const d of items) seen.set(d.canteen_id, d.canteen_name);
    return [...seen].map(([id, name]) => ({ id, name }));
  }, [items]);
  return (
    <Page title="Devices" sub="Cameras, simulators and test videos per canteen. Open one in Zones to see it live and draw its zones.">
      {!live ? <Banner>Devices need the real API. Start it with pnpm stack:cameras, then pnpm dev:console:api.</Banner> : null}
      {devices.isError && live ? <Banner tone="error">{errorText(devices.error)}</Banner> : null}
      {feeds.isError ? <Banner tone="error">{errorText(feeds.error)}</Banner> : null}
      {live ? (
        <div className="flex flex-wrap items-start gap-5">
          <Panel title="Devices" className="min-w-[320px] flex-[1.4_1_520px]">
            {devices.data && items.length === 0 ? <p className="m-0 text-sm text-muted">No devices yet.</p> : null}
            <ul className="m-0 flex list-none flex-col p-0">
              {items.map((d, i) => (
                <DeviceRow key={d.id} device={d} feed={byId.get(d.id)} now={now} first={i === 0} />
              ))}
            </ul>
          </Panel>
          <div className="flex min-w-[320px] flex-[1_1_380px] flex-col gap-5">
            <AddTestVideo canteens={canteens} />
          </div>
        </div>
      ) : null}
    </Page>
  );
}

import {
  apiMode,
  useAddCamera,
  useCameras,
  useFloor,
  useLiveLink,
  useRemoveCamera,
  useServerNow,
  useUpdateCamera,
  type CameraDetail,
  type CameraHealth,
  type VenueFloor,
} from "@dinemate/api-client";
import { cx, formatAgo, Icon, reachableStream } from "@dinemate/ui";
import { useState } from "react";
import { Link } from "react-router";
import { Banner, Button, errorText, Field, Page, Panel, Skeleton, TextInput } from "../kit";
import {
  DetailSelect,
  hasTestVideo,
  isTestHint,
  labelFromFile,
  NO_TEST_VIDEO,
  TestVideoInput,
  useTestVideoSource,
  type TestVideoChoice,
} from "../testVideo";
import { useVenue } from "../venue";

const SOURCE_HELP = "rtsp://user:password@192.168.1.50:554/stream1 · http://192.168.1.20:8080/video · 0 for a USB camera";

const STATUS: Record<CameraHealth["status"], { label: string; dot: string; text: string }> = {
  ok: { label: "Online", dot: "bg-ok-mark", text: "text-ok" },
  not_reporting: { label: "Online, not reporting", dot: "bg-busy-mark", text: "text-busy" },
  offline: { label: "Offline", dot: "bg-dash", text: "text-muted" },
};

const W = 1000;
const H = 600;

function SimulatedFeed({ floor }: { floor: VenueFloor }) {
  const staff = floor.totals.counter_staff ?? 0;
  const queue = floor.totals.queue_people ?? 0;
  return (
    <figure className="m-0 flex flex-col gap-2">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Simulated camera view: ${floor.tables.filter((t) => t.state === "occupied").length} tables seated, ${staff} staff at the counter, queue of about ${queue}`}
        className="w-full rounded-[14px] bg-[#1d232b]"
      >
        <rect x={W * 0.62} y={H * 0.02} width={W * 0.36} height={H * 0.13} rx={8} fill="none" stroke="#7c8aa5" strokeDasharray="6 6" />
        <text x={W * 0.63} y={H * 0.055} fill="#c6cfdd" fontSize="15" fontFamily="DM Sans, sans-serif">
          work: counter
        </text>
        {Array.from({ length: Math.min(staff, 4) }, (_, i) => (
          <g key={`s${i}`}>
            <rect x={W * 0.8 + i * 44} y={H * 0.035} width={30} height={46} rx={5} fill="none" stroke="#a78bfa" strokeWidth={2.5} />
            <text x={W * 0.8 + i * 44 + 1} y={H * 0.035 + 62} fill="#d9ccff" fontSize="12" fontFamily="DM Sans, sans-serif">
              Staff
            </text>
          </g>
        ))}
        {Array.from({ length: Math.min(queue, 6) }, (_, i) => (
          <g key={`q${i}`}>
            <rect x={W * 0.94 - i * 38} y={H * 0.2} width={26} height={40} rx={5} fill="none" stroke="#e6b450" strokeWidth={2} />
            <circle cx={W * 0.94 - i * 38 + 13} cy={H * 0.2 + 10} r={7} fill="#5c6675" />
          </g>
        ))}
        {queue > 0 ? (
          <text
            x={W * 0.94 - Math.min(queue, 6) * 38 - 10}
            y={H * 0.2 + 26}
            textAnchor="end"
            fill="#f1d38f"
            fontSize="13"
            fontFamily="DM Sans, sans-serif"
          >
            queue ~{queue}
          </text>
        ) : null}
        {floor.tables.map((t) => {
          const x = t.x * W;
          const y = (0.22 + t.y * 0.78) * H;
          const w = t.w * W;
          const h = t.h * H * 0.78;
          const seated = t.state === "occupied";
          return (
            <g key={t.id}>
              <rect
                x={x}
                y={y}
                width={w}
                height={h}
                rx={t.shape === "round" ? Math.min(w, h) / 2 : 8}
                fill={t.state === "needs_clearing" ? "#3a2f2f" : "#2a323d"}
                stroke={seated ? "#7aa2f7" : t.state === "free" ? "#5fb57f" : t.state === "held" ? "#e6b450" : "#8b96a8"}
                strokeWidth={2}
              />
              {Array.from({ length: seated ? t.party_size : 0 }, (_, i) => {
                const step = Math.min(26, (w - 12) / Math.max(1, t.party_size));
                return (
                  <g key={i}>
                    <rect
                      x={x + 6 + i * step}
                      y={y + 6}
                      width={step - 4}
                      height={28}
                      rx={4}
                      fill="none"
                      stroke="#7aa2f7"
                      strokeWidth={1.5}
                    />
                    <circle cx={x + 6 + i * step + (step - 4) / 2} cy={y + 14} r={5} fill="#5c6675" />
                  </g>
                );
              })}
              <text x={x + 6} y={y + h - 8} fill="#e2e8f0" fontSize="13" fontFamily="DM Sans, sans-serif">
                {t.name}
                {seated && t.seated_min !== null ? ` · ${t.seated_min} min` : ""}
              </text>
            </g>
          );
        })}
      </svg>
      <figcaption className="text-[13px] text-muted">
        Simulated view drawn from the sample simulator. Grey circles stand for blurred customer faces.
      </figcaption>
    </figure>
  );
}

function LiveStream({ venueId, camera }: { venueId: string; camera: CameraHealth }) {
  const link = useLiveLink(venueId, camera.id);
  const [broken, setBroken] = useState(false);
  if (link.isPending) return <Skeleton className="aspect-video" />;
  if (link.isError) {
    return (
      <div className="flex items-start gap-3 rounded-[14px] border border-dashed border-dash bg-page p-4">
        <Icon name="camera" size={22} className="mt-0.5 shrink-0 text-muted" />
        <p className="m-0 text-sm leading-relaxed text-ink-2">{errorText(link.error)}</p>
      </div>
    );
  }
  return (
    <figure className="m-0 flex flex-col gap-2">
      {broken ? (
        <Banner tone="info">
          The camera computer didn't answer. Live view works only on the café network.{" "}
          <Button
            className="ml-2 min-h-8"
            onClick={() => {
              setBroken(false);
              void link.refetch();
            }}
          >
            Try again
          </Button>
        </Banner>
      ) : (
        <img
          src={reachableStream(link.data.url)}
          alt={`Live view from ${camera.id} with tracking boxes; customer faces blurred`}
          className="aspect-video w-full rounded-[14px] bg-[#1d232b] object-contain"
          onError={() => setBroken(true)}
        />
      )}
      <figcaption className="text-[13px] text-muted">
        Streamed from the café computer, never recorded. The link works for 60 seconds; a viewing lasts up to 10 minutes.
      </figcaption>
    </figure>
  );
}

function LiveView({ venueId, cameras }: { venueId: string; cameras: CameraHealth[] }) {
  const floor = useFloor(venueId);
  const [chosen, setChosen] = useState<string | null>(null);
  const camera = cameras.find((c) => c.id === chosen) ?? cameras.find((c) => c.status !== "offline") ?? cameras[0];
  return (
    <Panel
      title="Live view"
      className="flex-[1.6_1_560px]"
      aside={
        cameras.length > 1 ? (
          <span className="flex flex-wrap gap-1.5" role="group" aria-label="Camera">
            {cameras.map((c) => (
              <button
                key={c.id}
                type="button"
                aria-pressed={c.id === camera?.id}
                onClick={() => setChosen(c.id)}
                className={cx(
                  "min-h-8 rounded-full px-3 text-[13px] font-semibold",
                  c.id === camera?.id ? "bg-brand text-on-dark" : "bg-chip text-neutral-ink hover:bg-line-soft",
                )}
              >
                {c.id}
              </button>
            ))}
          </span>
        ) : null
      }
    >
      {!camera ? <p className="m-0 text-sm text-muted">No cameras are set up for this venue.</p> : null}
      {camera?.kind === "simulator" ? floor.data ? <SimulatedFeed floor={floor.data} /> : <Skeleton className="aspect-video" /> : null}
      {camera && camera.kind === "camera" ? <LiveStream key={camera.id} venueId={venueId} camera={camera} /> : null}
      <p className="m-0 flex items-start gap-2 text-[13px] text-ink-2">
        <Icon name="lock" size={16} className="mt-0.5 shrink-0 text-muted" />
        On the café network only. Customer faces are blurred before the picture leaves the camera computer, and nothing is saved.
      </p>
    </Panel>
  );
}

function statusLine(c: CameraHealth): { label: string; dot: string; text: string } {
  if (c.kind === "camera" && c.status === "offline" && !c.last_seen_at) {
    return { label: "Waiting for the camera computer", dot: "bg-dash", text: "text-muted" };
  }
  if (c.waiting_for_zones || (c.kind === "camera" && c.status !== "offline" && !c.has_layout)) {
    return { label: "Waiting for zones", dot: "bg-busy-mark", text: "text-busy" };
  }
  return STATUS[c.status];
}

function AddCamera({ venueId }: { venueId: string }) {
  const add = useAddCamera(venueId);
  const video = useTestVideoSource();
  const [label, setLabel] = useState("");
  const [source, setSource] = useState("");
  const [testing, setTesting] = useState(false);
  const [clip, setClip] = useState<TestVideoChoice>(NO_TEST_VIDEO);
  const [problem, setProblem] = useState<string | null>(null);
  const [detail, setDetail] = useState<CameraDetail>("auto");
  const ready = label.trim() !== "" && (testing ? hasTestVideo(clip) : source.trim() !== "");
  const busy = add.isPending || video.uploading;
  return (
    <Panel title="Add a camera">
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setProblem(null);
          void (async () => {
            try {
              const chosen = testing ? await video.resolve(clip) : source.trim();
              await add.mutateAsync({ label: label.trim(), source: chosen, detail });
              setLabel("");
              setSource("");
              setClip(NO_TEST_VIDEO);
            } catch (error) {
              setProblem(errorText(error));
            }
          })();
        }}
      >
        <span className="flex flex-wrap gap-1.5" role="group" aria-label="Camera type">
          {[
            { on: false, text: "Camera" },
            { on: true, text: "Test video" },
          ].map((choice) => (
            <button
              key={choice.text}
              type="button"
              aria-pressed={testing === choice.on}
              onClick={() => setTesting(choice.on)}
              className={cx(
                "min-h-8 rounded-full px-3 text-[13px] font-semibold",
                testing === choice.on ? "bg-brand text-on-dark" : "bg-chip text-neutral-ink hover:bg-line-soft",
              )}
            >
              {choice.text}
            </button>
          ))}
        </span>
        <Field label="Name">
          <TextInput
            value={label}
            maxLength={40}
            placeholder={testing ? "Lunch rush clip" : "Counter camera"}
            onChange={(e) => setLabel(e.target.value)}
          />
        </Field>
        {testing ? (
          <TestVideoInput
            value={clip}
            onChange={(next) => {
              setClip(next);
              if (next.file && !label.trim()) setLabel(labelFromFile(next.file));
            }}
          />
        ) : (
          <Field label="Camera address" hint={SOURCE_HELP}>
            <TextInput
              value={source}
              maxLength={500}
              placeholder="rtsp://…"
              onChange={(e) => setSource(e.target.value)}
              autoComplete="off"
            />
          </Field>
        )}
        <DetailSelect value={detail} onChange={setDetail} />
        {problem ? <Banner tone="error">{problem}</Banner> : null}
        {add.isSuccess && !problem ? (
          <Banner tone="ok">Added. The camera computer picks it up within a minute; then press Set up to draw its zones.</Banner>
        ) : null}
        <div>
          <Button type="submit" tone="primary" disabled={!ready || busy}>
            {video.uploading ? "Uploading video…" : testing ? "Add test video" : "Add camera"}
          </Button>
        </div>
        <p className="m-0 text-xs text-muted">
          The address stays on this computer. DineMate only shows the camera's network address, never its password.
        </p>
      </form>
    </Panel>
  );
}

function CameraRow({ camera, venueId, now, first }: { camera: CameraHealth; venueId: string; now: number; first: boolean }) {
  const update = useUpdateCamera(venueId);
  const remove = useRemoveCamera(venueId);
  const [editing, setEditing] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [label, setLabel] = useState(camera.label ?? "");
  const [source, setSource] = useState("");
  const [detail, setDetail] = useState<CameraDetail>(camera.detail ?? "auto");
  const look = statusLine(camera);
  const real = camera.kind === "camera";
  return (
    <li className={cx("flex flex-col gap-2 py-3", !first && "border-t border-line-soft")}>
      <div className="flex items-center justify-between gap-3">
        <span className="flex items-center gap-3">
          <span aria-hidden="true" className={cx("h-2.5 w-2.5 shrink-0 rounded-full", look.dot)} />
          <span className="flex flex-col">
            <span className="text-[15px] font-bold">
              {camera.label ?? camera.id}
              {camera.kind === "simulator" ? (
                <span className="ml-2 rounded-full bg-chip px-2 py-0.5 text-xs font-semibold text-neutral-ink">Simulated</span>
              ) : null}
              {isTestHint(camera.source_hint) ? (
                <span className="ml-2 rounded-full bg-busy-bg px-2 py-0.5 text-xs font-semibold text-busy">Test video</span>
              ) : null}
            </span>
            <span className="text-[13px] text-muted">
              {camera.source_hint ? `${camera.source_hint} · ` : ""}
              {camera.zones.length > 0 ? camera.zones.join(" · ") : "No zones yet"}
            </span>
          </span>
        </span>
        <span className="flex flex-col items-end">
          <span className={cx("text-right text-sm font-bold", look.text)}>{look.label}</span>
          <span className="text-xs text-muted">
            {camera.last_seen_at ? `seen ${formatAgo(camera.last_seen_at, now)}` : "never seen"}
            {camera.fps !== null ? ` · ${camera.fps.toFixed(0)} fps` : ""}
          </span>
        </span>
      </div>
      {real ? (
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={`/cameras/${camera.id}/setup`}
            className="inline-flex min-h-9 items-center rounded-xl bg-brand px-3 text-sm font-bold text-on-dark no-underline hover:bg-brand-mid"
          >
            Set up zones<span className="sr-only"> for {camera.label ?? camera.id}</span>
          </Link>
          <Button className="min-h-9" onClick={() => setEditing((on) => !on)}>
            {editing ? "Cancel" : "Edit"}
            <span className="sr-only"> {camera.label ?? camera.id}</span>
          </Button>
          {confirm ? (
            <>
              <Button className="min-h-9" disabled={remove.isPending} onClick={() => remove.mutate(camera.id)}>
                Remove {camera.label ?? camera.id}
              </Button>
              <Button className="min-h-9" onClick={() => setConfirm(false)}>
                Keep
              </Button>
            </>
          ) : (
            <Button className="min-h-9" onClick={() => setConfirm(true)}>
              Remove<span className="sr-only"> {camera.label ?? camera.id}</span>
            </Button>
          )}
        </div>
      ) : null}
      {editing ? (
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            update.mutate(
              { deviceId: camera.id, body: { label: label.trim() || undefined, source: source.trim() || undefined, detail } },
              { onSuccess: () => setEditing(false) },
            );
          }}
        >
          <Field label="Name" className="w-[160px]">
            <TextInput value={label} maxLength={40} onChange={(e) => setLabel(e.target.value)} />
          </Field>
          <Field label="New address (leave empty to keep)" className="min-w-[220px] flex-1">
            <TextInput value={source} maxLength={500} onChange={(e) => setSource(e.target.value)} autoComplete="off" />
          </Field>
          <DetailSelect value={detail} onChange={setDetail} />
          <Button type="submit" tone="primary" disabled={update.isPending}>
            Save
          </Button>
        </form>
      ) : null}
      {update.isError ? <span className="text-[13px] text-crowd">{errorText(update.error)}</span> : null}
      {remove.isError ? <span className="text-[13px] text-crowd">{errorText(remove.error)}</span> : null}
    </li>
  );
}

export function CamerasScreen() {
  const { venue } = useVenue();
  const cameras = useCameras(venue?.id);
  const now = useServerNow(5000);
  const items = cameras.data?.items ?? [];
  return (
    <Page title="Cameras" sub="Camera health · live view stays on the café network">
      {cameras.isError ? <Banner tone="error">{errorText(cameras.error)}</Banner> : null}
      <div className="flex flex-wrap items-start gap-4">
        {venue && cameras.data ? <LiveView venueId={venue.id} cameras={items} /> : <Skeleton className="h-[360px] flex-[1.6_1_560px]" />}
        <div className="flex min-w-[320px] flex-[1_1_360px] flex-col gap-4">
          <Panel title="Cameras">
            {!cameras.data ? <Skeleton className="h-[160px]" /> : null}
            {cameras.data && items.length === 0 ? <p className="m-0 text-sm text-muted">No cameras yet. Add one below.</p> : null}
            <ul className="m-0 flex list-none flex-col p-0">
              {venue ? items.map((c, i) => <CameraRow key={c.id} camera={c} venueId={venue.id} now={now} first={i === 0} />) : null}
            </ul>
          </Panel>
          {venue && apiMode() === "api" ? <AddCamera venueId={venue.id} /> : null}
        </div>
      </div>
    </Page>
  );
}

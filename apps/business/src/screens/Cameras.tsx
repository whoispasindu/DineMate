import { useCameras, useFloor, useLiveLink, useServerNow, type CameraHealth, type VenueFloor } from "@dinemate/api-client";
import { cx, formatAgo, Icon } from "@dinemate/ui";
import { useState } from "react";
import { Banner, Button, errorText, Page, Panel, Skeleton } from "../kit";
import { useVenue } from "../venue";

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
          src={link.data.url}
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
        <Panel title="Cameras" className="flex-[1_1_320px]">
          {!cameras.data ? <Skeleton className="h-[160px]" /> : null}
          {cameras.data && items.length === 0 ? <p className="m-0 text-sm text-muted">No cameras are set up for this venue.</p> : null}
          <ul className="m-0 flex list-none flex-col p-0">
            {items.map((c, i) => {
              const look = STATUS[c.status];
              return (
                <li key={c.id} className={cx("flex items-center justify-between gap-3 py-3", i > 0 && "border-t border-line-soft")}>
                  <span className="flex items-center gap-3">
                    <span aria-hidden="true" className={cx("h-2.5 w-2.5 shrink-0 rounded-full", look.dot)} />
                    <span className="flex flex-col">
                      <span className="text-[15px] font-bold">
                        {c.id}
                        {c.kind === "simulator" ? (
                          <span className="ml-2 rounded-full bg-chip px-2 py-0.5 text-xs font-semibold text-neutral-ink">Simulated</span>
                        ) : null}
                      </span>
                      <span className="text-[13px] text-muted">{c.zones.length > 0 ? c.zones.join(" · ") : "No zones yet"}</span>
                    </span>
                  </span>
                  <span className="flex flex-col items-end">
                    <span className={cx("text-sm font-bold", look.text)}>{look.label}</span>
                    <span className="text-xs text-muted">
                      {c.last_seen_at ? `seen ${formatAgo(c.last_seen_at, now)}` : "never seen"}
                      {c.fps !== null ? ` · ${c.fps.toFixed(0)} fps` : ""}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        </Panel>
      </div>
    </Page>
  );
}

import { useCameras, useServerNow, type CameraHealth } from "@dinemate/api-client";
import { cx, formatAgo, Icon } from "@dinemate/ui";
import { Banner, errorText, Page, Panel, Skeleton } from "../kit";
import { useVenue } from "../venue";

const STATUS: Record<CameraHealth["status"], { label: string; dot: string; text: string }> = {
  ok: { label: "Online", dot: "bg-ok-mark", text: "text-ok" },
  not_reporting: { label: "Online, not reporting", dot: "bg-busy-mark", text: "text-busy" },
  offline: { label: "Offline", dot: "bg-dash", text: "text-muted" },
};

export function CamerasScreen() {
  const { venue } = useVenue();
  const cameras = useCameras(venue?.id);
  const now = useServerNow(5000);
  const items = cameras.data?.items ?? [];
  return (
    <Page title="Cameras" sub="Camera health · live view stays on the café network">
      {cameras.isError ? <Banner tone="error">{errorText(cameras.error)}</Banner> : null}
      <div className="flex flex-wrap items-start gap-4">
        <Panel title="Cameras" className="flex-[1.4_1_480px]">
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
        <Panel title="Live view" className="flex-[1_1_320px]">
          <div className="flex items-start gap-3 rounded-[14px] border border-dashed border-dash bg-page p-4">
            <Icon name="camera" size={22} className="mt-0.5 shrink-0 text-muted" />
            <p className="m-0 text-sm leading-relaxed text-ink-2">
              Live video with tracking boxes, stay times and table states arrives with the camera stream in Phase 9. It plays on the café
              network only, is never recorded and never reaches our cloud, and customer faces are blurred.
            </p>
          </div>
        </Panel>
      </div>
    </Page>
  );
}

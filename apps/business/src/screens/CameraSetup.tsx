import {
  ApiError,
  useAddArea,
  useCameraLayout,
  useCameras,
  useLiveLink,
  useSaveCameraLayout,
  type DeviceLayout,
  type LayoutPolygon,
  type PolygonType,
  type WorkAreaName,
} from "@dinemate/api-client";
import { cx, Icon, LayoutCanvas, nextSeatId, reachableStream } from "@dinemate/ui";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { Banner, Button, errorText, Field, Page, Panel, Select, Skeleton, TextInput } from "../kit";

import { useVenue } from "../venue";

const COLOR: Record<PolygonType, string> = {
  seating: "#1f9d55",
  queue: "#e0a020",
  walkway: "#7c8580",
  ignore: "#c2410c",
  work: "#2f5bea",
};

const AREA_LABEL: Record<WorkAreaName, string> = { counter: "Counter", kitchen: "Kitchen", floor: "Floor" };

const SQUARE: [number, number][] = [
  [0.35, 0.35],
  [0.65, 0.35],
  [0.65, 0.65],
  [0.35, 0.65],
];

function shapeLabel(polygon: LayoutPolygon, zones: DeviceLayout["zones"]): string {
  if (polygon.type === "seating") {
    const zone = zones.find((z) => z.id === polygon.zone_id);
    return zone ? `${zone.name} · ${(polygon.seats ?? []).length} seats` : "Seating: pick an area";
  }
  if (polygon.type === "work") return `Work: ${polygon.area ? AREA_LABEL[polygon.area] : "pick an area"}`;
  return polygon.type === "queue" ? "Queue" : "Ignore";
}

function Backdrop({ venueId, deviceId }: { venueId: string; deviceId: string }) {
  const link = useLiveLink(venueId, deviceId);
  const [broken, setBroken] = useState(false);
  if (link.data && !broken) {
    return (
      <img
        src={reachableStream(link.data.url)}
        alt="Live view from this camera"
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
          ? "Connecting to the camera…"
          : "No picture yet. The camera computer starts this camera within a minute of adding it. You can still draw, and the picture appears when it is ready."}
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

function Editor({ layout, venueId }: { layout: DeviceLayout; venueId: string }) {
  const save = useSaveCameraLayout(venueId, layout.device_id);
  const addArea = useAddArea(venueId, layout.device_id);
  const [polygons, setPolygons] = useState<LayoutPolygon[]>(layout.polygons);
  const [selected, setSelected] = useState<number | null>(null);
  const [seatMode, setSeatMode] = useState(false);
  const [newArea, setNewArea] = useState("");
  const [dirty, setDirty] = useState(false);
  useEffect(() => {
    setPolygons(layout.polygons);
    setDirty(false);
  }, [layout.version, layout.polygons]);
  const change = (next: LayoutPolygon[]) => {
    setPolygons(next);
    setDirty(true);
  };
  const current = selected !== null ? polygons[selected] : undefined;
  const usedZones = useMemo(() => new Set(polygons.map((p) => p.zone_id).filter(Boolean)), [polygons]);
  const add = (type: PolygonType, area: WorkAreaName | null = null) => {
    const free = layout.zones.find((z) => !usedZones.has(z.id));
    change([...polygons, { type, zone_id: type === "seating" ? (free?.id ?? null) : null, area, points: SQUARE, seats: [] }]);
    setSelected(polygons.length);
    setSeatMode(false);
  };
  const update = (patch: Partial<LayoutPolygon>) => {
    if (selected === null) return;
    change(polygons.map((p, i) => (i === selected ? { ...p, ...patch } : p)));
  };
  const conflict = save.error instanceof ApiError && save.error.status === 409;
  const unlinked = polygons.some((p) => (p.type === "seating" && !p.zone_id) || (p.type === "work" && !p.area));
  return (
    <div className="flex flex-wrap items-start gap-4">
      <Panel title="Draw on the camera" className="flex-[2_1_560px]">
        <div className="relative aspect-video w-full">
          <Backdrop venueId={venueId} deviceId={layout.device_id} />
          <LayoutCanvas
            overlay
            shapes={polygons}
            labelOf={(p) => shapeLabel(p, layout.zones)}
            colorOf={(p) => COLOR[p.type]}
            selected={selected}
            onSelect={(index) => {
              setSelected(index);
              if (index === null) setSeatMode(false);
            }}
            onMove={(shape, vertex, point) =>
              change(polygons.map((p, i) => (i === shape ? { ...p, points: p.points.map((pt, j) => (j === vertex ? point : pt)) } : p)))
            }
            seatMode={seatMode}
            onAddSeat={(shape, [x, y]) =>
              change(
                polygons.map((p, i) =>
                  i === shape ? { ...p, seats: [...(p.seats ?? []), { seat_id: nextSeatId(polygons, layout.device_id), x, y }] } : p,
                ),
              )
            }
            onRemoveSeat={(shape, seat) =>
              change(polygons.map((p, i) => (i === shape ? { ...p, seats: (p.seats ?? []).filter((_, k) => k !== seat) } : p)))
            }
          />
        </div>
        <p className="m-0 text-[13px] text-muted">
          Drag the corners so each shape covers where people's feet are. If the camera looks across the counter, draw the counter area only
          on the floor behind it, not over the counter top: customers' legs are hidden there, so their feet seem to be on it. Select a
          seating shape and press Place seats, then click each chair.
        </p>
      </Panel>
      <div className="flex min-w-[300px] flex-[1_1_320px] flex-col gap-4">
        <Panel title="Add a shape">
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => add("seating")}>Seating</Button>
            <Button onClick={() => add("work", "counter")}>Counter</Button>
            <Button onClick={() => add("work", "kitchen")}>Kitchen</Button>
            <Button onClick={() => add("work", "floor")}>Staff floor</Button>
            <Button onClick={() => add("queue")}>Queue</Button>
            <Button onClick={() => add("ignore")}>Ignore</Button>
          </div>
          <p className="m-0 text-[13px] text-muted">
            Seating counts guests and their tables. Counter, kitchen and staff floor track staff. Queue counts people waiting. Ignore hides
            a screen, mirror or doorway.
          </p>
        </Panel>
        {current && selected !== null ? (
          <Panel title="Selected shape">
            {current.type === "seating" ? (
              <>
                <Field label="Seating area">
                  <Select value={current.zone_id ?? ""} onChange={(e) => update({ zone_id: e.target.value || null })}>
                    <option value="">Pick an area</option>
                    {layout.zones.map((z) => (
                      <option key={z.id} value={z.id} disabled={usedZones.has(z.id) && z.id !== current.zone_id}>
                        {z.name}
                      </option>
                    ))}
                  </Select>
                </Field>
                <form
                  className="flex items-end gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const name = newArea.trim();
                    if (!name) return;
                    addArea.mutate(name, {
                      onSuccess: (result) => {
                        update({ zone_id: result.zone.id });
                        setNewArea("");
                      },
                    });
                  }}
                >
                  <Field label="Or a new area" className="flex-1">
                    <TextInput value={newArea} maxLength={40} placeholder="Patio" onChange={(e) => setNewArea(e.target.value)} />
                  </Field>
                  <Button type="submit" disabled={!newArea.trim() || addArea.isPending}>
                    Add area
                  </Button>
                </form>
                {addArea.isError ? <span className="text-[13px] text-crowd">{errorText(addArea.error)}</span> : null}
                <div className="flex flex-wrap items-center gap-2">
                  <Button tone={seatMode ? "primary" : "secondary"} onClick={() => setSeatMode((on) => !on)}>
                    {seatMode ? "Done placing seats" : "Place seats"}
                  </Button>
                  <span className="text-[13px] text-muted">
                    {(current.seats ?? []).length} seats{seatMode ? " · click a chair to add, a dot to remove" : ""}
                  </span>
                </div>
              </>
            ) : null}
            {current.type === "work" ? (
              <Field label="Work area">
                <Select value={current.area ?? "counter"} onChange={(e) => update({ area: e.target.value as WorkAreaName })}>
                  <option value="counter">Counter</option>
                  <option value="kitchen">Kitchen</option>
                  <option value="floor">Staff floor</option>
                </Select>
              </Field>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={() => {
                  const [a, b] = [current.points.at(-1), current.points[0]];
                  if (a && b) update({ points: [...current.points, [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]] });
                }}
              >
                Add corner
              </Button>
              <Button disabled={current.points.length <= 3} onClick={() => update({ points: current.points.slice(0, -1) })}>
                Remove corner
              </Button>
              <Button
                onClick={() => {
                  change(polygons.filter((_, i) => i !== selected));
                  setSelected(null);
                  setSeatMode(false);
                }}
              >
                Delete shape
              </Button>
            </div>
          </Panel>
        ) : null}
        <Panel title="Save">
          {save.isError ? (
            <Banner tone="error">
              {conflict ? "Someone saved this camera in the meantime. Reload the page to see their version." : errorText(save.error)}
            </Banner>
          ) : null}
          {save.isSuccess && !dirty ? (
            <Banner tone="ok">
              Saved as version {layout.version}. Next, group seats into tables in{" "}
              <Link to="/settings" className="font-bold text-ok underline">
                Settings
              </Link>
              .
            </Banner>
          ) : null}
          {unlinked ? <span className="text-[13px] text-busy">Pick an area for every seating and work shape before saving.</span> : null}
          <div className="flex items-center gap-3">
            <Button
              tone="primary"
              disabled={!dirty || unlinked || save.isPending}
              onClick={() => save.mutate({ base_version: layout.version, polygons })}
            >
              Save layout
            </Button>
            <span className="text-[13px] text-muted">
              {dirty ? "Unsaved changes" : layout.version ? `Version ${layout.version}` : "Not saved yet"}
            </span>
          </div>
        </Panel>
      </div>
    </div>
  );
}

export function CameraSetupScreen() {
  const { deviceId } = useParams();
  const { venue } = useVenue();
  const cameras = useCameras(venue?.id);
  const layout = useCameraLayout(deviceId);
  const camera = cameras.data?.items.find((c) => c.id === deviceId);
  return (
    <Page
      title={camera?.label ?? "Camera setup"}
      sub={camera?.source_hint ? `Camera setup · ${camera.source_hint}` : "Camera setup"}
      actions={
        <Link
          to="/cameras"
          className={cx("inline-flex min-h-10 items-center px-2 text-sm font-bold text-ink-2 no-underline hover:underline")}
        >
          Back to cameras
        </Link>
      }
    >
      {layout.isError ? <Banner tone="error">{errorText(layout.error)}</Banner> : null}
      {!layout.data || !venue ? (
        <Skeleton className="h-[420px]" />
      ) : (
        <Editor key={layout.data.device_id} layout={layout.data} venueId={venue.id} />
      )}
    </Page>
  );
}

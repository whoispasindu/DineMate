import {
  api,
  ApiError,
  apiMode,
  queryKeys,
  useDeviceLayout,
  useLayoutMutation,
  useManagedDevices,
  useServerNow,
  type DeviceLayout,
  type EditableZone,
  type LayoutPolygon,
  type PolygonType,
} from "@dinemate/api-client";
import { cx, formatAgo, formatClock } from "@dinemate/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { Banner, Button, errorText, Field, Page, Panel, Select, TextInput, useUnsavedGuard } from "../kit";

const W = 1600;
const H = 900;
const NUDGE = 0.005;
const TYPE_LABEL: Record<PolygonType, string> = {
  seating: "Seating",
  queue: "Queue",
  walkway: "Walkway",
  ignore: "Ignore",
  work: "Work area",
};
const CAMPUS_TYPES: PolygonType[] = ["seating", "queue", "walkway", "ignore"];
const TYPE_COLOR: Record<PolygonType, string> = {
  seating: "#1f7a4d",
  queue: "#1e6fc2",
  walkway: "#7c8580",
  ignore: "#c2410c",
  work: "#5b34c9",
};

type Point = [number, number];

const clamp = (v: number) => Math.round(Math.min(1, Math.max(0, v)) * 1000) / 1000;
const nextSeatId = (polygons: LayoutPolygon[]): string => {
  const used = new Set(polygons.flatMap((p) => (p.seats ?? []).map((seat) => seat.seat_id)));
  let n = used.size + 1;
  while (used.has(`seat-${n}`)) n += 1;
  return `seat-${n}`;
};
const centroid = (points: Point[]): Point => [
  points.reduce((s, p) => s + p[0], 0) / points.length,
  points.reduce((s, p) => s + p[1], 0) / points.length,
];

function Canvas({
  polygons,
  zones,
  selected,
  onSelect,
  onMove,
  backdrop,
  seatMode,
  onAddSeat,
  onRemoveSeat,
}: {
  polygons: LayoutPolygon[];
  zones: Map<string, EditableZone>;
  selected: number | null;
  onSelect: (index: number | null) => void;
  onMove: (polygon: number, vertex: number, point: Point) => void;
  backdrop: string | null;
  seatMode: boolean;
  onAddSeat: (polygon: number, point: Point) => void;
  onRemoveSeat: (polygon: number, seat: number) => void;
}) {
  const svg = useRef<SVGSVGElement>(null);
  const [drag, setDrag] = useState<{ polygon: number; vertex: number } | null>(null);
  const toPoint = (event: PointerEvent): Point | null => {
    const matrix = svg.current?.getScreenCTM();
    if (!svg.current || !matrix) return null;
    const p = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    return [clamp(p.x / W), clamp(p.y / H)];
  };
  const nudge = (event: KeyboardEvent, polygon: number, vertex: number) => {
    const step = event.shiftKey ? NUDGE * 4 : NUDGE;
    const delta = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[event.key];
    const point = polygons[polygon]?.points[vertex];
    if (!delta || !point) return;
    event.preventDefault();
    onMove(polygon, vertex, [clamp(point[0] + (delta[0] ?? 0)), clamp(point[1] + (delta[1] ?? 0))]);
  };
  return (
    <svg
      ref={svg}
      viewBox={`0 0 ${W} ${H}`}
      role="application"
      aria-label="Zone layout canvas. Select a shape, then drag its corners or move a focused corner with the arrow keys."
      className="aspect-video w-full touch-none select-none rounded-xl border border-line bg-[#1b2420]"
      onPointerMove={(e) => {
        if (!drag) return;
        const point = toPoint(e);
        if (point) onMove(drag.polygon, drag.vertex, point);
      }}
      onPointerUp={() => setDrag(null)}
      onPointerLeave={() => setDrag(null)}
      onPointerDown={(e) => {
        if (e.target === svg.current) onSelect(null);
      }}
    >
      {backdrop ? <image href={backdrop} x={0} y={0} width={W} height={H} preserveAspectRatio="none" opacity={0.85} /> : null}
      {Array.from({ length: 9 }, (_, i) => (
        <line key={`v${i}`} x1={((i + 1) * W) / 10} y1={0} x2={((i + 1) * W) / 10} y2={H} stroke="#ffffff" strokeOpacity={0.06} />
      ))}
      {Array.from({ length: 4 }, (_, i) => (
        <line key={`h${i}`} x1={0} y1={((i + 1) * H) / 5} x2={W} y2={((i + 1) * H) / 5} stroke="#ffffff" strokeOpacity={0.06} />
      ))}
      {polygons.map((polygon, index) => {
        const color = TYPE_COLOR[polygon.type];
        const zone = polygon.zone_id ? zones.get(polygon.zone_id) : undefined;
        const [cx_, cy_] = centroid(polygon.points);
        const active = index === selected;
        return (
          <g key={index}>
            <polygon
              points={polygon.points.map(([x, y]) => `${x * W},${y * H}`).join(" ")}
              fill={color}
              fillOpacity={active ? 0.35 : 0.2}
              stroke={color}
              strokeWidth={active ? 6 : 4}
              className={seatMode && active ? "cursor-crosshair" : "cursor-pointer"}
              onPointerDown={(e) => {
                e.stopPropagation();
                const point = seatMode && active ? toPoint(e) : null;
                if (point) onAddSeat(index, point);
                else onSelect(index);
              }}
            />
            <text x={cx_ * W} y={cy_ * H} textAnchor="middle" fill="#ffffff" fontSize={34} fontWeight={700} pointerEvents="none">
              {polygon.type === "seating" ? (zone ? `${zone.name} · ${zone.capacity}` : "Unlinked seating") : TYPE_LABEL[polygon.type]}
            </text>
            {(polygon.seats ?? []).map((seat, k) => (
              <circle
                key={seat.seat_id}
                cx={seat.x * W}
                cy={seat.y * H}
                r={12}
                fill="#ffffff"
                fillOpacity={0.9}
                stroke={color}
                strokeWidth={4}
                aria-label={`Seat ${seat.seat_id}`}
                className={seatMode && active ? "cursor-pointer" : undefined}
                pointerEvents={seatMode && active ? "all" : "none"}
                onPointerDown={(e) => {
                  e.stopPropagation();
                  onRemoveSeat(index, k);
                }}
              />
            ))}
            {active && !seatMode
              ? polygon.points.map(([x, y], vertex) => (
                  <circle
                    key={vertex}
                    cx={x * W}
                    cy={y * H}
                    r={16}
                    fill="#ffffff"
                    stroke={color}
                    strokeWidth={5}
                    tabIndex={0}
                    role="button"
                    aria-label={`Corner ${vertex + 1} at ${Math.round(x * 100)}%, ${Math.round(y * 100)}%`}
                    className="cursor-grab focus:outline-none"
                    onKeyDown={(e) => nudge(e, index, vertex)}
                    onPointerDown={(e) => {
                      e.stopPropagation();
                      (e.target as Element).setPointerCapture?.(e.pointerId);
                      setDrag({ polygon: index, vertex });
                    }}
                  />
                ))
              : null}
          </g>
        );
      })}
    </svg>
  );
}

function ShapeTools({
  polygon,
  zones,
  onChange,
  onDelete,
  seatMode,
  onSeatMode,
}: {
  polygon: LayoutPolygon;
  zones: EditableZone[];
  onChange: (next: LayoutPolygon) => void;
  onDelete: () => void;
  seatMode: boolean;
  onSeatMode: (on: boolean) => void;
}) {
  const points = polygon.points;
  return (
    <div className="flex flex-wrap items-end gap-3 rounded-xl bg-page p-3">
      <Field label="Shape type">
        <Select
          value={polygon.type}
          onChange={(e) => {
            const type = e.target.value as PolygonType;
            onChange({ ...polygon, type, zone_id: type === "seating" ? (polygon.zone_id ?? zones[0]?.id ?? null) : null });
          }}
        >
          {CAMPUS_TYPES.map((t) => (
            <option key={t} value={t}>
              {TYPE_LABEL[t]}
            </option>
          ))}
        </Select>
      </Field>
      {polygon.type === "seating" ? (
        <Field label="Seating zone">
          <Select value={polygon.zone_id ?? ""} onChange={(e) => onChange({ ...polygon, zone_id: e.target.value || null })}>
            <option value="">Choose a zone</option>
            {zones.map((z) => (
              <option key={z.id} value={z.id}>
                {z.name} ({z.capacity} seats)
              </option>
            ))}
          </Select>
        </Field>
      ) : null}
      {polygon.type === "seating" ? (
        <>
          <Button tone={seatMode ? "primary" : "secondary"} aria-pressed={seatMode} onClick={() => onSeatMode(!seatMode)}>
            {seatMode ? "Done placing seats" : "Place seats"}
          </Button>
          <span className="self-center text-xs text-muted">
            {(polygon.seats ?? []).length} seat(s){seatMode ? " · click a chair to add, click a seat to remove" : ""}
          </span>
          {(polygon.seats ?? []).length > 0 && !seatMode ? (
            <Button onClick={() => onChange({ ...polygon, seats: [] })}>Clear seats</Button>
          ) : null}
        </>
      ) : null}
      <Button
        disabled={points.length >= 32}
        onClick={() => {
          const [a, b] = [points[points.length - 1], points[0]];
          if (a && b) onChange({ ...polygon, points: [...points, [clamp((a[0] + b[0]) / 2), clamp((a[1] + b[1]) / 2)]] });
        }}
      >
        Add corner
      </Button>
      <Button disabled={points.length <= 3} onClick={() => onChange({ ...polygon, points: points.slice(0, -1) })}>
        Remove last corner
      </Button>
      <Button tone="danger" onClick={onDelete}>
        Delete shape
      </Button>
    </div>
  );
}

function ZoneList({ layout }: { layout: DeviceLayout }) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: queryKeys.deviceLayout(layout.device_id) });
  const update = useMutation({
    mutationFn: ({ id, name, capacity }: { id: string; name: string; capacity: number }) => api.updateZone(id, { name, capacity }),
    onSuccess: refresh,
  });
  const create = useMutation({
    mutationFn: (body: { name: string; capacity: number }) => api.createZone(layout.canteen_id, body),
    onSuccess: refresh,
  });
  const [edits, setEdits] = useState<Record<string, { name: string; capacity: string }>>({});
  const [fresh, setFresh] = useState({ name: "", capacity: "" });
  return (
    <Panel title={`Zones in ${layout.canteen_name}`}>
      <p className="m-0 text-xs text-muted">Names and capacities apply right away to every device that draws the zone.</p>
      {update.isError || create.isError ? <Banner tone="error">{errorText(update.error ?? create.error)}</Banner> : null}
      {layout.zones.map((zone) => {
        const edit = edits[zone.id] ?? { name: zone.name, capacity: String(zone.capacity) };
        const dirty = edit.name !== zone.name || edit.capacity !== String(zone.capacity);
        return (
          <div key={zone.id} className="flex flex-wrap items-center gap-2">
            <TextInput
              aria-label="Zone name"
              maxLength={60}
              className="min-w-40 flex-1"
              value={edit.name}
              onChange={(e) => setEdits({ ...edits, [zone.id]: { ...edit, name: e.target.value } })}
            />
            <TextInput
              aria-label={`Seats in ${zone.name}`}
              type="number"
              min={1}
              max={500}
              className="w-20"
              value={edit.capacity}
              onChange={(e) => setEdits({ ...edits, [zone.id]: { ...edit, capacity: e.target.value } })}
            />
            <span className="text-xs text-muted">seats</span>
            <Button
              className="min-h-9"
              disabled={!dirty || update.isPending}
              onClick={() =>
                update.mutate(
                  { id: zone.id, name: edit.name, capacity: Number(edit.capacity) },
                  {
                    onSuccess: () => setEdits((current) => Object.fromEntries(Object.entries(current).filter(([id]) => id !== zone.id))),
                  },
                )
              }
            >
              Save
            </Button>
          </div>
        );
      })}
      <form
        className="flex flex-wrap items-end gap-2 border-t border-line-soft pt-3"
        onSubmit={(e) => {
          e.preventDefault();
          create.mutate({ name: fresh.name, capacity: Number(fresh.capacity) }, { onSuccess: () => setFresh({ name: "", capacity: "" }) });
        }}
      >
        <Field label="New zone" className="min-w-40 flex-1">
          <TextInput required maxLength={60} value={fresh.name} onChange={(e) => setFresh({ ...fresh, name: e.target.value })} />
        </Field>
        <Field label="Seats">
          <TextInput
            required
            type="number"
            min={1}
            max={500}
            className="w-20"
            value={fresh.capacity}
            onChange={(e) => setFresh({ ...fresh, capacity: e.target.value })}
          />
        </Field>
        <Button type="submit" disabled={create.isPending}>
          Add zone
        </Button>
      </form>
    </Panel>
  );
}

function LayoutEditor({ layout }: { layout: DeviceLayout }) {
  const saved = useMemo(() => layout.polygons.map((p) => ({ ...p, zone_id: p.zone_id ?? null })), [layout]);
  const [polygons, setPolygons] = useState<LayoutPolygon[]>(saved);
  const [selected, setSelected] = useState<number | null>(null);
  const [backdrop, setBackdrop] = useState<string | null>(null);
  const [seatMode, setSeatMode] = useState(false);
  const now = useServerNow(30_000);
  const client = useQueryClient();
  const save = useLayoutMutation(layout.device_id, (body: { base_version: number | null; polygons: LayoutPolygon[] }) =>
    api.saveLayout(layout.device_id, body),
  );
  const rollback = useLayoutMutation(layout.device_id, (version: number) => api.rollbackLayout(layout.device_id, version));
  const zones = useMemo(() => new Map(layout.zones.map((z) => [z.id, z])), [layout.zones]);
  const dirty = JSON.stringify(polygons) !== JSON.stringify(saved);
  useUnsavedGuard(dirty);
  useEffect(() => {
    setPolygons(saved);
    setSelected(null);
  }, [saved]);
  useEffect(() => setSeatMode(false), [selected]);
  useEffect(() => () => (backdrop ? URL.revokeObjectURL(backdrop) : undefined), [backdrop]);

  const conflict = save.error instanceof ApiError && save.error.status === 409;
  const unlinked = polygons.some((p) => p.type === "seating" && !p.zone_id);
  const current = selected !== null ? polygons[selected] : undefined;
  const add = (type: PolygonType) => {
    const used = new Set(polygons.map((p) => p.zone_id));
    const zone = type === "seating" ? (layout.zones.find((z) => !used.has(z.id))?.id ?? null) : null;
    setPolygons([
      ...polygons,
      {
        type,
        zone_id: zone,
        points: [
          [0.35, 0.35],
          [0.65, 0.35],
          [0.65, 0.65],
          [0.35, 0.65],
        ],
      },
    ]);
    setSelected(polygons.length);
  };

  return (
    <>
      <Panel
        title={`${layout.device_id} · ${layout.version ? `version ${layout.version}` : "no layout yet"}`}
        aside={
          <div className="flex flex-wrap items-center gap-2">
            {dirty ? <span className="text-xs font-semibold text-busy">Unsaved changes</span> : null}
            <Button disabled={!dirty || save.isPending} onClick={() => setPolygons(saved)}>
              Reset
            </Button>
            <Button
              tone="primary"
              disabled={!dirty || unlinked || save.isPending}
              onClick={() => save.mutate({ base_version: layout.version, polygons })}
            >
              {save.isPending ? "Saving…" : "Save as new version"}
            </Button>
          </div>
        }
      >
        {conflict ? (
          <Banner tone="error">
            {errorText(save.error)}{" "}
            <button
              type="button"
              className="border-0 bg-transparent p-0 font-bold text-crowd underline"
              onClick={() => {
                save.reset();
                void client.invalidateQueries({ queryKey: queryKeys.deviceLayout(layout.device_id) });
              }}
            >
              Reload layout
            </button>
          </Banner>
        ) : save.isError ? (
          <Banner tone="error">{errorText(save.error)}</Banner>
        ) : null}
        {unlinked ? <Banner tone="error">Link every seating shape to a zone before saving.</Banner> : null}
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => add("seating")}>+ Seating</Button>
          <Button onClick={() => add("queue")}>+ Queue</Button>
          <Button onClick={() => add("walkway")}>+ Walkway</Button>
          <Button onClick={() => add("ignore")}>+ Ignore</Button>
          <label className="ml-auto inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-[10px] border border-line bg-card px-3.5 text-sm font-bold hover:bg-page">
            Backdrop image
            <input
              type="file"
              accept="image/*"
              className="sr-only"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) setBackdrop(URL.createObjectURL(file));
              }}
            />
          </label>
          {backdrop ? <Button onClick={() => setBackdrop(null)}>Clear backdrop</Button> : null}
        </div>
        <p className="m-0 text-xs text-muted">
          The backdrop stays in this browser and is never uploaded. Frames are never stored. The worker picks up a saved version within 30
          s.
        </p>
        <Canvas
          polygons={polygons}
          zones={zones}
          selected={selected}
          onSelect={setSelected}
          backdrop={backdrop}
          onMove={(polygon, vertex, point) =>
            setPolygons((all) =>
              all.map((p, i) => (i === polygon ? { ...p, points: p.points.map((pt, j) => (j === vertex ? point : pt)) } : p)),
            )
          }
          seatMode={seatMode}
          onAddSeat={(polygon, [x, y]) =>
            setPolygons((all) =>
              all.map((p, i) => (i === polygon ? { ...p, seats: [...(p.seats ?? []), { seat_id: nextSeatId(all), x, y }] } : p)),
            )
          }
          onRemoveSeat={(polygon, seat) =>
            setPolygons((all) => all.map((p, i) => (i === polygon ? { ...p, seats: (p.seats ?? []).filter((_, k) => k !== seat) } : p)))
          }
        />
        {current && selected !== null ? (
          <ShapeTools
            polygon={current}
            zones={layout.zones}
            onChange={(next) => setPolygons(polygons.map((p, i) => (i === selected ? next : p)))}
            onDelete={() => {
              setPolygons(polygons.filter((_, i) => i !== selected));
              setSelected(null);
            }}
            seatMode={seatMode}
            onSeatMode={setSeatMode}
          />
        ) : (
          <span className="text-xs text-muted">Select a shape to move its corners, change its type, link it to a zone or place seats.</span>
        )}
      </Panel>
      <div className="flex flex-wrap gap-5">
        <div className="flex min-w-[320px] flex-[2_1_420px] flex-col">
          <ZoneList layout={layout} />
        </div>
        <Panel title="Version history" className="min-w-[280px] flex-[1_1_280px]">
          {rollback.isError ? <Banner tone="error">{errorText(rollback.error)}</Banner> : null}
          {layout.history.length === 0 ? <span className="text-sm text-muted">No versions yet.</span> : null}
          <ol className="m-0 flex list-none flex-col gap-2 p-0">
            {layout.history.map((h) => (
              <li
                key={h.version}
                className={cx("flex items-center justify-between gap-2 rounded-lg px-3 py-2", h.is_current ? "bg-ok-bg" : "bg-page")}
              >
                <span className="flex flex-col">
                  <span className="text-sm font-bold">
                    v{h.version}
                    {h.is_current ? " · current" : ""}
                  </span>
                  <span className="text-xs text-muted">
                    {formatClock(h.created_at)} · {formatAgo(h.created_at, now)} · {h.seating_zones} seating
                  </span>
                </span>
                {!h.is_current ? (
                  <Button
                    className="min-h-9"
                    disabled={rollback.isPending}
                    onClick={() => {
                      if (dirty && !window.confirm("Discard your unsaved layout changes and roll back?")) return;
                      rollback.mutate(h.version);
                    }}
                  >
                    Roll back
                  </Button>
                ) : null}
              </li>
            ))}
          </ol>
          <p className="m-0 text-xs text-muted">Rolling back saves a copy of that version as a new version.</p>
        </Panel>
      </div>
    </>
  );
}

export function ZonesScreen() {
  const devices = useManagedDevices();
  const items = devices.data?.items ?? [];
  const [picked, setPicked] = useState<string | undefined>();
  const deviceId = picked ?? items[0]?.id;
  const layout = useDeviceLayout(deviceId);
  return (
    <Page title="Zones" sub="Draw seating zones per camera or simulator. Each save is a new version you can roll back.">
      {apiMode() === "sample" ? (
        <Banner>Editing zones needs the real API. Start it with pnpm stack:up, then pnpm dev:console:api.</Banner>
      ) : null}
      {devices.isError && apiMode() === "api" ? <Banner tone="error">{errorText(devices.error)}</Banner> : null}
      {items.length > 0 ? (
        <nav aria-label="Devices" className="flex flex-wrap gap-2">
          {items.map((d) => (
            <button
              key={d.id}
              type="button"
              aria-current={d.id === deviceId ? "page" : undefined}
              onClick={() => setPicked(d.id)}
              className={cx(
                "inline-flex min-h-10 items-center gap-2 rounded-[10px] border px-3 text-sm font-semibold",
                d.id === deviceId ? "border-brand bg-brand text-white" : "border-line bg-card text-ink hover:bg-page",
              )}
            >
              {d.id}
              <span className="text-xs opacity-80">
                {d.canteen_name} · {d.kind}
                {d.layout_version ? ` · v${d.layout_version}` : ""}
              </span>
            </button>
          ))}
        </nav>
      ) : null}
      {layout.isError ? <Banner tone="error">{errorText(layout.error)}</Banner> : null}
      {layout.data ? (
        <LayoutEditor key={layout.data.device_id} layout={layout.data} />
      ) : layout.isPending && deviceId ? (
        <div aria-busy="true" className="aspect-video w-full rounded-[20px] bg-line-soft motion-safe:animate-pulse" />
      ) : null}
    </Page>
  );
}

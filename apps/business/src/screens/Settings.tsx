import {
  useBusinessSettings,
  useSaveBusinessSettings,
  useSaveTables,
  useTableLayout,
  type StaffUser,
  type TableIn,
  type TableLayout,
  type TableShape,
} from "@dinemate/api-client";
import { cx } from "@dinemate/ui";
import { useEffect, useMemo, useState } from "react";
import { Banner, Button, errorText, Field, Page, Panel, Select, Skeleton, TextInput } from "../kit";
import { useVenue } from "../venue";

type Draft = TableIn & { key: string };

const PERCENT = (v: number) => Math.round(v * 100);

function toDrafts(layout: TableLayout): Draft[] {
  return layout.tables.map((t) => ({ ...t, key: t.id }));
}

function nextName(drafts: Draft[]): string {
  const taken = new Set(drafts.map((d) => d.name));
  let n = drafts.length + 1;
  while (taken.has(`T${n}`)) n++;
  return `T${n}`;
}

function TableRow({
  draft,
  zones,
  usedElsewhere,
  onChange,
  onRemove,
}: {
  draft: Draft;
  zones: TableLayout["zones"];
  usedElsewhere: Set<string>;
  onChange: (next: Draft) => void;
  onRemove: () => void;
}) {
  const zone = zones.find((z) => z.zone_id === draft.zone_id);
  const box = (key: "x" | "y" | "w" | "h", label: string) => (
    <Field label={label} className="w-[72px]">
      <TextInput
        type="number"
        min={key === "w" || key === "h" ? 1 : 0}
        max={100}
        value={PERCENT(draft[key])}
        onChange={(e) => onChange({ ...draft, [key]: Math.min(100, Math.max(0, Number(e.target.value))) / 100 })}
      />
    </Field>
  );
  return (
    <li className="flex flex-col gap-3 border-t border-line-soft py-4 first:border-t-0">
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Name" className="w-[90px]">
          <TextInput value={draft.name} maxLength={12} onChange={(e) => onChange({ ...draft, name: e.target.value })} />
        </Field>
        <Field label="Zone" className="w-[150px]">
          <Select value={draft.zone_id} onChange={(e) => onChange({ ...draft, zone_id: e.target.value, seat_ids: [] })}>
            {zones.map((z) => (
              <option key={z.zone_id} value={z.zone_id}>
                {z.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Shape" className="w-[110px]">
          <Select value={draft.shape} onChange={(e) => onChange({ ...draft, shape: e.target.value as TableShape })}>
            <option value="rect">Rectangle</option>
            <option value="round">Round</option>
          </Select>
        </Field>
        {box("x", "Left %")}
        {box("y", "Top %")}
        {box("w", "Width %")}
        {box("h", "Height %")}
        <Button className="ml-auto" onClick={onRemove}>
          Remove<span className="sr-only"> {draft.name}</span>
        </Button>
      </div>
      <fieldset className="m-0 flex flex-wrap gap-2 border-0 p-0">
        <legend className="mb-1.5 text-[13px] font-semibold text-ink-2">Seats from the camera layout</legend>
        {(zone?.seats ?? []).map((seat) => {
          const checked = draft.seat_ids.includes(seat.seat_id);
          const taken = usedElsewhere.has(seat.seat_id);
          return (
            <label
              key={seat.seat_id}
              className={cx(
                "inline-flex min-h-9 items-center gap-1.5 rounded-full border px-3 text-[13px] font-semibold",
                checked ? "border-brand bg-brand text-on-dark" : "border-line bg-card text-ink-2",
                taken && !checked && "opacity-50",
              )}
            >
              <input
                type="checkbox"
                className="sr-only"
                checked={checked}
                disabled={taken && !checked}
                onChange={() =>
                  onChange({
                    ...draft,
                    seat_ids: checked ? draft.seat_ids.filter((s) => s !== seat.seat_id) : [...draft.seat_ids, seat.seat_id],
                  })
                }
              />
              {seat.seat_id}
            </label>
          );
        })}
      </fieldset>
    </li>
  );
}

function TablesEditor({ venueId }: { venueId: string }) {
  const layout = useTableLayout(venueId);
  const save = useSaveTables(venueId);
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  useEffect(() => {
    if (layout.data) setDrafts(toDrafts(layout.data));
  }, [layout.data]);
  const seatOwner = useMemo(() => {
    const owner = new Map<string, string>();
    for (const d of drafts ?? []) for (const s of d.seat_ids) owner.set(`${d.zone_id}:${s}`, d.key);
    return owner;
  }, [drafts]);
  if (!layout.data || !drafts) return <Skeleton className="h-[240px]" />;
  const zones = layout.data.zones;
  const update = (key: string, next: Draft) => setDrafts(drafts.map((d) => (d.key === key ? next : d)));
  const add = () => {
    const zone = zones[0];
    if (!zone) return;
    setDrafts([
      ...drafts,
      {
        key: `new-${Date.now()}`,
        id: null,
        name: nextName(drafts),
        zone_id: zone.zone_id,
        shape: "rect",
        x: 0.1,
        y: 0.1,
        w: 0.15,
        h: 0.15,
        seat_ids: [],
      },
    ]);
  };
  const submit = () =>
    save.mutate(
      drafts.map((d) => ({
        id: d.id ?? null,
        name: d.name.trim(),
        zone_id: d.zone_id,
        shape: d.shape,
        x: d.x,
        y: d.y,
        w: d.w,
        h: d.h,
        seat_ids: d.seat_ids,
      })),
    );
  return (
    <Panel
      title="Tables"
      aside={<span className="text-[13px] text-muted">Group camera seats into tables and place them on the floor map</span>}
    >
      {save.isError ? <Banner tone="error">{errorText(save.error)}</Banner> : null}
      {save.isSuccess ? <Banner tone="ok">Tables saved. The live floor uses them straight away.</Banner> : null}
      <ul className="m-0 list-none p-0">
        {drafts.map((d) => (
          <TableRow
            key={d.key}
            draft={d}
            zones={zones}
            usedElsewhere={
              new Set(
                d.zone_id
                  ? Array.from(seatOwner.entries())
                      .filter(([k, owner]) => k.startsWith(`${d.zone_id}:`) && owner !== d.key)
                      .map(([k]) => k.split(":")[1] ?? "")
                  : [],
              )
            }
            onChange={(next) => update(d.key, next)}
            onRemove={() => setDrafts(drafts.filter((x) => x.key !== d.key))}
          />
        ))}
      </ul>
      <div className="flex flex-wrap gap-2.5">
        <Button onClick={add}>Add table</Button>
        <Button tone="primary" disabled={save.isPending || drafts.some((d) => d.seat_ids.length === 0 || !d.name.trim())} onClick={submit}>
          {save.isPending ? "Saving…" : "Save tables"}
        </Button>
      </div>
    </Panel>
  );
}

function Retention({ user }: { user: StaffUser }) {
  const settings = useBusinessSettings();
  const save = useSaveBusinessSettings();
  const [days, setDays] = useState<number | null>(null);
  const current = days ?? settings.data?.retention_days ?? 90;
  const owner = user.role === "owner";
  return (
    <Panel title="Data kept" aside={<span className="text-[13px] text-muted">{settings.data?.organization_name}</span>}>
      {save.isError ? <Banner tone="error">{errorText(save.error)}</Banner> : null}
      {save.isSuccess ? <Banner tone="ok">Saved. Older visits are deleted automatically.</Banner> : null}
      <ul className="m-0 flex list-none flex-col gap-2 p-0 text-sm">
        <li className="flex justify-between gap-3">
          <span className="font-semibold">Video and photos</span>
          <span className="text-muted">Never stored</span>
        </li>
        <li className="flex justify-between gap-3">
          <span className="font-semibold">Customer identities</span>
          <span className="text-muted">Never recorded</span>
        </li>
      </ul>
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Keep anonymous visits for (days)" hint="Between 7 and 730 days" className="w-[240px]">
          <TextInput type="number" min={7} max={730} value={current} disabled={!owner} onChange={(e) => setDays(Number(e.target.value))} />
        </Field>
        {owner ? (
          <Button
            tone="primary"
            disabled={save.isPending || current < 7 || current > 730}
            onClick={() => save.mutate({ retention_days: current })}
          >
            Save
          </Button>
        ) : (
          <span className="text-[13px] text-muted">Only the owner can change this.</span>
        )}
      </div>
    </Panel>
  );
}

export function SettingsScreen({ user }: { user: StaffUser }) {
  const { venue } = useVenue();
  return (
    <Page title="Settings" sub={venue?.name}>
      {venue ? <TablesEditor venueId={venue.id} /> : null}
      <Retention user={user} />
    </Page>
  );
}

import { apiMode, useSaveThresholds, useThresholds, type AlertFrom, type ThresholdValues, type ZoneThresholds } from "@dinemate/api-client";
import { useState } from "react";
import { Banner, Button, errorText, Page, Panel, Select, TextInput, useUnsavedGuard } from "../kit";

const ALERT_FROM: { value: AlertFrom; label: string }[] = [
  { value: "busy", label: "Busy" },
  { value: "crowded", label: "Crowded" },
  { value: "near_capacity", label: "Near capacity" },
];

const NUMBER_FIELDS: { key: keyof Omit<ThresholdValues, "alert_from">; label: string; suffix: string; step: number }[] = [
  { key: "busy_pct", label: "Busy from", suffix: "%", step: 1 },
  { key: "crowded_pct", label: "Crowded from", suffix: "%", step: 1 },
  { key: "near_capacity_pct", label: "Near capacity from", suffix: "%", step: 1 },
  { key: "hysteresis_pct", label: "Hysteresis", suffix: "pts", step: 0.5 },
  { key: "dwell_seconds", label: "Dwell", suffix: "s", step: 15 },
];

function ZoneRow({ zone, defaults }: { zone: ZoneThresholds; defaults: ThresholdValues }) {
  const [values, setValues] = useState(zone.values);
  const save = useSaveThresholds();
  const dirty = JSON.stringify(values) !== JSON.stringify(zone.values);
  useUnsavedGuard(dirty);
  return (
    <tr className="border-b border-line-soft align-top">
      <td className="min-w-44 py-3 pr-2">
        <span className="block text-sm font-bold">{zone.zone_name}</span>
        <span className="text-xs text-muted">
          {zone.canteen_name} · {zone.capacity} seats{zone.is_monitored ? " · monitored" : ""}
        </span>
        {zone.is_default && !dirty ? <span className="block text-xs font-semibold text-muted">Using defaults</span> : null}
      </td>
      {NUMBER_FIELDS.map((f) => (
        <td key={f.key} className="px-1.5 py-3">
          <span className="inline-flex items-center gap-1">
            <TextInput
              type="number"
              aria-label={`${f.label} for ${zone.zone_name}`}
              step={f.step}
              className="w-[72px] tabular-nums"
              value={values[f.key]}
              onChange={(e) => setValues({ ...values, [f.key]: Number(e.target.value) })}
            />
            <span className="text-xs text-muted">{f.suffix}</span>
          </span>
        </td>
      ))}
      <td className="px-1.5 py-3">
        <Select
          aria-label={`Alert level for ${zone.zone_name}`}
          value={values.alert_from}
          onChange={(e) => setValues({ ...values, alert_from: e.target.value as AlertFrom })}
        >
          {ALERT_FROM.map((a) => (
            <option key={a.value} value={a.value}>
              {a.label}
            </option>
          ))}
        </Select>
      </td>
      <td className="py-3 pl-1.5">
        <span className="flex flex-col items-end gap-1">
          <span className="flex gap-1.5">
            <Button className="min-h-9" disabled={save.isPending} onClick={() => setValues(defaults)}>
              Defaults
            </Button>
            <Button
              tone="primary"
              className="min-h-9"
              disabled={!dirty || save.isPending}
              onClick={() => save.mutate({ zoneId: zone.zone_id, values }, { onSuccess: ({ item }) => setValues(item.values) })}
            >
              Save
            </Button>
          </span>
          {save.isError ? <span className="max-w-56 text-right text-xs font-semibold text-crowd">{errorText(save.error)}</span> : null}
        </span>
      </td>
    </tr>
  );
}

export function ThresholdsScreen() {
  const thresholds = useThresholds();
  const data = thresholds.data;
  return (
    <Page title="Thresholds & config" sub="Crowding levels per zone. Changes apply on the next rules run (about 15 s).">
      {apiMode() === "sample" ? (
        <Banner>Editing thresholds needs the real API. Start it with pnpm stack:up, then pnpm dev:console:api.</Banner>
      ) : null}
      {thresholds.isError && apiMode() === "api" ? <Banner tone="error">{errorText(thresholds.error)}</Banner> : null}
      {data ? (
        <Panel
          title="Crowding thresholds"
          aside={
            <span className="text-xs text-muted">
              Defaults {data.defaults.busy_pct}/{data.defaults.crowded_pct}/{data.defaults.near_capacity_pct}% ·{" "}
              {data.defaults.hysteresis_pct} pts · {data.defaults.dwell_seconds} s
            </span>
          }
        >
          <p className="m-0 text-xs text-muted">
            A level starts after the load stays above it for the dwell time, and ends when it falls below the level minus the hysteresis.
            Alerts open at the chosen level.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-sm">
              <thead>
                <tr className="text-left text-xs text-muted">
                  {["Zone", ...NUMBER_FIELDS.map((f) => f.label), "Alert from", ""].map((h, i) => (
                    <th key={i} scope="col" className="border-b border-chip px-1.5 pb-2 font-semibold first:pl-0">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.items.map((zone) => (
                  <ZoneRow key={zone.zone_id} zone={zone} defaults={data.defaults} />
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      ) : null}
    </Page>
  );
}

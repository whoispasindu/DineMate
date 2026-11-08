import {
  api,
  apiMode,
  useCanteens,
  useSafetyAction,
  useSafetyEvents,
  useSafetySources,
  useServerNow,
  type SafetySourceHealth,
  type StaffSafetyEvent,
} from "@dinemate/api-client";
import { cx, formatAgo, formatClock, HazardFrame, Icon, SimulationLabel } from "@dinemate/ui";
import { useState } from "react";
import { Banner, Button, errorText, Field, Page, Panel, Select, TextInput } from "../kit";

const SEVERITY_STYLE = {
  critical: "bg-crowd-bg text-crowd",
  warning: "bg-busy-bg text-busy",
  info: "bg-neutral text-neutral-ink",
} as const;

const STATUS_LABEL = { active: "Unacknowledged", acknowledged: "Acknowledged", resolved: "Resolved" } as const;

const SOURCE_STATE = {
  online: { label: "Online", className: "bg-ok-bg text-ok" },
  offline: { label: "Offline", className: "bg-crowd-bg text-crowd" },
  never_connected: { label: "Never connected", className: "bg-neutral text-neutral-ink" },
} as const;

const SIM_TYPES = [
  { value: "fire_alarm", label: "Fire alarm" },
  { value: "evacuation", label: "Evacuation notice" },
  { value: "test_notice", label: "Test notice" },
];

function Chip({ className, children }: { className: string; children: string }) {
  return <span className={cx("rounded-full px-2.5 py-1 text-xs font-bold", className)}>{children}</span>;
}

function EventActions({ event }: { event: StaffSafetyEvent }) {
  const [ackNote, setAckNote] = useState("");
  const [resolveNote, setResolveNote] = useState("");
  const acknowledge = useSafetyAction((note: string) => api.acknowledgeSafety(event.id, note.trim() || null));
  const resolve = useSafetyAction((note: string) => api.resolveSafety(event.id, note.trim()));
  const error = acknowledge.error ?? resolve.error;
  return (
    <div className="flex flex-col gap-2.5 border-t border-line-soft pt-3">
      {error ? <Banner tone="error">{errorText(error)}</Banner> : null}
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Acknowledge note (optional)" className="min-w-48 flex-1">
          <TextInput maxLength={500} value={ackNote} onChange={(e) => setAckNote(e.target.value)} placeholder="e.g. Seen by safety desk" />
        </Field>
        <Button
          tone={event.status === "active" ? "primary" : "secondary"}
          disabled={acknowledge.isPending}
          onClick={() => acknowledge.mutate(ackNote, { onSuccess: () => setAckNote("") })}
        >
          {event.status === "active" ? "Acknowledge" : "Add acknowledgement"}
        </Button>
      </div>
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Resolution note (required)" className="min-w-48 flex-1">
          <TextInput
            maxLength={500}
            value={resolveNote}
            onChange={(e) => setResolveNote(e.target.value)}
            placeholder="What happened and who confirmed it"
          />
        </Field>
        <Button tone="danger" disabled={resolve.isPending || resolveNote.trim().length < 3} onClick={() => resolve.mutate(resolveNote)}>
          Resolve
        </Button>
      </div>
    </div>
  );
}

function EventCard({ event, now }: { event: StaffSafetyEvent; now: number }) {
  const body = (
    <div className="flex flex-col gap-2.5">
      {event.is_simulation ? <SimulationLabel /> : null}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-lg font-bold">{event.title}</span>
        <Chip className={SEVERITY_STYLE[event.severity]}>{event.severity}</Chip>
        <Chip className={event.status === "active" ? "bg-crowd-mark text-white" : "bg-neutral text-neutral-ink"}>
          {STATUS_LABEL[event.status]}
        </Chip>
        {event.repeat_count > 1 ? <Chip className="bg-neutral text-neutral-ink">{`×${event.repeat_count} repeats`}</Chip> : null}
      </div>
      <span className="text-sm text-ink-2">
        {[event.canteen_name ?? "Campus-wide", event.zone_name].filter(Boolean).join(" · ")} · received {formatClock(event.received_at)} (
        {formatAgo(event.received_at, now)}) · {event.source_name}
        {event.source_kind === "simulator" ? " (simulator)" : ""}
      </span>
      {event.note ? <span className="text-sm text-muted">Note: {event.note}</span> : null}
      <span className="text-sm text-muted">
        {event.severity === "warning" ? "Staff only — not shown to students." : `Students see: ${event.instructions}`}
      </span>
      {event.acks.length > 0 ? (
        <ul className="m-0 flex list-none flex-col gap-1 p-0 text-xs text-muted">
          {event.acks.map((a, i) => (
            <li key={i}>
              Acknowledged by {a.user_name} at {formatClock(a.acknowledged_at)}
              {a.note ? ` — ${a.note}` : ""}
            </li>
          ))}
        </ul>
      ) : null}
      {event.status !== "resolved" ? <EventActions event={event} /> : null}
    </div>
  );
  return event.is_simulation ? (
    <HazardFrame innerClassName="p-4">{body}</HazardFrame>
  ) : (
    <section className="rounded-2xl border-2 border-crowd-mark bg-danger-surface p-4">{body}</section>
  );
}

function SimulatorPanel() {
  const canteens = useCanteens();
  const [type, setType] = useState("fire_alarm");
  const [canteen, setCanteen] = useState("");
  const [note, setNote] = useState("");
  const simulate = useSafetyAction(() => api.simulateSafety({ event_type: type, canteen_id: canteen || null, note: note.trim() || null }));
  return (
    <Panel title="Simulator" aside={<SimulationLabel />}>
      <p className="m-0 text-xs text-muted">
        Simulated events are always labelled on every screen. Run them only on your own devices and the demo screen.
      </p>
      {simulate.isError ? <Banner tone="error">{errorText(simulate.error)}</Banner> : null}
      {simulate.isSuccess ? <Banner tone="ok">Simulated event sent. Students see it on their next 10 s check.</Banner> : null}
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Event">
          <Select value={type} onChange={(e) => setType(e.target.value)}>
            {SIM_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Location">
          <Select value={canteen} onChange={(e) => setCanteen(e.target.value)}>
            <option value="">Campus-wide</option>
            {(canteens.data?.items ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Note for the log" className="min-w-48 flex-1">
          <TextInput maxLength={500} value={note} placeholder="e.g. Judging demo run 1" onChange={(e) => setNote(e.target.value)} />
        </Field>
        <Button tone="danger" disabled={simulate.isPending} onClick={() => simulate.mutate(undefined)}>
          <Icon name="flame" size={16} />
          Trigger simulation
        </Button>
      </div>
    </Panel>
  );
}

function SourceList({ sources, now }: { sources: SafetySourceHealth[]; now: number }) {
  return (
    <ul className="m-0 flex list-none flex-col gap-2 p-0">
      {sources.map((s) => (
        <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-page px-3 py-2">
          <span className="flex flex-col">
            <span className="text-sm font-bold">{s.name}</span>
            <span className="text-xs text-muted">
              {s.kind === "simulator" ? "Simulator" : "Approved integration"} · {s.id}
              {s.last_heartbeat_at ? ` · last heartbeat ${formatAgo(s.last_heartbeat_at, now)}` : ""}
              {s.is_enabled ? "" : " · disabled"}
            </span>
          </span>
          <Chip className={SOURCE_STATE[s.state].className}>{SOURCE_STATE[s.state].label}</Chip>
        </li>
      ))}
    </ul>
  );
}

export function SafetyScreen() {
  const open = useSafetyEvents("open");
  const resolved = useSafetyEvents("resolved");
  const sources = useSafetySources();
  const now = useServerNow(5_000);
  const sample = apiMode() === "sample";
  const items = open.data?.items ?? [];
  const lost = open.isError && !sample;
  return (
    <Page
      title="Safety"
      sub="Separate from crowding alerts. DineMate mirrors approved alarms; it is not a life-safety system."
      actions={open.data?.simulation_mode ? <SimulationLabel>SIMULATION MODE ON</SimulationLabel> : null}
    >
      {sample ? <Banner>The safety desk needs the real API. Start it with pnpm stack:up, then pnpm dev:console:api.</Banner> : null}
      {lost ? (
        <div
          role="alert"
          className="rounded-2xl border-2 border-dashed border-crowd-mark bg-danger-surface p-4 text-sm font-bold text-crowd"
        >
          Connection to the safety service lost — status unknown. Follow official alarms and staff instructions. Retrying every 5 s.
        </div>
      ) : null}
      {open.data?.simulation_mode ? <SimulatorPanel /> : null}
      <Panel
        title={`Open events (${items.length})`}
        aside={<span className="text-xs text-muted">Unacknowledged first · refreshes every 5 s</span>}
      >
        {open.data && items.length === 0 ? <span className="text-sm text-muted">No open safety events.</span> : null}
        {items.map((event) => (
          <EventCard key={event.id} event={event} now={now} />
        ))}
      </Panel>
      <div className="flex flex-wrap gap-5">
        <Panel title="Sources" className="min-w-[300px] flex-[1_1_320px]">
          {sources.data ? <SourceList sources={sources.data.items} now={now} /> : null}
          <p className="m-0 text-xs text-muted">
            A source that misses heartbeats for 60 s raises an "Alarm integration offline" warning here. Students never see it.
          </p>
        </Panel>
        <Panel title="Resolved in the last 7 days" className="min-w-[300px] flex-[2_1_420px]">
          {resolved.data && resolved.data.items.length === 0 ? (
            <span className="text-sm text-muted">Nothing resolved recently.</span>
          ) : null}
          <ol className="m-0 flex list-none flex-col gap-2 p-0">
            {(resolved.data?.items ?? []).map((e) => (
              <li key={e.id} className="flex flex-col gap-0.5 rounded-lg bg-page px-3 py-2 text-xs text-muted">
                <span className="text-sm font-bold text-ink">
                  {e.label ? "[SIMULATION] " : ""}
                  {e.title}
                  {e.canteen_name ? ` · ${e.canteen_name}` : ""}
                </span>
                <span>
                  Received {formatClock(e.received_at)} · {e.acks.length} acknowledgement{e.acks.length === 1 ? "" : "s"} · resolved by{" "}
                  {e.resolved_by_name ?? "—"}
                  {e.resolved_at ? ` at ${formatClock(e.resolved_at)}` : ""}
                </span>
                {e.resolution_note ? <span>“{e.resolution_note}”</span> : null}
              </li>
            ))}
          </ol>
        </Panel>
      </div>
    </Page>
  );
}

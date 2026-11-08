import { api, useShopMutation, type HoursException, type ShopEditor, type WeeklyHours } from "@dinemate/api-client";
import { useEffect, useMemo, useState } from "react";
import { Banner, Button, errorText, Panel, TextInput, useUnsavedGuard } from "../kit";

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

const hm = (value: string | null) => (value ?? "").slice(0, 5);

const campusDate = (iso: string) => new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Colombo" }).format(Date.parse(iso));

interface Draft {
  weekly: WeeklyHours[];
  exceptions: HoursException[];
}

function fromEditor(editor: ShopEditor): Draft {
  return {
    weekly: editor.weekly.map((w) => ({ ...w, opens: hm(w.opens), closes: hm(w.closes) })),
    exceptions: editor.exceptions.map((e) => ({ ...e, opens: e.opens && hm(e.opens), closes: e.closes && hm(e.closes) })),
  };
}

export function HoursPanel({ editor, onDirty }: { editor: ShopEditor; onDirty: (dirty: boolean) => void }) {
  const saved = useMemo(() => fromEditor(editor), [editor]);
  const [draft, setDraft] = useState<Draft>(saved);
  const dirty = JSON.stringify(draft) !== JSON.stringify(saved);
  const save = useShopMutation(editor.shop.id, (body: Draft) => api.saveShopHours(editor.shop.id, body));

  useEffect(() => setDraft(saved), [saved]);
  useEffect(() => onDirty(dirty), [dirty, onDirty]);
  useUnsavedGuard(dirty);

  const setSlot = (index: number, patch: Partial<WeeklyHours>) =>
    setDraft((d) => ({ ...d, weekly: d.weekly.map((w, i) => (i === index ? { ...w, ...patch } : w)) }));
  const setException = (index: number, patch: Partial<HoursException>) =>
    setDraft((d) => ({ ...d, exceptions: d.exceptions.map((e, i) => (i === index ? { ...e, ...patch } : e)) }));

  return (
    <Panel
      title="Opening hours"
      aside={
        <div className="flex items-center gap-2">
          {dirty ? <span className="text-xs font-semibold text-busy">Unsaved changes</span> : null}
          <Button disabled={!dirty || save.isPending} onClick={() => setDraft(saved)}>
            Reset
          </Button>
          <Button tone="primary" disabled={!dirty || save.isPending} onClick={() => save.mutate(draft)}>
            {save.isPending ? "Saving…" : "Save hours"}
          </Button>
        </div>
      }
    >
      {save.isError ? <Banner tone="error">{errorText(save.error)}</Banner> : null}
      <p className="m-0 text-xs text-muted">Times are Asia/Colombo. Hours save straight away; students see them on their next refresh.</p>
      <div className="flex flex-col divide-y divide-line-soft">
        {WEEKDAYS.map((label, weekday) => {
          const slots = draft.weekly.map((w, i) => ({ w, i })).filter(({ w }) => w.weekday === weekday);
          return (
            <div key={label} className="flex flex-wrap items-center gap-3 py-2.5">
              <span className="w-28 text-sm font-bold">{label}</span>
              {slots.length === 0 ? <span className="text-sm text-muted">Closed</span> : null}
              {slots.map(({ w, i }) => (
                <span key={i} className="inline-flex items-center gap-1.5">
                  <TextInput
                    type="time"
                    aria-label={`${label} opens`}
                    value={w.opens}
                    onChange={(e) => setSlot(i, { opens: e.target.value })}
                  />
                  <span className="text-muted">–</span>
                  <TextInput
                    type="time"
                    aria-label={`${label} closes`}
                    value={w.closes}
                    onChange={(e) => setSlot(i, { closes: e.target.value })}
                  />
                  <Button
                    aria-label={`Remove ${label} interval`}
                    className="min-h-9 px-2.5"
                    onClick={() => setDraft((d) => ({ ...d, weekly: d.weekly.filter((_, j) => j !== i) }))}
                  >
                    ×
                  </Button>
                </span>
              ))}
              <Button
                className="min-h-9"
                onClick={() => setDraft((d) => ({ ...d, weekly: [...d.weekly, { weekday, opens: "07:00", closes: "15:00" }] }))}
              >
                + Interval
              </Button>
            </div>
          );
        })}
      </div>

      <h3 className="m-0 mt-2 font-display text-base font-semibold">Exceptions (holidays and special hours)</h3>
      {draft.exceptions.length === 0 ? <span className="text-sm text-muted">No exceptions.</span> : null}
      {draft.exceptions.map((e, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2.5">
          <TextInput type="date" aria-label="Exception date" value={e.date} onChange={(ev) => setException(i, { date: ev.target.value })} />
          <label className="inline-flex items-center gap-1.5 text-sm font-semibold">
            <input
              type="checkbox"
              checked={e.is_closed}
              onChange={(ev) =>
                setException(
                  i,
                  ev.target.checked
                    ? { is_closed: true, opens: null, closes: null }
                    : { is_closed: false, opens: "08:00", closes: "14:00" },
                )
              }
            />
            Closed all day
          </label>
          {!e.is_closed ? (
            <>
              <TextInput
                type="time"
                aria-label="Special opening"
                value={e.opens ?? ""}
                onChange={(ev) => setException(i, { opens: ev.target.value })}
              />
              <span className="text-muted">–</span>
              <TextInput
                type="time"
                aria-label="Special closing"
                value={e.closes ?? ""}
                onChange={(ev) => setException(i, { closes: ev.target.value })}
              />
            </>
          ) : null}
          <TextInput
            aria-label="Reason"
            placeholder="Reason (optional)"
            maxLength={120}
            value={e.reason ?? ""}
            onChange={(ev) => setException(i, { reason: ev.target.value || null })}
          />
          <Button
            aria-label="Remove exception"
            className="min-h-9 px-2.5"
            onClick={() => setDraft((d) => ({ ...d, exceptions: d.exceptions.filter((_, j) => j !== i) }))}
          >
            ×
          </Button>
        </div>
      ))}
      <div>
        <Button
          onClick={() =>
            setDraft((d) => ({
              ...d,
              exceptions: [
                ...d.exceptions,
                { date: campusDate(editor.server_time), is_closed: true, opens: null, closes: null, reason: null },
              ],
            }))
          }
        >
          + Exception
        </Button>
      </div>
    </Panel>
  );
}

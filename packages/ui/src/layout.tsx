import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { cx } from "./cx";

export const LAYOUT_W = 1600;
export const LAYOUT_H = 900;
const NUDGE = 0.005;

export type LayoutPoint = [number, number];

export interface LayoutSeat {
  seat_id: string;
  x: number;
  y: number;
}

export interface LayoutShape {
  points: LayoutPoint[];
  seats?: LayoutSeat[];
}

export const clampUnit = (v: number) => Math.round(Math.min(1, Math.max(0, v)) * 1000) / 1000;

export const centroid = (points: LayoutPoint[]): LayoutPoint => [
  points.reduce((s, p) => s + p[0], 0) / points.length,
  points.reduce((s, p) => s + p[1], 0) / points.length,
];

export function nextSeatId(shapes: LayoutShape[], prefix = "seat"): string {
  const used = new Set(shapes.flatMap((p) => (p.seats ?? []).map((seat) => seat.seat_id)));
  let n = used.size + 1;
  while (used.has(`${prefix}-${n}`)) n += 1;
  return `${prefix}-${n}`;
}

export function LayoutCanvas<T extends LayoutShape>({
  shapes,
  labelOf,
  colorOf,
  selected,
  onSelect,
  onMove,
  backdrop,
  overlay,
  seatMode,
  onAddSeat,
  onRemoveSeat,
  label = "Zone layout canvas. Select a shape, then drag its corners or move a focused corner with the arrow keys.",
}: {
  shapes: T[];
  labelOf: (shape: T) => string;
  colorOf: (shape: T) => string;
  selected: number | null;
  onSelect: (index: number | null) => void;
  onMove: (shape: number, vertex: number, point: LayoutPoint) => void;
  backdrop?: string | null;
  overlay?: boolean;
  seatMode: boolean;
  onAddSeat: (shape: number, point: LayoutPoint) => void;
  onRemoveSeat: (shape: number, seat: number) => void;
  label?: string;
}) {
  const svg = useRef<SVGSVGElement>(null);
  const [drag, setDrag] = useState<{ shape: number; vertex: number } | null>(null);
  const toPoint = (event: PointerEvent): LayoutPoint | null => {
    const matrix = svg.current?.getScreenCTM();
    if (!svg.current || !matrix) return null;
    const p = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    return [clampUnit(p.x / LAYOUT_W), clampUnit(p.y / LAYOUT_H)];
  };
  const nudge = (event: KeyboardEvent, shape: number, vertex: number) => {
    const step = event.shiftKey ? NUDGE * 4 : NUDGE;
    const delta = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[event.key];
    const point = shapes[shape]?.points[vertex];
    if (!delta || !point) return;
    event.preventDefault();
    onMove(shape, vertex, [clampUnit(point[0] + (delta[0] ?? 0)), clampUnit(point[1] + (delta[1] ?? 0))]);
  };
  return (
    <svg
      ref={svg}
      viewBox={`0 0 ${LAYOUT_W} ${LAYOUT_H}`}
      role="application"
      aria-label={label}
      className={cx(
        "aspect-video w-full touch-none select-none rounded-xl",
        overlay ? "absolute inset-0 h-full bg-transparent" : "border border-line bg-[#1b2420]",
      )}
      onPointerMove={(e) => {
        if (!drag) return;
        const point = toPoint(e);
        if (point) onMove(drag.shape, drag.vertex, point);
      }}
      onPointerUp={() => setDrag(null)}
      onPointerLeave={() => setDrag(null)}
      onPointerDown={(e) => {
        if (e.target === svg.current) onSelect(null);
      }}
    >
      {backdrop ? <image href={backdrop} x={0} y={0} width={LAYOUT_W} height={LAYOUT_H} preserveAspectRatio="none" opacity={0.85} /> : null}
      {Array.from({ length: 9 }, (_, i) => (
        <line
          key={`v${i}`}
          x1={((i + 1) * LAYOUT_W) / 10}
          y1={0}
          x2={((i + 1) * LAYOUT_W) / 10}
          y2={LAYOUT_H}
          stroke="#ffffff"
          strokeOpacity={0.06}
          pointerEvents="none"
        />
      ))}
      {Array.from({ length: 4 }, (_, i) => (
        <line
          key={`h${i}`}
          x1={0}
          y1={((i + 1) * LAYOUT_H) / 5}
          x2={LAYOUT_W}
          y2={((i + 1) * LAYOUT_H) / 5}
          stroke="#ffffff"
          strokeOpacity={0.06}
          pointerEvents="none"
        />
      ))}
      {shapes.map((shape, index) => {
        const color = colorOf(shape);
        const [cx_, cy_] = centroid(shape.points);
        const active = index === selected;
        return (
          <g key={index}>
            <polygon
              points={shape.points.map(([x, y]) => `${x * LAYOUT_W},${y * LAYOUT_H}`).join(" ")}
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
            <text
              x={cx_ * LAYOUT_W}
              y={cy_ * LAYOUT_H}
              textAnchor="middle"
              fill="#ffffff"
              stroke="#000000"
              strokeOpacity={0.5}
              strokeWidth={6}
              paintOrder="stroke"
              fontSize={34}
              fontWeight={700}
              pointerEvents="none"
            >
              {labelOf(shape)}
            </text>
            {(shape.seats ?? []).map((seat, k) => (
              <circle
                key={seat.seat_id}
                cx={seat.x * LAYOUT_W}
                cy={seat.y * LAYOUT_H}
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
              ? shape.points.map(([x, y], vertex) => (
                  <circle
                    key={vertex}
                    cx={x * LAYOUT_W}
                    cy={y * LAYOUT_H}
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
                      setDrag({ shape: index, vertex });
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

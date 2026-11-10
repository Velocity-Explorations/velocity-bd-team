"use client";

// One of Deep field's planets (David, 10 Nov 2026; lib/sky.ts lays them out). Back to front: the gas cloud, the far
// half of the rings, moons behind the planet, the body with the near half of the rings, moons in front. Each moon is
// drawn twice on the same orbit, once under the body and once over it, and each copy shows only on its own half of the
// orbit (globals.css), so a moon passes behind the planet and out again with only transform and opacity changing.

import { useId, type CSSProperties, type ReactNode } from "react";
import type { Haze, Moon, Planet, Ring } from "@/lib/sky";
import { inkColour } from "./deep-field-craft";

/** Two decimals is plenty for a px. */
const n = (v: number) => Math.round(v * 100) / 100;

const fill = (ink: number): CSSProperties => ({ fill: inkColour(ink) });

/** An SVG drawn about the planet's centre, `half` px each way. */
function Square({ half, children }: { half: number; children: ReactNode }) {
  const h = Math.ceil(half) + 2;
  return (
    <svg width={2 * h} height={2 * h} viewBox={`${-h} ${-h} ${2 * h} ${2 * h}`} style={{ left: -h, top: -h }}>
      {children}
    </svg>
  );
}

/** A full ellipse about the centre, as a path, so rings can be cut from several with even-odd fill. */
function ellipse(a: number, b: number): string {
  return `M${n(-a)} 0A${n(a)} ${n(b)} 0 1 0 ${n(a)} 0A${n(a)} ${n(b)} 0 1 0 ${n(-a)} 0Z`;
}

function ringPath(ring: Ring): string {
  const radii = [ring.inner, ring.outer];
  if (ring.gap) {
    const g0 = ring.inner + (ring.outer - ring.inner) * 0.55;
    radii.splice(1, 0, g0, g0 + Math.max(0.8, (ring.outer - ring.inner) * 0.12));
  }
  return radii.map((r) => ellipse(r, r * ring.squash)).join("");
}

/** The far (upper) or near (lower) half of the rings, in the planet's tilted frame. */
function RingHalf({ p, half, id }: { p: Planet; half: "far" | "near"; id: string }) {
  const ring = p.ring!;
  const e = Math.ceil(ring.outer) + 2;
  return (
    <g transform={`rotate(${n(p.tilt)})`}>
      <clipPath id={`${id}-${half}`}>
        <rect x={-e} y={half === "far" ? -e : 0} width={2 * e} height={e} />
      </clipPath>
      <path d={ringPath(ring)} fillRule="evenodd" clipPath={`url(#${id}-${half})`} style={fill(ring.ink)} />
    </g>
  );
}

function Cloud({ haze, reverse, id }: { haze: Haze; reverse: boolean; id: string }) {
  const half = Math.max(...haze.blobs.map((b) => Math.hypot(b.dx, b.dy) + b.r));
  const style = {
    "--breath": `${n(haze.seconds)}s`,
    "--swirl": `${n(haze.swirlSeconds)}s`,
    "--delay": `${n(-haze.phase * haze.swirlSeconds)}s`,
    "--way": reverse ? "reverse" : "normal",
  } as CSSProperties;
  return (
    <div className="topbar-deep-haze" style={style}>
      <Square half={half}>
        <defs>
          {haze.blobs.map((b, i) => (
            <radialGradient key={i} id={`${id}-gas${i}`}>
              <stop offset="0" style={{ stopColor: inkColour(b.ink), stopOpacity: 1 }} />
              <stop offset="0.5" style={{ stopColor: inkColour(b.ink), stopOpacity: 0.45 }} />
              <stop offset="1" style={{ stopColor: inkColour(b.ink), stopOpacity: 0 }} />
            </radialGradient>
          ))}
        </defs>
        {haze.blobs.map((b, i) => (
          <circle key={i} cx={n(b.dx)} cy={n(b.dy)} r={n(b.r)} fill={`url(#${id}-gas${i})`} />
        ))}
      </Square>
    </div>
  );
}

/** A moon's place on its orbit when nothing moves (reduced motion), and the orbit the animation follows. */
function moonStyle(m: Moon, reverse: boolean, side: "back" | "front"): CSSProperties {
  const a = m.phase * 2 * Math.PI;
  const inFront = Math.sin(a) >= 0;   // the lower half of the orbit is the near side
  return {
    width: `${n(2 * m.r)}px`,
    height: `${n(2 * m.r)}px`,
    left: `${n(-m.r)}px`,
    top: `${n(-m.r)}px`,
    background: inkColour(m.ink),
    transform: `translate(${n(m.rx * Math.cos(a))}px, ${n(m.ry * Math.sin(a))}px)`,
    opacity: (side === "front") === inFront ? 1 : 0,
    "--rx": `${n(m.rx)}px`,
    "--ry": `${n(m.ry)}px`,
    "--dur": `${n(m.seconds)}s`,
    "--delay": `${n(-m.phase * m.seconds)}s`,
    "--way": reverse ? "reverse" : "normal",
  } as CSSProperties;
}

function Moons({ p, side }: { p: Planet; side: "back" | "front" }) {
  return (
    <div className="topbar-deep-orbit" style={{ transform: `rotate(${n(p.tilt)}deg)` }}>
      {p.moons.map((m, i) => (
        <div key={i} className={`topbar-deep-moon topbar-deep-moon-${side}`} style={moonStyle(m, p.reverse, side)} />
      ))}
    </div>
  );
}

export function PlanetGlyph({ planet: p, x }: { planet: Planet; x: number }) {
  const id = "pl" + useId().replace(/[^\w-]/g, "");
  const r = n(p.r);
  return (
    <div
      className="topbar-deep-planet"
      data-kind={p.kind}
      data-ring={p.ring ? (p.ring.gap ? "gap" : "plain") : undefined}
      data-haze={p.haze ? "" : undefined}
      data-moons={p.moons.length || undefined}
      style={{ left: `${n(x)}px`, top: `${n(p.y)}px` }}
    >
      {p.haze && <Cloud haze={p.haze} reverse={p.reverse} id={id} />}
      {p.ring && (
        <Square half={p.ring.outer}>
          <RingHalf p={p} half="far" id={id} />
        </Square>
      )}
      {p.moons.length > 0 && <Moons p={p} side="back" />}
      <Square half={Math.max(p.r, p.ring?.outer ?? 0)}>
        <defs>
          {/* lit from the upper left, as every planet in the sky is */}
          <radialGradient id={`${id}-lit`} cx="0.34" cy="0.32" r="0.78">
            <stop offset="0" style={{ stopColor: inkColour(p.lit) }} />
            <stop offset="1" style={{ stopColor: inkColour(p.ink) }} />
          </radialGradient>
          <radialGradient id={`${id}-shade`} cx="0.34" cy="0.32" r="0.95">
            <stop offset="0.45" style={{ stopColor: "var(--fx-ground)", stopOpacity: 0 }} />
            <stop offset="1" style={{ stopColor: "var(--fx-ground)", stopOpacity: 0.7 }} />
          </radialGradient>
          <clipPath id={`${id}-disc`}>
            <circle r={r} />
          </clipPath>
        </defs>
        <circle r={r} fill={`url(#${id}-lit)`} />
        <g clipPath={`url(#${id}-disc)`}>
          <g transform={`rotate(${n(p.tilt)})`}>
            {p.bands.map((b, i) => (
              <rect key={i} x={-r} y={n(b.y - b.h / 2)} width={2 * r} height={n(b.h)} style={fill(b.ink)} />
            ))}
            {p.marks.map((m, i) => (
              <ellipse key={i} cx={n(m.dx)} cy={n(m.dy)} rx={n(m.rx)} ry={n(m.ry)} style={fill(m.ink)} />
            ))}
          </g>
          <circle r={r} fill={`url(#${id}-shade)`} />
        </g>
        {p.ring && <RingHalf p={p} half="near" id={id} />}
      </Square>
      {p.moons.length > 0 && <Moons p={p} side="front" />}
    </div>
  );
}

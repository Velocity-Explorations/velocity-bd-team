"use client";

// Bar theme "deep-field" (board concept 1i, Claude Design handoff). The default. Three layers of faint stars drift left
// behind the bar. One craft at a time (shuttle, satellite, rocket or UFO) crosses now and then, chosen at random.
// The full spec is docs/design/topbar-animation/handoff/bar-themes/README.md.

import { useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { CraftGlyph, type CraftType } from "./deep-field-craft";
import { phaseToClock, rng, useReducedMotion, useTabHidden } from "./motion";

/** Every tunable number for the effect lives here. */
export const DEEP_FIELD = {
  /** Star layers, far to near. Each tile repeats horizontally; moving exactly one tile per loop is what makes the loop
   *  seamless. */
  layers: [
    { tile: 320, stars: 20, seed: 11, radius: 0.6, opacity: 0.14, seconds: 90 },
    { tile: 480, stars: 12, seed: 23, radius: 0.8, opacity: 0.2, seconds: 60 },
    { tile: 640, stars: 6, seed: 37, radius: 1.1, opacity: 0.24, seconds: 40 },
  ],
  /** Star tile height. Matches the bar at its tallest (three rows on a phone). */
  tileHeight: 172,
  /** First craft appears this long after mount. */
  firstCraftMs: 4000,
  /** Empty sky between crossings, picked at random in this range. */
  gapMs: [5000, 16000] as [number, number],
  /** Base crossing time at a 1440 px bar, and how often each type is picked. */
  craft: {
    shuttle: { weight: 0.3, seconds: 22 },
    satellite: { weight: 0.25, seconds: 24 },
    rocket: { weight: 0.23, seconds: 13 },
    ufo: { weight: 0.22, seconds: 30 },
  } as Record<CraftType, { weight: number; seconds: number }>,
  /** Crossing time scales with bar width, clamped to this range. */
  widthFactor: [0.75, 1.25] as [number, number],
  referenceWidth: 1440,
  /** The satellite rides this lane, above every label (labels start at about y 12). */
  satelliteY: 6,
};

// ---------------------------------------------------------------- stars

/** One star tile as an SVG data URI, used as a mask so the colour stays a token. */
function starTile(tile: number, count: number, seed: number, radius: number, height: number) {
  const r = rng(seed);
  let dots = "";
  for (let i = 0; i < count; i++) {
    const x = (r() * tile).toFixed(1);
    const y = (3 + r() * (height - 6)).toFixed(1);
    dots += `<circle cx="${x}" cy="${y}" r="${radius}"/>`;
  }
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${tile}" height="${height}">${dots}</svg>`;
  return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
}

// ---------------------------------------------------------------- component

export function DeepField() {
  const reduced = useReducedMotion();
  const hidden = useTabHidden();
  const stars = useRef<(HTMLDivElement | null)[]>([]);
  const layers = useMemo(
    () => DEEP_FIELD.layers.map((l) => ({ ...l, mask: starTile(l.tile, l.stars, l.seed, l.radius, DEEP_FIELD.tileHeight) })),
    [],
  );

  // Carry on from the frame the last bar showed (motion.ts, the themes' clock), before the first paint.
  useLayoutEffect(() => phaseToClock(stars.current), [reduced]);

  return (
    <div className="topbar-fx topbar-deep" aria-hidden="true" data-paused={hidden || undefined}>
      {layers.map((l, i) => (
        <div
          key={l.tile}
          ref={(el) => {
            stars.current[i] = el;
          }}
          className="topbar-deep-stars"
          style={
            {
              "--tile": `${l.tile}px`,
              "--tile-h": `${DEEP_FIELD.tileHeight}px`,
              "--dur": `${l.seconds}s`,
              "--mix": `${Math.round(l.opacity * 1000) / 10}%`,   // the layer's ink in the ground, opaque (globals.css)
              maskImage: l.mask,
              WebkitMaskImage: l.mask,
            } as CSSProperties
          }
        />
      ))}
      {!reduced && <CraftLane paused={hidden} />}
    </div>
  );
}

// ---------------------------------------------------------------- craft

type Craft = { id: number; type: CraftType; dir: 1 | -1; y: number; w: number; ms: number; bright: boolean };

/**
 * How far below the bar's top its highest text or icon starts, in px (David, 9 Nov 2026). The handoff put the bright
 * satellite at y 6 on the understanding that labels start at about y 12; on a phone the bar's first row starts at the
 * very top, so the satellite would cross "BD Team" at 45% ink. Read once per crossing, not per frame.
 */
function skyAbove(lane: HTMLElement): number {
  const bar = lane.closest(".topbar");
  if (!bar) return 0;
  const top = lane.getBoundingClientRect().top;
  let highest = Infinity;
  const walk = document.createTreeWalker(bar, NodeFilter.SHOW_TEXT);
  while (walk.nextNode()) {
    const node = walk.currentNode;
    if (!node.textContent?.trim() || node.parentElement?.closest(".topbar-fx")) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    for (const rect of range.getClientRects()) highest = Math.min(highest, rect.top - top);
  }
  for (const el of bar.querySelectorAll("svg, img")) {
    if (!el.closest(".topbar-fx")) highest = Math.min(highest, el.getBoundingClientRect().top - top);
  }
  return highest;
}

/** The satellite's bright lane needs this much clear sky above the bar's content: its trail is 1 px at satelliteY. */
const SATELLITE_CLEARANCE = 4;

function pickType(): CraftType {
  const entries = Object.entries(DEEP_FIELD.craft) as [CraftType, { weight: number }][];
  const total = entries.reduce((s, [, c]) => s + c.weight, 0);
  let x = Math.random() * total;
  for (const [type, c] of entries) {
    x -= c.weight;
    if (x <= 0) return type;
  }
  return "shuttle";
}

function CraftLane({ paused }: { paused: boolean }) {
  const laneRef = useRef<HTMLDivElement>(null);
  const craftRef = useRef<HTMLDivElement>(null);
  const anim = useRef<Animation | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const pausedRef = useRef(paused);
  const nextId = useRef(0);
  const [craft, setCraft] = useState<Craft | null>(null);

  const schedule = (ms: number) => {
    window.clearTimeout(timer.current);
    if (pausedRef.current) return;
    timer.current = window.setTimeout(launch, ms);
  };

  const launch = () => {
    const lane = laneRef.current;
    if (!lane || !lane.clientWidth) return schedule(1000);
    const w = lane.clientWidth;
    const h = lane.clientHeight;
    const type = pickType();
    // Shuttles and rockets always fly left to right; the others pick a side.
    const dir: 1 | -1 = (type === "ufo" || type === "satellite") && Math.random() < 0.5 ? -1 : 1;
    // The satellite flies bright in its lane only where that lane is clear of every label; otherwise it flies like
    // the rest, in any lane at craft brightness.
    const bright = type === "satellite" && skyAbove(lane) >= DEEP_FIELD.satelliteY + SATELLITE_CLEARANCE;
    const y = bright ? DEEP_FIELD.satelliteY : 4 + Math.random() * Math.max(0, h - 16);
    const [lo, hi] = DEEP_FIELD.widthFactor;
    const factor = Math.min(hi, Math.max(lo, w / DEEP_FIELD.referenceWidth));
    const ms = DEEP_FIELD.craft[type].seconds * 1000 * factor;
    setCraft({ id: ++nextId.current, type, dir, y, w, ms, bright });
  };

  // Fly the current craft across, then clear it and wait for the next one.
  useEffect(() => {
    const el = craftRef.current;
    if (!craft || !el) return;
    const from = craft.dir > 0 ? -60 : craft.w + 60;
    const to = craft.dir > 0 ? craft.w + 60 : -60;
    const steps = craft.type === "ufo" ? 12 : 1;
    const frames: Keyframe[] = [];
    for (let i = 0; i <= steps; i++) {
      const t = i / steps;
      // UFO bobs 2.5 px three times per crossing; the shuttle climbs 3 px.
      const dy = craft.type === "ufo" ? 2.5 * Math.sin(t * Math.PI * 6) : craft.type === "shuttle" ? -3 * t : 0;
      frames.push({ transform: `translate(${(from + (to - from) * t).toFixed(1)}px, ${(craft.y + dy).toFixed(1)}px)` });
    }
    const a = el.animate(frames, { duration: craft.ms, easing: "linear", fill: "both" });
    if (pausedRef.current) a.pause();
    anim.current = a;
    a.onfinish = () => {
      anim.current = null;
      setCraft(null);
      const [lo, hi] = DEEP_FIELD.gapMs;
      schedule(lo + Math.random() * (hi - lo));
    };
    return () => a.cancel();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [craft]);

  // Pause the crossing and the timer while the tab is hidden.
  useEffect(() => {
    pausedRef.current = paused;
    if (paused) {
      window.clearTimeout(timer.current);
      anim.current?.pause();
    } else if (anim.current) {
      anim.current.play();
    } else {
      schedule(1500);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paused]);

  // First craft, and cleanup on unmount.
  useEffect(() => {
    schedule(DEEP_FIELD.firstCraftMs);
    return () => window.clearTimeout(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div ref={laneRef} className="topbar-deep-lane">
      {craft && (
        <div key={craft.id} ref={craftRef} className="topbar-deep-craft" data-dir={craft.dir}>
          <CraftGlyph type={craft.type} bright={craft.bright} />
        </div>
      )}
    </div>
  );
}

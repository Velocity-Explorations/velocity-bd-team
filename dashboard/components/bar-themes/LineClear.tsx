"use client";

// Bar theme "line-clear" (board concept 1j, Claude Design handoff). Faint blocks drift in from the left and stack
// against the right until the bar is full, then the row breaks apart left to right, fades, and starts again.

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { fxClock, rng, useReducedMotion, useTabHidden } from "./motion";

/** Every tunable number for the effect. Seconds unless noted. */
export const LINE_CLEAR = {
  /** One strip is two cells tall. The bar gets round(height / stripHeight) strips. */
  stripHeight: 56,
  /** Target time to fill the bar, whatever its width. */
  fillSeconds: 60,
  /** Longest gap between pieces (caps the interval on narrow bars). */
  maxInterval: 4,
  /** Each piece fades in this far (px) short of its place and slides the rest. */
  entryOffset: 160,
  slide: 3.2,
  /** Share of the slide spent fading in. */
  fadeInShare: 0.45,
  hold: 3,
  /** The break runs left to right over this long. */
  stagger: 1.4,
  breakSeconds: 3.6,
  rest: 2.8,
  /** Gap between cells, px. */
  gap: 2,
  ease: "cubic-bezier(0.2, 0.7, 0.2, 1)", // the theme's ease out
};

type Cell = { x: number; y: number; size: number; frames: Keyframe[] };
type Layout = { cells: Cell[]; ms: number };

/** Builds every cell and its keyframes for a bar of this size. Pure; runs once per size. */
export function buildLineClear(w: number, h: number): Layout {
  const C = LINE_CLEAR;
  const strips = Math.max(1, Math.round(h / C.stripHeight));
  const cell = Math.floor(h / (strips * 2));
  const cols = Math.floor(w / cell);
  const used = cols - (cols % 2);
  if (used < 2) return { cells: [], ms: 1000 };
  const ox = w - used * cell; // stack is flush right; leftover columns sit under the left fade
  const oy = Math.floor((h - strips * 2 * cell) / 2);
  const rand = rng(w * 7 + h);
  const run = (r: number, c0: number, n: number) => Array.from({ length: n }, (_, k) => [r, c0 + k] as [number, number]);

  // Fill each two-cell strip right to left with O, I+I or interlocking L+J pieces.
  const perStrip: [number, number][][][] = [];
  for (let s = 0; s < strips; s++) {
    const list: [number, number][][] = [];
    const r0 = s * 2;
    const r1 = s * 2 + 1;
    let c = used;
    while (c > 0) {
      const x = rand();
      const kind = c < 4 || x < 0.34 ? "O" : x < 0.67 ? "II" : "LJ";
      if (kind === "O") {
        c -= 2;
        list.push([[r0, c], [r0, c + 1], [r1, c], [r1, c + 1]]);
      } else if (kind === "II") {
        c -= 4;
        list.push(run(r0, c, 4), run(r1, c, 4));
      } else {
        c -= 4;
        const t = rand() < 0.5 ? r0 : r1;
        const b = t === r0 ? r1 : r0;
        // the piece reaching further right lands first, then its partner
        list.push([...run(t, c + 1, 3), [b, c + 3]], [[t, c], ...run(b, c, 3)]);
      }
    }
    perStrip.push(list);
  }
  // Interleave strips so all rows fill together.
  const pieces: [number, number][][] = [];
  const longest = Math.max(...perStrip.map((l) => l.length));
  for (let i = 0; i < longest; i++) perStrip.forEach((l) => l[i] && pieces.push(l[i]));

  const n = pieces.length;
  const iv = Math.min(C.maxInterval, C.fillSeconds / n);
  const L = n * iv + C.hold + C.stagger + C.breakSeconds + C.rest;
  const tf = (x: number, y: number, r: number, s: number) =>
    `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) rotate(${r.toFixed(1)}deg) scale(${s})`;

  const cells: Cell[] = [];
  pieces.forEach((piece, i) => {
    const t0 = (i * iv) / L;
    const tv = (i * iv + C.slide * C.fadeInShare) / L;
    const t1 = (i * iv + C.slide) / L;
    piece.forEach(([row, col]) => {
      const tb = (n * iv + C.hold + (col / used) * C.stagger) / L;
      const te = tb + C.breakSeconds / L;
      const dx = -6 + rand() * 26;
      const dy = (rand() - 0.5) * 14;
      const rot = (rand() - 0.5) * 36;
      const sx = -C.entryOffset;
      cells.push({
        x: ox + col * cell + C.gap / 2,
        y: oy + row * cell + C.gap / 2,
        size: cell - C.gap,
        frames: [
          { offset: 0, transform: tf(sx, 0, 0, 1), opacity: 0 },
          { offset: t0, transform: tf(sx, 0, 0, 1), opacity: 0, easing: C.ease },
          { offset: tv, opacity: 1 },
          { offset: t1, transform: tf(0, 0, 0, 1), opacity: 1 },
          { offset: tb, transform: tf(0, 0, 0, 1), opacity: 1, easing: C.ease },
          { offset: te, transform: tf(dx, dy, rot, 0.7), opacity: 0 },
          { offset: 1, transform: tf(dx, dy, rot, 0.7), opacity: 0 },
        ],
      });
    });
  });
  return { cells, ms: L * 1000 };
}

export function LineClear() {
  const ref = useRef<HTMLDivElement>(null);
  const anims = useRef<Animation[]>([]);
  const reduced = useReducedMotion();
  const hidden = useTabHidden();
  const [layout, setLayout] = useState<Layout | null>(null);

  // Measure after mount and on resize (debounced). Client only: renders nothing on the server.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let w = 0;
    let h = 0;
    let t: number | undefined;
    const measure = () => {
      const nw = el.clientWidth;
      const nh = el.clientHeight;
      if (!nw || !nh || (nw === w && nh === h)) return;
      w = nw;
      h = nh;
      setLayout(buildLineClear(nw, nh));
    };
    const ro = new ResizeObserver(() => {
      window.clearTimeout(t);
      t = window.setTimeout(measure, 150);
    });
    ro.observe(el);
    measure();
    return () => {
      ro.disconnect();
      window.clearTimeout(t);
    };
  }, []);

  // One infinite animation per cell, started before the cells first paint (so the full row never flashes) and at the
  // themes' clock, so a bar drawn again carries on from the frame the last one showed. Reduced motion: none, so the
  // cells show the full row.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || !layout || reduced) return;
    const at = fxClock() % layout.ms;
    const list = Array.from(el.children).map((child, i) => {
      const a = (child as HTMLElement).animate(layout.cells[i].frames, { duration: layout.ms, iterations: Infinity });
      a.currentTime = at;
      return a;
    });
    anims.current = list;
    return () => {
      list.forEach((a) => a.cancel());
      anims.current = [];
    };
  }, [layout, reduced]);

  useEffect(() => {
    anims.current.forEach((a) => (hidden ? a.pause() : a.play()));
  }, [hidden, layout, reduced]);

  return (
    <div ref={ref} className="topbar-fx topbar-lines" aria-hidden="true">
      {layout?.cells.map((c, i) => (
        <div key={i} className="topbar-lines-cell" style={{ left: c.x, top: c.y, width: c.size, height: c.size }} />
      ))}
    </div>
  );
}

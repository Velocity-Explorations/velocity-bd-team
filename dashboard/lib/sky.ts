// Deep field's planets (David, 10 Nov 2026; not in the Claude Design handoff): a few planets of random size, kind and
// place drift behind the bar, slower than the farthest stars. Some have rings, some a cloud of gas around them, some
// one to three moons. This file lays out a sky; components/bar-themes/deep-field-planets.tsx draws it. No imports, so
// the bar and `node --test` share it.

/** Small deterministic PRNG, so a seed always gives the same sky (and the star tiles the same stars). */
export function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export type PlanetKind = "rocky" | "banded" | "storm" | "ice";
export const PLANET_KINDS: PlanetKind[] = ["rocky", "banded", "storm", "ice"];

/**
 * The most ink any part of a planet carries over the ground. Below the craft's 0.22, so silver labels keep 4.5:1 with
 * any planet behind them. Planets paint opaque greys (the ink mixed into the ground), so where a planet covers a star
 * the planet shows, and nothing adds up.
 */
export const PLANET_INK_CAP = 0.2;

/** Every tunable number for the planets. */
export const PLANETS = {
  /** Drift, px per second. The farthest stars move 3.6. */
  pxPerSecond: 3,
  /** About one planet for this much bar, so a desktop bar shows two or three and a phone one. */
  everyPx: 640,
  /** Body radius, px, in three bands so each sky mixes sizes. */
  radius: [3, 15] as [number, number],
  sizes: [
    [3, 5.5],
    [6.5, 9.5],
    [10.5, 15],
  ] as [number, number][],
  /** Clear sky between neighbours' outermost parts (rings, gas, moons), px. */
  minGap: 48,
  minLoop: 800,
  /** Chances of each feature. Rings and gas only on planets of radius 5 or more. */
  ring: 0.42,
  haze: 0.32,
  moons: 0.45,
  /** One moon, two or three. */
  moonCounts: [0.5, 0.35, 0.15],
  /** A moon's orbit; outer moons are slower. */
  moonSeconds: [14, 40] as [number, number],
  /** The gas cloud breathes (fades a little and back) and turns slowly. */
  hazeSeconds: [18, 30] as [number, number],
  swirlSeconds: [100, 180] as [number, number],
};

export type Band = { y: number; h: number; ink: number };
export type Mark = { dx: number; dy: number; rx: number; ry: number; ink: number };
export type Ring = { squash: number; inner: number; outer: number; gap: boolean; ink: number };
export type Moon = { r: number; rx: number; ry: number; seconds: number; phase: number; ink: number; extent: number };
export type Blob = { dx: number; dy: number; r: number; ink: number };
export type Haze = { blobs: Blob[]; seconds: number; swirlSeconds: number; phase: number };

export type Planet = {
  /** Centre: x along the loop, y down from the bar's top, px. */
  x: number;
  y: number;
  r: number;
  kind: PlanetKind;
  /** Axis tilt, degrees. Bands, rings and moons' orbits share it. */
  tilt: number;
  /** The body's ink, and its lit side's. */
  ink: number;
  lit: number;
  bands: Band[];
  marks: Mark[];
  ring: Ring | null;
  haze: Haze | null;
  moons: Moon[];
  /** Moons and the gas cloud turn this way. */
  reverse: boolean;
  /** Half the width of everything the planet draws, px. */
  extent: number;
};

export type Sky = { width: number; height: number; loop: number; seconds: number; planets: Planet[] };

/** Every ink a planet paints, for the cap. */
export function inksOf(p: Planet): number[] {
  return [
    p.ink,
    p.lit,
    ...p.bands.map((b) => b.ink),
    ...p.marks.map((m) => m.ink),
    ...(p.ring ? [p.ring.ink] : []),
    ...p.moons.map((m) => m.ink),
    ...(p.haze ? p.haze.blobs.map((b) => b.ink) : []),
  ];
}

/**
 * The planets for a bar this wide and tall. The same seed and size always give the same sky. They sit along a loop at
 * least the bar's width plus two of the widest planets, which the bar draws twice end to end and moves one loop left
 * in `seconds`.
 */
export function planetSky(seed: number, width: number, height: number): Sky {
  const rand = rng(seed);
  const between = (lo: number, hi: number) => lo + rand() * (hi - lo);
  const shuffled = <T,>(items: T[]) => {
    const out = [...items];
    for (let i = out.length - 1; i > 0; i--) {
      const j = Math.floor(rand() * (i + 1));
      [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
  };

  const count = Math.max(1, Math.round((width + 120) / PLANETS.everyPx + rand() - 0.5));
  const kinds = shuffled(PLANET_KINDS);
  const sizes = shuffled(PLANETS.sizes);
  const planets = Array.from({ length: count }, (_, i) =>
    planet(kinds[i % kinds.length], between(...sizes[i % sizes.length]), height, rand, between),
  );

  // A sky with nothing around any planet gets rings (or a moon) on its largest.
  if (!planets.some((p) => p.ring || p.haze || p.moons.length)) {
    const big = planets.reduce((a, b) => (b.r > a.r ? b : a));
    if (big.r >= 5) big.ring = ring(big.r, between, rand);
    else big.moons = moons(big, 1, between, rand);
    big.extent = extentOf(big);
  }

  const widest = Math.max(...planets.map((p) => p.extent));
  const need = planets.reduce((s, p) => s + 2 * p.extent + PLANETS.minGap, 0);
  const loop = Math.ceil(Math.max(width + 2 * widest, need * 1.5, PLANETS.minLoop) / 200) * 200;

  // Share the spare sky between the gaps at random, then lay the planets round the loop in a random order, so each
  // keeps its clear sky from both neighbours however the loop wraps.
  const spare = loop - need;
  const weights = planets.map(() => rand() + 0.2);
  const total = weights.reduce((s, w) => s + w, 0);
  let cursor = rand() * loop;
  for (const [k, p] of shuffled(planets).entries()) {
    p.x = (cursor + p.extent) % loop;
    cursor += 2 * p.extent + PLANETS.minGap + (spare * weights[k]) / total;
  }

  return { width, height, loop, seconds: loop / PLANETS.pxPerSecond, planets };
}

type Between = (lo: number, hi: number) => number;

function planet(kind: PlanetKind, r: number, height: number, rand: () => number, between: Between): Planet {
  const lo = 0.45 * r;
  const hi = height - 0.45 * r;
  const p: Planet = {
    x: 0,
    y: hi > lo ? between(lo, hi) : height / 2,
    r,
    kind,
    tilt: between(-28, 28),
    ink: 0,
    lit: 0,
    bands: [],
    marks: [],
    ring: null,
    haze: null,
    moons: [],
    reverse: rand() < 0.5,
    extent: 0,
  };
  surface(p, between, rand);
  const ringChance = PLANETS.ring * (kind === "banded" || kind === "ice" ? 1.3 : 0.8);
  if (r >= 5 && rand() < ringChance) p.ring = ring(r, between, rand);
  if (r >= 5 && rand() < PLANETS.haze) p.haze = haze(r, between, rand);
  if (rand() < PLANETS.moons) {
    const [one, two] = PLANETS.moonCounts;
    const pick = rand();
    const n = r < 5 ? 1 : pick < one ? 1 : pick < one + two ? 2 : 3;
    p.moons = moons(p, n, between, rand);
  }
  p.extent = extentOf(p);
  return p;
}

/** The body's inks, and its bands, craters, storm or ice cap, all in the planet's own (tilted) frame. */
function surface(p: Planet, between: Between, rand: () => number): void {
  const r = p.r;
  const lit = (ink: number) => Math.min(PLANET_INK_CAP, ink + 0.035);
  const stripes = (n: number) => {
    for (let i = 0; i < n; i++) {
      const y = -0.85 * r + ((i + between(0.2, 0.8)) / n) * 1.7 * r;
      const light = i % 2 === 0;
      p.bands.push({ y, h: between(0.1, 0.24) * r, ink: light ? between(0.145, 0.16) : between(0.08, 0.095) });
    }
  };
  if (p.kind === "rocky") {
    p.ink = between(0.11, 0.13);
    const n = 2 + Math.floor(rand() * 3);
    for (let i = 0; i < n; i++) {
      const a = rand() * Math.PI * 2;
      const d = between(0.1, 0.6) * r;
      const s = between(0.1, 0.22) * r;
      p.marks.push({ dx: Math.cos(a) * d, dy: Math.sin(a) * d, rx: s, ry: s, ink: between(0.07, 0.09) });
    }
  } else if (p.kind === "banded") {
    p.ink = between(0.11, 0.125);
    stripes(3 + Math.floor(rand() * 3));
  } else if (p.kind === "storm") {
    p.ink = between(0.11, 0.125);
    stripes(2 + Math.floor(rand() * 2));
    p.marks.push({
      dx: between(-0.35, 0.35) * r,
      dy: between(0.15, 0.4) * r,
      rx: between(0.26, 0.34) * r,
      ry: between(0.13, 0.17) * r,
      ink: between(0.165, 0.18),
    });
  } else {
    p.ink = between(0.13, 0.145);
    p.bands.push({ y: between(-0.1, 0.1) * r, h: 0.08 * r, ink: 0.115 });
    p.marks.push({ dx: 0, dy: -0.8 * r, rx: 0.55 * r, ry: 0.26 * r, ink: between(0.18, 0.195) });
  }
  p.lit = lit(p.ink);
}

function ring(r: number, between: Between, rand: () => number): Ring {
  return {
    squash: between(0.22, 0.36),
    inner: between(1.25, 1.45) * r,
    outer: between(1.85, 2.3) * r,
    gap: rand() < 0.5,
    ink: between(0.15, 0.19),
  };
}

function haze(r: number, between: Between, rand: () => number): Haze {
  const n = 3 + Math.floor(rand() * 2);
  const blobs = Array.from({ length: n }, () => {
    const a = rand() * Math.PI * 2;
    const d = between(0.2, 0.9) * r;
    return { dx: Math.cos(a) * d, dy: Math.sin(a) * d, r: between(1.5, 2.4) * r, ink: between(0.05, 0.085) };
  });
  return {
    blobs,
    seconds: between(...PLANETS.hazeSeconds),
    swirlSeconds: between(...PLANETS.swirlSeconds),
    phase: rand(),
  };
}

/** Moons in the ring plane (or the planet's own), each orbit clear of the last; inner moons are faster. */
function moons(p: Planet, n: number, between: Between, rand: () => number): Moon[] {
  const squash = p.ring ? p.ring.squash : between(0.24, 0.42);
  const out: Moon[] = [];
  let rx = (p.ring ? p.ring.outer : p.r) + 2;
  let seconds = between(PLANETS.moonSeconds[0], PLANETS.moonSeconds[0] + 8);
  for (let i = 0; i < n; i++) {
    const r = between(1, 1.3) + Math.min(0.6, p.r * 0.045);
    const prev = rx;
    rx += r + (i === 0 ? between(1, 3) : Math.max(3.5, 0.45 * p.r) + between(0, 2));
    if (i > 0) seconds *= (rx / prev) ** 1.5;
    out.push({
      r,
      rx,
      ry: rx * squash,
      seconds: Math.min(PLANETS.moonSeconds[1], seconds),
      phase: rand(),
      ink: between(0.15, 0.19),
      extent: rx + r,
    });
    rx += r;
  }
  return out;
}

function extentOf(p: Planet): number {
  return Math.max(
    p.r,
    p.ring ? p.ring.outer : 0,
    p.haze ? Math.max(...p.haze.blobs.map((b) => Math.hypot(b.dx, b.dy) + b.r)) : 0,
    ...p.moons.map((m) => m.extent),
  );
}

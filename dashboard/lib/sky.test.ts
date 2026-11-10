import assert from "node:assert/strict";
import { test } from "node:test";
import {
  METEORS,
  PLANET_INK_CAP,
  PLANET_KINDS,
  PLANETS,
  eventInks,
  inksOf,
  planetSky,
  rng,
  skyEvent,
  type Planet,
  type Sky,
  type SkyEvent,
} from "./sky.ts";

const SEEDS = Array.from({ length: 300 }, (_, i) => i * 7919 + 13);
const desktop = (seed: number) => planetSky(seed, 1440, 56);

/** Distance between two points on the loop, the short way round. */
function around(a: number, b: number, loop: number): number {
  const d = Math.abs(a - b) % loop;
  return Math.min(d, loop - d);
}

test("a sky is the same for the same seed and bar size, so moving between pages keeps it", () => {
  assert.deepEqual(desktop(42), desktop(42));
  assert.notDeepEqual(desktop(42), desktop(43));
});

test("no part of a planet is brighter than the cap, which is below the craft's 0.22, so silver labels keep 4.5:1", () => {
  assert.ok(PLANET_INK_CAP <= 0.22);
  for (const seed of SEEDS) {
    for (const p of desktop(seed).planets) {
      for (const ink of inksOf(p)) assert.ok(ink > 0 && ink <= PLANET_INK_CAP, `${seed}: ${ink}`);
    }
  }
});

test("the loop is longer than the bar by two of the widest planets, so a planet and its copy are never both in view", () => {
  for (const [w, h] of [[1440, 56], [1024, 56], [390, 172], [2560, 56]]) {
    for (const seed of SEEDS) {
      const sky = planetSky(seed, w, h);
      const widest = Math.max(...sky.planets.map((p) => p.extent));
      assert.ok(sky.loop >= w + 2 * widest, `${seed} at ${w}: loop ${sky.loop}, widest ${widest}`);
      for (const p of sky.planets) assert.ok(p.x >= 0 && p.x < sky.loop);
    }
  }
});

test("planets never overlap: each keeps clear sky from its neighbours, rings, gas and moons included", () => {
  for (const seed of SEEDS) {
    const sky = desktop(seed);
    sky.planets.forEach((a, i) =>
      sky.planets.slice(i + 1).forEach((b) => {
        assert.ok(around(a.x, b.x, sky.loop) >= a.extent + b.extent + PLANETS.minGap, `${seed}`);
      }),
    );
  }
});

test("each planet sits in the row with most of its disc showing", () => {
  for (const [w, h] of [[1440, 56], [390, 172]]) {
    for (const seed of SEEDS) {
      for (const p of planetSky(seed, w, h).planets) {
        assert.ok(p.y >= 0.45 * p.r - 1e-9 && p.y <= h - 0.45 * p.r + 1e-9, `${seed}: y ${p.y}, r ${p.r}`);
      }
    }
  }
});

test("two or three planets on a desktop bar, one or two on a phone", () => {
  const counts = (w: number, h: number) => new Set(SEEDS.map((s) => planetSky(s, w, h).planets.length));
  assert.deepEqual([...counts(1440, 56)].sort(), [2, 3]);
  for (const n of counts(390, 172)) assert.ok(n >= 1 && n <= 2, `${n}`);
});

test("sizes, types and features vary: every kind, rings, gas clouds and one to three moons all turn up", () => {
  const all: Planet[] = SEEDS.flatMap((s) => desktop(s).planets);
  assert.deepEqual(new Set(all.map((p) => p.kind)), new Set(PLANET_KINDS));
  const [lo, hi] = PLANETS.radius;
  assert.ok(all.some((p) => p.r < lo + 2) && all.some((p) => p.r > hi - 3));
  for (const p of all) assert.ok(p.r >= lo && p.r <= hi);
  assert.ok(all.some((p) => p.ring) && all.some((p) => !p.ring));
  assert.ok(all.some((p) => p.ring?.gap) && all.some((p) => p.ring && !p.ring.gap));
  assert.ok(all.some((p) => p.haze) && all.some((p) => !p.haze));
  assert.deepEqual(new Set(all.map((p) => p.moons.length)), new Set([0, 1, 2, 3]));
  assert.ok(all.some((p) => p.ring && p.moons.length && p.haze), "a planet can have all three");
  // Within one sky the planets differ from each other in kind and size.
  for (const seed of SEEDS) {
    const ps = desktop(seed).planets;
    assert.equal(new Set(ps.map((p) => p.kind)).size, ps.length, `${seed}`);
    assert.equal(new Set(ps.map((p) => Math.round(p.r))).size, ps.length, `${seed}`);
    assert.ok(ps.some((p) => p.ring || p.haze || p.moons.length), `${seed}: a sky with nothing around any planet`);
  }
});

test("moons orbit clear of the body and the rings, inner moons faster, all one way round", () => {
  for (const seed of SEEDS) {
    for (const p of desktop(seed).planets) {
      const clear = (p.ring ? p.ring.outer : p.r) + 2;
      let last = 0;
      for (const m of p.moons) {
        assert.ok(m.rx - m.r >= clear, `${seed}: moon at ${m.rx} inside ${clear}`);
        assert.ok(m.ry > 0 && m.ry < m.rx);
        assert.ok(m.seconds >= last && m.seconds >= PLANETS.moonSeconds[0] && m.seconds <= PLANETS.moonSeconds[1]);
        assert.ok(m.extent <= p.extent);
        last = m.seconds;
      }
      if (p.ring && p.moons.length) assert.ok(p.moons.every((m) => Math.abs(m.ry / m.rx - p.ring!.squash) < 1e-9), "moons orbit in the ring plane");
    }
  }
});

/** Many events at a bar this size, from one seeded stream. */
function events(w: number, h: number, n = 600, cometCrossing = false): SkyEvent[] {
  const rand = rng(99);
  return Array.from({ length: n }, () => skyEvent(rand, w, h, cometCrossing));
}

test("sky events: shooting stars, meteor showers and comets all turn up, comets rarest of the three", () => {
  const kinds = events(1440, 56).map((e) => e.kind);
  const count = (k: string) => kinds.filter((x) => x === k).length;
  assert.ok(count("shooting-star") > count("shower") && count("shower") > 0 && count("comet") > 0);
  assert.ok(count("comet") < count("shooting-star"));
  assert.ok(METEORS.gapMs[0] >= 4000 && METEORS.gapMs[1] > METEORS.gapMs[0]);
});

test("while a comet crosses, the next event is never another comet", () => {
  assert.ok(events(1440, 56, 400, true).every((e) => e.kind !== "comet"));
});

test("no streak or comet is brighter than the craft's 0.22, so labels keep 4.5:1 when one passes behind them", () => {
  assert.ok(METEORS.inkCap <= 0.22);
  for (const e of events(1440, 56)) for (const ink of eventInks(e)) assert.ok(ink > 0 && ink <= METEORS.inkCap, `${ink}`);
});

test("a shooting star is one streak; a shower is a burst of streaks one way, its density random", () => {
  const all = [...events(1440, 56), ...events(390, 172)];
  const showers = all.filter((e) => e.kind === "shower");
  const sizes = new Set<number>();
  for (const e of all) {
    if (e.kind === "comet") continue;
    if (e.kind === "shooting-star") assert.equal(e.streaks.length, 1);
    else {
      const [lo, hi] = METEORS.shower.count;
      assert.ok(e.streaks.length >= lo && e.streaks.length <= hi);
      sizes.add(e.streaks.length);
      assert.equal(new Set(e.streaks.map((s) => s.dir)).size, 1, "a shower falls one way");
      const angles = e.streaks.map((s) => s.angle);
      assert.ok(Math.max(...angles) - Math.min(...angles) <= 2 * METEORS.shower.jitter + 1e-9);
      for (const s of e.streaks) assert.ok(s.delay >= 0 && s.delay <= METEORS.shower.spanMs[1]);
    }
  }
  assert.ok(showers.length > 0 && sizes.size >= 6, "showers differ in density");
});

test("streaks start over the bar, fall at a shallow angle and end inside it, in sizes that vary", () => {
  const lengths: number[] = [];
  for (const [w, h] of [[1440, 56], [390, 172]]) {
    for (const e of events(w, h)) {
      if (e.kind === "comet") continue;
      for (const s of e.streaks) {
        assert.ok(s.x >= 0 && s.x <= w && s.y >= 0 && s.y <= 0.4 * h + 1e-9, `${s.x}, ${s.y}`);
        assert.ok(s.angle > 0 && s.angle <= METEORS.star.angle[1]);
        assert.ok(s.y + s.distance * Math.sin((s.angle * Math.PI) / 180) <= h, "the head stays in the bar");
        assert.ok(s.ms >= METEORS.minStreakMs && s.width > 0);
        lengths.push(s.length);
      }
    }
  }
  assert.ok(Math.min(...lengths) < 20 && Math.max(...lengths) > 60);
});

test("a comet crosses the whole bar, off one side to off the other, slowly, at a random height and size", () => {
  const comets = events(1440, 56).flatMap((e) => (e.kind === "comet" ? [e.comet] : []));
  assert.ok(comets.length > 10);
  for (const c of comets) {
    const [from, to] = c.dir > 0 ? [c.from, c.to] : [c.to, c.from];
    assert.ok(from <= -c.tail && to >= 1440 + c.tail, `${c.from} to ${c.to}`);
    assert.ok(c.y0 >= 0.15 * 56 && c.y0 <= 0.85 * 56 && c.y1 >= 0.15 * 56 && c.y1 <= 0.85 * 56);
    assert.ok(c.ms >= METEORS.comet.seconds[0] * 1000 && c.ms <= METEORS.comet.seconds[1] * 1000);
  }
  assert.ok(new Set(comets.map((c) => c.dir)).size === 2);
  const tails = comets.map((c) => c.tail);
  assert.ok(Math.max(...tails) - Math.min(...tails) > 60, "tails differ in length");
});

test("the planets drift one loop in loop / speed seconds, slower than the farthest stars", () => {
  const sky: Sky = desktop(5);
  assert.equal(sky.seconds, sky.loop / PLANETS.pxPerSecond);
  assert.ok(PLANETS.pxPerSecond < 320 / 90);   // the far star layer: 320 px in 90 s
});

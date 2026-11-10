import assert from "node:assert/strict";
import { test } from "node:test";
import { PLANET_INK_CAP, PLANET_KINDS, PLANETS, inksOf, planetSky, type Planet, type Sky } from "./sky.ts";

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

test("the planets drift one loop in loop / speed seconds, slower than the farthest stars", () => {
  const sky: Sky = desktop(5);
  assert.equal(sky.seconds, sky.loop / PLANETS.pxPerSecond);
  assert.ok(PLANETS.pxPerSecond < 320 / 90);   // the far star layer: 320 px in 90 s
});

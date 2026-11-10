"use client";

// Deep field's shooting stars, meteor showers and comets (David, 10 Nov 2026; lib/sky.ts picks each one: its kind,
// size, density and place). They fly in front of the stars and planets, blended with lighten as the craft are, so over
// a star or a planet the brighter shows and nothing adds up. Not drawn when the system asks for reduced motion, and
// paused, with no new ones started, while the tab is hidden.

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { COMET_PARTS, METEORS, skyEvent, type Comet, type SkyEvent, type Streak } from "@/lib/sky";
import { inkColour } from "./deep-field-craft";

type Live = SkyEvent & { id: number };

/** Two decimals is plenty for a px. */
const n = (v: number) => Math.round(v * 100) / 100;

export function SkyEvents({ paused }: { paused: boolean }) {
  const laneRef = useRef<HTMLDivElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const pausedRef = useRef(paused);
  const nextId = useRef(0);
  const [live, setLive] = useState<Live[]>([]);
  const liveRef = useRef<Live[]>([]);

  useEffect(() => {
    liveRef.current = live;
  }, [live]);

  const schedule = (ms: number) => {
    window.clearTimeout(timer.current);
    if (pausedRef.current) return;
    timer.current = window.setTimeout(launch, ms);
  };

  const launch = () => {
    const lane = laneRef.current;
    if (!lane || !lane.clientWidth) return schedule(1000);
    const comet = liveRef.current.some((e) => e.kind === "comet");
    const event = skyEvent(Math.random, lane.clientWidth, lane.clientHeight, comet);
    setLive((l) => [...l, { ...event, id: ++nextId.current }]);
    const [lo, hi] = METEORS.gapMs;
    schedule(lo + Math.random() * (hi - lo));
  };

  const done = (id: number) => setLive((l) => l.filter((e) => e.id !== id));

  // Stop starting new ones while the tab is hidden; start again a gap after it returns.
  useEffect(() => {
    pausedRef.current = paused;
    if (paused) window.clearTimeout(timer.current);
    else schedule(METEORS.gapMs[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paused]);

  // The first one, and cleanup on unmount.
  useEffect(() => {
    schedule(METEORS.firstMs);
    return () => window.clearTimeout(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div ref={laneRef} className="topbar-deep-events">
      {live.map((e) => (
        <div key={e.id} className="topbar-deep-event" data-kind={e.kind}>
          {e.kind === "comet" ? (
            <CometFlight comet={e.comet} paused={paused} onDone={() => done(e.id)} />
          ) : (
            <Streaks streaks={e.streaks} paused={paused} onDone={() => done(e.id)} />
          )}
        </div>
      ))}
    </div>
  );
}

/** Runs these animations once, from before the first paint, pauses them with the tab, and reports when the last ends. */
function useFlight(start: () => Animation[], paused: boolean, onDone: () => void) {
  const anims = useRef<Animation[]>([]);
  useLayoutEffect(() => {
    const list = start();
    anims.current = list;
    let live = true;
    Promise.all(list.map((a) => a.finished)).then(
      () => live && onDone(),
      () => {},
    );
    return () => {
      live = false;
      list.forEach((a) => a.cancel());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    for (const a of anims.current) {
      if (paused) a.pause();
      else if (a.playState === "paused") a.play();
    }
  }, [paused]);
}

/** One shooting star, or a shower's burst: each streak flares, falls and fades. */
function Streaks({ streaks, paused, onDone }: { streaks: Streak[]; paused: boolean; onDone: () => void }) {
  const refs = useRef<(HTMLDivElement | null)[]>([]);
  useFlight(
    () =>
      streaks.map((s, i) =>
        refs.current[i]!.animate(
          [
            { transform: "translateX(0)", opacity: 0 },
            { opacity: 1, offset: 0.12 },
            { opacity: 0.9, offset: 0.65 },
            { transform: `translateX(${n(s.distance)}px)`, opacity: 0 },
          ],
          { duration: s.ms, delay: s.delay, easing: "linear", fill: "both" },
        ),
      ),
    paused,
    onDone,
  );
  return (
    <>
      {streaks.map((s, i) => (
        <div
          key={i}
          className="topbar-deep-meteor"
          style={{ transform: `translate(${n(s.x)}px, ${n(s.y)}px) rotate(${n(s.dir > 0 ? s.angle : 180 - s.angle)}deg)` }}
        >
          <div
            ref={(el) => {
              refs.current[i] = el;
            }}
            className="topbar-deep-streak"
            style={{
              left: `${n(-s.length)}px`,
              top: `${n(-s.width / 2)}px`,
              width: `${n(s.length)}px`,
              height: `${n(s.width)}px`,
              background: `linear-gradient(90deg, transparent, ${inkColour(s.ink)})`,
              opacity: 0,
            }}
          />
        </div>
      ))}
    </>
  );
}

/** A comet: a small bright head in a soft glow, a curved dust tail and a thin straight one, crossing slowly. */
function CometFlight({ comet: c, paused, onDone }: { comet: Comet; paused: boolean; onDone: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const id = "cm" + useId().replace(/[^\w-]/g, "");
  useFlight(
    () => [
      ref.current!.animate(
        [
          { transform: `translate(${n(c.from)}px, ${n(c.y0)}px)` },
          { transform: `translate(${n(c.to)}px, ${n(c.y1)}px)` },
        ],
        { duration: c.ms, easing: "linear", fill: "both" },
      ),
    ],
    paused,
    onDone,
  );
  const angle = (Math.atan2(c.y1 - c.y0, c.to - c.from) * 180) / Math.PI;
  const t = c.tail;
  const coma = c.head * 2.8;
  const w0 = c.head * 0.9;
  const w = 2 + t * 0.07;
  const left = Math.ceil(t * 1.15) + 2;
  const right = Math.ceil(coma) + 2;
  const half = Math.ceil(w * 1.2 + coma) + 2;
  return (
    <div ref={ref} className="topbar-deep-meteor">
      <div className="topbar-deep-comet" style={{ transform: `rotate(${n(angle)}deg)` }}>
        <svg
          width={left + right}
          height={2 * half}
          viewBox={`${-left} ${-half} ${left + right} ${2 * half}`}
          style={{ left: -left, top: -half }}
        >
          <defs>
            <linearGradient id={`${id}-dust`} gradientUnits="userSpaceOnUse" x1="0" y1="0" x2={n(-t)} y2="0">
              <stop offset="0" style={{ stopColor: inkColour(c.ink * COMET_PARTS.tail), stopOpacity: 1 }} />
              <stop offset="1" style={{ stopColor: inkColour(c.ink * COMET_PARTS.tail), stopOpacity: 0 }} />
            </linearGradient>
            <linearGradient id={`${id}-ion`} gradientUnits="userSpaceOnUse" x1="0" y1="0" x2={n(-t * 1.15)} y2="0">
              <stop offset="0" style={{ stopColor: inkColour(c.ink * COMET_PARTS.ion), stopOpacity: 1 }} />
              <stop offset="1" style={{ stopColor: inkColour(c.ink * COMET_PARTS.ion), stopOpacity: 0 }} />
            </linearGradient>
            <radialGradient id={`${id}-coma`}>
              <stop offset="0" style={{ stopColor: inkColour(c.ink * COMET_PARTS.coma), stopOpacity: 1 }} />
              <stop offset="1" style={{ stopColor: inkColour(c.ink * COMET_PARTS.coma), stopOpacity: 0 }} />
            </radialGradient>
          </defs>
          {/* the dust tail fans out and bends a little */}
          <path
            d={`M0 ${n(-w0)}Q${n(-t * 0.5)} ${n(-w * 0.6)} ${n(-t)} ${n(-w * 0.35)}L${n(-t)} ${n(w * 1.2)}Q${n(-t * 0.5)} ${n(w * 0.9)} 0 ${n(w0)}Z`}
            fill={`url(#${id}-dust)`}
          />
          <rect x={n(-t * 1.15)} y={-0.35} width={n(t * 1.15)} height={0.7} fill={`url(#${id}-ion)`} transform="rotate(-2.5)" />
          <circle r={n(coma)} fill={`url(#${id}-coma)`} />
          <circle r={n(c.head)} style={{ fill: inkColour(c.ink) }} />
        </svg>
      </div>
    </div>
  );
}

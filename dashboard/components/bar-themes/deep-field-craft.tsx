// The four craft for Deep field (Claude Design handoff). Each is a 20 x 10 glyph centred on its position, drawn facing
// right; CSS mirrors it for right-to-left crossings.

import { useId, type CSSProperties } from "react";

export type CraftType = "shuttle" | "satellite" | "rocket" | "ufo";

/** How much ink each part carries over the ground. Keep craft at 0.22 or below so silver labels stay above 4.5:1 when a
 *  craft passes behind them. The satellite is brighter only in the lane above every label (DeepField's skyAbove). */
const BODY = 0.22;
const DIM = 0.14;
const TRAIL = 0.12;
const SATELLITE = 0.45;

/**
 * A part's colour: the ink mixed into the ground, opaque, in place of the handoff's ink at an opacity. With the craft's
 * lighten blending (globals.css) a craft over a star shows the brighter of the two, never their sum, so no pixel behind
 * a label is brighter than the craft itself (David, 9 Nov 2026). Over plain ground it looks the same as before.
 */
function tone(ink: number): CSSProperties {
  return { fill: `color-mix(in srgb, var(--fx-ink) ${Math.round(ink * 1000) / 10}%, var(--fx-ground))` };
}

export function CraftGlyph({ type, bright = true }: { type: CraftType; bright?: boolean }) {
  const gid = useId().replace(/:/g, "");

  const Trail = ({ x, w, h, y, top }: { x: number; w: number; h: number; y: number; top: number }) => (
    <>
      <defs>
        <linearGradient id={gid}>
          <stop offset="0" style={{ stopColor: tone(top).fill as string, stopOpacity: 0 }} />
          <stop offset="1" style={{ stopColor: tone(top).fill as string, stopOpacity: 1 }} />
        </linearGradient>
      </defs>
      <rect x={x} y={y} width={w} height={h} fill={`url(#${gid})`} />
    </>
  );

  return (
    <svg className="topbar-deep-glyph" width="20" height="10" viewBox="0 0 20 10">
      {type === "shuttle" && (
        <>
          <Trail x={-14} y={4.5} w={14} h={1} top={0.1} />
          {/* fuselage */}
          <path style={tone(BODY)} d="M1 4.1H13Q18 4.3 19.5 5Q18 5.7 13 5.9H1Z" />
          {/* delta wings */}
          <path style={tone(BODY)} d="M3.5 4.2L8.5 0.6H10.5L12 4.2ZM3.5 5.8L8.5 9.4H10.5L12 5.8Z" />
          {/* engine block */}
          <path style={tone(DIM)} d="M0 4.4H1.4V5.6H0Z" />
        </>
      )}
      {type === "rocket" && (
        <>
          <Trail x={-22} y={4.4} w={22} h={1.2} top={TRAIL} />
          <path style={tone(BODY)} d="M2 3.5H12Q16 3.5 18 5Q16 6.5 12 6.5H2Z" />
          <path style={tone(BODY)} d="M2 3.5L0 1L4.5 3.5ZM2 6.5L0 9L4.5 6.5Z" />
        </>
      )}
      {type === "ufo" && (
        <>
          <path style={tone(DIM)} d="M6 5.4Q10 0.6 14 5.4Z" />
          <ellipse style={tone(BODY)} cx="10" cy="6.4" rx="9.5" ry="2.1" />
        </>
      )}
      {type === "satellite" && <Trail x={-20} y={4.5} w={30} h={1} top={bright ? SATELLITE : BODY} />}
    </svg>
  );
}

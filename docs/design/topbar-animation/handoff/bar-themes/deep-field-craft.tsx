// dashboard/components/bar-themes/deep-field-craft.tsx
// The four craft for Deep field. Each is a 20 x 10 glyph centred on its
// position, drawn facing right; CSS mirrors it for right-to-left crossings.
// Colour comes from currentColor (the ink token, set on .topbar-fx).

import { useId } from 'react';

export type CraftType = 'shuttle' | 'satellite' | 'rocket' | 'ufo';

/** Opacity of each part over the ground. Keep craft at 0.22 or below so
 *  silver labels stay above 4.5:1 when a craft passes behind them.
 *  The satellite is brighter because it only flies the lane above the labels. */
const BODY = 0.22;
const DIM = 0.14;
const TRAIL = 0.12;
const SATELLITE = 0.45;

export function CraftGlyph({ type }: { type: CraftType }) {
  const gid = useId().replace(/:/g, '');

  const Trail = ({ x, w, h, y, top }: { x: number; w: number; h: number; y: number; top: number }) => (
    <>
      <defs>
        <linearGradient id={gid}>
          <stop offset="0" stopColor="currentColor" stopOpacity="0" />
          <stop offset="1" stopColor="currentColor" stopOpacity={top} />
        </linearGradient>
      </defs>
      <rect x={x} y={y} width={w} height={h} fill={`url(#${gid})`} />
    </>
  );

  return (
    <svg className="topbar-deep-glyph" width="20" height="10" viewBox="0 0 20 10" fill="currentColor">
      {type === 'shuttle' && (
        <>
          <Trail x={-14} y={4.5} w={14} h={1} top={0.1} />
          {/* fuselage */}
          <path fillOpacity={BODY} d="M1 4.1H13Q18 4.3 19.5 5Q18 5.7 13 5.9H1Z" />
          {/* delta wings */}
          <path fillOpacity={BODY} d="M3.5 4.2L8.5 0.6H10.5L12 4.2ZM3.5 5.8L8.5 9.4H10.5L12 5.8Z" />
          {/* engine block */}
          <path fillOpacity={DIM} d="M0 4.4H1.4V5.6H0Z" />
        </>
      )}
      {type === 'rocket' && (
        <>
          <Trail x={-22} y={4.4} w={22} h={1.2} top={TRAIL} />
          <path fillOpacity={BODY} d="M2 3.5H12Q16 3.5 18 5Q16 6.5 12 6.5H2Z" />
          <path fillOpacity={BODY} d="M2 3.5L0 1L4.5 3.5ZM2 6.5L0 9L4.5 6.5Z" />
        </>
      )}
      {type === 'ufo' && (
        <>
          <path fillOpacity={DIM} d="M6 5.4Q10 0.6 14 5.4Z" />
          <ellipse fillOpacity={BODY} cx="10" cy="6.4" rx="9.5" ry="2.1" />
        </>
      )}
      {type === 'satellite' && <Trail x={-20} y={4.5} w={30} h={1} top={SATELLITE} />}
    </svg>
  );
}

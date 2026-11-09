'use client';

// dashboard/components/bar-themes/TopbarFx.tsx
// Picks the person's bar theme and renders it. First child of .topbar.

import { DeepField } from './DeepField';
import { GroundDrift } from './GroundDrift';
import { LineClear } from './LineClear';

export type BarTheme = 'deep-field' | 'line-clear' | 'ground-drift';

export const DEFAULT_BAR_THEME: BarTheme = 'deep-field';

/** Order and copy for the settings control. */
export const BAR_THEMES: { id: BarTheme; name: string; description: string }[] = [
  {
    id: 'deep-field',
    name: 'Deep field',
    description: 'Faint stars drift behind the bar. Now and then a shuttle, satellite, rocket or UFO crosses.',
  },
  {
    id: 'line-clear',
    name: 'Line clear',
    description: 'Faint blocks stack across the bar, then break apart and start again.',
  },
  {
    id: 'ground-drift',
    name: 'Ground drift',
    description: 'Two soft pools of light drift slowly across the bar.',
  },
];

export function isBarTheme(value: unknown): value is BarTheme {
  return BAR_THEMES.some((t) => t.id === value);
}

/** Unknown, empty or retired values fall back to the default. */
export function resolveBarTheme(value: unknown): BarTheme {
  return isBarTheme(value) ? value : DEFAULT_BAR_THEME;
}

export function TopbarFx({ theme }: { theme?: string | null }) {
  const t = resolveBarTheme(theme);
  // key: switching themes unmounts the old one, which cancels its animations
  if (t === 'line-clear') return <LineClear key={t} />;
  if (t === 'ground-drift') return <GroundDrift key={t} />;
  return <DeepField key={t} />;
}

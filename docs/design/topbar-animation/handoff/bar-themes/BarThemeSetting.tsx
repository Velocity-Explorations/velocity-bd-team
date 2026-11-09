'use client';

// dashboard/components/bar-themes/BarThemeSetting.tsx
// The personal settings control. If the settings page already has a radio
// group or option card component, use that and keep only the data and copy.

import { useId } from 'react';
import { BAR_THEMES, resolveBarTheme, type BarTheme } from './TopbarFx';
import { useReducedMotion } from './motion';

type Props = {
  /** The saved value from the person's profile. null or unknown means the default. */
  value?: string | null;
  onChange: (theme: BarTheme) => void;
  disabled?: boolean;
};

export function BarThemeSetting({ value, onChange, disabled }: Props) {
  const name = useId();
  const current = resolveBarTheme(value);
  const reduced = useReducedMotion();

  return (
    <fieldset className="bar-theme-setting" disabled={disabled}>
      <legend className="bar-theme-setting-legend">Top bar animation</legend>
      <p className="bar-theme-setting-help">
        {reduced
          ? 'Your system is set to reduce motion, so the bar shows a still frame of the theme you pick.'
          : 'A quiet loop behind the top bar. It pauses when the tab is hidden.'}
      </p>
      <div className="bar-theme-setting-options">
        {BAR_THEMES.map((t) => (
          <label key={t.id} className="bar-theme-setting-option" data-checked={t.id === current || undefined}>
            <input
              type="radio"
              name={name}
              value={t.id}
              checked={t.id === current}
              onChange={() => onChange(t.id)}
            />
            <span className="bar-theme-setting-name">{t.name}</span>
            <span className="bar-theme-setting-desc">{t.description}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

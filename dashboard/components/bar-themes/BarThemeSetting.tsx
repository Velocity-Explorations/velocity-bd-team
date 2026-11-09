"use client";

// Profile settings' top bar animation (Claude Design handoff). The page's own option cards (radio-card), as the handoff
// asks where a settings page has them, with the handoff's copy. Inside the profile form, which saves a choice at once
// (components/AutoSaveForm.tsx); the bar is the preview and switches when the save lands.

import { BAR_THEME_HELP, BAR_THEME_HELP_REDUCED, BAR_THEMES, resolveBarTheme } from "@/lib/barthemes";
import { useReducedMotion } from "./motion";

/** The setting's help, which says so when the system asks for reduced motion. */
export function BarThemeHelp() {
  return <>{useReducedMotion() ? BAR_THEME_HELP_REDUCED : BAR_THEME_HELP}</>;
}

export function BarThemeSetting({ value }: { value?: string | null }) {
  const current = resolveBarTheme(value);
  return (
    <div className="radio-cards radio-cards-three">
      {BAR_THEMES.map((t) => (
        <label key={t.id} className="radio-card">
          <input type="radio" name="bar_theme" value={t.id} defaultChecked={t.id === current} />
          <span>
            <strong>{t.name}</strong>
            <span>{t.description}</span>
          </span>
        </label>
      ))}
    </div>
  );
}

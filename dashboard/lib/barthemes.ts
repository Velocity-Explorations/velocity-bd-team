// The top bar's themes (David, 9 Nov 2026; Claude Design handoff, docs/design/topbar-animation/handoff/bar-themes).
// The ids, the default and the settings copy. No imports, so the server action, the bar and `node --test` share it.

export type BarTheme = "deep-field" | "line-clear" | "ground-drift";

/** Everyone who has not chosen follows this; change it to change the default for them all. */
export const DEFAULT_BAR_THEME: BarTheme = "deep-field";

/** Order and copy for the settings control. */
export const BAR_THEMES: { id: BarTheme; name: string; description: string }[] = [
  {
    id: "deep-field",
    name: "Deep field",
    description:
      "Faint stars and planets drift behind the bar. Now and then a spacecraft, a shooting star, a meteor shower or a comet crosses.",
  },
  {
    id: "line-clear",
    name: "Line clear",
    description: "Faint blocks stack across the bar, then break apart and start again.",
  },
  {
    id: "ground-drift",
    name: "Ground drift",
    description: "Two soft pools of light drift slowly across the bar.",
  },
];

/** The setting's help, and what it says when the system asks for reduced motion. */
export const BAR_THEME_HELP = "A quiet loop behind the top bar. It pauses when the tab is hidden.";
export const BAR_THEME_HELP_REDUCED = "Your system is set to reduce motion, so the bar shows a still frame of the theme you pick.";

export function isBarTheme(value: unknown): value is BarTheme {
  return BAR_THEMES.some((t) => t.id === value);
}

/** Unknown, empty or retired values fall back to the default. */
export function resolveBarTheme(value: unknown): BarTheme {
  return isBarTheme(value) ? value : DEFAULT_BAR_THEME;
}

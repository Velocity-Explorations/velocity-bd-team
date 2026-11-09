// Reference only: where the pieces go. Merge into the real files.

// ---------------------------------------------------------------- Shell.tsx
// <TopbarFx> is the first child of the bar's root element.

import { TopbarFx } from './bar-themes/TopbarFx';

export function ShellBarExample({ barTheme }: { barTheme?: string | null }) {
  return (
    <header className="topbar">
      <TopbarFx theme={barTheme} />
      {/* existing logo, sections, Ask Grok and account markup, unchanged */}
    </header>
  );
}

// ---------------------------------------------------------------- settings page
// Save to the profile, and update the value Shell reads so the bar switches at once.

import { BarThemeSetting } from './bar-themes/BarThemeSetting';
import type { BarTheme } from './bar-themes/TopbarFx';

export function SettingsExample({
  barTheme,
  saveBarTheme,
}: {
  barTheme?: string | null;
  saveBarTheme: (t: BarTheme) => Promise<void>;
}) {
  return <BarThemeSetting value={barTheme} onChange={(t) => void saveBarTheme(t)} />;
}
